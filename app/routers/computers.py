# app/routers/computers.py
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from ..models import Computer, IPAddress, CheckStatus
from ..database import get_db
from ..services.computer_service import ComputerService
from ..repositories.computer_repository import ComputerRepository
from ..schemas import Computer as ComputerSchema, ComputerCreate, ComputerUpdateCheckStatus, ComponentHistory, ComputersResponse, ComputerList
from typing import List, Optional
import logging
import io
import csv
from ..logging_config import setup_logging
from ..settings import settings
from .auth import get_current_user
import re
from pydantic import ValidationError

logger = logging.getLogger(__name__)
setup_logging(log_level=settings.log_level)

router = APIRouter(tags=["computers"])

@router.get("/computers/export/csv", response_model=None, dependencies=[Depends(get_current_user)])
async def export_computers_to_csv(
    db: AsyncSession = Depends(get_db),
    hostname: Optional[str] = Query(None, description="Фильтр по hostname"),
    os_version: Optional[str] = Query(None, description="Фильтр по версии ОС"),
    os_name: Optional[str] = Query(None, description="Фильтр по имени ОС"),
    check_status: Optional[str] = Query(None, description="Фильтр по check_status"),
    sort_by: str = Query("hostname", description="Поле для сортировки"),
    sort_order: str = Query("asc", description="Порядок: asc или desc"),
    server_filter: Optional[str] = Query(None, description="Фильтр для серверных ОС"),
):
    """Экспорт компьютеров в CSV с потоковой передачей данных."""
    logger.info(f"Экспорт компьютеров в CSV с параметрами: hostname={hostname}, os_name={os_name}, os_version={os_version}, check_status={check_status}, server_filter={server_filter}")
    
    async def generate_csv():
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', lineterminator='\n', quoting=csv.QUOTE_ALL)
        output.write('\ufeff')  # BOM для корректного отображения кириллицы в Excel
        
        header = [ 
            'IP', 'Назва', 'RAM', 'MAC', 'Материнська плата', 'Имя ОС',
            'Время последней проверки', 'Тип', 'Виртуализация', 'Диск', 'Процессор', 'Видеокарта'
        ]
        writer.writerow(header)
        
        yield output.getvalue() 
        output.seek(0)
        output.truncate(0)

        repo = ComputerRepository(db)
        unwanted_video_cards_pattern = re.compile(
            r'(?i)microsoft basic display adapter|'
            r'базовый видеоадаптер \(майкрософт\)|'
            r'dameware development mirror driver 64-bit|'
            r'microsoft hyper-v video|'
            r'видеоустройство microsoft hyper-v|'
            r'@oem\d+\.inf,%dwmirrordrv% 64-bit'
        )

        async for computer in repo.stream_computers(
            hostname=hostname,
            os_name=os_name,
            check_status=check_status,
            sort_by=sort_by,
            sort_order=sort_order,
            server_filter=server_filter
        ):
            try:
                ip_addresses = ', '.join(ip.address for ip in computer.ip_addresses) if computer.ip_addresses else ''
                mac_addresses = ', '.join(mac.address for mac in computer.mac_addresses) if computer.mac_addresses else ''
                disk_info = [pd.model for pd in computer.physical_disks if pd.model] if computer.physical_disks else []
                disk_info_str = '; '.join(disk_info) if disk_info else ''
                processor_info = ', '.join(proc.name for proc in computer.processors if proc.name) if computer.processors else ''
                video_cards = ', '.join(vc.name for vc in computer.video_cards if vc.name and not unwanted_video_cards_pattern.search(vc.name.lower())) if computer.video_cards else ''
                
                is_server = 'Сервер' if computer.os_name and 'server' in computer.os_name.lower() else 'Клиент'
                virtualization = 'Виртуальный' if computer.is_virtual else 'Физический'

                row_data = [
                    ip_addresses,
                    computer.hostname or '',
                    str(computer.ram) if computer.ram is not None else '',
                    mac_addresses,
                    computer.motherboard or '',
                    computer.os_name or '',
                    computer.last_updated.strftime('%Y-%m-%d %H:%M:%S') if computer.last_updated else '',
                    is_server,
                    virtualization,
                    disk_info_str,
                    processor_info,
                    video_cards
                ]
                writer.writerow(row_data)

                yield output.getvalue()
                output.seek(0)
                output.truncate(0)

            except Exception as e:
                logger.error(f"Ошибка при обработке компьютера {computer.hostname} для CSV: {e}", exc_info=True)
                logger.debug(f"Данные компьютера: {computer.model_dump()}")
                continue

        output.close()

    headers = {
        'Content-Disposition': 'attachment; filename="computers.csv"',
        'Content-Type': 'text/csv; charset=utf-8-sig'
    }
    return StreamingResponse(generate_csv(), headers=headers)

