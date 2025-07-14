from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks, Body
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..services.computer_service import ComputerService
from ..services.ad_service import ADService
from ..repositories.computer_repository import ComputerRepository
from ..schemas import ScanTask
from .. import models
from typing import Optional
import logging
import uuid
from ..logging_config import setup_logging
from ..settings import settings
from .auth import get_current_user

logger = logging.getLogger(__name__)
setup_logging(log_level=settings.log_level)

router = APIRouter(tags=["scan"])

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
    logger_adapter.info(f"Запуск фонового сканирования с ID: {task_id}, hostname: {hostname or 'все хосты'}")
    try:
        async with db as session:
            computer_service = ComputerService(session)
            task = await computer_service.create_scan_task(task_id)
            if task.status != models.ScanStatus.running:
                logger_adapter.warning(f"Задача {task_id} уже существует и имеет статус {task.status}")
                raise HTTPException(
                    status_code=409,
                    detail=f"Задача с ID {task_id} уже существует"
                )
            background_tasks.add_task(computer_service.run_scan_task, task_id, logger_adapter, hostname=hostname)
            return {"status": "success", "task_id": task_id}
    except HTTPException:
        raise
    except Exception as e:
        logger_adapter.error(f"Ошибка запуска сканирования {task_id}: {str(e)}", exc_info=True)
        await session.rollback()
        raise HTTPException(status_code=500, detail="Ошибка сервера")

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
                logger_adapter.error(f"Задача {task_id} не найдена")
                raise HTTPException(status_code=404, detail="Задача не найдена")
            return db_task
    except Exception as e:
        logger_adapter.error(f"Ошибка получения статуса задачи {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@router.post("/ad/scan", response_model=dict, operation_id="start_ad_scan", dependencies=[Depends(get_current_user)])
async def start_ad_scan(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    logger_adapter = request.state.logger if request else logger
    task_id = str(uuid.uuid4())
    logger_adapter.info(f"Запуск фонового сканирования AD с task_id: {task_id}")
    try:
        async with db as session:
            repo = ComputerRepository(session)
            ad_service = ADService(repo)
            await repo.create_scan_task(task_id)
            background_tasks.add_task(ad_service.scan_and_update_ad, task_id, logger_adapter)
            return {"status": "success", "task_id": task_id}
    except Exception as e:
        logger_adapter.error(f"Ошибка запуска AD сканирования: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")