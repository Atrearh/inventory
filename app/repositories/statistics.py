# app/repositories/statistics.py
import logging
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, Float
from sqlalchemy.orm import selectinload
from datetime import datetime
from typing import List, Optional

from .. import models, schemas

logger = logging.getLogger(__name__)

class StatisticsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_total_computers(self) -> int:
        """Возвращает общее количество компьютеров."""
        logger.debug("Запрос количества компьютеров")
        try:
            async with self.db as session:
                result = await session.execute(select(func.count(models.Computer.id)))
                return result.scalar_one()
        except Exception as e:
            logger.error(f"Ошибка при получении количества компьютеров: {str(e)}")
            raise

    async def get_os_distribution(self) -> schemas.OsStats:
        """Возвращает распределение по версиям ОС (клиентские и серверные) на основе os_name."""
        logger.debug("Запрос распределения по версиям ОС")
        try:
            async with self.db as session:
                result = await session.execute(
                    select(
                        models.Computer.os_name,
                        func.count(models.Computer.id).label("count")
                    ).group_by(models.Computer.os_name)
                )
                os_data = result.all()
                logger.debug(f"Полученные данные OS: {os_data}")

                client_os_map = {
                    "Windows 11": r"windows 11",
                    "Windows 10": r"windows 10(?![^,]*server|ltsc)",
                    "Windows 7": r"windows 7",
                }

                server_os_map = {
                    "Windows Server 2022": r"server 2022",
                    "Windows Server 2019": r"server 2019",
                    "Windows Server 2016": r"server 2016",
                    "Windows Server 2008": r"server 2008",
                }

                client_os_counts = {key: 0 for key in client_os_map}
                client_os_counts["Other Clients"] = 0
                client_os_counts["Unknown"] = 0

                server_os_counts = {key: 0 for key in server_os_map}
                server_os_counts["Other Servers"] = 0

                for os_name, count in os_data:
                    logger.debug(f"Обработка OS: {os_name}, count: {count}")
                    if not os_name:
                        client_os_counts["Unknown"] += count
                        continue

                    os_name_lower = os_name.lower()
                    matched = False

                    if "server" in os_name_lower:
                        for name, pattern in server_os_map.items():
                            if re.search(pattern, os_name_lower, re.IGNORECASE):
                                server_os_counts[name] += count
                                logger.debug(f"Сопоставлено как {name}")
                                matched = True
                                break
                        if not matched:
                            server_os_counts["Other Servers"] += count
                            logger.debug("Сопоставлено как Other Servers")
                    else:
                        for name, pattern in client_os_map.items():
                            if re.search(pattern, os_name_lower, re.IGNORECASE):
                                client_os_counts[name] += count
                                logger.debug(f"Сопоставлено как {name}")
                                matched = True
                                break
                        if not matched:
                            client_os_counts["Other Clients"] += count
                            logger.debug("Сопоставлено как Other Clients")

                client_os = [schemas.OsDistribution(category=cat, count=count) for cat, count in client_os_counts.items() if count > 0]
                server_os = [schemas.ServerDistribution(category=cat, count=count) for cat, count in server_os_counts.items() if count > 0]

                logger.debug(f"Client OS counts: {client_os}")
                logger.debug(f"Server OS counts: {server_os}")
                return schemas.OsStats(client_os=client_os, server_os=server_os)
        except Exception as e:
            logger.error(f"Ошибка при получении распределения ОС: {str(e)}")
            raise

    async def get_low_disk_space_with_volumes(self) -> List[schemas.DiskVolume]:
        """Возвращает список дисков с низким уровнем свободного места."""
        logger.debug("Запрос дисков с низким свободным местом и объемами")
        try:
            async with self.db as session:
                stmt = (
                    select(
                        models.Computer.hostname,
                        models.Disk.device_id,
                        models.Disk.total_space,
                        models.Disk.free_space,
                    )
                    .join(models.Computer, models.Disk.computer_id == models.Computer.id)
                    .filter(
                        models.Disk.total_space > 0,
                        models.Disk.free_space.isnot(None),
                        (models.Disk.free_space.cast(Float) / models.Disk.total_space) < 0.1,
                    )
                )

                result = await session.execute(stmt)
                disks_data = result.all()

                # Преобразуем байты в гигабайты для ответа
                return [
                    schemas.DiskVolume(
                        hostname=hostname,
                        disk_id=device_id or "Unknown",
                        total_space_gb=round(total_space / (1024**3), 2) if total_space else 0.0,
                        free_space_gb=round(free_space / (1024**3), 2) if free_space else 0.0,
                    )
                    for hostname, device_id, total_space, free_space in disks_data
                ]
        except Exception as e:
            logger.error(f"Ошибка при получении данных о дисках: {str(e)}")
            raise

    async def get_last_scan_time(self) -> Optional[datetime]:
        """Возвращает время последнего полного сканирования."""
        # This function appears correct in the original file
        logger.debug("Запрос последней задачи сканирования")
        try:
            async with self.db as session:
                result = await session.execute(
                    select(models.ScanTask).order_by(models.ScanTask.updated_at.desc()).limit(1)
                )
                last_scan = result.scalar_one_or_none()
                return last_scan.updated_at if last_scan else None
        except Exception as e:
            logger.error(f"Ошибка при получении времени последнего сканирования: {str(e)}")
            raise

    async def get_status_stats(self) -> List[schemas.StatusStats]:
        """Возвращает статистику по статусам компьютеров."""
        # This function appears correct in the original file
        logger.debug("Запрос статистики по статусам")
        try:
            async with self.db as session:
                result = await session.execute(
                    select(
                        models.Computer.check_status,
                        func.count(models.Computer.id).label("count")
                    ).group_by(models.Computer.check_status)
                )
                return [
                    schemas.StatusStats(status=str(status.value) if status else "Unknown", count=count)
                    for status, count in result.all()
                ]
        except Exception as e:
            logger.error(f"Ошибка при получении статистики статусов: {str(e)}")
            raise

    async def get_statistics(self, metrics: List[str] = None) -> schemas.DashboardStats:
        """Возвращает статистику для дашборда."""
        if metrics is None:
            metrics = ["total_computers", "os_distribution", "low_disk_space_with_volumes", "last_scan_time", "status_stats"]
        
        total_computers = 0
        os_stats = schemas.OsStats(client_os=[], server_os=[])
        low_disk_space = []
        last_scan_time = None
        status_stats = []
        
        try:
            if "total_computers" in metrics:
                total_computers = await self.get_total_computers()
            if "os_distribution" in metrics:
                os_stats = await self.get_os_distribution()
            if "low_disk_space_with_volumes" in metrics:
                low_disk_space = await self.get_low_disk_space_with_volumes()
            if "last_scan_time" in metrics:
                last_scan_time = await self.get_last_scan_time()
            if "status_stats" in metrics:
                status_stats = await self.get_status_stats()
            
            logger.debug("Статистика собрана успешно")
        
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {str(e)}", exc_info=True)
            raise
        
        result = schemas.DashboardStats(
            total_computers=total_computers,
            os_stats=os_stats,
            disk_stats=schemas.DiskStats(low_disk_space=low_disk_space),
            scan_stats=schemas.ScanStats(
                last_scan_time=last_scan_time,
                status_stats=status_stats
            )
        )
        logger.debug(f"Возвращаемые данные статистики: {result.model_dump()}")
        return result