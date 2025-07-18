import logging
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, Float
from sqlalchemy.sql.expression import case, or_
from typing import List, Optional

from .. import models, schemas

logger = logging.getLogger(__name__)

class StatisticsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_total_computers(self) -> Optional[int]:
        """Возвращает общее количество компьютеров."""
        logger.debug("Запрос количества компьютеров")
        try:
            result = await self.db.execute(select(func.count(models.Computer.id)))
            count = result.scalar_one()
            logger.debug(f"Получено количество компьютеров: {count}")
            return count
        except Exception as e:
            logger.error(f"Ошибка при получении количества компьютеров: {str(e)}", exc_info=True)
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
                "Windows 11 Pro": r"windows 11 pro",
                "Windows 10 Pro": r"windows 10 pro",
                "Windows 10 Корпоративная": r"windows 10.*(корпоративная|enterprise|ltsc|ltsb)",
                "Windows 7 Профессиональная": r"windows 7.*профессиональная",
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
                        logger.debug(f"Сопоставлено как Other Servers: {category}")
                else:
                    for name, pattern in client_os_map.items():
                        if re.search(pattern, category_lower, re.IGNORECASE):
                            client_os_counts[name] += count
                            logger.debug(f"Сопоставлено как {name}")
                            matched = True
                            break
                    if not matched:
                        client_os_counts["Other Clients"] += count
                        logger.debug(f"Сопоставлено як Other Clients: {category}")

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
        logger.debug("Запрос логических дисков с низким свободным местом")
        try:
            stmt = (
                select(
                    models.Computer.id,
                    models.Computer.hostname,
                    models.LogicalDisk.device_id,
                    models.LogicalDisk.volume_label,
                    models.LogicalDisk.total_space,
                    models.LogicalDisk.free_space,
                )
                .join(models.Computer, models.LogicalDisk.computer_id == models.Computer.id)
                .filter(
                    models.LogicalDisk.total_space > 0,
                    models.LogicalDisk.free_space.isnot(None),
                    (models.LogicalDisk.free_space.cast(Float) / models.LogicalDisk.total_space) < 0.1,
                )
            )
            result = await self.db.execute(stmt)
            disks_data = result.all()
            logger.debug(f"Получено {len(disks_data)} записей о логических дисках: {disks_data}")

            disk_volumes = [
                schemas.DiskVolume(
                    id=computer_id,
                    hostname=hostname,
                    disk_id=device_id or "Unknown",
                    volume_label=volume_label,
                    total_space_gb=round(total_space / (1024**3), 2) if total_space else 0.0,
                    free_space_gb=round(free_space / (1024**3), 2) if free_space else 0.0,
                )
                for computer_id, hostname, device_id, volume_label, total_space, free_space in disks_data
            ]
            logger.debug(f"Сформировано {len(disk_volumes)} объектов DiskVolume")
            return disk_volumes
        except Exception as e:
            logger.error(f"Ошибка при получении данных о дисках: {str(e)}", exc_info=True)
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

    async def get_statistics(self, metrics: List[str]) -> schemas.DashboardStats:
        stats = schemas.DashboardStats(
            total_computers=None,
            os_stats=schemas.OsStats(client_os=[], server_os=[]),
            disk_stats=schemas.DiskStats(low_disk_space=[]),
            scan_stats=schemas.ScanStats(last_scan_time=None, status_stats=[]),
            component_changes=[]
        )

        if "total_computers" in metrics:
            stats.total_computers = (await self.db.execute(select(func.count()).select_from(models.Computer))).scalar() or 0

        if "os_distribution" in metrics:
            # Використовуємо get_os_distribution для коректного об'єднання ОС
            os_stats = await self.get_os_distribution()
            stats.os_stats.client_os = os_stats.client_os
            stats.os_stats.server_os = os_stats.server_os

        if "low_disk_space_with_volumes" in metrics:
            low_disk_space_query = await self.db.execute(
                select(models.Computer.id, models.Computer.hostname, models.LogicalDisk.device_id, models.LogicalDisk.volume_label, models.LogicalDisk.total_space, models.LogicalDisk.free_space)
                .join(models.LogicalDisk, models.Computer.id == models.LogicalDisk.computer_id)
                .filter(models.LogicalDisk.free_space / models.LogicalDisk.total_space < 0.1)
            )
            stats.disk_stats.low_disk_space = [
                schemas.DiskVolume(
                    id=row.id,
                    hostname=row.hostname,
                    disk_id=row.device_id or "Unknown",
                    volume_label=row.volume_label,
                    total_space_gb=row.total_space / (1024 * 1024 * 1024),
                    free_space_gb=row.free_space / (1024 * 1024 * 1024) if row.free_space else 0
                )
                for row in low_disk_space_query.all()
            ]

        if "last_scan_time" in metrics:
            last_scan = await self.db.execute(select(models.ScanTask.updated_at).order_by(models.ScanTask.updated_at.desc()))
            last_scan_time = last_scan.scalars().first()
            stats.scan_stats.last_scan_time = last_scan_time

        if "status_stats" in metrics:
            status_query = await self.db.execute(
                select(models.Computer.check_status, func.count().label("count"))
                .group_by(models.Computer.check_status)
            ) 
            stats.scan_stats.status_stats = [
                schemas.StatusStats(status=row.check_status or "Unknown", count=row.count)
                for row in status_query.all()
            ]

        if "component_changes" in metrics:
            component_types = [
                ("software", models.Software),
                ("physical_disk", models.PhysicalDisk),
                ("logical_disk", models.LogicalDisk),
                ("processor", models.Processor),
                ("video_card", models.VideoCard),
                ("ip_address", models.IPAddress),
                ("mac_address", models.MACAddress)
            ]
            for component_type, model in component_types:
                count_query = await self.db.execute(
                    select(func.count()).select_from(model).filter(
                        or_(model.detected_on != None, model.removed_on != None)
                    )
                )
                count = count_query.scalar() or 0
                stats.component_changes.append(
                    schemas.ComponentChangeStats(component_type=component_type, changes_count=count)
                )

        return stats
 