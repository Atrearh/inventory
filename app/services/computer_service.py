# app/services/computer_service.py
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from ..schemas import ComputerCreate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..config import settings
from ..data_collector import WinRMDataCollector
from ..database import async_session_factory
from ..decorators import log_function_call
from ..mappers.component_mapper import map_to_components
from ..repositories.computer_repository import ComputerRepository
from ..repositories.component_repository import ComponentRepository
from ..repositories.software_repository import SoftwareRepository
from ..repositories.tasks_repository import TasksRepository
from ..services.encryption_service import get_encryption_service
from ..services.winrm_service import WinRMService

logger = logging.getLogger(__name__)


class ComputerService:
    def __init__(self, db: AsyncSession):
        self.semaphore = asyncio.Semaphore(settings.scan_max_workers)
        self.db = db
        self.computer_repo = ComputerRepository(db)
        self.component_repo = ComponentRepository(db)
        self.software_repo = SoftwareRepository(db)
        self.tasks_repo = TasksRepository(db)

    async def get_hosts_to_scan(self) -> List[str]:
        """Отримання хостів для сканування."""
        return await self.computer_repo.get_all_hosts()

    @log_function_call
    async def update_scan_task_status(
        self,
        task_id: str,
        status: models.ScanStatus,
        scanned_hosts: int = 0,
        successful_hosts: int = 0,
        error: Optional[str] = None,
    ):
        """Оновлює статус задачі сканування в базі даних."""
        await self.tasks_repo.update_scan_task_status(task_id, status, scanned_hosts, successful_hosts, error)

    def _determine_scan_mode(self, db_computer: Optional[models.Computer]) -> str:
        """Визначає, чи потрібне повне сканування."""
        if not db_computer or not db_computer.last_full_scan:
            return "Full"
        if db_computer.last_full_scan < datetime.utcnow() - timedelta(days=30):
            return "Full"
        return "Changes"

    @log_function_call
    async def _get_scan_context(self, host: str) -> Tuple[Optional[models.Computer], str]:
        """Визначає контекст сканування: режим та наявність комп'ютера в БД."""
        computers, _ = await self.computer_repo.get_computer(hostname=host)
        db_computer = computers[0] if computers else None
        mode = self._determine_scan_mode(db_computer)
        logger.debug(
            f"Контекст сканування для {host}: режим {mode}",
            extra={"hostname": host, "mode": mode},
        )
        return db_computer, mode

    @log_function_call
    async def _fetch_data_from_host(
        self,
        host: str,
        mode: str,
        last_updated: Optional[datetime],
        winrm_service: WinRMService,
    ) -> Dict[str, Any]:
        """Викликає WinRMDataCollector для збору даних з хоста."""
        encryption_service = get_encryption_service()
        collector = WinRMDataCollector(
            hostname=host,
            db=self.db,
            encryption_service=encryption_service,
        )
        return await collector.collect_pc_info(mode=mode, last_updated=last_updated, winrm_service=winrm_service)

    @log_function_call
    async def _prepare_and_save_data(self, raw_data: Dict[str, Any], hostname: str, mode: str):
        """
        Підготовка та збереження даних, отриманих із хоста, включаючи ОС, компоненти та ПЗ.
        """
        logger.debug(
            f"Підготовка та збереження даних для хоста {hostname}",
            extra={"hostname": hostname},
        )
        try:
            # Оновлення або створення основного об'єкта Computer
            computer_data = {
                "hostname": hostname,
                "ram": raw_data.get("ram"),
                "motherboard": raw_data.get("motherboard"),
                "last_boot": raw_data.get("last_boot"),
                "check_status": raw_data.get("check_status", "failed"),
            }
            computer_id = await self.computer_repo.async_upsert_computer(computer=ComputerCreate(**computer_data), hostname=hostname, mode=mode)
            computers, _ = await self.computer_repo.get_computer(id=computer_id)
            db_computer = computers[0]

            # --- Обробка Operating System ---
            os_name = raw_data.get("os_name")
            if os_name:
                os_version = raw_data.get("os_version")
                # Пошук або створення запису ОС
                os_result = await self.db.execute(
                    select(models.OperatingSystem).where(
                        models.OperatingSystem.name == os_name,
                        models.OperatingSystem.version == os_version,
                    )
                )
                os_entry = os_result.scalar_one_or_none()

                if not os_entry:
                    os_entry = models.OperatingSystem(name=os_name, version=os_version)
                    self.db.add(os_entry)
                    await self.db.flush()  # Отримання нового ID

                # Прив’язка ОС до комп'ютера
                await self.computer_repo.update_computer(db_computer.id, {"os_id": os_entry.id})

            # --- Обробка компонентів ---
            disks_data = raw_data.get("disks", {})
            await self.component_repo.update_related_entities(
                db_computer,
                map_to_components(models.IPAddress, raw_data.get("ip_addresses", []), hostname),
                models.IPAddress,
                "address",
                "ip_addresses",
            )
            await self.component_repo.update_related_entities(
                db_computer,
                map_to_components(models.MACAddress, raw_data.get("mac_addresses", []), hostname),
                models.MACAddress,
                "address",
                "mac_addresses",
            )
            await self.component_repo.update_related_entities(
                db_computer,
                map_to_components(models.Processor, raw_data.get("processors", []), hostname),
                models.Processor,
                "name",
                "processors",
            )
            await self.component_repo.update_related_entities(
                db_computer,
                map_to_components(models.VideoCard, raw_data.get("video_cards", []), hostname),
                models.VideoCard,
                "name",
                "video_cards",
            )
            await self.component_repo.update_related_entities(
                db_computer,
                map_to_components(models.PhysicalDisk, disks_data.get("physical_disks", []), hostname),
                models.PhysicalDisk,
                "serial",
                "physical_disks",
            )
            await self.component_repo.update_related_entities(
                db_computer,
                map_to_components(models.LogicalDisk, disks_data.get("logical_disks", []), hostname),
                models.LogicalDisk,
                "device_id",
                "logical_disks",
                custom_logic=self.component_repo._create_logical_disk,
            )
            await self.component_repo.update_related_entities(
                db_computer,
                map_to_components(models.Role, raw_data.get("roles", []), hostname),
                models.Role,
                "name",
                "roles",
            )

            # --- Обробка програмного забезпечення ---
            software_list = raw_data.get("software", [])
            if software_list is not None:
                await self.software_repo.update_installed_software(db_computer, software_list)

            await self.db.commit()
            logger.debug(f"Дані для {hostname} успішно збережено", extra={"hostname": hostname})

        except Exception as e:
            logger.error(
                f"Помилка валідації або збереження даних для {hostname}: {str(e)}",
                extra={"hostname": hostname},
                exc_info=True,
            )
            await self.db.rollback()
            raise

    @log_function_call
    async def process_single_host(self, host: str, winrm_service: WinRMService, logger_adapter: logging.LoggerAdapter) -> bool:
        try:
            db_computer, mode = await self._get_scan_context(host)
            last_updated = db_computer.last_updated if db_computer else None

            raw_data = await self._fetch_data_from_host(host, mode, last_updated, winrm_service)

            if not raw_data or raw_data.get("check_status") in ["failed", "unreachable"]:
                logger_adapter.warning(
                    f"Збір даних з хоста {host} не вдався.",
                    extra={"details": raw_data.get("errors")},
                )
                await self.computer_repo.async_update_computer_check_status(host, raw_data.get("check_status", "failed"))
                await self.computer_repo.db.commit()
                return False

            await self._prepare_and_save_data(raw_data, host, mode)
            logger_adapter.info(f"Хост {host} успішно оброблено.")
            return True
        except Exception as e:
            logger_adapter.error(f"Критична помилка при обробці хоста {host}: {e}", exc_info=True)
            await self.computer_repo.db.rollback()
            await self.computer_repo.async_update_computer_check_status(host, "failed")
            await self.computer_repo.db.commit()
            return False

    @log_function_call
    async def create_scan_task(self, task_id: str) -> Optional[models.ScanTask]:
        """Створює нову задачу сканування."""
        return await self.tasks_repo.create_scan_task(task_id)

    @log_function_call
    async def run_scan_task(
        self,
        task_id: str,
        logger_adapter: logging.LoggerAdapter,
        hostname: Optional[str] = None,
        winrm_service: WinRMService = None,
    ):
        hosts = []
        successful = 0
        try:
            task = await self.tasks_repo.db.get(models.ScanTask, task_id)
            if not task:
                raise ValueError(f"Задача {task_id} не знайдена")
            if task.status != models.ScanStatus.running:
                await self.update_scan_task_status(
                    task_id=task_id,
                    status=models.ScanStatus.failed,
                    scanned_hosts=0,
                    successful_hosts=0,
                    error=f"Задача має некоректний статус: {task.status}",
                )
                return

            if hostname:
                hosts = [hostname]
                all_hosts = await self.get_hosts_to_scan()
                if hostname not in all_hosts:
                    await self.update_scan_task_status(
                        task_id=task_id,
                        status=models.ScanStatus.failed,
                        scanned_hosts=0,
                        successful_hosts=0,
                        error=f"Хост {hostname} не знайдено",
                    )
                    return
            else:
                hosts = await self.get_hosts_to_scan()

            if not hosts:
                await self.update_scan_task_status(
                    task_id=task_id,
                    status=models.ScanStatus.completed,
                    scanned_hosts=0,
                    successful_hosts=0,
                )
                return

            async def process_host_with_semaphore(host: str):
                nonlocal successful
                async with self.semaphore:
                    result = await self.process_single_host(host, winrm_service, logger_adapter)
                    if result:
                        successful += 1

            await asyncio.gather(
                *[process_host_with_semaphore(host) for host in hosts],
                return_exceptions=True,
            )
            await self.update_scan_task_status(
                task_id=task_id,
                status=models.ScanStatus.completed,
                scanned_hosts=len(hosts),
                successful_hosts=successful,
            )
        except Exception as e:
            await self.tasks_repo.db.rollback()
            await self.update_scan_task_status(
                task_id=task_id,
                status=models.ScanStatus.failed,
                scanned_hosts=len(hosts),
                successful_hosts=successful,
                error=str(e),
            )
            raise
