import csv
import io
import logging
import re
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from ..schemas import (
    ComputerCreate,
    ComputerDetail,
    ComputersResponse,
    ComputerUpdateCheckStatus,
    InstalledSoftwareRead,
)
from ..repositories.component_repository import ComponentRepository
from ..database import get_db
from ..models import Computer, OperatingSystem
from ..repositories.computer_repository import ComputerRepository
from ..services.computer_service import ComputerService
from .auth import get_current_user


logger = logging.getLogger(__name__)

router = APIRouter(tags=["computers"])


@router.get(
    "/computers/export/csv",
    response_model=None,
    dependencies=[Depends(get_current_user)],
)
async def export_computers_to_csv(
    db: AsyncSession = Depends(get_db),
    hostname: Optional[str] = Query(None, description="Фільтр по hostname"),
    os_name: Optional[str] = Query(None, description="Фільтр по імені ОС"),
    check_status: Optional[str] = Query(None, description="Фільтр по check_status"),
    sort_by: str = Query("hostname", description="Поле для сортування"),
    sort_order: str = Query("asc", description="Порядок: asc або desc"),
    server_filter: Optional[str] = Query(None, description="Фільтр для серверних ОС"),
):
    """Експорт комп'ютерів у CSV з потоковою передачею даних."""
    logger.info("Експорт комп'ютерів у CSV", extra=locals())

    async def generate_csv():
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";", lineterminator="\n", quoting=csv.QUOTE_ALL)
        output.write("\ufeff")  # BOM for Excel

        header = [
            "IP",
            "Назва",
            "RAM",
            "MAC",
            "Материнська плата",
            "Ім'я ОС",
            "Час останньої перевірки",
            "Тип",
            "Диск",
            "Процесор",
            "Відеокарта",
            "Статус",
        ]
        writer.writerow(header)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        unwanted_video_cards_pattern = re.compile(r"(?i)microsoft basic display adapter|базовий відеоадаптер \(майкрософт\)|dameware|hyper-v video")

        # --- Оптимізований запит з JOIN та selectinload для уникнення N+1 проблеми ---
        query = (
            select(Computer)
            .options(
                selectinload(Computer.ip_addresses),
                selectinload(Computer.mac_addresses),
                selectinload(Computer.physical_disks),
                selectinload(Computer.processors),
                selectinload(Computer.video_cards),
                selectinload(Computer.os),
            )
            .outerjoin(OperatingSystem, Computer.os_id == OperatingSystem.id)
        )

        # Застосування фільтрів
        if hostname:
            query = query.filter(Computer.hostname.ilike(f"%{hostname}%"))
        if os_name:
            query = query.filter(OperatingSystem.name.ilike(f"%{os_name}%"))
        if check_status:
            query = query.filter(Computer.check_status == check_status)
        if server_filter == "server":
            query = query.filter(OperatingSystem.name.ilike("%server%"))
        elif server_filter == "client":
            query = query.filter(~OperatingSystem.name.ilike("%server%"))

        # Застосування сортування
        sort_column = getattr(Computer, sort_by, Computer.hostname)
        if sort_order.lower() == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        stream_result = await db.stream(query)
        async for computer in stream_result.scalars():
            try:
                os_name_str = computer.os.name if computer.os else "N/A"
                is_server = "Сервер" if "server" in os_name_str.lower() else "Клієнт"

                row_data = [
                    ", ".join([ip.address for ip in computer.ip_addresses if ip.address]),
                    computer.hostname,
                    computer.ram,
                    ", ".join([mac.address for mac in computer.mac_addresses if mac.address]),
                    computer.motherboard,
                    os_name_str,
                    (computer.last_updated.strftime("%Y-%m-%d %H:%M:%S") if computer.last_updated else ""),
                    is_server,
                    "; ".join([disk.model for disk in computer.physical_disks if disk.model]),
                    ", ".join([proc.name for proc in computer.processors if proc.name]),
                    ", ".join([vc.name for vc in computer.video_cards if vc.name and not unwanted_video_cards_pattern.search(vc.name)]),
                    (computer.check_status.value if computer.check_status else "Невідомо"),
                ]
                writer.writerow(row_data)
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)
            except Exception as e:
                logger.error(f"Помилка при обробці комп'ютера {computer.hostname} для CSV: {e}")
                continue
        output.close()

    headers = {
        "Content-Disposition": 'attachment; filename="computers.csv"',
        "Content-Type": "text/csv; charset=utf-8-sig",
    }
    return StreamingResponse(generate_csv(), headers=headers)


