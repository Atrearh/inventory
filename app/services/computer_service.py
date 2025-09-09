import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from ..settings import settings
from ..repositories.computer_repository import ComputerRepository
from .. import models
from ..schemas import ComputerCreate
from ..data_collector import WinRMDataCollector
from ..database import async_session_factory
from ..decorators import log_function_call
from ..services.encryption_service import get_encryption_service
from ..schemas import ComputerCreate, Role, Software, PhysicalDisk, LogicalDisk, VideoCard, Processor, IPAddress, MACAddress
from ..services.winrm_service import WinRMService


logger = logging.getLogger(__name__)

class ComputerService:
    def __init__(self, db: AsyncSession):
        self.semaphore = asyncio.Semaphore(settings.scan_max_workers)
        self.db = db
        self.computer_repo = ComputerRepository(db)

    async def get_hosts_to_scan(self) -> List[str]:
        """Отримання хостів для сканування"""
        return await self.computer_repo.get_all_hosts()

    @log_function_call
    async def update_scan_task_status(self, task_id: str, status: models.ScanStatus, scanned_hosts: int = 0, successful_hosts: int = 0, error: Optional[str] = None):
        """Оновлює статус задачі сканування в базі даних."""
        await self.computer_repo.update_scan_task_status(task_id, status, scanned_hosts, successful_hosts, error)

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
        db_computer = await self.computer_repo.get_computer_by_hostname(self.computer_repo.db, host)
        mode = self._determine_scan_mode(db_computer)
        logger.debug(f"Контекст сканування для {host}: режим {mode}", extra={"hostname": host, "mode": mode})
        return db_computer, mode

    @log_function_call
    async def _fetch_data_from_host(self, host: str, mode: str, last_updated: Optional[datetime], winrm_service: WinRMService) -> Dict[str, Any]:
        """Викликає WinRMDataCollector для збору даних з хоста."""
        encryption_service = get_encryption_service()
        collector = WinRMDataCollector(hostname=host, db=self.computer_repo.db, encryption_service=encryption_service)
        return await collector.collect_pc_info(mode=mode, last_updated=last_updated, winrm_service=winrm_service)

    @log_function_call
    async def _prepare_and_validate_data(self, raw_data: Dict[str, Any], hostname: str) -> ComputerCreate:
        """Підготовка та валідація даних для збереження."""
        logger.debug(f"Підготовка даних для хоста {hostname}", extra={"hostname": hostname})
        try:
            # Виклик методів from_raw_data для кожної схеми компонентів
            ip_addresses = IPAddress.from_raw_data(raw_data.get("ip_addresses", []), hostname)
            mac_addresses = MACAddress.from_raw_data(raw_data.get("mac_addresses", []), hostname)
            processors = Processor.from_raw_data(raw_data.get("processors", []), hostname)
            video_cards = VideoCard.from_raw_data(raw_data.get("video_cards", []), hostname)
            software = Software.from_raw_data(raw_data.get("software", []), hostname)
            roles = Role.from_raw_data(raw_data.get("roles", []), hostname)

            disks_data = raw_data.get("disks", {})
            physical_disks = PhysicalDisk.from_raw_data(disks_data.get("physical_disks", []), hostname)
            logical_disks = LogicalDisk.from_raw_data(disks_data.get("logical_disks", []), hostname)

            # Створення Pydantic-схеми комп'ютера
            computer_schema = ComputerCreate(
                hostname=hostname,
                os_name=raw_data.get("os_name", "Unknown"),
                os_version=raw_data.get("os_version"),
                ram=raw_data.get("ram"),
                motherboard=raw_data.get("motherboard"),
                last_boot=raw_data.get("last_boot"),
                is_virtual=raw_data.get("is_virtual", False),
                check_status=raw_data.get("check_status", "failed"),
                ip_addresses=ip_addresses,
                mac_addresses=mac_addresses,
                processors=processors,
                video_cards=video_cards,
                software=software,
                roles=roles,
                physical_disks=physical_disks,
                logical_disks=logical_disks
            )
            logger.debug(f"Дані для {hostname} успішно валідовано", extra={"hostname": hostname})
            return computer_schema
        except Exception as e:
            logger.error(f"Помилка валідації даних для {hostname}: {str(e)}", extra={"hostname": hostname})
            raise

    @log_function_call
    async def _save_computer_data(self, computer_schema: ComputerCreate) -> None:
        """Зберігає дані комп'ютера в базі даних з попереднім завантаженням пов’язаних сутностей."""
        try:
            db_computer_id = await self.computer_repo.async_upsert_computer(
                computer_schema, computer_schema.hostname
            )
            # Попереднє завантаження всіх пов’язаних сутностей
            result = await self.db.execute(
                select(models.Computer)
                .where(models.Computer.id == db_computer_id)
                .options(
                    selectinload(models.Computer.ip_addresses),
                    selectinload(models.Computer.mac_addresses),
                    selectinload(models.Computer.processors),
                    selectinload(models.Computer.video_cards),
                    selectinload(models.Computer.software),
                    selectinload(models.Computer.roles),
                    selectinload(models.Computer.physical_disks).selectinload(models.PhysicalDisk.logical_disks),
                    selectinload(models.Computer.logical_disks),
                )
            )
            db_computer = result.scalars().first()
            
            if not db_computer:
                logger.error(f"Не вдалося знайти або створити комп'ютер: {computer_schema.hostname}")
                raise Exception(f"Failed to upsert computer {computer_schema.hostname}")

            # Явне оновлення об’єкта для забезпечення ініціалізації всіх атрибутів
            await self.db.refresh(db_computer, ["hostname", "ip_addresses", "mac_addresses", "processors", "video_cards", "software", "roles", "physical_disks", "logical_disks"])

            await self.computer_repo.update_computer_entities(db_computer, computer_schema)
            logger.info(f"Дані комп'ютера {computer_schema.hostname} збережено успішно", extra={"hostname": computer_schema.hostname})
        except Exception as e:
            logger.error(f"Помилка збереження даних комп'ютера {computer_schema.hostname}: {str(e)}")
            await self.db.rollback()
            raise

    @log_function_call
    async def process_single_host(self, host: str, logger_adapter: logging.LoggerAdapter) -> bool:
        """Обробляє один хост із створенням нової сесії бази даних."""
        async with async_session_factory() as host_db:
            service_for_host = ComputerService(host_db)
            return await service_for_host.process_single_host_inner(host, logger_adapter)
        
    @log_function_call
    async def process_single_host_inner(self, host: str, logger_adapter: logging.LoggerAdapter) -> bool:
        """Обробляє один хост, розбиваючи процес на логічні кроки."""
        try:
            # Створюємо залежності вручну, а не через функцію-провайдер
            encryption_service = get_encryption_service()
            winrm_service = WinRMService(encryption_service, self.db)
            await winrm_service.initialize() # Важливо викликати асинхронну ініціалізацію

            db_computer, mode = await self._get_scan_context(host)
            last_updated = db_computer.last_updated if db_computer else None

            raw_data = await self._fetch_data_from_host(host, mode, last_updated, winrm_service)

            if raw_data.get("check_status") in ("unreachable", "failed"):
                logger_adapter.warning(f"Збір даних з хоста {host} не вдався.", extra={"details": raw_data.get("errors")})
                await self.computer_repo.async_update_computer_check_status(host, raw_data.get("check_status"))
                await self.computer_repo.db.commit()
                return False

            computer_schema = await self._prepare_and_validate_data(raw_data, host)
            await self._save_computer_data(computer_schema)

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
        try:
            result = await self.computer_repo.db.execute(
                select(models.ScanTask).filter(models.ScanTask.id == task_id)
            )
            existing_task = result.scalars().first()
            if existing_task:
                if existing_task.status in [models.ScanStatus.completed, models.ScanStatus.failed]:
                    logger.warning(f"Задача {task_id} існує зі статусом {existing_task.status}, видаляємо", extra={"task_id": task_id})
                    await self.computer_repo.db.delete(existing_task)
                    await self.computer_repo.db.flush()
                else:
                    logger.error(f"Задача {task_id} вже виконується зі статусом {existing_task.status}", extra={"task_id": task_id})
                    raise ValueError(f"Задача {task_id} вже виконується")
            
            db_task = models.ScanTask(
                id=task_id,
                status=models.ScanStatus.running,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            self.computer_repo.db.add(db_task)
            await self.computer_repo.db.flush()
            await self.computer_repo.db.refresh(db_task)
            return db_task
        except Exception as e:
            logger.error(f"Помилка створення задачі: {str(e)}", extra={"task_id": task_id})
            await self.computer_repo.db.rollback()
            raise

    @log_function_call
    async def run_scan_task(self, task_id: str, logger_adapter: logging.LoggerAdapter, hostname: Optional[str] = None):
        """Запускає задачу сканування для одного або всіх хостів."""
        hosts = []
        successful = 0
        try:
            result = await self.computer_repo.db.execute(
                select(models.ScanTask).filter(models.ScanTask.id == task_id)
            )
            task = result.scalars().first()
            if not task:
                raise ValueError(f"Задача {task_id} не знайдена")
            if task.status != models.ScanStatus.running:
                await self.update_scan_task_status(
                    task_id=task_id,
                    status=models.ScanStatus.failed,
                    scanned_hosts=0,
                    successful_hosts=0,
                    error=f"Задача має некоректний статус: {task.status}"
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
                        error=f"Хост {hostname} не знайдено"
                    )
                    return
            else:
                hosts = await self.get_hosts_to_scan()

            if not hosts:
                await self.update_scan_task_status(
                    task_id=task_id, 
                    status=models.ScanStatus.completed, 
                    scanned_hosts=0, 
                    successful_hosts=0
                )
                return

            async def process_host_with_semaphore(host: str):
                nonlocal successful
                async with self.semaphore:
                    result = await self.process_single_host(host, logger_adapter)
                    if result:
                        successful += 1

            await asyncio.gather(*[process_host_with_semaphore(host) for host in hosts], return_exceptions=True)
            await self.update_scan_task_status(
                task_id=task_id, 
                status=models.ScanStatus.completed, 
                scanned_hosts=len(hosts), 
                successful_hosts=successful
            )
        except Exception as e:
            await self.computer_repo.db.rollback()
            await self.update_scan_task_status(
                task_id=task_id,
                status=models.ScanStatus.failed,
                scanned_hosts=len(hosts),
                successful_hosts=successful,
                error=str(e)
            )
            raise