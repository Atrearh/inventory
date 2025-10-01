import logging
import asyncio
from time import perf_counter
from typing import List, Optional
from aiocache import Cache, cached
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import and_, case, or_

from .. import models, schemas

logger = logging.getLogger(__name__)

class StatisticsRepository: 
    def __init__(self, db: AsyncSession):
        self.db = db

    @cached(ttl=300, cache=Cache.MEMORY)
    async def get_total_computers(self) -> Optional[int]:
        start_time = perf_counter()
        logger.debug("Запит кількості активних комп’ютерів")
        try:
            result = await self.db.execute(
                select(func.count(models.Computer.id)).filter(models.Computer.is_deleted == False)
            )
            count = result.scalar_one()
            logger.debug(f"Отримано кількість активних комп’ютерів: {count} за {perf_counter() - start_time:.4f}с")
            return count
        except Exception as e:
            logger.error(f"Помилка при отриманні кількості активних комп’ютерів: {str(e)}", exc_info=True)
            raise

    @cached(ttl=300, cache=Cache.MEMORY)
    async def get_os_names(self, limit: int = 100, offset: int = 0) -> List[str]:
        start_time = perf_counter()
        logger.debug(f"Запит унікальних назв ОС з limit={limit}, offset={offset}")
        try:
            result = await self.db.execute(
                select(models.OperatingSystem.name)
                .join(models.Computer, models.Computer.os_id == models.OperatingSystem.id)
                .filter(models.OperatingSystem.name != None)
                .distinct()
                .offset(offset)
                .limit(limit)
            )
            os_names = [row for row in result.scalars().all() if row]
            if not os_names:
                logger.warning("Не знайдено жодної операційної системи")
            else:
                logger.debug(f"Знайдено {len(os_names)} унікальних назв ОС за {perf_counter() - start_time:.4f}с")
            return sorted(os_names)
        except Exception as e:
            logger.error(f"Помилка при отриманні списку ОС: {str(e)}")
            raise

    @cached(ttl=300, cache=Cache.MEMORY)
    async def get_os_distribution(self) -> schemas.OsStats:
        start_time = perf_counter()
        logger.debug("Запит розподілу за версіями ОС")
        try:
            os_category = case(
                (
                    or_(
                        models.OperatingSystem.name.is_(None),
                        models.OperatingSystem.name == "",
                    ),
                    "Unknown",
                ),
                (
                    models.OperatingSystem.name.ilike("%server%"),
                    "Server",
                ),
                else_="Client",
            )
            result = await self.db.execute(
                select(
                    models.OperatingSystem.name,
                    models.OperatingSystem.version,
                    models.OperatingSystem.architecture,
                    os_category.label("category"),
                    func.count(models.Computer.id).label("count"),
                )
                .join(models.Computer, models.Computer.os_id == models.OperatingSystem.id)
                .group_by(
                    models.OperatingSystem.name,
                    models.OperatingSystem.version,
                    models.OperatingSystem.architecture,
                    os_category,
                )
            )
            client_os = []
            server_os = []
            total_count = 0

            for row in result.all():
                name, version, architecture, category, count = row
                os_info = schemas.OsInfo(
                    name=name or "Unknown",
                    version=version or "Unknown",
                    architecture=architecture or "Unknown",
                    count=count,
                )
                total_count += count
                if category == "Server":
                    server_os.append(os_info)
                else:
                    client_os.append(os_info)

            stats = schemas.OsStats(
                count=total_count,
                client_os=client_os,
                server_os=server_os,
            )
            logger.debug(f"Розподіл ОС: {total_count} комп’ютерів, {len(client_os)} клієнтських, {len(server_os)} серверних за {perf_counter() - start_time:.4f}с")
            return stats
        except Exception as e:
            logger.error(f"Помилка при отриманні розподілу ОС: {str(e)}")
            raise

    @cached(ttl=300, cache=Cache.MEMORY)
    async def get_low_disk_space_with_volumes(self, threshold_percent: float = 10.0) -> List[schemas.LowDiskSpaceInfo]:
        start_time = perf_counter()
        logger.debug(f"Запит дисків із вільним простором менше {threshold_percent}%")
        try:
            result = await self.db.execute(
                select(
                    models.Computer.hostname,
                    models.LogicalDisk.name,
                    models.LogicalDisk.free_space,
                    models.LogicalDisk.size
                )
                .join(models.Computer, models.Computer.id == models.LogicalDisk.computer_id)
                .filter(
                    and_(
                        models.Computer.is_deleted == False,
                        models.LogicalDisk.size > 0,
                        (models.LogicalDisk.free_space / models.LogicalDisk.size * 100) < threshold_percent
                    )
                )
            )
            low_disks = [
                schemas.LowDiskSpaceInfo(
                    hostname=row.hostname,
                    disk_name=row.name,
                    free_space=row.free_space,
                    total_space=row.size
                )
                for row in result.all()
            ]
            logger.debug(f"Знайдено {len(low_disks)} дисків із низьким рівнем вільного простору за {perf_counter() - start_time:.4f}с")
            return low_disks
        except Exception as e:
            logger.error(f"Помилка при отриманні дисків із низьким рівнем вільного простору: {str(e)}")
            raise

    @cached(ttl=300, cache=Cache.MEMORY)
    async def get_software_distribution(self, limit: int = 100, offset: int = 0) -> List[schemas.SoftwareInfo]:
        start_time = perf_counter()
        logger.debug(f"Запит розподілу програмного забезпечення з limit={limit}, offset={offset}")
        try:
            result = await self.db.execute(
                select(
                    models.InstalledSoftware.name,
                    models.InstalledSoftware.version,
                    func.count(models.Computer.id).label("count")
                )
                .join(models.Computer, models.Computer.id == models.InstalledSoftware.computer_id)
                .filter(
                    and_(
                        models.Computer.is_deleted == False,
                        models.InstalledSoftware.name != None
                    )
                )
                .group_by(
                    models.InstalledSoftware.name,
                    models.InstalledSoftware.version
                )
                .offset(offset)
                .limit(limit)
            )
            software_list = [
                schemas.SoftwareInfo(
                    name=row.name or "Unknown",
                    version=row.version or "Unknown",
                    count=row.count
                )
                for row in result.all()
            ]
            if not software_list:
                logger.warning("Не знайдено жодного програмного забезпечення")
            else:
                logger.debug(f"Знайдено {len(software_list)} програм за {perf_counter() - start_time:.4f}с")
            return software_list
        except Exception as e:
            logger.error(f"Помилка при отриманні розподілу ПЗ: {str(e)}")
            raise

    @cached(ttl=300, cache=Cache.MEMORY)
    async def get_status_stats(self) -> List[schemas.StatusStats]:
        start_time = perf_counter()
        logger.debug("Запит статистики статусів сканування")
        try:
            result = await self.db.execute(
                select(
                    models.ScanTask.status,
                    func.count(models.ScanTask.id).label("count")
                )
                .group_by(models.ScanTask.status)
            )
            status_stats = [
                schemas.StatusStats(
                    status=row.status,
                    count=row.count
                )
                for row in result.all()
            ]
            logger.debug(f"Знайдено {len(status_stats)} статусів сканування за {perf_counter() - start_time:.4f}с")
            return status_stats
        except Exception as e:
            logger.error(f"Помилка при отриманні статистики статусів: {str(e)}")
            raise

    async def get_statistics(self, metrics: List[str]) -> schemas.DashboardStats:
        start_time = perf_counter()
        stats = schemas.DashboardStats(
            total_computers=None,
            os_stats=schemas.OsStats(count=0, client_os=[], server_os=[]),
            disk_stats=schemas.DiskStats(low_disk_space=[]),
            scan_stats=schemas.ScanStats(last_scan_time=None, status_stats=[]),
            component_changes=[],
        )

        async def fetch_total_and_last_scan():
            total_query = select(func.count(models.Computer.id)).filter(models.Computer.is_deleted == False)
            last_scan_query = select(models.ScanTask.updated_at).order_by(models.ScanTask.updated_at.desc())
            total_result, last_scan_result = await asyncio.gather(
                self.db.execute(total_query),
                self.db.execute(last_scan_query)
            )
            stats.total_computers = total_result.scalar_one()
            stats.scan_stats.last_scan_time = last_scan_result.scalars().first()

        async def fetch_component_changes():
            component_types = [
                (schemas.ComponentType.SOFTWARE, models.InstalledSoftware),
                (schemas.ComponentType.PHYSICAL_DISK, models.PhysicalDisk),
                (schemas.ComponentType.LOGICAL_DISK, models.LogicalDisk),
                (schemas.ComponentType.PROCESSOR, models.Processor),
                (schemas.ComponentType.VIDEO_CARD, models.VideoCard),
                (schemas.ComponentType.IP_ADDRESS, models.IPAddress),
                (schemas.ComponentType.MAC_ADDRESS, models.MACAddress),
            ]
            for component_type, model in component_types:
                count_query = select(func.count()).select_from(model).filter(
                    or_(model.detected_on.is_not(None), model.removed_on.is_not(None))
                )
                count_result = await self.db.execute(count_query)
                count = count_result.scalar() or 0
                stats.component_changes.append(
                    schemas.ComponentChangeStats(component_type=component_type, changes_count=count)
                )

        tasks = []
        if "total_computers" in metrics or "last_scan_time" in metrics:
            tasks.append(fetch_total_and_last_scan())
        if "os_distribution" in metrics:
            tasks.append(self.get_os_distribution())
        if "software_distribution" in metrics:
            tasks.append(self.get_software_distribution())
        if "low_disk_space_with_volumes" in metrics:
            tasks.append(self.get_low_disk_space_with_volumes())
        if "status_stats" in metrics:
            tasks.append(self.get_status_stats())
        if "component_changes" in metrics:
            tasks.append(fetch_component_changes())

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Помилка при виконанні завдання {metrics[i]}: {str(result)}")
            elif metrics[i] == "os_distribution":
                stats.os_stats = result
            elif metrics[i] == "software_distribution":
                stats.os_stats.software_distribution = result
            elif metrics[i] == "low_disk_space_with_volumes":
                stats.disk_stats.low_disk_space = result
            elif metrics[i] == "status_stats":
                stats.scan_stats.status_stats = result

        logger.debug(f"Статистика зібрана за {perf_counter() - start_time:.4f}с")
        return stats