@router.post(
    "/report",
    response_model=ComputerDetail,
    operation_id="create_computer_report",
    dependencies=[Depends(get_current_user)],
)
async def create_computer(
    comp_data: ComputerCreate,
    db: AsyncSession = Depends(get_db),
):
    logger.info("Отримано звіт для hostname", extra={"hostname": comp_data.hostname})
    try:
        computer_service = ComputerService(db)

        return await computer_service.upsert_computer_from_schema(comp_data, comp_data.hostname)
    except Exception as e:
        logger.error(
            f"Помилка створення/оновлення комп'ютера: {e}",
            extra={"hostname": comp_data.hostname},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Помилка сервера: {e}")


@router.post(
    "/update_check_status",
    operation_id="update_computer_check_status",
    dependencies=[Depends(get_current_user)],
)
async def update_check_status(
    data: ComputerUpdateCheckStatus,
    db: AsyncSession = Depends(get_db),
):
    logger.info("Оновлення check_status", extra={"hostname": data.hostname})
    repo = ComputerRepository(db)
    db_computer = await repo.async_update_computer_check_status(data.hostname, data.check_status.value)
    if not db_computer:
        raise HTTPException(status_code=404, detail="Комп'ютер не знайдений")
    return {"status": "success"}


@router.get("/{computer_id}/history", response_model=List[Dict[str, Any]])
async def get_component_history(computer_id: int, db: AsyncSession = Depends(get_db)):
    """Отримує історію компонентів для комп'ютера по ID."""
    logger.info("Запит історії компонентів", extra={"computer_id": computer_id})
    repo = ComponentRepository(db)  # Використовуємо ComponentRepository
    history = await repo.get_component_history(computer_id)
    if not history:
        raise HTTPException(status_code=404, detail="Історія компонентів не знайдена")
    return history


@router.get(
    "/computers",
    response_model=ComputersResponse,
    dependencies=[Depends(get_current_user)],
)
async def get_computers(
    hostname: Optional[str] = Query(None, description="Фільтр по hostname"),
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
    repo = ComputerRepository(db)
    computers, total = await repo.get_computers_list(
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        hostname=hostname,
        os_name=os_name,
        check_status=check_status,
        server_filter=server_filter,
    )
    return ComputersResponse(data=computers, total=total)


@router.get(
    "/computers/{computer_id}",
    response_model=ComputerDetail,
    operation_id="get_computer_by_id",
    dependencies=[Depends(get_current_user)],
)
async def get_computer_by_id(
    computer_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Отримує детальну інформацію про комп'ютер за його ID."""
    logger.info("Запит комп'ютера по ID", extra={"computer_id": computer_id})
    try:
        repo = ComputerRepository(db)
        computer = await repo.get_computer_details_by_id(computer_id)
        if not computer:
            logger.warning("Комп'ютер не знайдено", extra={"computer_id": computer_id})
            raise HTTPException(status_code=404, detail="Комп'ютер не знайдено")

        # Формування списку ПЗ для відповіді
        software_list = [
            InstalledSoftwareRead(
                name=installation.software_details.name,
                version=installation.software_details.version,
                publisher=installation.software_details.publisher,
                install_date=installation.install_date,
            )
            for installation in computer.installed_software
            if installation.software_details and not installation.removed_on
        ]

        # Створення Pydantic-схеми з базових даних комп'ютера
        response_data = ComputerDetail.model_validate(computer, from_attributes=True)
        response_data.software = software_list
        response_data.domain_name = computer.domain.name if computer.domain else None

        logger.info("Комп'ютер успішно отримано", extra={"computer_id": computer_id})
        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Помилка отримання комп'ютера {computer_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Помилка сервера: {e}")
