import logging
import re
from typing import List, Optional

from sqlalchemy import Float, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import and_, case, or_

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
                            models.Computer.check_status != "disabled",
                            models.Computer.check_status != "is_deleted",
                        )
                    )
                )
                count = result.scalar_one()
                logger.debug(f"Отримано кількість активних комп’ютерів: {count}")
                return count
            except Exception as e:
                logger.error(
                    f"Помилка при отриманні кількості активних комп’ютерів: {str(e)}",
                    exc_info=True,
                )
                raise
    async def get_os_names(self) -> List[str]:
            """Повертає список унікальних назв ОС, включно із серверними."""
            logger.debug("Запит унікальних назв ОС")
            try:
                result = await self.db.execute(
                    select(models.OperatingSystem.name)
                    .join(models.Computer, models.Computer.os_id == models.OperatingSystem.id)
                    .filter(models.OperatingSystem.name != None)
                    .distinct()
                )
                os_names = [row for row in result.scalars().all() if row]
                logger.debug(f"Знайдено {len(os_names)} унікальних назв ОС")
                return sorted(os_names)
            except Exception as e:
                logger.error(f"Помилка при отриманні списку ОС: {str(e)}")
                raise

    async def get_os_distribution(self) -> schemas.OsStats:
            """Повертає розподіл за версіями ОС (клієнтські та серверні) на основі operating_systems."""
            logger.debug("Запит розподілу за версіями ОС")
            try:
                # Визначаємо категорію ОС із явною обробкою NULL та серверних ОС
                os_category = case(
                    (
                        models.OperatingSystem.name.is_(None) | (models.OperatingSystem.name == ""),
                        "Unknown",
                    ),
                    (
                        models.OperatingSystem.name.ilike("%Server%")
                        | models.OperatingSystem.name.ilike("%Hyper-V%"),
                        func.coalesce(models.OperatingSystem.name, "Other Servers"),
                    ),
                    else_=func.coalesce(models.OperatingSystem.name, "Other Clients"),
                ).label("category")

                result = await self.db.execute(
                    select(os_category, func.count(models.Computer.id).label("count"))
                    .join(models.Computer, models.Computer.os_id == models.OperatingSystem.id)
                    .filter(
                        and_(
                            models.Computer.check_status != "disabled",
                            models.Computer.check_status != "is_deleted",
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
                    if category == "Unknown":
                        client_os_counts["Unknown"] += count
                        continue

                    category_lower = category.lower()
                    matched = False

                    if "server" in category_lower or "hyper-v" in category_lower:
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

                client_os_stats = [
                    schemas.OsCategoryStats(category=cat, count=count)
                    for cat, count in client_os_counts.items()
                    if count > 0
                ]
                server_os_stats = [
                    schemas.OsCategoryStats(category=cat, count=count)
                    for cat, count in server_os_counts.items()
                    if count > 0
                ]

                total_count = sum(
                    item.count for item in client_os_stats + server_os_stats
                )
                logger.debug(f"Загальна кількість комп’ютерів: {total_count}")
                logger.debug(f"Клієнтські ОС: {client_os_stats}")
                logger.debug(f"Серверні ОС: {server_os_stats}")

                return schemas.OsStats(
                    count=total_count,
                    client_os=client_os_stats,
                    server_os=server_os_stats,
                )
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
                .join(
                    models.Computer,
                    models.LogicalDisk.computer_id == models.Computer.id,
                )
                .filter(
                    models.LogicalDisk.total_space > 0,
                    models.LogicalDisk.free_space.isnot(None),
                    (
                        models.LogicalDisk.free_space.cast(Float)
                        / models.LogicalDisk.total_space
                    )
                    < 0.1,  # Виправлено: cast до Float для уникнення помилок
                )
            )
            result = await self.db.execute(stmt)
            disks_data = result.all()
            logger.debug(f"Отримано {len(disks_data)} записів про логічні диски")

            disk_volumes = [
                schemas.DiskVolume(
                    id=computer_id,  # Забезпечено: ID комп'ютера передається в схему
                    hostname=hostname,
                    device_id=device_id or "Unknown",
                    volume_label=volume_label,
                    total_space_gb=(
                        round(total_space / (1024**3), 2) if total_space else 0.0
                    ),
                    free_space_gb=(
                        round(free_space / (1024**3), 2) if free_space else 0.0
                    ),
                )
                for computer_id, hostname, device_id, volume_label, total_space, free_space in disks_data
            ]
            logger.debug(f"Сформовано {len(disk_volumes)} об’єктів DiskVolume")
            return disk_volumes
        except Exception as e:
            logger.error(
                f"Помилка при отриманні даних про диски: {str(e)}", exc_info=True
            )
            raise

    async def get_status_stats(self) -> List[schemas.StatusStats]:
        """Повертає статистику за статусами комп’ютерів."""
        logger.debug("Запит статистики за статусами")
        try:
            result = await self.db.execute(
                select(
                    models.Computer.check_status,
                    func.count(models.Computer.id).label("count"),
                ).group_by(models.Computer.check_status)
            )
            return [
                schemas.StatusStats(
                    status=str(status.value) if status else "Unknown", count=count
                )
                for status, count in result.all()
                if count > 0
            ]
        except Exception as e:
            logger.error(f"Помилка при отриманні статистики статусів: {str(e)}")
            raise




    # Додаємо до StatisticsRepository
    async def get_software_distribution(self) -> List[schemas.OsCategoryStats]:
        """Повертає розподіл встановленого програмного забезпечення."""
        logger.debug("Запит розподілу програмного забезпечення")
        try:
            result = await self.db.execute(
                select(
                    models.SoftwareCatalog.name,
                    func.count(models.InstalledSoftware.id).label("count")
                )
                .join(models.InstalledSoftware, models.InstalledSoftware.software_id == models.SoftwareCatalog.id)
                .join(models.Computer, models.InstalledSoftware.computer_id == models.Computer.id)
                .filter(
                    and_(
                        models.Computer.check_status != "disabled",
                        models.Computer.check_status != "is_deleted",
                    )
                )
                .group_by(models.SoftwareCatalog.name)
                .order_by(func.count(models.InstalledSoftware.id).desc())
            )
            software_data = result.all()
            logger.debug(f"Отримані дані ПЗ: {software_data}")

            return [
                schemas.OsCategoryStats(category=name, count=count)
                for name, count in software_data
                if count > 0
            ]
        except Exception as e:
            logger.error(f"Помилка при отриманні розподілу ПЗ: {str(e)}")
            raise

    # Оновлюємо метод get_statistics
    async def get_statistics(self, metrics: List[str]) -> schemas.DashboardStats:
        stats = schemas.DashboardStats(
            total_computers=None,
            os_stats=schemas.OsStats(count=0, client_os=[], server_os=[]),
            disk_stats=schemas.DiskStats(low_disk_space=[]),
            scan_stats=schemas.ScanStats(last_scan_time=None, status_stats=[]),
            component_changes=[],
        )

        if "total_computers" in metrics:
            stats.total_computers = await self.get_total_computers()

        if "os_distribution" in metrics:
            stats.os_stats = await self.get_os_distribution()

        if "software_distribution" in metrics:
            stats.os_stats.software_distribution = await self.get_software_distribution()

        if "low_disk_space_with_volumes" in metrics:
            stats.disk_stats.low_disk_space = await self.get_low_disk_space_with_volumes()

        if "last_scan_time" in metrics:
            last_scan = await self.db.execute(
                select(models.ScanTask.updated_at).order_by(
                    models.ScanTask.updated_at.desc()
                )
            )
            stats.scan_stats.last_scan_time = last_scan.scalars().first()

        if "status_stats" in metrics:
            stats.scan_stats.status_stats = await self.get_status_stats()

        if "component_changes" in metrics:
            component_types = [
                ("software", models.InstalledSoftware),  # Змінено на InstalledSoftware
                ("physical_disk", models.PhysicalDisk),
                ("logical_disk", models.LogicalDisk),
                ("processor", models.Processor),
                ("video_card", models.VideoCard),
                ("ip_address", models.IPAddress),
                ("mac_address", models.MACAddress),
            ]
            for component_type, model in component_types:
                count_query = await self.db.execute(
                    select(func.count())
                    .select_from(model)
                    .filter(
                        or_(
                            model.detected_on.is_not(None),
                            model.removed_on.is_not(None),
                        )
                    )
                )
                count = count_query.scalar() or 0
                stats.component_changes.append(
                    schemas.ComponentChangeStats(
                        component_type=component_type, changes_count=count
                    )
                )

        return stats