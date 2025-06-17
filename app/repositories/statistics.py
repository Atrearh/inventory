# app/repositories/statistics.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from .. import models, schemas
import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

class StatisticsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_total_computers(self) -> int:
        logger.debug("Запрос количества компьютеров")
        result = await self.db.execute(select(func.count(models.Computer.id)))
        return result.scalar()

    async def get_os_versions(self) -> List[schemas.OsVersion]:
        logger.debug("Запрос статистики по версиям ОС")
        os_stats = await self.db.execute(
            select(
                models.Computer.os_version,
                func.count(models.Computer.id).label("count")
            ).group_by(models.Computer.os_version)
        )
        return [
            schemas.OsVersion(os_version=str(os_version) or "Unknown", count=count)
            for os_version, count in os_stats.all()
        ]

    async def get_low_disk_space(self) -> List[schemas.LowDiskSpace]:
        logger.debug("Запрос дисков с низким свободным местом")
        result = await self.db.execute(
            select(models.Disk)
            .join(models.Computer, isouter=True)
            .filter(
                (models.Disk.total_space > 0) &
                (models.Disk.free_space / models.Disk.total_space < 0.1)
            )
            .options(selectinload(models.Disk.computer))
        )
        disks = result.scalars().all()
        return [
            schemas.LowDiskSpace(
                hostname=disk.computer.hostname if disk.computer else "Unknown",
                disk_id=disk.device_id or "Unknown",
                free_space_percent=(disk.free_space / disk.total_space * 100 if disk.total_space and disk.free_space else 0.0)
            )
            for disk in disks
        ]

    async def get_last_scan_time(self) -> Optional[datetime]:
        logger.debug("Запрос последней задачи сканирования")
        last_scan = await self.db.execute(
            select(models.ScanTask).order_by(models.ScanTask.updated_at.desc()).limit(1)
        )
        last_scan = last_scan.scalar_one_or_none()
        return last_scan.updated_at if last_scan else None

    async def get_status_stats(self) -> List[schemas.StatusStats]:
        logger.debug("Запрос статистики по статусам")
        status_stats = await self.db.execute(
            select(
                models.Computer.check_status,
                func.count(models.Computer.id).label("count")
            ).group_by(models.Computer.check_status)
        )
        return [
            schemas.StatusStats(status=str(status.value) or "Unknown", count=count)
            for status, count in status_stats.all()
        ]

    async def get_statistics(self, metrics: List[str] = None) -> schemas.DashboardStats:
        if metrics is None:
            metrics = ["total_computers", "os_versions", "low_disk_space", "last_scan_time", "status_stats"]
        total_computers = 0
        os_versions = []
        low_disk_space = []
        last_scan_time = None
        status_stats = []
        try:
            if "total_computers" in metrics:
                total_computers = await self.get_total_computers()
            if "os_versions" in metrics:
                os_versions = await self.get_os_versions()
            if "low_disk_space" in metrics:
                low_disk_space = await self.get_low_disk_space()
            if "last_scan_time" in metrics:
                last_scan_time = await self.get_last_scan_time()
            if "status_stats" in metrics:
                status_stats = await self.get_status_stats()
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {str(e)}", exc_info=True)
            raise
        result = schemas.DashboardStats(
            total_computers=total_computers,
            os_stats=schemas.OsStats(os_versions=os_versions),
            disk_stats=schemas.DiskStats(low_disk_space=low_disk_space),
            scan_stats=schemas.ScanStats(
                last_scan_time=last_scan_time,
                status_stats=status_stats
            )
        )
        logger.debug(f"Возвращаемые данные статистики: {result.model_dump()}")
        return result