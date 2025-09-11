# app/services/computer_service.py
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..config import settings
from ..repositories.computer_repository import ComputerRepository
from .. import models
from ..data_collector import WinRMDataCollector
from ..database import async_session_factory
from ..decorators import log_function_call
from ..services.encryption_service import get_encryption_service
from ..services.winrm_service import WinRMService
from ..mappers.component_mapper import map_to_components

logger = logging.getLogger(__name__)

class ComputerService:
    def __init__(self, db: AsyncSession):
        self.semaphore = asyncio.Semaphore(settings.scan_max_workers)
        self.db = db
        self.computer_repo = ComputerRepository(db)

    async def get_hosts_to_scan(self) -> List[str]:
        """Отримання хостів для сканування."""
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
    async def _prepare_and_save_data(self, raw_data: Dict[str, Any], hostname: str, mode: str):
        """
        Готує та зберігає дані, отримані з хоста, напряму працюючи з SQLModel.
        """
        logger.debug(f"Підготовка та збереження даних для хоста {hostname}", extra={"hostname": hostname})
        try:
            # Отримуємо або створюємо основний об'єкт Computer
            computer_data = {
                "os_name": raw_data.get("os_name", "Unknown"),
                "os_version": raw_data.get("os_version"),
                "ram": raw_data.get("ram"),
                "motherboard": raw_data.get("motherboard"),
                "last_boot": raw_data.get("last_boot"),
                "check_status": raw_data.get("check_status", "failed"),
            }
            # Цей виклик тепер повертає комп'ютер з усіма завантаженими зв'язками
            db_computer = await self.computer_repo.get_or_create_computer(computer_data, hostname)
            
            # Встановлюємо дати сканування
            db_computer.last_updated = datetime.utcnow()
            if mode == "Full":
                db_computer.last_full_scan = datetime.utcnow()

            # Мапимо та оновлюємо пов'язані сутності
            disks_data = raw_data.get("disks", {})
            
            # Ця частина тепер буде працювати без помилки, бо `db_computer` має завантажені зв'язки
            await self.computer_repo.update_related_entities(db_computer, map_to_components(models.IPAddress, raw_data.get("ip_addresses", []), hostname), models.IPAddress, "address", "ip_addresses")
            await self.computer_repo.update_related_entities(db_computer, map_to_components(models.MACAddress, raw_data.get("mac_addresses", []), hostname), models.MACAddress, "address", "mac_addresses")
            await self.computer_repo.update_related_entities(db_computer, map_to_components(models.Processor, raw_data.get("processors", []), hostname), models.Processor, "name", "processors")
            await self.computer_repo.update_related_entities(db_computer, map_to_components(models.VideoCard, raw_data.get("video_cards", []), hostname), models.VideoCard, "name", "video_cards")
            await self.computer_repo.update_related_entities(db_computer, map_to_components(models.PhysicalDisk, disks_data.get("physical_disks", []), hostname), models.PhysicalDisk, "serial", "physical_disks")
            await self.computer_repo.update_related_entities(db_computer, map_to_components(models.LogicalDisk, disks_data.get("logical_disks", []), hostname), models.LogicalDisk, "device_id", "logical_disks", custom_logic=self.computer_repo._create_logical_disk)
            await self.computer_repo.update_related_entities(db_computer, map_to_components(models.Software, raw_data.get("software", []), hostname), models.Software, ("name", "version"), "software")
            await self.computer_repo.update_related_entities(db_computer, map_to_components(models.Role, raw_data.get("roles", []), hostname), models.Role, "name", "roles")
            
            await self.db.commit()
            logger.debug(f"Дані для {hostname} успішно збережено", extra={"hostname": hostname})

        except Exception as e:
            logger.error(f"Помилка валідації або збереження даних для {hostname}: {str(e)}", extra={"hostname": hostname})
            await self.db.rollback()
            raise


    @log_function_call
    async def process_single_host(self, host: str, logger_adapter: logging.LoggerAdapter) -> bool:
        """Обробка одного хоста."""
        try:
            db_computer, mode = await self._get_scan_context(host)
            last_updated = db_computer.last_updated if db_computer else None

            async with async_session_factory() as session:
                encryption_service = get_encryption_service()
                winrm_service = WinRMService(encryption_service=encryption_service, db=session)
                await winrm_service.initialize()
                
                raw_data = await self._fetch_data_from_host(host, mode, last_updated, winrm_service)
                
                if not raw_data or raw_data.get("check_status") in ["failed", "unreachable"]:
                    logger_adapter.warning(f"Збір даних з хоста {host} не вдався.", extra={"details": raw_data.get("errors")})
                    await self.computer_repo.async_update_computer_check_status(host, raw_data.get("check_status", "failed"))
                    await self.computer_repo.db.commit()
                    return False

                # Викликаємо оновлену функцію для підготовки та збереження
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