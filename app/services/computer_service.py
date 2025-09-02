import logging
import asyncio
from hashlib import md5
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..settings import settings
from ..repositories.computer_repository import ComputerRepository
from .. import models
from ..schemas import ComputerCreate
from ..data_collector import WinRMDataCollector
from ..database import async_session_factory
from ..decorators import log_function_call
from ..services.encryption_service import get_encryption_service
from ..services.winrm_service import WinRMService
from ..main import get_winrm_service
from fastapi import Depends 

logger = logging.getLogger(__name__)

class ComputerService:
    def __init__(self, db: AsyncSession):
        self.semaphore = asyncio.Semaphore(settings.scan_max_workers)
        self.db = db
        self.computer_repo = ComputerRepository(db)

    async def process_component_list(self, raw_data: Dict[str, Any], hostname: str, component_key: str) -> List[Any]:
        config = self.COMPONENT_CONFIG.get(component_key)
        if not config:
            logger.warning("Немає конфігурації для компонента", extra={"component_key": component_key, "hostname": hostname})
            return []

        result = []
        seen_identifiers = set()
        component_data_list = raw_data.get(component_key, [])
        if not isinstance(component_data_list, list):
            component_data_list = [component_data_list] if component_data_list else []

        logger.debug(f"Обробка {component_key}: {len(component_data_list)} елементів", extra={"hostname": hostname, "component_key": component_key})

        for item in component_data_list:
            if not isinstance(item, (dict, str)):
                logger.warning(f"Пропущено некоректний елемент: {item}", extra={"component_key": component_key, "hostname": hostname})
                continue
            try:
                identifier_source = item if isinstance(item, str) else item.get(config["unique_field"])
                identifier = config["validate"](identifier_source)
                
                if not identifier or identifier in seen_identifiers:
                    continue
                seen_identifiers.add(identifier)

                if component_key in ["ip_addresses", "mac_addresses"] and isinstance(item, str):
                    component_data = {"address": item}
                elif component_key == "roles" and isinstance(item, str):
                    component_data = {"name": item}
                else:
                    component_data = {field: item.get(field, None) for field in config["fields"]}
                    if component_key == "software":
                        component_data["name"] = item.get("DisplayName", item.get("name", ""))
                    if component_key == "physical_disks" and not component_data.get("serial"):
                        model = item.get("model", "")
                        component_data["serial"] = md5(f"{model}_{item.get('size', '')}_{hostname}".encode()).hexdigest()[:100]
                    if component_key == "logical_disks" and component_data.get("volume_label") == "":
                        component_data["volume_label"] = None

                result.append(config["model"](**component_data))
            except Exception as e:
                logger.warning(f"Помилка валідації: {str(e)}", extra={"data": item, "component_key": component_key, "hostname": hostname})
                continue
        return result

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
    async def _fetch_data_from_host(self, host: str, mode: str, last_updated: Optional[datetime], winrm_service: WinRMService = Depends(get_winrm_service)) -> Dict[str, Any]:
        """Викликає WinRMDataCollector для збору даних з хоста."""
        encryption_service = get_encryption_service()
        collector = WinRMDataCollector(hostname=host, db=self.computer_repo.db, encryption_service=encryption_service, winrm_service=winrm_service)
        return await collector.collect_pc_info(mode=mode, last_updated=last_updated)

    @log_function_call
    async def _prepare_and_validate_data(self, raw_data: Dict[str, Any], hostname: str) -> ComputerCreate:
        """Підготовка та валідація даних для збереження."""
        logger.debug(f"Підготовка даних для хоста {hostname}", extra={"hostname": hostname})
        try:
            ip_addresses = await self.process_component_list(raw_data, hostname, "ip_addresses")
            mac_addresses = await self.process_component_list(raw_data, hostname, "mac_addresses")
            processors = await self.process_component_list(raw_data, hostname, "processors")
            video_cards = await self.process_component_list(raw_data, hostname, "video_cards")
            software = await self.process_component_list(raw_data, hostname, "software")
            roles = await self.process_component_list(raw_data, hostname, "roles")

            disks_data = raw_data.get("disks", {})
            physical_disks = await self.process_component_list(disks_data, hostname, "physical_disks")
            logical_disks = await self.process_component_list(disks_data, hostname, "logical_disks")

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
        """Зберігає дані комп'ютера в базі даних."""
        try:
            db_computer_id = await self.computer_repo.async_upsert_computer(
                computer_schema, computer_schema.hostname
            )
            result = await self.db.execute(
                select(models.Computer).where(models.Computer.id == db_computer_id)
            )
            db_computer = result.scalars().first()
            
            if not db_computer:
                logger.error(f"Не вдалося знайти або створити комп'ютер: {computer_schema.hostname}")
                raise Exception(f"Failed to upsert computer {computer_schema.hostname}")

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
            db_computer, mode = await self._get_scan_context(host)
            last_updated = db_computer.last_updated if db_computer else None

            raw_data = await self._fetch_data_from_host(host, mode, last_updated)

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