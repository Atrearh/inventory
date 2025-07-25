import logging
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, Float
from sqlalchemy.sql.expression import case, or_, and_
from typing import List, Optional

from .. import models, schemas

logger = logging.getLogger(__name__)

class StatisticsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_total_computers(self) -> Optional[int]:
        """Повертає кількість активних комп’ютерів (без статусів disabled та is_deleted)."""
        logger.debug("Запит кількості активних комп’ютерів")
        try:
            result = await self.db.execute(
                select(func.count(models.Computer.id)).filter(
                    and_(
                        models.Computer.check_status != 'disabled',
                        models.Computer.check_status != 'is_deleted'
                    )
                )
            )
            count = result.scalar_one()
            logger.debug(f"Отримано кількість активних комп’ютерів: {count}")
            return count
        except Exception as e:
            logger.error(f"Помилка при отриманні кількості активних комп’ютерів: {str(e)}", exc_info=True)
            raise

    async def get_os_names(self) -> List[str]:
        """Повертає список унікальних назв ОС, включно із серверними."""
        logger.debug("Запит унікальних назв ОС")
        try:
            result = await self.db.execute(
                select(models.Computer.os_name)
                .filter(models.Computer.os_name != None)
                .distinct()
            )
            os_names = [row.os_name for row in result.scalars().all() if row.os_name]
            # Додаємо серверні ОС із розподілу ОС
            os_dist = await self.get_os_distribution()
            server_os_names = [os.category for os in os_dist.server_os]
            all_os_names = sorted(set(os_names + server_os_names))
            logger.debug(f"Знайдено {len(all_os_names)} унікальних назв ОС")
            return all_os_names
        except Exception as e:
            logger.error(f"Помилка при отриманні списку ОС: {str(e)}")
            raise

    async def get_os_distribution(self) -> schemas.OsStats:
        """Повертає розподіл за версіями ОС (клієнтські та серверні) на основі os_name, виключаючи disabled та is_deleted."""
        logger.debug("Запит розподілу за версіями ОС")
        try:
            # Визначаємо категорію ОС із явною обробкою NULL та серверних ОС
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
                )
                .filter(
                    and_(
                        models.Computer.check_status != 'disabled',
                        models.Computer.check_status != 'is_deleted'
                    )
                )
                .group_by(os_category)
            )
            os_data = result.all()
            logger.debug(f"Отримані дані ОС: {os_data}")

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
                logger.debug(f"Обробка категорії: {category}, count: {count}")
                if category == 'Unknown':
                    client_os_counts["Unknown"] += count
                    continue

                category_lower = category.lower()
                matched = False

                if 'server' in category_lower or 'hyper-v' in category_lower:
                    for name, pattern in server_os_map.items():
                        if re.search(pattern, category_lower, re.IGNORECASE):
                            server_os_counts[name] += count
                            logger.debug(f"Супоставлено як {name}")
                            matched = True
                            break
                    if not matched:
                        server_os_counts["Other Servers"] += count
                        logger.debug(f"Супоставлено як Other Servers: {category}")
                else:
                    for name, pattern in client_os_map.items():
                        if re.search(pattern, category_lower, re.IGNORECASE):
                            client_os_counts[name] += count
                            logger.debug(f"Супоставлено як {name}")
                            matched = True
                            break
                    if not matched:
                        client_os_counts["Other Clients"] += count
                        logger.debug(f"Супоставлено як Other Clients: {category}")

            client_os = [
                schemas.OsDistribution(category=cat, count=count)
                for cat, count in client_os_counts.items() if count > 0
            ]
            server_os = [
                schemas.ServerDistribution(category=cat, count=count)
                for cat, count in server_os_counts.items() if count > 0
            ]

            logger.debug(f"Клієнтські ОС: {client_os}")
            logger.debug(f"Серверні ОС: {server_os}")
            return schemas.OsStats(client_os=client_os, server_os=server_os)
        except Exception as e:
            logger.error(f"Помилка при отриманні розподілу ОС: {str(e)}")
            raise

    async def get_low_disk_space_with_volumes(self) -> List[schemas.DiskVolume]:
        """Повертає логічні диски з низьким вільним місцем."""
        logger.debug("Запит логічних дисків із низьким вільним місцем")
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
            logger.debug(f"Отримано {len(disks_data)} записів про логічні диски: {disks_data}")

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
            logger.debug(f"Сформовано {len(disk_volumes)} об’єктів DiskVolume")
            return disk_volumes
        except Exception as e:
            logger.error(f"Помилка при отриманні даних про диски: {str(e)}", exc_info=True)
            raise

    async def get_status_stats(self) -> List[schemas.StatusStats]:
        """Повертає статистику за статусами комп’ютерів."""
        logger.debug("Запит статистики за статусами")
        try:
            result = await self.db.execute(
                select(
                    models.Computer.check_status,
                    func.count(models.Computer.id).label("count")
                ).group_by(models.Computer.check_status)
            )
            return [
                schemas.StatusStats(status=str(status.value) if status else "Unknown", count=count)
                for status, count in result.all() if count > 0
            ]
        except Exception as e:
            logger.error(f"Помилка при отриманні статистики статусів: {str(e)}")
            raise

    async def get_statistics(self, metrics: List[str]) -> schemas.DashboardStats:
        """Повертає статистику за вказаними метриками."""
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
            os_stats = await self.get_os_distribution()
            stats.os_stats.client_os = os_stats.client_os
            stats.os_stats.server_os = os_stats.server_os

        if "low_disk_space_with_volumes" in metrics:
            low_disk_space_query = await self.db.execute(
                select(models.Computer.id, models.Computer.hostname, models.LogicalDisk.device_id, models.LogicalDisk.volume_label, models.LogicalDisk.total_space, models.LogicalDisk.free_space)
                .join(models.Computer, models.Computer.id == models.LogicalDisk.computer_id)
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
                for row in status_query.all() if row.count > 0
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