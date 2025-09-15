import logging
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from .. import models

logger = logging.getLogger(__name__)


class TasksRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_scan_task(self, task_id: str) -> models.ScanTask:
        try:
            existing_task = await self.db.get(models.ScanTask, task_id)
            if existing_task:
                logger.warning(
                    "Задача сканування вже існує", extra={"task_id": task_id}
                )
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
            await self.db.refresh(new_task)
            logger.debug("Нова задача сканування створена", extra={"task_id": task_id})
            return new_task
        except SQLAlchemyError as e:
            logger.error(
                f"Помилка створення задачі сканування: {str(e)}",
                extra={"task_id": task_id},
            )
            await self.db.rollback()
            raise

    async def update_scan_task_status(
        self,
        task_id: str,
        status: str,
        scanned_hosts: int,
        successful_hosts: int,
        error: Optional[str] = None,
    ):
        try:
            scan_task = await self.db.get(models.ScanTask, task_id)
            if scan_task:
                scan_task.status = status
                scan_task.scanned_hosts = scanned_hosts
                scan_task.successful_hosts = successful_hosts
                scan_task.error = error
                scan_task.updated_at = datetime.utcnow()
                await self.db.commit()
                await self.db.refresh(scan_task)
                logger.debug(
                    f"Статус задачі оновлено: {status}", extra={"task_id": task_id}
                )
            else:
                logger.warning(
                    "Задача сканування не знайдена", extra={"task_id": task_id}
                )
        except SQLAlchemyError as e:
            logger.error(
                f"Помилка оновлення статусу задачі: {str(e)}",
                extra={"task_id": task_id},
            )
            await self.db.rollback()
            raise

    async def get_scan_tasks(
        self, limit: int = 100, offset: int = 0
    ) -> Tuple[List[models.ScanTask], int]:
        try:
            query = (
                select(models.ScanTask)
                .order_by(models.ScanTask.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            count_query = select(func.count()).select_from(models.ScanTask)
            result = await self.db.execute(query)
            count_result = await self.db.execute(count_query)
            tasks = result.scalars().all()
            total = count_result.scalar() or 0
            logger.debug(
                f"Отримано {len(tasks)} задач сканування",
                extra={"limit": limit, "offset": offset},
            )
            return tasks, total
        except SQLAlchemyError as e:
            logger.error(f"Помилка отримання задач сканування: {str(e)}")
            raise

    async def delete_scan_task(self, task_id: str) -> bool:
        try:
            scan_task = await self.db.get(models.ScanTask, task_id)
            if not scan_task:
                logger.warning(
                    "Задача сканування не знайдена", extra={"task_id": task_id}
                )
                return False
            await self.db.delete(scan_task)
            await self.db.commit()
            logger.debug("Задача сканування видалена", extra={"task_id": task_id})
            return True
        except SQLAlchemyError as e:
            logger.error(
                f"Помилка видалення задачі сканування: {str(e)}",
                extra={"task_id": task_id},
            )
            await self.db.rollback()
            raise

    async def update_scan_task_state(
        self, task_id: str, state: str
    ) -> Optional[models.ScanTask]:
        try:
            scan_task = await self.db.get(models.ScanTask, task_id)
            if not scan_task:
                logger.warning(
                    "Задача сканування не знайдена", extra={"task_id": task_id}
                )
                return None
            if state not in ["SUSPENDED", "RESUMED", "PENDING", "RUNNING", "FAILED"]:
                logger.error(f"Недопустимий стан: {state}", extra={"task_id": task_id})
                raise ValueError(f"Недопустимий стан: {state}")
            scan_task.status = state
            scan_task.updated_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(scan_task)
            logger.debug(
                f"Статус задачі оновлено до {state}", extra={"task_id": task_id}
            )
            return scan_task
        except SQLAlchemyError as e:
            logger.error(
                f"Помилка оновлення стану задачі: {str(e)}", extra={"task_id": task_id}
            )
            await self.db.rollback()
            raise