@router.post("/report", response_model=ComputerSchema, operation_id="create_computer_report", dependencies=[Depends(get_current_user)])
async def create_computer(
    comp_data: ComputerCreate,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    logger_adapter = request.state.logger if request else logger
    logger_adapter.info(f"Получен отчет для hostname: {comp_data.hostname}")
    try:
        computer_service = ComputerService(db)
        return await computer_service.upsert_computer_from_schema(comp_data, comp_data.hostname)
    except Exception as e:
        logger_adapter.error(f"Ошибка создания/обновления компьютера {comp_data.hostname}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")

@router.post("/update_check_status", operation_id="update_computer_check_status", dependencies=[Depends(get_current_user)])
async def update_check_status(
    data: ComputerUpdateCheckStatus,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    logger_adapter = request.state.logger if request else logger
    logger_adapter.info(f"Обновление check_status для {data.hostname}")
    try:
        repo = ComputerRepository(db)
        db_computer = await repo.async_update_computer_check_status(data.hostname, data.check_status)
        if not db_computer:
            raise HTTPException(status_code=404, detail="Компьютер не найден")
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger_adapter.error(f"Ошибка обновления check_status для {data.hostname}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")

@router.get("/computers/{computer_id}/history", response_model=List[ComponentHistory], dependencies=[Depends(get_current_user)])
async def get_component_history(
    computer_id: int,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    logger_adapter = request.state.logger if request else logger
    logger_adapter.info(f"Отримання історії компонентів для комп’ютера з ID: {computer_id}")
    try:
        repo = ComputerRepository(db)
        history = await repo.get_component_history(computer_id)
        return history
    except Exception as e:
        logger_adapter.error(f"Помилка отримання історії компонентів для ID {computer_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")

@router.get("/computers", response_model=ComputersResponse, operation_id="get_computers", dependencies=[Depends(get_current_user)])
async def get_computers(
    hostname: Optional[str] = Query(None, description="Фильтр по hostname"),
    ip_range: Optional[str] = Query(None, description="Фильтр по диапазону IP-адресов (например, '192.168.0.[0-1]' или 'none')"),
    os_name: Optional[str] = Query(None, description="Фильтр по имени ОС"),
    check_status: Optional[str] = Query(None, description="Фильтр по check_status"),
    sort_by: Optional[str] = Query("hostname", description="Поле для сортировки"),
    sort_order: Optional[str] = Query("asc", description="Порядок сортировки: asc или desc"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    limit: int = Query(1000, ge=1, le=1000, description="Количество записей на странице"),
    server_filter: Optional[str] = Query(None, description="Фильтр для серверных ОС"),
    db: AsyncSession = Depends(get_db),
):
    logger.info(f"Запрос списка компьютеров с параметрами: hostname={hostname}, ip_range={ip_range}, os_name={os_name}, check_status={check_status}, sort_by={sort_by}, sort_order={sort_order}, page={page}, limit={limit}, server_filter={server_filter}")
    try:
        logger.debug(f"Using Computer class: {Computer}")
        # Используем модель Computer из app.models
        query = select(Computer).options(
            selectinload(Computer.ip_addresses)
        )

        # Присоединяем таблицу ip_addresses с LEFT JOIN для включения компьютеров без IP
        query = query.outerjoin(IPAddress, Computer.id == IPAddress.computer_id)

        if hostname:
            query = query.filter(Computer.hostname.ilike(f"%{hostname}%"))
        if ip_range:
            logger.debug(f"Processing ip_range filter: {ip_range}")
            if ip_range == 'none':
                logger.debug("Applying filter for computers without IP addresses")
                query = query.filter(IPAddress.address.is_(None))
            else:
                try:
                    logger.debug(f"Parsing ip_range: {ip_range}")
                    base_ip, octet_range = ip_range.split('.[')
                    start_octet, end_octet = map(int, octet_range.replace(']', '').split('-'))
                    logger.debug(f"Applying IP filter: base_ip={base_ip}, start_octet={start_octet}, end_octet={end_octet}")
                    query = query.filter(
                        IPAddress.address.startswith(base_ip),
                        IPAddress.address.between(f"{base_ip}.{start_octet}.0", f"{base_ip}.{end_octet}.255")
                    )
                except ValueError as e:
                    logger.error(f"Некорректный формат ip_range: {ip_range}, ошибка: {str(e)}")
                    raise HTTPException(status_code=400, detail=f"Некорректный формат ip_range: {ip_range}")
        if os_name:
            query = query.filter(Computer.os_name.ilike(f"%{os_name}%"))
        if check_status:
            try:
                logger.debug(f"Validating check_status: {check_status}")
                CheckStatus(check_status)
            except ValueError:
                logger.error(f"Некорректное значение check_status: {check_status}")
                raise HTTPException(status_code=422, detail=f"Некорректное значение check_status: {check_status}")
        if server_filter == "server":
            query = query.filter(Computer.os_name.ilike("%server%"))
        elif server_filter == "client":
            query = query.filter(~Computer.os_name.ilike("%server%"))

        if sort_by not in ["hostname", "os_name", "check_status", "last_updated"]:
            sort_by = "hostname"
        if sort_order not in ["asc", "desc"]:
            sort_order = "asc"
        
        sort_column = getattr(Computer, sort_by)
        if sort_order == "desc":
            sort_column = sort_column.desc()
        
        # Логируем SQL-запрос для отладки
        logger.debug(f"SQL Query: {str(query)}")
        
        total = await db.scalar(select(func.count()).select_from(query))
        query = query.offset((page - 1) * limit).limit(limit).order_by(sort_column)
        
        computers = (await db.execute(query)).scalars().unique().all()
        try:
            computer_list = [
                ComputerList(
                    id=c.id,
                    hostname=c.hostname,
                    ip_addresses=[{"address": ip.address, "detected_on": ip.detected_on, "removed_on": ip.removed_on} for ip in c.ip_addresses if ip.removed_on is None] if c.ip_addresses else [],
                    os_version=c.os_version,
                    os_name=c.os_name,
                    check_status=c.check_status.value,
                    last_updated=c.last_updated,
                    physical_disks=[],
                    logical_disks=[],
                    processors=[],
                    mac_addresses=[],
                    motherboard=c.motherboard,
                    last_boot=c.last_boot,
                    is_virtual=c.is_virtual,
                    roles=[],
                    software=[],
                    video_cards=[],
                ) for c in computers
            ]
        except ValidationError as ve:
            logger.error(f"Ошибка валидации данных для ComputersResponse: {ve.errors()}", exc_info=True)
            raise HTTPException(status_code=422, detail=f"Ошибка валидации данных: {ve.errors()}")
        
        logger.debug(f"Возвращено {len(computer_list)} компьютеров, всего: {total}")
        return ComputersResponse(data=computer_list, total=total)
    except HTTPException as e:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения списка компьютеров: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}") 
      
@router.get("/computers/{computer_id}", response_model=ComputerSchema, operation_id="get_computer_by_id", dependencies=[Depends(get_current_user)])
async def get_computer_by_id(
    computer_id: int,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    logger_adapter = request.state.logger if request else logger
    logger_adapter.info(f"Получение данных компьютера с ID: {computer_id}")
    try:
        repo = ComputerRepository(db)
        computer = await repo.async_get_computer_by_id(computer_id)
        if not computer:
            logger_adapter.warning(f"Компьютер с ID {computer_id} не найден")
            raise HTTPException(status_code=404, detail="Компьютер не найден")
        return computer
    except HTTPException:
        raise
    except Exception as e:
        logger_adapter.error(f"Ошибка получения компьютера с ID {computer_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")