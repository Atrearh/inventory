from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks, Body
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..services.computer_service import ComputerService
from ..services.ad_service import ADService
from ..repositories.computer_repository import ComputerRepository
from ..schemas import ScanTask
from .. import models
from uuid import uuid4
import structlog
from ..logging_config import setup_logging
from ..settings import settings
from .auth import get_current_user
import uuid

logger = structlog.get_logger(__name__)
setup_logging(log_level=settings.log_level)

router = APIRouter(tags=["scan"])

def get_computer_service(db: AsyncSession = Depends(get_db)) -> ComputerService:
    return ComputerService(db)

def get_ad_service(db: AsyncSession = Depends(get_db)) -> ADService:
    return ADService(ComputerRepository(db))

@router.post("/scan", response_model=dict, operation_id="start_scan")
async def start_scan(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
    payload: dict = Body(None),
):
    logger_adapter = request.state.logger if request else logger
    task_id = str(uuid.uuid4())
    hostname = payload.get("hostname") if payload else None
    logger_adapter.info(f"Запуск фонового сканування з ID: {task_id}", hostname=hostname or "всі хости")
    try:
        async with db as session:
            computer_service = ComputerService(session)
            task = await computer_service.create_scan_task(task_id)
            if task.status != models.ScanStatus.running:
                logger_adapter.warning(f"Задача {task_id} вже існує і має статус {task.status}")
                raise HTTPException(
                    status_code=409,
                    detail=f"Задача з ID {task_id} вже існує"
                )
            background_tasks.add_task(computer_service.run_scan_task, task_id, logger_adapter, hostname=hostname)
            return {"status": "success", "task_id": task_id}
    except HTTPException:
        raise
    except Exception as e:
        logger_adapter.error(f"Помилка запуску сканування {task_id}: {str(e)}", exc_info=True)
        await session.rollback()
        raise HTTPException(status_code=500, detail="Помилка сервера")

@router.get("/scan/status/{task_id}", response_model=ScanTask)
async def scan_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    logger_adapter = request.state.logger if request else logger
    try:
        async with db as session:
            from sqlalchemy import select
            result = await session.execute(select(models.ScanTask).filter(models.ScanTask.id == task_id))
            db_task = result.scalars().first()
            if not db_task:
                logger_adapter.error(f"Задача {task_id} не знайдена")
                raise HTTPException(status_code=404, detail="Задача не знайдена")
            return db_task
    except Exception as e:
        logger_adapter.error(f"Помилка отримання статусу задачі {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Помилка сервера")

@router.post("/ad/scan")
async def start_ad_scan(
    background_tasks: BackgroundTasks,
    service: ComputerService = Depends(get_computer_service),
    ad_service: ADService = Depends(get_ad_service)
):
    task_id = uuid4()
    try:
        logger.info(f"Запуск задачи сканирования AD с task_id: {task_id}", task_id=str(task_id))
        await service.create_scan_task(str(task_id))
        background_tasks.add_task(run_ad_scan_background, str(task_id), ad_service, service.computer_repo.db)
        return {"task_id": str(task_id), "status": "Scan started"}
    except Exception as e:
        logger.error(f"Ошибка при создании задачи сканирования: {str(e)}", task_id=str(task_id))
        raise HTTPException(status_code=500, detail="Помилка сервера")

async def run_ad_scan_background(task_id: str, ad_service: ADService, db: AsyncSession):
    """Фоновая задача для сканирования AD."""
    logger.info(f"Запуск фонового сканирования AD для task_id: {task_id}", task_id=task_id)
    try:
        await ad_service.scan_and_update_ad(db)
        logger.info(f"Фоновое сканирование AD завершено для task_id: {task_id}", task_id=task_id)
        computer_service = ComputerService(db)
        await computer_service.update_scan_task_status(
            task_id=task_id,
            status="completed",
            scanned_hosts=0,  # Можно обновить после доработки ADService
            successful_hosts=0  # Можно обновить после доработки ADService
        )
    except Exception as e:
        logger.error(f"Ошибка фонового сканирования AD: {str(e)}", task_id=task_id)
        computer_service = ComputerService(db)
        await computer_service.update_scan_task_status(
            task_id=task_id,
            status="failed",
            scanned_hosts=0,
            successful_hosts=0,
            error=str(e)
        )