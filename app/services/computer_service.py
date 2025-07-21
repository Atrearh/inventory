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
            "validate": lambda x: x.get("DisplayName", "").strip() if isinstance(x, dict) else x,
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
        logger = logger.bind(hostname=hostname, component=component_key)
        config = self.COMPONENT_CONFIG.get(component_key)
        if not config:
            logger.warning("Немає конфігурації для компонента")
            return []

        result = []
        seen_identifiers = set()
        raw_data = comp_data.get(component_key, [])
        if not isinstance(raw_data, list):
            raw_data = [raw_data] if raw_data else []

        for item in raw_data:
            if not isinstance(item, dict) and not isinstance(item, str):
                logger.warning(f"Пропущен некорректный элемент: {item}")
                continue

            identifier = config["validate"](item)
            if not identifier or identifier in seen_identifiers:
                continue
            seen_identifiers.add(identifier)

            try:
                component_data = {field: item.get(field, None) for field in config["fields"]}
                if component_key == "physical_disks" and not component_data.get("serial"):
                    model = item.get("model", "")
                    component_data["serial"] = md5(f"{model}_{item.get('size', '')}_{hostname}".encode()).hexdigest()[:100]
                    logger.debug(f"Сгенерирован серийный номер для диска: {component_data['serial']}")
                result.append(config["model"](**component_data))
            except ValueError as e:
                logger.warning(f"Ошибка валидации: {str(e)}", data=item)
                continue

        return result

    async def prepare_computer_data_for_db(self, comp_data: Dict[str, Any], hostname: str, mode: str = "Full") -> ComputerCreate:
        """Підготовка даних для збереження в базі."""
        logger = logger.bind(hostname=hostname)
        try:
            logger.debug("Підготовка даних")
            computer_data = {
                "hostname": hostname,
                "ip_addresses": await self.process_component_list(comp_data, hostname, "ip_addresses"),
                "mac_addresses": await self.process_component_list(comp_data, hostname, "mac_addresses"),
                "processors": await self.process_component_list(comp_data, hostname, "processors"),
                "video_cards": await self.process_component_list(comp_data, hostname, "video_cards"),
                "physical_disks": await self.process_component_list(comp_data, hostname, "physical_disks"),
                "logical_disks": await self.process_component_list(comp_data, hostname, "logical_disks"),
                "software": await self.process_component_list(comp_data, hostname, "software"),
                "roles": await self.process_component_list(comp_data, hostname, "roles"),
                "os_name": comp_data.get('os_name', 'Unknown').strip() or 'Unknown',
                "os_version": comp_data.get('os_version') and comp_data.get('os_version').strip() or None,
                "ram": int(comp_data.get('ram', 0)) if comp_data.get('ram') else None,
                "motherboard": comp_data.get('motherboard', '').strip() or None,
                "last_boot": datetime.fromisoformat(comp_data['last_boot']) if comp_data.get('last_boot') else None,
                "is_virtual": comp_data.get('is_virtual', False),
                "check_status": comp_data.get('check_status', CheckStatus.success),
            }
            logger.info("Дані підготовлено успішно")
            return ComputerCreate(**computer_data)
        except Exception as e:
            logger.error("Помилка підготовки даних", error=str(e))
            raise

    async def upsert_computer_from_schema(self, comp_data: ComputerCreate, hostname: str) -> Computer:
        logger = logger.bind(hostname=hostname)
        try:
            computer_id = await self.computer_repo.async_upsert_computer(comp_data, hostname)
            db_computer = await self.computer_repo.async_get_computer_by_id(computer_id)
            if not db_computer:
                logger.error("Комп’ютер не знайдено після збереження")
                raise ValueError("Комп’ютер не знайдено після збереження")
            await self.computer_repo.update_related_entities(db_computer, comp_data)
            logger.info(f"Комп’ютер збережено з ID {computer_id}")
            return Computer.model_validate(db_computer, from_attributes=True)
        except Exception as e:
            logger.error("Помилка збереження комп’ютера", error=str(e))
            raise

    async def get_hosts_to_scan(self) -> List[str]:
        logger.info("Отримання хостів для сканування")
        if settings.test_hosts and settings.test_hosts.strip():
            hosts = [host.strip() for host in settings.test_hosts.split(",") if host.strip()]
            logger.info(f"Використовуються тестові хости: {hosts}")
            return hosts
        return await self.computer_repo.get_all_hosts()

    async def update_scan_task_status(self, task_id: str, status: models.ScanStatus, scanned_hosts: int = 0, successful_hosts: int = 0, error: Optional[str] = None):
        logger = logger.bind(task_id=task_id)
        logger.debug(f"Оновлення статусу задачі: {status}")
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
        logger = logger.bind(hostname=hostname)
        if db_computer and db_computer.os_name and "server" in db_computer.os_name.lower():
            return True
        result = await self.computer_repo.db.execute(
            select(models.ADComputer).filter(models.ADComputer.hostname == hostname)
        )
        ad_computer = result.scalars().first()
        return bool(ad_computer and ad_computer.os_name and "server" in ad_computer.os_name.lower())

    async def _update_host_status(self, hostname: str, status: models.CheckStatus = None, error_msg: Optional[str] = None):
        logger = logger.bind(hostname=hostname)
        try:
            if error_msg:
                logger.error(f"Помилка хоста: {error_msg}")
            await self.computer_repo.async_update_computer_check_status(
                hostname=hostname,
                check_status=status.value if status else models.CheckStatus.unreachable.value
            )
        except Exception as e:
            logger.error("Помилка оновлення статусу", error=str(e))
            raise

    async def _get_scan_context(self, host: str) -> Tuple[Optional[models.Computer], str, bool]:
        logger = logger.bind(hostname=host)
        logger.debug("Отримання контекста сканування")
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
                    logger.debug("Відсутні дані про ПО, встановлено режим 'Full'")
            
            is_server = await self._is_server(host, db_computer)
            return db_computer, mode, is_server
        except Exception as e:
            logger.error("Помилка отримання контекста", error=str(e))
            raise

    async def _process_and_save_data(self, host: str, result_data: Dict[str, Any], mode: str, db_computer: Optional[models.Computer]) -> bool:
        logger = logger.bind(hostname=host)
        logger.debug("Обробка і збереження даних")
        try:
            computer_to_create = await self.prepare_computer_data_for_db(result_data, host, mode)
            computer_id = await self.computer_repo.async_upsert_computer(computer_to_create, host, mode)
            db_computer = await self.computer_repo.async_get_computer_by_id(computer_id)
            if not db_computer:
                logger.error("Комп’ютер не знайдено після збереження")
                raise ValueError("Комп’ютер не знайдено після збереження")
            await self.computer_repo.update_related_entities(db_computer, computer_to_create, mode=mode)
            logger.info("Хост оброблено успішно")
            return True
        except Exception as e:
            logger.error("Помилка обробки даних", error=str(e))
            raise

    async def _handle_scan_failure(self, host: str, result_data: Dict[str, Any]) -> bool:
        logger = logger.bind(hostname=host)
        logger.debug("Обробка помилки сканування")
        error_msg = result_data.get("error", "Неизвестная ошибка сбора данных")
        status = models.CheckStatus.unreachable if result_data.get("check_status") == "unreachable" else models.CheckStatus.failed
        await self.computer_repo.async_update_computer_check_status(host, status.value)
        logger.error(f"Сбор даних не вдався: {error_msg}")
        return False

    async def _get_domain_credentials(self, hostname: str) -> Tuple[str, str]:
        logger = logger.bind(hostname=hostname)
        logger.debug("Отримання учетних даних")
        try:
            result = await self.computer_repo.db.execute(
                select(models.ADComputer).filter(models.ADComputer.hostname == hostname)
            )
            ad_computer = result.scalars().first()
            if ad_computer and ad_computer.domain_id:
                result = await self.computer_repo.db.execute(
                    select(models.Domain).filter(models.Domain.id == ad_computer.domain_id)
                )
                domain = result.scalars().first()
                if domain:
                    return domain.username, domain.password
            return settings.ad_username, settings.ad_password
        except Exception as e:
            logger.error("Помилка отримання учетних даних", error=str(e))
            return settings.ad_username, settings.ad_password

    async def process_single_host(self, host: str, logger_adapter: logging.LoggerAdapter) -> bool:
        logger = logger.bind(hostname=host)
        try:
            async with async_session_factory() as host_db:
                logger.debug(f"Відкрито сесію: {id(host_db)}")
                repo = ComputerRepository(host_db)
                service = ComputerService(host_db)
                result = await service.process_single_host_inner(host, logger_adapter)
                logger.debug("Сесію завершено")
                return result
        except Exception as e:
            logger.error("Помилка обробки хоста", error=str(e))
            return False

    async def process_single_host_inner(self, host: str, logger_adapter: logging.LoggerAdapter) -> bool:
        logger = logger.bind(hostname=host)
        try:
            logger.info("Початок обробки хоста")
            db_computer, mode, is_server = await self._get_scan_context(host)
            username, password = await self._get_domain_credentials(host)
            collector = WinRMDataCollector(hostname=host, username=username, password=password)
            result_data = await collector.get_all_pc_info(mode=mode, last_updated=db_computer.last_updated if db_computer else None)
            
            if result_data.get("check_status") in ("unreachable", "failed"):
                logger.warning(f"Хост не оброблено: check_status={result_data.get('check_status')}")
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
                logger.warning("Хост не містить значущих даних")
                return await self._handle_scan_failure(host, {"check_status": "unreachable", "error": "Пусті дані"})
            
            computer_to_create = await self.prepare_computer_data_for_db(result_data, host, mode)
            computer_id = await self.computer_repo.async_upsert_computer(computer_to_create, host, mode)
            db_computer = await self.computer_repo.async_get_computer_by_id(computer_id)
            if not db_computer:
                logger.error("Комп’ютер не знайдено після збереження")
                raise ValueError("Комп’ютер не знайдено після збереження")
            
            await self.computer_repo.update_related_entities(db_computer, computer_to_create, mode=mode)
            
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
                        f"ip_addresses={[ip.address for ip in db_computer_check.ip_addresses]}")
            
            logger.info("Хост оброблено успішно")
            return True
        except asyncio.CancelledError:
            logger.error("Задача скасовано")
            raise
        except Exception as e:
            logger.error("Критична помилка при обробці", error=str(e))
            await self._handle_scan_failure(host, {"check_status": "unreachable", "error": str(e)})
            return False

    async def create_scan_task(self, task_id: str) -> Optional[models.ScanTask]:
        logger_with_task = logger.bind(task_id=task_id)  # Используем локальную переменную для привязки task_id
        try:
            result = await self.computer_repo.db.execute(
                select(models.ScanTask).filter(models.ScanTask.id == task_id)
            )
            existing_task = result.scalars().first()
            if existing_task:
                if existing_task.status in [models.ScanStatus.completed, models.ScanStatus.failed]:
                    logger_with_task.warning(f"Задача {task_id} існує зі статусом {existing_task.status}, видаляємо")
                    await self.computer_repo.db.delete(existing_task)
                    await self.computer_repo.db.flush()
                else:
                    logger_with_task.warning(f"Задача {task_id} існує зі статусом {existing_task.status}")
                    return existing_task

            db_task = models.ScanTask(
                id=task_id,
                status=models.ScanStatus.running,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            self.computer_repo.db.add(db_task)
            await self.computer_repo.db.flush()
            await self.computer_repo.db.refresh(db_task)
            logger_with_task.info("Создана новая задача сканирования")
            return db_task
        except Exception as e:
            logger_with_task.error("Помилка створення задачі", error=str(e))
            await self.computer_repo.db.rollback()
            raise

async def run_scan_task(self, task_id: str, logger_adapter: logging.LoggerAdapter, hostname: Optional[str] = None):
    logger_with_task = logger.bind(task_id=task_id)  # Используем локальную переменную для привязки task_id
    hosts = []
    successful = 0
    try:
        task = await self.create_scan_task(task_id)
        if not task:
            logger_with_task.error("Не вдалося створити задачу")
            return

        if hostname:
            hosts = [hostname]
            logger_with_task.info(f"Сканування одного хоста: {hostname}")
            all_hosts = await self.get_hosts_to_scan()
            if hostname not in all_hosts:
                logger_with_task.warning(f"Хост {hostname} не знайдено")
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
            logger_with_task.info(f"Отримано {len(hosts)} хостів")

        if not hosts:
            logger_with_task.warning("Список хостів порожній")
            await self.update_scan_task_status(
                task_id=task_id, 
                status=models.ScanStatus.completed, 
                scanned_hosts=0, 
                successful_hosts=0
            )
            return

        async def process_host_with_semaphore(host: str):
            async with self.semaphore:
                result = await self.process_single_host(host, logger_adapter)
                if result:
                    nonlocal successful
                    successful += 1

        tasks = [process_host_with_semaphore(host) for host in hosts]
        await asyncio.gather(*tasks, return_exceptions=True)

        await self.update_scan_task_status(
            task_id=task_id, 
            status=models.ScanStatus.completed, 
            scanned_hosts=len(hosts), 
            successful_hosts=successful
        )
        logger_with_task.info(f"Сканування завершено: {successful}/{len(hosts)} хостів успішно")
    
    except Exception as e:
        logger_with_task.error("Критична помилка в задачі", error=str(e))
        await self.computer_repo.db.rollback()
        await self.update_scan_task_status(
            task_id=task_id,
            status=models.ScanStatus.failed,
            scanned_hosts=len(hosts),
            successful_hosts=successful,
            error=str(e)
        )
        raise