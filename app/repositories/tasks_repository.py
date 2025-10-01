import logging
import asyncio
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession
from time import perf_counter
from aiocache import Cache, cached
from .. import models

logger = logging.getLogger(__name__)

def validate_task_id(task_id: str) -> bool:
    try:
        UUID(task_id)
        return True
    except ValueError:
        logger.error(f"Невалідний task_id: {task_id}")
        raise ValueError(f"Невалідний task_id: {task_id}")

def validate_hosts_count(scanned_hosts: int, successful_hosts: int) -> bool:
    if scanned_hosts < 0 or successful_hosts < 0:
        logger.error(f"Кількість хостів не може бути від’ємною: scanned_hosts={scanned_hosts}, successful_hosts={successful_hosts}")
        raise ValueError("Кількість хостів не може бути від’ємною")
    if successful_hosts > scanned_hosts:
        logger.error(f"Кількість успішних хостів ({successful_hosts}) не може перевищувати відскановані ({scanned_hosts})")
        raise ValueError("Кількість успішних хостів не може перевищувати відскановані")
    return True

class TasksRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_scan_task(self, task_id: str) -> models.ScanTask:
        start_time = perf_counter()
        validate_task_id(task_id)
        try:
            existing_task = await self.db.get(models.ScanTask, task_id)
            if existing_task:
                logger.warning("Задача сканування вже існує", extra={"task_id": task_id})
                return existing_task

            new_task = models.ScanTask(
                id=task_id,
                status=models.ScanStatus.running,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                scanned_hosts=0,
                successful_hosts=0,
                error=None,
            )
            self.db.add(new_task)
            await self.db.commit()
            logger.debug(f"Нова задача сканування створена за {perf_counter() - start_time:.4f}с", extra={"task_id": task_id})
            return new_task
        except SQLAlchemyError as e:
            logger.error(f"Помилка створення задачі сканування: {str(e)}", extra={"task_id": task_id})
            await self.db.rollback()
            raise

    async def update_scan_task_status(
        self,
        task_id: str,
        status: models.ScanStatus,
        scanned_hosts: int,
        successful_hosts: int,
        error: Optional[str] = None,
    ) -> Optional[models.ScanTask]:
        start_time = perf_counter()
        validate_task_id(task_id)
        validate_hosts_count(scanned_hosts, successful_hosts)
        try:
            scan_task = await self.db.get(models.ScanTask, task_id)
            if not scan_task:
                logger.warning("Задача сканування не знайдена", extra={"task_id": task_id})
                return None
            scan_task.status = status
            scan_task.scanned_hosts = scanned_hosts
            scan_task.successful_hosts = successful_hosts
            scan_task.error = error
            scan_task.updated_at = datetime.utcnow()
            await self.db.commit()
            logger.debug(f"Статус задачі оновлено: {status} за {perf_counter() - start_time:.4f}с", extra={"task_id": task_id})
            return scan_task
        except SQLAlchemyError as e:
            logger.error(f"Помилка оновлення задачі: {str(e)}", extra={"task_id": task_id})
            await self.db.rollback()
            raise

    @cached(ttl=300, cache=Cache.MEMORY)
    async def get_scan_tasks(self, limit: int = 100, offset: int = 0) -> Tuple[List[models.ScanTask], int]:
        start_time = perf_counter()
        if limit < 0 or offset < 0:
            logger.error(f"Невалідні параметри пагінації: limit={limit}, offset={offset}")
            raise ValueError("Параметри limit і offset не можуть бути від’ємними")
        try:
            query = select(models.ScanTask).order_by(models.ScanTask.created_at.desc()).offset(offset).limit(limit)
            count_query = select(func.count()).select_from(models.ScanTask)
            result, count_result = await asyncio.gather(
                self.db.execute(query),
                self.db.execute(count_query)
            )
            tasks = result.scalars().all()
            total = count_result.scalar() or 0
            logger.debug(
                f"Отримано {len(tasks)} задач сканування за {perf_counter() - start_time:.4f}с",
                extra={"limit": limit, "offset": offset},
            )
            return tasks, total
        except SQLAlchemyError as e:
            logger.error(f"Помилка отримання задач сканування: {str(e)}")
            raise

    async def delete_scan_task(self, task_id: str) -> bool:
        start_time = perf_counter()
        validate_task_id(task_id)
        try:
            scan_task = await self.db.get(models.ScanTask, task_id)
            if not scan_task:
                logger.warning("Задача сканування не знайдена", extra={"task_id": task_id})
                return False
            await self.db.delete(scan_task)
            await self.db.commit()
            logger.debug(f"Задача сканування видалена за {perf_counter() - start_time:.4f}с", extra={"task_id": task_id})
            return True
        except SQLAlchemyError as e:
            logger.error(f"Помилка видалення задачі сканування: {str(e)}", extra={"task_id": task_id})
            await self.db.rollback()
            raise

    async def update_scan_task_state(self, task_id: str, state: models.ScanStatus) -> Optional[models.ScanTask]:
        start_time = perf_counter()
        validate_task_id(task_id)
        try:
            scan_task = await self.db.get(models.ScanTask, task_id)
            if not scan_task:
                logger.warning("Задача сканування не знайдена", extra={"task_id": task_id})
                return None
            if state not in models.ScanStatus:
                logger.error(f"Недопустимий стан: {state}", extra={"task_id": task_id})
                raise ValueError(f"Недопустимий стан: {state}")
            scan_task.status = state
            scan_task.updated_at = datetime.utcnow()
            await self.db.commit()
            logger.debug(f"Статус задачі оновлено до {state} за {perf_counter() - start_time:.4f}с", extra={"task_id": task_id})
            return scan_task
        except SQLAlchemyError as e:
            logger.error(f"Помилка оновлення стану задачі: {str(e)}", extra={"task_id": task_id})
            await self.db.rollback()
            raise