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
from ..schemas import ComputerCreate, Role, Software, PhysicalDisk, LogicalDisk, CheckStatus, Computer, VideoCard, Processor, IPAddress, MACAddress
from ..data_collector import WinRMDataCollector
from app.utils.validators import validate_ip_address, validate_mac_address
from ..database import async_session_factory 
from ..decorators import log_function_call

logger = logging.getLogger(__name__)

class ComputerService:
    def __init__(self, db: AsyncSession):
        self.semaphore = asyncio.Semaphore(settings.scan_max_workers)
        self.computer_repo = ComputerRepository(db)

    # Конфігурація для обробки компонентів
    COMPONENT_CONFIG = {
        "ip_addresses": {
            "model": IPAddress,
            "unique_field": "address",
            "validate": lambda x: validate_ip_address(IPAddress, x, "IP address"),
            "fields": ["address"]
        },
        "mac_addresses": {
            "model": MACAddress,
            "unique_field": "address",
            "validate": lambda x: validate_mac_address(MACAddress, x, "MAC address"),
            "fields": ["address"]
        },
        "processors": {
            "model": Processor,
            "unique_field": "name",
            "validate": lambda x: x.get("name", "").strip() if isinstance(x, dict) else x,
            "fields": ["name", "number_of_cores", "number_of_logical_processors"]
        },
        "video_cards": {
            "model": VideoCard,
            "unique_field": "name",
            "validate": lambda x: x.get("name", "").strip() if isinstance(x, dict) else x,
            "fields": ["name", "driver_version"]
        },
        "physical_disks": {
            "model": PhysicalDisk,
            "unique_field": "serial",
            "validate": lambda x: x.get("serial", "").strip() if isinstance(x, dict) else x,
            "fields": ["model", "serial", "interface", "media_type"]
        },
        "logical_disks": {
            "model": LogicalDisk,
            "unique_field": "device_id",
            "validate": lambda x: x.get("device_id", "").strip() if isinstance(x, dict) else x,
            "fields": ["device_id", "volume_label", "total_space", "free_space", "parent_disk_serial"]
        },
        "software": {
            "model": Software,
            "unique_field": "name",
            "validate": lambda x: x.get("DisplayName", x.get("name", "")).strip() if isinstance(x, dict) else x,
            "fields": ["name", "version", "install_date"]
        },
        "roles": {
            "model": Role,
            "unique_field": "name",
            "validate": lambda x: x.strip() if isinstance(x, str) else x.get("name", "").strip(),
            "fields": ["name"]
        }
    }

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
                identifier = config["validate"](item)
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
        logger.info("Отримання хостів для сканування")
        if settings.test_hosts and settings.test_hosts.strip():
            hosts = [host.strip() for host in settings.test_hosts.split(",") if host.strip()]
            logger.info(f"Використовуються тестові хости: {hosts}")
            return hosts
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
        """Крок 1: Отримання даних з БД про хост і визначення режиму сканування."""
        db_computer = await self.computer_repo.get_computer_by_hostname(host)
        mode = self._determine_scan_mode(db_computer)
        logger.debug(f"Контекст сканування для {host}: режим={mode}", extra={"hostname": host, "mode": mode})
        return db_computer, mode

    @log_function_call
    async def _fetch_data_from_host(self, host: str, mode: str, last_updated: Optional[datetime]) -> Dict[str, Any]:
        """Крок 2: Виклик WinRMDataCollector для збору даних з хоста."""
        username, password = settings.ad_username, settings.ad_password
        if not username or not password:
            raise ValueError("Облікові дані WinRM не налаштовано")
        
        collector = WinRMDataCollector(hostname=host, username=username, password=password)
        return await collector.get_all_pc_info(mode=mode, last_updated=last_updated)

    @log_function_call
    async def _prepare_and_validate_data(self, raw_data: Dict[str, Any], hostname: str, mode: str) -> ComputerCreate:
        """Крок 3: Перетворення сирих даних у валідну Pydantic-схему ComputerCreate."""
        try:
            if not isinstance(raw_data, dict):
                raise TypeError(f"Очікувався словник, отримано: {type(raw_data)}")
            
            computer_data = {
                "hostname": hostname, "ip_addresses": [], "mac_addresses": [], "processors": [],
                "video_cards": [], "physical_disks": [], "logical_disks": [], "software": [],
                "roles": [], "os_name": "Unknown", "os_version": None, "ram": None,
                "motherboard": None, "last_boot": None, "is_virtual": False,
                "check_status": CheckStatus.success, "object_guid": None, "when_created": None,
                "when_changed": None, "enabled": None, "is_deleted": False,
                "ad_notes": None, "local_notes": None
            }

            successful_components = 0
            failed_components = 0

            for component_key in ["ip_addresses", "mac_addresses", "processors", "video_cards", "software", "roles"]:
                if component_key in raw_data and isinstance(raw_data.get(component_key), (list, dict)):
                    try:
                        computer_data[component_key] = await self.process_component_list(raw_data, hostname, component_key)
                        successful_components += 1
                    except Exception as e:
                        logger.warning(f"Помилка обробки {component_key}: {str(e)}", extra={"hostname": hostname, "component_key": component_key})
                        failed_components += 1
                        computer_data.setdefault("errors", []).append(f"Помилка {component_key}: {str(e)}")
                else:
                    logger.warning(f"Некоректні дані для {component_key}: {raw_data.get(component_key)}", extra={"hostname": hostname, "component_key": component_key})
                    failed_components += 1
                    computer_data.setdefault("errors", []).append(f"Некоректні дані для {component_key}")

            if "disks" in raw_data and isinstance(raw_data.get("disks"), dict):
                try:
                    computer_data["physical_disks"] = await self.process_component_list(raw_data["disks"], hostname, "physical_disks")
                    computer_data["logical_disks"] = await self.process_component_list(raw_data["disks"], hostname, "logical_disks")
                    successful_components += 1
                except Exception as e:
                    logger.warning(f"Помилка обробки disks: {str(e)}", extra={"hostname": hostname})
                    failed_components += 1
                    computer_data.setdefault("errors", []).append(f"Помилка disks: {str(e)}")
            
            scalar_fields = ["os_name", "os_version", "ram", "motherboard", "last_boot", "is_virtual", "object_guid", "when_created", "when_changed", "enabled", "is_deleted", "ad_notes", "local_notes"]
            for field in scalar_fields:
                if field in raw_data:
                    try:
                        value = raw_data[field]
                        if field in ["last_boot", "when_created", "when_changed"] and value:
                            computer_data[field] = datetime.fromisoformat(value)
                        elif field == "ram" and value:
                            computer_data[field] = int(value)
                        else:
                            computer_data[field] = value
                    except Exception as e:
                        logger.warning(f"Помилка обробки поля {field}: {str(e)}", extra={"hostname": hostname, "field": field})
                        failed_components += 1
                        computer_data.setdefault("errors", []).append(f"Помилка поля {field}: {str(e)}")

            if "check_status" in raw_data:
                computer_data["check_status"] = raw_data["check_status"]
            elif successful_components > 0 and failed_components > 0:
                computer_data["check_status"] = CheckStatus.partially_successful
            elif successful_components > 0:
                computer_data["check_status"] = CheckStatus.success
            else:
                computer_data["check_status"] = CheckStatus.failed

            logger.info("Дані підготовлено успішно", extra={"hostname": hostname})
            return ComputerCreate(**computer_data)
        except Exception as e:
            logger.error(f"Критична помилка підготовки даних: {str(e)}", extra={"hostname": hostname})
            raise

    @log_function_call
    async def _save_computer_data(self, computer_schema: ComputerCreate, mode: str) -> models.Computer:
        """Крок 4: Збереження даних про комп'ютер через репозиторій."""
        computer_data_for_upsert = computer_schema.model_dump(
            exclude_unset=True,
            exclude={'ip_addresses', 'mac_addresses', 'processors', 'video_cards', 'physical_disks', 'logical_disks', 'software', 'roles'}
        )
        
        db_computer = await self.computer_repo.get_or_create_computer(computer_schema.hostname, computer_data_for_upsert)
        
        related_entities_config = {
            "ip_addresses": (models.IPAddress, "address"),
            "mac_addresses": (models.MACAddress, "address"),
            "processors": (models.Processor, "name"),
            "video_cards": (models.VideoCard, "name"),
            "physical_disks": (models.PhysicalDisk, "serial"),
            "logical_disks": (models.LogicalDisk, "device_id"),
            "software": (models.Software, "name"),
            "roles": (models.Role, "name"),
        }

        for collection_name, (model_class, unique_field) in related_entities_config.items():
            await self.computer_repo.update_related_entities(
                db_computer, getattr(computer_schema, collection_name), model_class, unique_field, collection_name
            )

        await self.computer_repo.db.commit()
        await self.computer_repo.db.refresh(db_computer)
        return db_computer

    @log_function_call
    async def process_single_host(self, host: str, logger_adapter: logging.LoggerAdapter) -> bool:
        """Обробляє один хост із створенням нової сесії бази даних."""
        async with async_session_factory() as host_db:
            repo = ComputerRepository(host_db)
            service = ComputerService(host_db)
            return await service.process_single_host_inner(host, logger_adapter)

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

            computer_schema = await self._prepare_and_validate_data(raw_data, host, mode)
            await self._save_computer_data(computer_schema, mode)

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