from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import List, Tuple
from uuid import UUID
from ..database import get_db
from ..schemas import  ScanTask
from ..repositories.tasks_repository import TasksRepository
import logging


logger = logging.getLogger(__name__)



router = APIRouter(prefix="/api/tasks", tags=["tasks"])

@router.get("/", response_model=Tuple[List[ScanTask], int])

async def get_scan_tasks(
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
) -> Tuple[List[ScanTask], int]:
    try:
        repo = TasksRepository(db)
        tasks, total = await repo.get_scan_tasks(limit=limit, offset=offset)
        return [ScanTask.model_validate(task, from_attributes=True) for task in tasks], total
    except Exception as e:
        logger.error(f"Помилка отримання задач сканування: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Помилка сервера при отриманні задач")

@router.delete("/{task_id}", status_code=status.HTTP_200_OK, response_model=dict)

async def delete_scan_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> dict:
    try:
        repo = TasksRepository(db)
        success = await repo.delete_scan_task(str(task_id))
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не знайдена")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Помилка видалення задачі {task_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Помилка сервера при видаленні задачі")

@router.patch("/{task_id}/state", response_model=ScanTask)

async def update_scan_task_state(
    task_id: UUID,
    state: str,
    db: AsyncSession = Depends(get_db)
) -> ScanTask:
    try:
        repo = TasksRepository(db)
        task = await repo.update_scan_task_state(str(task_id), state)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не знайдена")
        return ScanTask.model_validate(task, from_attributes=True)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Помилка оновлення стану задачі {task_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Помилка сервера при оновленні стану задачі")