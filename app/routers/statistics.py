import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..repositories.statistics import StatisticsRepository
from ..schemas import DashboardStats
from .auth import get_current_user

logger = logging.getLogger(__name__)


router = APIRouter(tags=["statistics"])


@router.get(
    "/statistics",
    response_model=DashboardStats,
    operation_id="get_statistics",
    dependencies=[Depends(get_current_user)],
)
async def get_statistics(
    metrics: List[str] = Query(
        None, description="Список метрик для отримання статистики"
    ),
    db: AsyncSession = Depends(get_db),
):
    logger.info(f"Запит статистики з метриками: {metrics}")
    try:
        repo = StatisticsRepository(db)
        if metrics is None:
            metrics = [
                "total_computers",
                "os_distribution",
                "low_disk_space_with_volumes",
                "last_scan_time",
                "status_stats",
            ]
        return await repo.get_statistics(metrics)
    except Exception as e:
        logger.error(f"Помилка отримання статистики: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Помилка сервера: {str(e)}")
