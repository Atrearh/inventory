# app/repositories/statistics.py
import logging
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, Float
from sqlalchemy.sql.expression import case
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
            result = await self.db.execute(select(func.count(models.Computer.id)))
            return result.scalar_one()
        except Exception as e:
            logger.error(f"Ошибка при получении количества компьютеров: {str(e)}")
            raise

    async def get_os_names(self) -> List[str]:
        """Возвращает список уникальных имен ОС, включая серверные."""
        logger.debug("Запрос уникальных имен ОС")
        try:
            result = await self.db.execute(
                select(models.Computer.os_name)
                .filter(models.Computer.os_name != None)
                .distinct()
            )
            os_names = [row.os_name for row in result.scalars().all() if row.os_name]
            # Добавляем серверные ОС из os_distribution
            os_dist = await self.get_os_distribution()
            server_os_names = [os.category for os in os_dist.server_os]
            all_os_names = sorted(set(os_names + server_os_names))
            logger.debug(f"Найдено {len(all_os_names)} уникальных имен ОС")
            return sorted(set(all_os_names)) 
        except Exception as e:
            logger.error(f"Ошибка при получении списка ОС: {str(e)}")
            raise

    async def get_os_distribution(self) -> schemas.OsStats:
        """Возвращает распределение по версиям ОС (клиентские и серверные) на основе os_name."""
        logger.debug("Запрос распределения по версиям ОС")
        try:
            # Определяем категорию ОС с использованием case для явной обработки NULL и серверных ОС
            os_category = case(
                (
                    models.Computer.os_name.is_(None) | (models.Computer.os_name == ''),
                    'Unknown'
                ),
                (
                    models.Computer.os_name.ilike('%Server%') | models.Computer.os_name.ilike('%Hyper-V%'),
                    func.coalesce(models.Computer.os_name, 'Other Servers')
                ),
                else_=func.coalesce(models.Computer.os_name, 'Other Clients')
            ).label('category')

            result = await self.db.execute(
                select(
                    os_category,
                    func.count(models.Computer.id).label('count')
                ).group_by(os_category)
            )
            os_data = result.all()
            logger.debug(f"Полученные данные OS: {os_data}")

            client_os_map = {
                "Windows 11": r"windows 11",
                "Windows 10": r"windows 10(?![^,]*server|ltsc)",
                "Windows 7": r"windows 7",
                "Ubuntu": r"ubuntu",
                "CentOS": r"centos",
                "Debian": r"debian",
            }

            server_os_map = {
                "Windows Server 2022": r"server 2022",
                "Windows Server 2019": r"server 2019",
                "Windows Server 2016": r"server 2016",
                "Windows Server 2008": r"server 2008",
                "Hyper-V Server": r"hyper-v",
            }

            client_os_counts = {key: 0 for key in client_os_map}
            client_os_counts["Other Clients"] = 0
            client_os_counts["Unknown"] = 0

            server_os_counts = {key: 0 for key in server_os_map}
            server_os_counts["Other Servers"] = 0

            for category, count in os_data:
                logger.debug(f"Обработка категории: {category}, count: {count}")
                if category == 'Unknown':
                    client_os_counts["Unknown"] += count
                    continue

                category_lower = category.lower()
                matched = False

                if 'server' in category_lower or 'hyper-v' in category_lower:
                    for name, pattern in server_os_map.items():
                        if re.search(pattern, category_lower, re.IGNORECASE):
                            server_os_counts[name] += count
                            logger.debug(f"Сопоставлено как {name}")
                            matched = True
                            break
                    if not matched:
                        server_os_counts["Other Servers"] += count
                        logger.debug("Сопоставлено как Other Servers")
                else:
                    for name, pattern in client_os_map.items():
                        if re.search(pattern, category_lower, re.IGNORECASE):
                            client_os_counts[name] += count
                            logger.debug(f"Сопоставлено как {name}")
                            matched = True
                            break
                    if not matched:
                        client_os_counts["Other Clients"] += count
                        logger.debug("Сопоставлено как Other Clients")

            client_os = [
                schemas.OsDistribution(category=cat, count=count)
                for cat, count in client_os_counts.items() if count > 0
            ]
            server_os = [
                schemas.ServerDistribution(category=cat, count=count)
                for cat, count in server_os_counts.items() if count > 0
            ]

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
            result = await self.db.execute(stmt)
            disks_data = result.all()

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
        logger.debug("Запрос последней задачи сканирования")
        try:
            result = await self.db.execute(
                select(models.ScanTask).order_by(models.ScanTask.updated_at.desc()).limit(1)
            )
            last_scan = result.scalar_one_or_none()
            return last_scan.updated_at if last_scan else None
        except Exception as e:
            logger.error(f"Ошибка при получении времени последнего сканирования: {str(e)}")
            raise

    async def get_status_stats(self) -> List[schemas.StatusStats]:
        """Возвращает статистику по статусам компьютеров."""
        logger.debug("Запрос статистики по статусам")
        try:
            result = await self.db.execute(
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
        """Возвращает статистику для дашборда, включая список уникальных имен ОС."""
        if metrics is None:
            metrics = ["total_computers", "os_distribution", "low_disk_space_with_volumes", "last_scan_time", "status_stats", "os_names"]
        
        total_computers = 0
        os_stats = schemas.OsStats(client_os=[], server_os=[])
        low_disk_space = []
        last_scan_time = None
        status_stats = []
        os_names = []
        
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
            if "os_names" in metrics:
                os_names = await self.get_os_names()
            
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
            ),
            os_names=os_names
        )
        logger.debug(f"Возвращаемые данные статистики: {result.model_dump()}")
        return result