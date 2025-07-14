from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..services.computer_service import ComputerService
from ..services.ad_service import ADService
from ..repositories.computer_repository import ComputerRepository
from ..schemas import Computer, ComputerCreate, ComputerUpdateCheckStatus, ComponentHistory, ComputersResponse, ComputerList
from .. import models
from typing import List, Optional
import logging
import io
import csv
from ..logging_config import setup_logging
from ..settings import settings
from .auth import get_current_user
import re

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
        
        # Заголовки CSV файла (убираем логические диски)
        header = [
            'IP', 'Назва', 'RAM', 'MAC', 'Материнська плата', 'Имя ОС',
            'Время последней проверки', 'Тип', 'Виртуализация', 'Диск', 'Процессор', 'Видеокарта'
        ]
        writer.writerow(header)
        
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        repo = ComputerRepository(db)
        # Список нежелательных видеокарт с использованием регулярного выражения
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
            check_status=check_status.value if check_status else None,
            sort_by=sort_by,
            sort_order=sort_order,
            server_filter=server_filter
        ):
            try:
                # Объединяем все IP-адреса в строку
                ip_addresses = ', '.join(ip.address for ip in computer.ip_addresses) if computer.ip_addresses else ''
                
                # Объединяем все MAC-адреса в строку
                mac_addresses = ', '.join(mac.address for mac in computer.mac_addresses) if computer.mac_addresses else ''
                
                # Формируем информацию только о физических дисках
                disk_info = [pd.model for pd in computer.physical_disks if pd.model] if computer.physical_disks else []
                disk_info_str = '; '.join(disk_info) if disk_info else ''
                
                # Формируем информацию о процессорах (только модель)
                processor_info = ', '.join(proc.name for proc in computer.processors if proc.name) if computer.processors else ''
                
                # Фильтруем видеокарты с использованием регулярного выражения
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

@router.post("/report", response_model=Computer, operation_id="create_computer_report", dependencies=[Depends(get_current_user)])
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
    os_name: Optional[str] = Query(None),
    check_status: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("hostname", description="Поле для сортировки"),
    sort_order: Optional[str] = Query("asc", description="Порядок сортировки: asc или desc"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    limit: int = Query(1000, ge=1, le=1000, description="Количество записей на странице"),
    server_filter: Optional[str] = Query(None, description="Фильтр для серверных ОС"),
    db: AsyncSession = Depends(get_db),
):
    """Получение списка компьютеров с фильтрацией и пагинацией."""
    logger.info(f"Запрос списка компьютеров с параметрами: os_name={os_name}, check_status={check_status}, sort_by={sort_by}, sort_order={sort_order}, page={page}, limit={limit}, server_filter={server_filter}")
    try:
        repo = ComputerRepository(db)
        computers, total = await repo.get_computers(
            os_name=os_name,
            check_status=check_status,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            limit=limit,
            server_filter=server_filter
        )
        return ComputersResponse(data=computers, total=total)
    except Exception as e:
        logger.error(f"Ошибка получения списка компьютеров: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")

@router.get("/computers/{computer_id}", response_model=Computer, operation_id="get_computer_by_id", dependencies=[Depends(get_current_user)])
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