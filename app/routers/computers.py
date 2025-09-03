from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from ..models import Computer, IPAddress, CheckStatus, MACAddress, PhysicalDisk, Processor, VideoCard, Domain
from ..database import get_db
from ..services.computer_service import ComputerService
from ..repositories.computer_repository import ComputerRepository
from ..schemas import Computer as ComputerSchema, ComputerCreate, ComputerUpdateCheckStatus, ComponentHistory, ComputersResponse, ComputerList
from typing import List, Optional, Dict, Any
import logging
import io
import csv
from ..settings import settings
from .auth import get_current_user
import re
from pydantic import ValidationError

logger = logging.getLogger(__name__)

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
    logger.info("Экспорт компьютеров в CSV", extra={"hostname": hostname, "os_name": os_name, "os_version": os_version, "check_status": check_status, "server_filter": server_filter})
    
    async def generate_csv():
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', lineterminator='\n', quoting=csv.QUOTE_ALL)
        output.write('\ufeff')  # BOM для корректного отображения кириллицы в Excel
        
        header = [ 
            'IP', 'Назва', 'RAM', 'MAC', 'Материнська плата', 'Имя ОС',
            'Время последней проверки', 'Тип', 'Виртуализация', 'Диск', 'Процессор', 'Видеокарта', 'Статус'
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

        # Проверка корректности sort_by
        valid_sort_fields = ["hostname", "os_name", "check_status", "last_updated"]
        sort_by_value = sort_by if sort_by in valid_sort_fields else "hostname"
        sort_order_value = sort_order if sort_order in ["asc", "desc"] else "asc"

        # Запрос без selectinload
        query = select(Computer)
        if hostname:
            query = query.filter(Computer.hostname.ilike(f"%{hostname}%"))
        if os_name:
            query = query.filter(Computer.os_name.ilike(f"%{os_name}%"))
        if check_status:
            try:
                CheckStatus(check_status)
                query = query.filter(Computer.check_status == check_status)
            except ValueError:
                logger.error("Некорректное значение check_status", extra={"check_status": check_status})
                raise HTTPException(status_code=422, detail=f"Некорректное значение check_status: {check_status}")
        if server_filter == "server":
            query = query.filter(Computer.os_name.ilike("%server%"))
        elif server_filter == "client":
            query = query.filter(~Computer.os_name.ilike("%server%"))

        sort_column = getattr(Computer, sort_by_value)
        if sort_order_value == "desc":
            sort_column = sort_column.desc()
        
        query = query.order_by(sort_column)
        
        # Логирование количества записей
        total = await db.scalar(select(func.count()).select_from(query))
        logger.info("Найдено компьютеров для экспорта", extra={"total": total})

        row_count = 0
        async for computer in (await db.stream(query)).scalars():
            try:
                # Ручная загрузка связанных данных
                ip_addresses_query = select(IPAddress).where(IPAddress.computer_id == computer.id, IPAddress.removed_on.is_(None))
                mac_addresses_query = select(MACAddress).where(MACAddress.computer_id == computer.id, MACAddress.removed_on.is_(None))
                physical_disks_query = select(PhysicalDisk).where(PhysicalDisk.computer_id == computer.id)
                processors_query = select(Processor).where(Processor.computer_id == computer.id)
                video_cards_query = select(VideoCard).where(VideoCard.computer_id == computer.id)

                ip_addresses = (await db.execute(ip_addresses_query)).scalars().all()
                mac_addresses = (await db.execute(mac_addresses_query)).scalars().all()
                physical_disks = (await db.execute(physical_disks_query)).scalars().all()
                processors = (await db.execute(processors_query)).scalars().all()
                video_cards = (await db.execute(video_cards_query)).scalars().all()

                ip_addresses_str = ', '.join(ip.address for ip in ip_addresses) if ip_addresses else ''
                mac_addresses_str = ', '.join(mac.address for mac in mac_addresses) if mac_addresses else ''
                disk_info = [pd.model for pd in physical_disks if pd.model] if physical_disks else []
                disk_info_str = '; '.join(disk_info) if disk_info else ''
                processor_info = ', '.join(proc.name for proc in processors if proc.name) if processors else ''
                video_cards_str = ', '.join(vc.name for vc in video_cards if vc.name and not unwanted_video_cards_pattern.search(vc.name.lower())) if video_cards else ''
                
                is_server = 'Сервер' if computer.os_name and 'server' in computer.os_name.lower() else 'Клиент'
                status_str = computer.check_status.value if computer.check_status else 'Неизвестно'

                row_data = [
                    ip_addresses_str,
                    computer.hostname or '',
                    str(computer.ram) if computer.ram is not None else '',
                    mac_addresses_str,
                    computer.motherboard or '',
                    computer.os_name or '',
                    computer.last_updated.strftime('%Y-%m-%d %H:%M:%S') if computer.last_updated else '',
                    is_server,
                    disk_info_str,
                    processor_info,
                    video_cards_str,
                    status_str
                ]
                writer.writerow(row_data)
                row_count += 1
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)

            except Exception as e:
                logger.error("Ошибка при обработке компьютера для CSV", extra={"hostname": computer.hostname, "error": str(e)})
                logger.debug("Данные компьютера", extra={"computer": computer.__dict__})
                continue

        logger.info("Экспорт завершён", extra={"rows_written": row_count})
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
    logger.info("Получен отчет для hostname", extra={"hostname": comp_data.hostname})
    try:
        computer_service = ComputerService(db)
        return await computer_service.upsert_computer_from_schema(comp_data, comp_data.hostname)
    except Exception as e:
        logger.error("Ошибка создания/обновления компьютера", extra={"hostname": comp_data.hostname, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")

@router.post("/update_check_status", operation_id="update_computer_check_status", dependencies=[Depends(get_current_user)])
async def update_check_status(
    data: ComputerUpdateCheckStatus,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    logger.info("Обновление check_status", extra={"hostname": data.hostname})
    try:
        repo = ComputerRepository(db)
        db_computer = await repo.async_update_computer_check_status(data.hostname, data.check_status)
        if not db_computer:
            raise HTTPException(status_code=404, detail="Компьютер не найден")
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Ошибка обновления check_status", extra={"hostname": data.hostname, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")

@router.get("/{computer_id}/history")
async def get_component_history(computer_id: int, db: AsyncSession = Depends(get_db), request: Request = None) -> List[Dict[str, Any]]:
    """Получает историю компонентов для компьютера по ID."""
    logger.info("Запрос истории компонентов", extra={"computer_id": computer_id})
    try:
        service = ComputerService(db)
        history = await service.computer_repo.get_component_history(computer_id)
        if not history:
            logger.warning("История компонентов не найдена", extra={"computer_id": computer_id})
            raise HTTPException(status_code=404, detail="История компонентов не найдена")
        logger.info(f"Получено {len(history)} записей истории компонентов", extra={"computer_id": computer_id})
        return history
    except Exception as e:
        logger.error("Ошибка получения истории компонентов", extra={"computer_id": computer_id, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")

@router.get("/computers", response_model=ComputersResponse, dependencies=[Depends(get_current_user)])
async def get_computers(
    hostname: Optional[str] = Query(None, description="Фільтр по hostname"),
    ip_range: Optional[str] = Query(None, description="Фільтр по діапазону IP-адрес"),
    os_name: Optional[str] = Query(None, description="Фільтр по імені ОС"),
    check_status: Optional[str] = Query(None, description="Фільтр по check_status"),
    domain: Optional[str] = Query(None, description="Фільтр по імені домену"),
    sort_by: str = Query("hostname", description="Поле для сортування"),
    sort_order: str = Query("asc", description="Порядок: asc або desc"),
    page: int = Query(1, ge=1, description="Номер сторінки"),
    limit: int = Query(100, ge=1, le=1000, description="Кількість записів на сторінку"),
    server_filter: Optional[str] = Query(None, description="Фільтр для серверних ОС"),
    db: AsyncSession = Depends(get_db),
):
    logger.info("Запит списку комп’ютерів", extra={
        "hostname": hostname, 
        "ip_range": ip_range, 
        "os_name": os_name, 
        "check_status": check_status, 
        "domain": domain,
        "sort_by": sort_by, 
        "sort_order": sort_order, 
        "page": page, 
        "limit": limit, 
        "server_filter": server_filter
    })
    try:
        query = select(Computer).options(
            selectinload(Computer.ip_addresses),
            selectinload(Computer.physical_disks),
            selectinload(Computer.logical_disks),
            selectinload(Computer.processors),
            selectinload(Computer.mac_addresses),
            selectinload(Computer.roles),
            selectinload(Computer.software),
            selectinload(Computer.video_cards),
            selectinload(Computer.domain)
        ).outerjoin(Domain, Computer.domain_id == Domain.id)

        if hostname:
            query = query.filter(Computer.hostname.ilike(f"%{hostname}%"))
        if ip_range:
            logger.debug("Обробка фільтру ip_range", extra={"ip_range": ip_range})
            if ip_range == 'none':
                logger.debug("Фільтр для комп’ютерів без IP-адрес")
                query = query.filter(IPAddress.address.is_(None))
            else:
                try:
                    logger.debug("Парсинг ip_range", extra={"ip_range": ip_range})
                    base_ip, octet_range = ip_range.split('.[')
                    start_octet, end_octet = map(int, octet_range.replace(']', '').split('-'))
                    logger.debug("Застосування IP-фільтру", extra={"base_ip": base_ip, "start_octet": start_octet, "end_octet": end_octet})
                    query = query.filter(
                        IPAddress.address.startswith(base_ip),
                        IPAddress.address.between(f"{base_ip}.{start_octet}.0", f"{base_ip}.{end_octet}.255")
                    )
                except ValueError as e:
                    logger.error("Некоректний формат ip_range", extra={"ip_range": ip_range, "error": str(e)})
                    raise HTTPException(status_code=400, detail=f"Некоректний формат ip_range: {ip_range}")
        if os_name:
            query = query.filter(Computer.os_name.ilike(f"%{os_name}%"))
        if check_status:
            try:
                logger.debug("Валідація check_status", extra={"check_status": check_status})
                CheckStatus(check_status)
                query = query.filter(Computer.check_status == check_status)
            except ValueError:
                logger.error("Некоректне значення check_status", extra={"check_status": check_status})
                raise HTTPException(status_code=422, detail=f"Некоректне значення check_status: {check_status}")
        if domain:
            query = query.filter(Domain.name.ilike(f"%{domain}%"))
        if server_filter:
            if server_filter == "server":
                query = query.filter(Computer.os_name.ilike("%server%"))
            elif server_filter == "client":
                query = query.filter(~Computer.os_name.ilike("%server%"))

        sort_column = getattr(Computer, sort_by if sort_by in ["hostname", "os_name", "check_status", "last_updated", "last_full_scan", "domain_id"] else "hostname")
        if sort_by == "domain_id":
            sort_column = Domain.name  # Сортування за ім’ям домену
        if sort_order.lower() == "desc":
            sort_column = sort_column.desc()
        query = query.order_by(sort_column)

        total = await db.scalar(select(func.count()).select_from(query))
        query = query.offset((page - 1) * limit).limit(limit)
        result = await db.execute(query)
        computers = result.scalars().all()
        pydantic_computers = [ComputerList.model_validate(comp, from_attributes=True) for comp in computers]
        logger.info(f"Отримано {len(pydantic_computers)} комп’ютерів, усього: {total}")
        return ComputersResponse(data=pydantic_computers, total=total)
    except Exception as e:
        logger.error("Помилка отримання списку комп’ютерів", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Помилка сервера: {str(e)}")

@router.get("/computers/{computer_id}", response_model=ComputerSchema, operation_id="get_computer_by_id", dependencies=[Depends(get_current_user)])
async def get_computer_by_id(
    computer_id: int,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    logger.info("Запрос компьютера по ID", extra={"computer_id": computer_id})
    try:
        repo = ComputerRepository(db)
        computer = await repo.get_computer_details_by_id(computer_id)  # Змінено на правильний метод
        if not computer:
            logger.warning("Компьютер не найден", extra={"computer_id": computer_id})
            raise HTTPException(status_code=404, detail="Компьютер не найден")
        logger.info("Компьютер успешно получен", extra={"computer_id": computer_id})
        return computer
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Ошибка получения компьютера", extra={"computer_id": computer_id, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")