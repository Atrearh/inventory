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
from ..data_collector import WinRMDataCollector, winrm_session
from ..utils import validate_ip_address, validate_mac_address
from ..database import async_session_factory 
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

class ComputerService:
    def __init__(self, db: AsyncSession):
        self.semaphore = asyncio.Semaphore(settings.scan_max_workers)
        self.computer_repo = ComputerRepository(db)

    async def get_hosts_to_scan(self) -> List[str]:
        if settings.test_hosts and settings.test_hosts.strip():
            hosts = [host.strip() for host in settings.test_hosts.split(",") if host.strip()]
            logger.info(f"Используются тестовые хосты из настроек: {hosts}")
            return hosts
        return await self.computer_repo.get_all_hosts()

    async def prepare_computer_data_for_db(self, comp_data: Dict[str, Any], hostname: str, mode: str = "Full") -> ComputerCreate:
        logger.debug(f"Подготовка данных для компьютера: {hostname}")
        try:
            # Удаление дубликатов и валидация
            ip_addresses = [IPAddress(address=ip) for ip in set(comp_data.get('ip_addresses', [])) if ip and validate_ip_address(IPAddress, ip, "IP address")]
            mac_addresses = [MACAddress(address=mac) for mac in set(comp_data.get('mac_addresses', [])) if mac and validate_mac_address(MACAddress, mac, "MAC address")]
            
            # Обработка физических дисков
            physical_disks = []
            disk_data = comp_data.get('disks', {})
            logger.debug(f"Входные данные physical_disks для {hostname}: {disk_data.get('physical_disks', [])}")
            serial_to_physical_disk = {}
            seen_serials = set()
            physical_disks_raw = disk_data.get('physical_disks', [])
            # Распаковка вложенных списков
            physical_disks_list = []
            for item in physical_disks_raw:
                if isinstance(item, list):
                    physical_disks_list.extend(item)
                else:
                    physical_disks_list.append(item)
            for disk in physical_disks_list:
                if not isinstance(disk, dict):
                    logger.warning(f"Пропущен некорректный элемент физического диска для {hostname}: {disk} (ожидался словарь, получен {type(disk)})")
                    continue
                serial = disk.get('serial', '') if not isinstance(disk.get('serial'), list) else disk.get('serial', [])[0] if disk.get('serial') else ''
                if not serial or serial in seen_serials or serial.lower() == 'data':
                    model = disk.get('model', '') if not isinstance(disk.get('model'), list) else disk.get('model', [])[0] if disk.get('model') else ''
                    serial = md5(f"{model}_{disk.get('size', '')}_{hostname}".encode()).hexdigest()[:100]
                    logger.debug(f"Сгенерирован серийный номер для диска {model} на {hostname}: {serial}")
                seen_serials.add(serial)
                model = disk.get('model', '') if not isinstance(disk.get('model'), list) else disk.get('model', [])[0] if disk.get('model') else ''
                interface = disk.get('interface', '') if not isinstance(disk.get('interface'), list) else disk.get('interface', [])[0] if disk.get('interface') else ''
                media_type = disk.get('media_type', '')
                try:
                    physical_disk = PhysicalDisk(
                        model=model.strip() or None,
                        serial=serial.strip(),
                        interface=interface.strip() or None,
                        media_type=media_type.strip() or None
                    )
                    physical_disks.append(physical_disk)
                    serial_to_physical_disk[serial] = physical_disk
                except ValueError as e:
                    logger.warning(f"Ошибка валидации физического диска для {hostname}: {str(e)}, данные: {disk}")
                    continue

            # Обработка логических дисков
            logical_disks = []
            seen_device_ids = set()
            logger.debug(f"Входные данные logical_disks для {hostname}: {disk_data.get('logical_disks', [])}")
            logical_disks_raw = disk_data.get('logical_disks', [])
            # Распаковка вложенных списков
            logical_disks_list = []
            for item in logical_disks_raw:
                if isinstance(item, list):
                    logical_disks_list.extend(item)
                else:
                    logical_disks_list.append(item)
            for disk in logical_disks_list:
                if not isinstance(disk, dict):
                    logger.warning(f"Пропущен некорректный элемент логического диска для {hostname}: {disk} (ожидался словарь, получен {type(disk)})")
                    continue
                device_id = disk.get('device_id')
                if not device_id or device_id in seen_device_ids:
                    logger.warning(f"Пропущен дублирующийся или пустой логический диск для {hostname}: device_id={device_id}")
                    continue
                seen_device_ids.add(device_id)
                total_space = disk.get('total_space', 0)
                free_space = disk.get('free_space', 0)
                volume_label = disk.get('volume_label', '') or ''
                serial = disk.get('serial', '')
                try:
                    logical_disk = LogicalDisk(
                        device_id=device_id.strip(),
                        volume_label=volume_label.strip() or None,
                        parent_disk_serial=serial.strip() or None if serial and serial.lower() != 'data' else None,
                        total_space=int(total_space),
                        free_space=int(free_space) if free_space else None
                    )
                    logical_disks.append(logical_disk)
                except ValueError as e:
                    logger.warning(f"Ошибка валидации логического диска для {hostname}: {str(e)}, данные: {disk}")
                    continue

            # Обработка процессоров и видеокарт
            processors = []
            seen_processor_names = set()
            for proc in comp_data.get('processors', []):
                if not isinstance(proc, dict):
                    logger.warning(f"Пропущен некорректный элемент процессора для {hostname}: {proc} (ожидался словарь, получен {type(proc)})")
                    continue
                name = proc.get('name')
                if name and name not in seen_processor_names:
                    seen_processor_names.add(name)
                    try:
                        processors.append(Processor(
                            name=name.strip(),
                            number_of_cores=int(proc.get('number_of_cores', 0)),
                            number_of_logical_processors=int(proc.get('number_of_logical_processors', 0))
                        ))
                    except ValueError as e:
                        logger.warning(f"Ошибка валидации процессора для {hostname}: {str(e)}, данные: {proc}")
                        continue

            video_cards = []
            seen_video_card_names = set()
            for card in comp_data.get('video_cards', []):
                if not isinstance(card, dict):
                    logger.warning(f"Пропущен некорректный элемент видеокарты для {hostname}: {card} (ожидался словарь, получен {type(card)})")
                    continue
                name = card.get('name')
                if name and name not in seen_video_card_names:
                    seen_video_card_names.add(name)
                    try:
                        video_cards.append(VideoCard(
                            name=name.strip(),
                            driver_version=card.get('driver_version', '').strip() or None
                        ))
                    except ValueError as e:
                        logger.warning(f"Ошибка валидации видеокарты для {hostname}: {str(e)}, данные: {card}")
                        continue

            computer_data = ComputerCreate(
                hostname=hostname,
                ip_addresses=ip_addresses,
                mac_addresses=mac_addresses,
                os_name=comp_data.get('os_name', 'Unknown').strip() or 'Unknown',
                os_version=comp_data.get('os_version') and comp_data.get('os_version').strip() or None,
                ram =int(comp_data.get('ram', 0)) if comp_data.get('ram') else None,
                motherboard=comp_data.get('motherboard', '') and comp_data.get('motherboard', '').strip() or None,
                last_boot=datetime.fromisoformat(comp_data['last_boot']) if comp_data.get('last_boot') else None,
                is_virtual=comp_data.get('is_virtual', False),
                check_status=comp_data.get('check_status', CheckStatus.success),
                roles=[Role(name=role.strip()) for role in comp_data.get('roles', []) if role.strip()],
                software=[Software(
                    name=soft.get('DisplayName', '').strip(),
                    version=soft.get('DisplayVersion', '').strip() or None,
                    install_date=datetime.fromisoformat(soft['InstallDate']) if soft.get('InstallDate') else None
                ) for soft in comp_data.get('software', []) if soft.get('DisplayName', '').strip()],
                physical_disks=physical_disks,
                logical_disks=logical_disks,
                video_cards=video_cards,
                processors=processors
            )
            logger.info(f"Данные компьютера {hostname} подготовлены успешно")
            return computer_data
        except Exception as e:
            logger.error(f"Ошибка подготовки данных для {hostname}: {str(e)}", exc_info=True)
            raise

    async def upsert_computer_from_schema(self, comp_data: ComputerCreate, hostname: str) -> Computer:
        try:
            computer_id = await self.computer_repo.async_upsert_computer(comp_data, hostname)
            db_computer = await self.computer_repo.async_get_computer_by_id(computer_id)
            if not db_computer:
                logger.error(f"Компьютер {hostname} не найден после сохранения")
                raise ValueError("Компьютер не найден после сохранения")
            await self.computer_repo.update_related_entities(db_computer, comp_data)
            logger.info(f"Компьютер {hostname} успешно сохранен с ID {computer_id}")
            return Computer.model_validate(db_computer, from_attributes=True)
        except Exception as e:
            logger.error(f"Ошибка сохранения компьютера {hostname}: {str(e)}")
            raise

    async def update_scan_task_status(self, task_id: str, status: models.ScanStatus, scanned_hosts: int = 0, successful_hosts: int = 0, error: Optional[str] = None):
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
        """Определяет, является ли хост сервером."""
        if db_computer and db_computer.os_name and "server" in db_computer.os_name.lower():
            return True
        result = await self.computer_repo.db.execute(
            select(models.ADComputer).filter(models.ADComputer.hostname == hostname)
        )
        ad_computer = result.scalars().first()
        return bool(ad_computer and ad_computer.os_name and "server" in ad_computer.os_name.lower())

    async def _update_host_status(self, hostname: str, status: models.CheckStatus = None, error_msg: Optional[str] = None):
        try:
            if error_msg:
                logger.error(f"Ошибка для хоста {hostname}: {error_msg}")
            await self.computer_repo.async_update_computer_check_status(
                hostname=hostname,
                check_status=status.value if status else models.CheckStatus.unreachable.value
            )
        except Exception as e:
            logger.error(f"Ошибка обновления статуса хоста {hostname}: {str(e)}")
            raise

    async def _get_scan_context(self, host: str) -> Tuple[Optional[models.Computer], str, bool]:
        """Получение контекста сканирования для хоста."""
        logger.debug(f"Получение контекста сканирования для {host}")
        try:
            db_computer_result = await self.computer_repo.db.execute(select(models.Computer).filter(models.Computer.hostname == host))
            db_computer = db_computer_result.scalars().first()
            mode = self._determine_scan_mode(db_computer)
            is_server = await self._is_server(host, db_computer)
            return db_computer, mode, is_server
        except Exception as e:
            logger.error(f"Ошибка получения контекста для {host}: {str(e)}")
            raise

    async def _collect_host_data(self, host: str, mode: str, is_server: bool, last_updated: Optional[datetime]) -> Dict[str, Any]:
        """Сбор данных с хоста через WinRM."""
        logger.debug(f"Сбор данных для {host} в режиме {mode}")
        collector = WinRMDataCollector(hostname=host, username=settings.ad_username, password=settings.ad_password)
        with winrm_session(host, settings.ad_username, settings.ad_password) as session:
            return await collector.get_all_pc_info(session, mode=mode, last_updated=last_updated)

    async def _process_and_save_data(self, host: str, result_data: Dict[str, Any], mode: str, db_computer: Optional[models.Computer]) -> bool:
        """Обработка и сохранение данных хоста."""
        logger.debug(f"Обработка и сохранение данных для {host}")
        try:
            computer_to_create = await self.prepare_computer_data_for_db(result_data, host, mode)
            computer_id = await self.computer_repo.async_upsert_computer(computer_to_create, host, mode)
            db_computer = await self.computer_repo.async_get_computer_by_id(computer_id)
            if not db_computer:
                logger.error(f"Компьютер {host} не найден после сохранения")
                raise ValueError("Компьютер не найден после сохранения")
            await self.computer_repo.update_related_entities(db_computer, computer_to_create, mode=mode)
            logger.info(f"Хост {host} успешно обработан")
            return True
        except Exception as e:
            logger.error(f"Ошибка обработки данных для {host}: {str(e)}")
            raise

    async def _handle_scan_failure(self, host: str, result_data: Dict[str, Any]) -> bool:
        """Обработка ошибок сканирования."""
        logger.debug(f"Обработка ошибки сканирования для {host}")
        error_msg = result_data.get("error", "Неизвестная ошибка сбора данных")
        status = models.CheckStatus.unreachable if result_data.get("check_status") == "unreachable" else models.CheckStatus.failed
        await self.computer_repo.async_update_computer_check_status(host, status.value)
        logger.error(f"Сбор данных для {host} не удался: {error_msg}")
        return False

    async def _get_domain_credentials(self, hostname: str) -> Tuple[str, str]:
        """Получение учетных данных для хоста на основе домена."""
        logger.debug(f"Получение учетных данных для {hostname}")
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
            logger.error(f"Ошибка получения учетных данных для {hostname}: {str(e)}")
            return settings.ad_username, settings.ad_password

    async def process_single_host(self, host: str, logger_adapter: logging.LoggerAdapter) -> bool:
        try:
            async with async_session_factory() as host_db:
                logger_adapter.debug(f"Открыта сессия для хоста {host}: {id(host_db)}")
                repo = ComputerRepository(host_db)
                service = ComputerService(host_db)
                result = await service.process_single_host_inner(host, logger_adapter)
                logger_adapter.debug(f"Сессия для хоста {host} успешно завершена")
                return result
        except Exception as e:
            logger_adapter.error(f"Ошибка обработки хоста {host}: {str(e)}", exc_info=True)
            return False

    async def process_single_host_inner(self, host: str, logger_adapter: logging.LoggerAdapter) -> bool:
        try:
            db_computer, mode, is_server = await self._get_scan_context(host)
            username, password = await self._get_domain_credentials(host)
            collector = WinRMDataCollector(hostname=host, username=username, password=password)
            result_data = await collector.get_all_pc_info(mode=mode, last_updated=db_computer.last_updated if db_computer else None)
            
            if result_data.get("check_status") in ("unreachable", "failed"):
                logger_adapter.warning(f"Хост {host} не обработан: check_status={result_data.get('check_status')}")
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
                logger_adapter.warning(f"Хост {host} не содержит значимых данных, обновление базы данных пропущено")
                return await self._handle_scan_failure(host, {"check_status": "unreachable", "error": "Пустые данные"})
            
            computer_to_create = await self.prepare_computer_data_for_db(result_data, host, mode)
            computer_id = await self.computer_repo.async_upsert_computer(computer_to_create, host, mode)
            db_computer = await self.computer_repo.async_get_computer_by_id(computer_id)
            if not db_computer:
                logger_adapter.error(f"Компьютер {host} не найден после сохранения")
                raise ValueError("Компьютер не найден после сохранения")
            
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
            logger_adapter.debug(f"Проверка данных в базе для {host}: "
                            f"os_name={db_computer_check.os_name}, "
                            f"os_version={db_computer_check.os_version}, "
                            f"ram={db_computer_check.ram}, "
                            f"motherboard={db_computer_check.motherboard}, "
                            f"last_boot={db_computer_check.last_boot}, "
                            f"ip_addresses={[ip.address for ip in db_computer_check.ip_addresses]}, "
                            f"mac_addresses={[mac.address for mac in db_computer_check.mac_addresses]}, "
                            f"processors={[proc.name for proc in db_computer_check.processors]}, "
                            f"physical_disks={[pd.serial for pd in db_computer_check.physical_disks]}, "
                            f"logical_disks={[ld.device_id for ld in db_computer_check.logical_disks]}, "
                            f"video_cards={[vc.name for vc in db_computer_check.video_cards]}")
            
            return True
        except asyncio.CancelledError:
            logger_adapter.error(f"Задача для хоста {host} была отменена")
            raise
        except Exception as e:
            logger_adapter.error(f"Критическая ошибка при обработке хоста {host}: {str(e)}", exc_info=True)
            await self._handle_scan_failure(host, {"check_status": "unreachable", "error": str(e)})
            return False
        
    async def create_scan_task(self, task_id: str) -> Optional[models.ScanTask]:
        try:
            # Проверяем, существует ли задача с таким task_id
            result = await self.computer_repo.db.execute(
                select(models.ScanTask).filter(models.ScanTask.id == task_id)
            )
            existing_task = result.scalars().first()
            if existing_task:
                # Если задача завершена или неуспешна, удаляем её и создаём новую
                if existing_task.status in [models.ScanStatus.completed, models.ScanStatus.failed]:
                    logger.warning(f"Задача {task_id} уже существует с статусом {existing_task.status}, удаляем старую задачу")
                    await self.computer_repo.db.delete(existing_task)
                    await self.computer_repo.db.flush()
                else:
                    logger.warning(f"Задача с ID {task_id} уже существует и имеет статус {existing_task.status}")
                    return existing_task

            # Создаем новую задачу
            db_task = models.ScanTask(
                id=task_id,
                status=models.ScanStatus.running,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            self.computer_repo.db.add(db_task)
            await self.computer_repo.db.flush()
            await self.computer_repo.db.refresh(db_task)
            logger.info(f"Создана новая задача сканирования {task_id}")
            return db_task
        except SQLAlchemyError as e:
            logger.error(f"Ошибка создания задачи сканирования {task_id}: {str(e)}")
            await self.computer_repo.db.rollback()  # Откатываем транзакцию
            raise

    async def run_scan_task(self, task_id: str, logger_adapter: logging.LoggerAdapter, hostname: Optional[str] = None):
        hosts = []
        successful = 0
        try:
            task = await self.create_scan_task(task_id)
            if not task:
                logger_adapter.error(f"Не удалось создать или получить задачу {task_id}")
                return

            if hostname:
                hosts = [hostname]
                logger_adapter.info(f"Сканирование одного хоста: {hostname}")
                all_hosts = await self.get_hosts_to_scan()
                if hostname not in all_hosts:
                    logger_adapter.warning(f"Хост {hostname} не найден в списке доступных хостов")
                    await self.update_scan_task_status(
                        task_id=task_id,
                        status=models.ScanStatus.failed,
                        scanned_hosts=0,
                        successful_hosts=0,
                        error=f"Хост {hostname} не найден"
                    )
                    return
            else:
                hosts = await self.get_hosts_to_scan()
                logger_adapter.info(f"Получено {len(hosts)} хостов для сканирования: {hosts[:5]}...")

            if not hosts:
                logger_adapter.warning("Список хостов для сканирования пуст. Завершение задачи.")
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
            logger_adapter.info(f"Сканирование завершено. Успешно обработано {successful} из {len(hosts)} хостов")
        
        except SQLAlchemyError as e:
            logger_adapter.error(f"Критическая ошибка в задаче сканирования {task_id}: {str(e)}", exc_info=True)
            await self.computer_repo.db.rollback()
            await self.update_scan_task_status(
                task_id=task_id,
                status=models.ScanStatus.failed,
                scanned_hosts=len(hosts),
                successful_hosts=successful,
                error=str(e)
            )
        except Exception as e:
            logger_adapter.error(f"Критическая ошибка в задаче сканирования {task_id}: {str(e)}", exc_info=True)
            await self.computer_repo.db.rollback()
            await self.update_scan_task_status(
                task_id=task_id,
                status=models.ScanStatus.failed,
                scanned_hosts=len(hosts),
                successful_hosts=successful,
                error=str(e)
            )
            raise