import logging
import asyncio
from hashlib import md5
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from ..settings import settings
from ..repositories.computer_repository import ComputerRepository
from .. import models
from ..schemas import ComputerCreate, Role, Software, PhysicalDisk, LogicalDisk, CheckStatus, Computer, VideoCard, Processor, IPAddress, MACAddress
from ..data_collector import WinRMDataCollector
from ..utils import validate_ip_address, validate_mac_address
from ..database import async_session_factory 

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
 
    async def process_component_list(self, comp_data: Dict[str, Any], hostname: str, component_key: str) -> List[Any]:
        """Універсальна функція для обробки списків компонентів."""
        config = self.COMPONENT_CONFIG.get(component_key)
        if not config:
            logger.warning("Немає конфігурації для компонента", extra={"component_key": component_key, "hostname": hostname})
            return []

        result = []
        seen_identifiers = set()
        raw_data = comp_data.get(component_key, [])
        if not isinstance(raw_data, list):
            raw_data = [raw_data] if raw_data else []

        logger.debug(f"Обробка {component_key}: {len(raw_data)} елементів", extra={"hostname": hostname, "component_key": component_key})

        for item in raw_data:
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
                    logger.debug(f"Обробка {component_key}: {component_data}", extra={"hostname": hostname, "component_key": component_key})
                elif component_key == "roles" and isinstance(item, str):
                    component_data = {"name": item}
                    logger.debug(f"Обробка ролі: {component_data}", extra={"hostname": hostname, "component_key": component_key})
                else:
                    component_data = {field: item.get(field, None) for field in config["fields"]}
                    if component_key == "software":
                        component_data["name"] = item.get("DisplayName", item.get("name", ""))
                        logger.debug(f"Обробка елемента ПЗ: {component_data}", extra={"hostname": hostname, "component_key": component_key})
                    if component_key == "physical_disks" and not component_data.get("serial"):
                        model = item.get("model", "")
                        component_data["serial"] = md5(f"{model}_{item.get('size', '')}_{hostname}".encode()).hexdigest()[:100]
                        logger.debug(f"Сгенерирован серийный номер для диска: {component_data['serial']}", extra={"hostname": hostname})
                    if component_key == "logical_disks" and component_data.get("volume_label") == "":
                        component_data["volume_label"] = None  # Перетворюємо порожній рядок на None
                        logger.debug(f"Перетворено порожній volume_label на None: {component_data}", extra={"hostname": hostname, "component_key": component_key})

                result.append(config["model"](**component_data))
            except Exception as e:
                logger.warning(f"Помилка валідації: {str(e)}", extra={"data": item, "component_key": component_key, "hostname": hostname})
                continue

        return result

    async def prepare_computer_data_for_db(self, comp_data: Dict[str, Any], hostname: str, mode: str = "Full") -> ComputerCreate:
        """Підготовка даних для збереження в базі."""
        logger.debug("Підготовка даних", extra={"hostname": hostname})
        try:
            if not isinstance(comp_data, dict):
                logger.error(f"Очікувався словник, отримано: {type(comp_data)}", extra={"hostname": hostname, "comp_data": str(comp_data)})
                raise ValueError(f"Некоректний тип вхідних даних: {type(comp_data)}, очікувався словник")

            computer_data = {
                "hostname": hostname,
                "ip_addresses": [],
                "mac_addresses": [],
                "processors": [],
                "video_cards": [],
                "physical_disks": [],
                "logical_disks": [],
                "software": [],
                "roles": [],
                "os_name": "Unknown",
                "os_version": None,
                "ram": None,
                "motherboard": None,
                "last_boot": None,
                "is_virtual": False,
                "check_status": CheckStatus.success,
                "object_guid": None,
                "when_created": None,
                "when_changed": None,
                "enabled": None,
                "is_deleted": False,
                "ad_notes": None,
                "local_notes": None
            }

            successful_components = 0
            failed_components = 0

            # Обробка компонентів із перевіркою типу
            for component_key in ["ip_addresses", "mac_addresses", "processors", "video_cards", "software", "roles"]:
                if component_key in comp_data and isinstance(comp_data[component_key], (list, dict)):
                    try:
                        computer_data[component_key] = await self.process_component_list(comp_data, hostname, component_key)
                        successful_components += 1
                    except Exception as e:
                        logger.warning(f"Помилка обробки {component_key}: {str(e)}", extra={"hostname": hostname, "component_key": component_key})
                        failed_components += 1
                        computer_data["errors"] = computer_data.get("errors", []) + [f"Помилка {component_key}: {str(e)}"]
                else:
                    logger.warning(f"Некоректні дані для {component_key}: {comp_data.get(component_key)}", extra={"hostname": hostname, "component_key": component_key})
                    failed_components += 1
                    computer_data["errors"] = computer_data.get("errors", []) + [f"Некоректні дані для {component_key}: {comp_data.get(component_key)}"]

            # Обробка дисків
            if "disks" in comp_data and isinstance(comp_data["disks"], dict):
                try:
                    computer_data["physical_disks"] = await self.process_component_list(comp_data["disks"], hostname, "physical_disks")
                    computer_data["logical_disks"] = await self.process_component_list(comp_data["disks"], hostname, "logical_disks")
                    successful_components += 1
                except Exception as e:
                    logger.warning(f"Помилка обробки disks: {str(e)}", extra={"hostname": hostname})
                    failed_components += 1
                    computer_data["errors"] = computer_data.get("errors", []) + [f"Помилка disks: {str(e)}"]
            else:
                logger.warning(f"Некоректні дані для disks: {comp_data.get('disks')}", extra={"hostname": hostname})
                failed_components += 1
                computer_data["errors"] = computer_data.get("errors", []) + [f"Некоректні дані для disks: {comp_data.get('disks')}"]

            # Обробка скалярних полів
            scalar_fields = ["os_name", "os_version", "ram", "motherboard", "last_boot", "is_virtual", "object_guid", "when_created", "when_changed", "enabled", "is_deleted", "ad_notes", "local_notes"]
            for field in scalar_fields:
                if field in comp_data:
                    try:
                        if field == "last_boot" and comp_data[field]:
                            computer_data[field] = datetime.fromisoformat(comp_data[field])
                        elif field in ["when_created", "when_changed"] and comp_data[field]:
                            computer_data[field] = datetime.fromisoformat(comp_data[field])
                        elif field == "ram" and comp_data[field]:
                            computer_data[field] = int(comp_data[field])
                        elif field == "is_deleted":
                            computer_data[field] = comp_data.get(field, False)
                        else:
                            computer_data[field] = comp_data[field]
                        successful_components += 1
                    except Exception as e:
                        logger.warning(f"Помилка обробки поля {field}: {str(e)}", extra={"hostname": hostname, "field": field})
                        failed_components += 1
                        computer_data["errors"] = computer_data.get("errors", []) + [f"Помилка поля {field}: {str(e)}"]
                else:
                    if field == "is_deleted":
                        computer_data[field] = False

            # Визначення статусу
            if "check_status" in comp_data:
                computer_data["check_status"] = comp_data["check_status"]
            elif successful_components > 0 and failed_components > 0:
                computer_data["check_status"] = CheckStatus.partially_successful
            elif successful_components > 0:
                computer_data["check_status"] = CheckStatus.success
            else:
                computer_data["check_status"] = CheckStatus.failed

            logger.debug(f"AD-поля: is_deleted={computer_data['is_deleted']}, object_guid={computer_data['object_guid']}, enabled={computer_data['enabled']}", extra={"hostname": hostname})
            logger.debug(f"Статус: {computer_data['check_status']}, успішних: {successful_components}, невдалих: {failed_components}", extra={"hostname": hostname})
            logger.info("Дані підготовлено успішно", extra={"hostname": hostname})
            return ComputerCreate(**computer_data)
        except Exception as e:
            logger.error(f"Помилка підготовки даних: {str(e)}", extra={"hostname": hostname})
            raise

    async def upsert_computer_from_schema(self, comp_data: ComputerCreate, hostname: str) -> Computer:
        try:
            computer_id = await self.computer_repo.async_upsert_computer(comp_data, hostname)
            db_computer = await self.computer_repo.async_get_computer_by_id(computer_id)
            if not db_computer:
                logger.error("Комп’ютер не знайдено після збереження", extra={"hostname": hostname})
                raise ValueError("Комп’ютер не знайдено після збереження")
            await self.computer_repo.update_related_entities(db_computer, comp_data)
            logger.info(f"Комп’ютер збережено з ID {computer_id}", extra={"hostname": hostname})
            return Computer.model_validate(db_computer, from_attributes=True)
        except Exception as e:
            logger.error(f"Помилка збереження комп’ютера: {str(e)}", extra={"hostname": hostname})
            raise

    async def get_hosts_to_scan(self) -> List[str]:
        logger.info("Отримання хостів для сканування")
        if settings.test_hosts and settings.test_hosts.strip():
            hosts = [host.strip() for host in settings.test_hosts.split(",") if host.strip()]
            logger.info(f"Використовуються тестові хости: {hosts}")
            return hosts
        return await self.computer_repo.get_all_hosts()

    async def update_scan_task_status(self, task_id: str, status: models.ScanStatus, scanned_hosts: int = 0, successful_hosts: int = 0, error: Optional[str] = None):
        """Оновлює статус задачі сканування в базі даних."""
        logger.debug(f"Оновлення статусу задачі: {status}", extra={"task_id": task_id})
        await self.computer_repo.update_scan_task_status(task_id, status, scanned_hosts, successful_hosts, error)

    def _determine_scan_mode(self, db_computer: Optional[models.Computer]) -> str:
        if not db_computer or not db_computer.last_updated:
            return "Full"
        is_full_scan_needed = (
            not db_computer.last_full_scan or 
            db_computer.last_full_scan < datetime.utcnow() - timedelta(days=30)
        )
        return "Full" if is_full_scan_needed else "Changes"

    async def _is_server(self, hostname: str, db_computer: Optional[models.Computer]) -> bool:
        logger.debug("Перевірка, чи є хост сервером", extra={"hostname": hostname})
        if db_computer and db_computer.os_name and "server" in db_computer.os_name.lower():
            return True
        return False

    async def _update_host_status(self, hostname: str, status: models.CheckStatus = None, error_msg: Optional[str] = None):
        try:
            if error_msg:
                logger.error(f"Помилка хоста: {error_msg}", extra={"hostname": hostname})
            await self.computer_repo.async_update_computer_check_status(
                hostname=hostname,
                check_status=status.value if status else models.CheckStatus.unreachable.value
            )
        except Exception as e:
            logger.error(f"Помилка оновлення статусу: {str(e)}", extra={"hostname": hostname})
            raise

    async def _get_scan_context(self, host: str) -> Tuple[Optional[models.Computer], str, bool]:
        logger.debug("Отримання контексту сканування", extra={"hostname": host})
        try:
            db_computer_result = await self.computer_repo.db.execute(
                select(models.Computer).filter(models.Computer.hostname == host)
            )
            db_computer = db_computer_result.scalars().first()
            mode = self._determine_scan_mode(db_computer)
            
            if db_computer:
                query = select(models.Software).filter(models.Software.computer_id == db_computer.id)
                result = await self.computer_repo.db.execute(query)
                software_records = result.scalars().all()
                if not software_records:
                    mode = "Full"
                    logger.debug("Відсутні дані про ПО, встановлено режим 'Full'", extra={"hostname": host})
            
            is_server = await self._is_server(host, db_computer)
            return db_computer, mode, is_server
        except Exception as e:
            logger.error(f"Помилка отримання контексту: {str(e)}", extra={"hostname": host})
            raise

    async def _process_and_save_data(self, host: str, result_data: Dict[str, Any], mode: str, db_computer: Optional[models.Computer]) -> bool:
        logger.debug("Обробка і збереження даних", extra={"hostname": host})
        try:
            computer_to_create = await self.prepare_computer_data_for_db(result_data, host, mode)
            computer_id = await self.computer_repo.async_upsert_computer(computer_to_create, host, mode)
            db_computer = await self.computer_repo.async_get_computer_by_id(computer_id)
            if not db_computer:
                logger.error("Комп’ютер не знайдено після збереження", extra={"hostname": host})
                raise ValueError("Комп’ютер не знайдено після збереження")
            await self.computer_repo.update_related_entities(db_computer, computer_to_create, mode=mode)
            logger.info("Хост оброблено успішно", extra={"hostname": host})
            return True
        except Exception as e:
            logger.error(f"Помилка обробки даних: {str(e)}", extra={"hostname": host})
            raise

    async def _handle_scan_failure(self, host: str, result_data: Dict[str, Any]) -> bool:
        logger.debug("Обробка помилки сканування", extra={"hostname": host})
        error_msg = result_data.get("errors", ["Невідома помилка збору даних"]) if isinstance(result_data, dict) else [str(result_data)]
        status = models.CheckStatus.unreachable if isinstance(result_data, dict) and result_data.get("check_status") == "unreachable" else models.CheckStatus.failed
        try:
            await self.computer_repo.async_update_computer_check_status(host, status.value)
            logger.error(f"Збір даних не вдався: {error_msg}", extra={"hostname": host})
            return False
        except Exception as e:
            logger.error(f"Помилка оновлення статусу хоста: {str(e)}", extra={"hostname": host})
            raise

    async def _get_domain_credentials(self, hostname: str) -> Tuple[str, str]:
        logger.debug("Отримання облікових даних", extra={"hostname": hostname})
        try:
            result = await self.computer_repo.db.execute(
                select(models.Computer).filter(models.Computer.hostname == hostname)
            )
            computer = result.scalars().first()
            if computer and computer.domain_id:
                result = await self.computer_repo.db.execute(
                    select(models.Domain).filter(models.Domain.id == computer.domain_id)
                )
                domain = result.scalars().first()
                if domain:
                    return domain.username, domain.encrypted_password
            return settings.ad_username, settings.ad_password
        except Exception as e:
            logger.error(f"Помилка отримання облікових даних: {str(e)}", extra={"hostname": hostname})
            return settings.ad_username, settings.ad_password

    async def process_single_host(self, host: str, logger_adapter: logging.LoggerAdapter) -> bool:
        try:
            async with async_session_factory() as host_db:
                logger.debug(f"Відкрито сесію: {id(host_db)}", extra={"hostname": host})
                repo = ComputerRepository(host_db)
                service = ComputerService(host_db)
                result = await service.process_single_host_inner(host, logger_adapter)
                logger.debug("Сесію завершено", extra={"hostname": host})
                return result
        except Exception as e:
            logger.error(f"Помилка обробки хоста: {str(e)}", extra={"hostname": host})
            return False
        
    async def process_single_host_inner(self, host: str, logger_adapter: logging.LoggerAdapter) -> bool:
        logger.info("Початок обробки хоста", extra={"hostname": host})
        try:
            logger.debug("Крок 1: Отримання контексту сканування", extra={"hostname": host})
            db_computer, mode, is_server = await self._get_scan_context(host)
            logger.debug("Крок 2: Отримання облікових даних", extra={"hostname": host})
            username, password = await self._get_domain_credentials(host)
            logger.debug("Крок 3: Ініціалізація WinRMDataCollector", extra={"hostname": host})
            collector = WinRMDataCollector(hostname=host, username=username, password=password)
            logger.debug("Крок 4: Збір даних", extra={"hostname": host})
            result_data = await collector.get_all_pc_info(mode=mode, last_updated=db_computer.last_updated if db_computer else None)
            
            logger.debug(f"Результат збору даних: check_status={result_data.get('check_status') if isinstance(result_data, dict) else 'Невідомо'}", extra={"hostname": host})
            logger.debug(f"Сирі дані від WinRMDataCollector: {result_data}", extra={"hostname": host})
            
            if not isinstance(result_data, dict):
                logger.warning(f"Некоректні дані від WinRMDataCollector: {result_data}", extra={"hostname": host})
                return await self._handle_scan_failure(host, {"check_status": "failed", "errors": [f"Некоректні дані: {result_data}"]})
            
            if result_data.get("check_status") in ("unreachable", "failed"):
                logger.warning(f"Хост не оброблено: check_status={result_data.get('check_status')}, errors={result_data.get('errors', ['Немає детальної помилки'])}", extra={"hostname": host})
                return await self._handle_scan_failure(host, result_data)
            
            if not any([
                result_data.get("ip_addresses"),
                result_data.get("mac_addresses"),
                result_data.get("processors"),
                result_data.get("video_cards"), 
                result_data.get("disks", {}).get("physical_disks"),
                result_data.get("disks", {}).get("logical_disks"),
                result_data.get("software"),
                result_data.get("roles")
            ]):
                logger.warning("Хост не містить значущих даних", extra={"hostname": host})
                return await self._handle_scan_failure(host, {"check_status": "unreachable", "errors": ["Пусті дані"]})
            
            logger.debug("Крок 5: Підготовка даних для БД", extra={"hostname": host})
            computer_to_create = await self.prepare_computer_data_for_db(result_data, host, mode)
            logger.debug("Крок 6: Збереження комп’ютера", extra={"hostname": host})
            computer_id = await self.computer_repo.async_upsert_computer(computer_to_create, host, mode)
            logger.debug("Крок 7: Отримання комп’ютера з БД", extra={"hostname": host})
            db_computer = await self.computer_repo.async_get_computer_by_id(computer_id)
            if not db_computer:
                logger.error("Комп’ютер не знайдено після збереження", extra={"hostname": host})
                raise ValueError("Комп’ютер не знайдено після збереження")
            
            logger.debug("Крок 8: Оновлення пов’язаних сутностей", extra={"hostname": host})
            await self.computer_repo.update_related_entities(db_computer, computer_to_create, mode=mode)
            
            logger.debug("Крок 9: Перевірка даних з БД", extra={"hostname": host})
            result = await self.computer_repo.db.execute(
                select(models.Computer).options(
                    selectinload(models.Computer.ip_addresses),
                    selectinload(models.Computer.mac_addresses),
                    selectinload(models.Computer.processors),
                    selectinload(models.Computer.physical_disks),
                    selectinload(models.Computer.logical_disks),
                    selectinload(models.Computer.video_cards),
                    selectinload(models.Computer.software),
                    selectinload(models.Computer.roles)
                ).filter(models.Computer.id == computer_id)
            )
            db_computer_check = result.scalars().first()
            logger.debug(f"Перевірка даних: os_name={db_computer_check.os_name}, "
                        f"ip_addresses={[ip.address for ip in db_computer_check.ip_addresses]}", extra={"hostname": host})
            
            logger.info("Хост оброблено успішно", extra={"hostname": host})
            return True
        except asyncio.CancelledError:
            logger.error("Задача скасовано", extra={"hostname": host})
            raise
        except Exception as e:
            logger.error(f"Критична помилка при обробці: {str(e)}", extra={"hostname": host})
            await self._handle_scan_failure(host, {"check_status": "unreachable", "errors": [str(e)]})
            return False

    async def create_scan_task(self, task_id: str) -> Optional[models.ScanTask]:
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
            logger.info("Створено нову задачу сканування", extra={"task_id": task_id})
            return db_task
        except Exception as e:
            logger.error(f"Помилка створення задачі: {str(e)}", extra={"task_id": task_id})
            await self.computer_repo.db.rollback()
            raise

    async def run_scan_task(self, task_id: str, logger_adapter: logging.LoggerAdapter, hostname: Optional[str] = None):
        hosts = []
        successful = 0
        try:
            # Перевіряємо, чи існує задача
            result = await self.computer_repo.db.execute(
                select(models.ScanTask).filter(models.ScanTask.id == task_id)
            )
            task = result.scalars().first()
            if not task:
                logger.error(f"Задача {task_id} не знайдена", extra={"task_id": task_id})
                raise ValueError(f"Задача {task_id} не знайдена")
            if task.status != models.ScanStatus.running:
                logger.error(f"Задача {task_id} має некоректний статус: {task.status}", extra={"task_id": task_id})
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
                logger.info(f"Сканування одного хоста: {hostname}", extra={"task_id": task_id})
                all_hosts = await self.get_hosts_to_scan()
                if hostname not in all_hosts:
                    logger.warning(f"Хост {hostname} не знайдено", extra={"task_id": task_id})
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
                logger.info(f"Отримано {len(hosts)} хостів", extra={"task_id": task_id})

            if not hosts:
                logger.warning("Список хостів порожній", extra={"task_id": task_id})
                await self.update_scan_task_status(
                    task_id=task_id, 
                    status=models.ScanStatus.completed, 
                    scanned_hosts=0, 
                    successful_hosts=0
                )
                return

            async def process_host_with_semaphore(host: str):
                async with self.semaphore:
                    try:
                        result = await self.process_single_host(host, logger_adapter)
                        if result:
                            nonlocal successful
                            successful += 1
                        else:
                            logger.warning(f"Не вдалося обробити хост {host}", extra={"task_id": task_id})
                    except Exception as e:
                        logger.error(f"Помилка обробки хоста {host}: {str(e)}", extra={"task_id": task_id})

            tasks = [process_host_with_semaphore(host) for host in hosts]
            await asyncio.gather(*tasks, return_exceptions=True)

            await self.update_scan_task_status(
                task_id=task_id, 
                status=models.ScanStatus.completed, 
                scanned_hosts=len(hosts), 
                successful_hosts=successful
            )
            logger.info(f"Сканування завершено: {successful}/{len(hosts)} хостів успішно", extra={"task_id": task_id})
        
        except Exception as e:
            logger.error(f"Критична помилка в задачі: {str(e)}", extra={"task_id": task_id})
            await self.computer_repo.db.rollback()
            await self.update_scan_task_status(
                task_id=task_id,
                status=models.ScanStatus.failed,
                scanned_hosts=len(hosts),
                successful_hosts=successful,
                error=str(e)
            )
            raise