import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..settings import settings
from ..repositories.computer_repository import ComputerRepository
from .. import models
from ..database import get_db
from ..schemas import ComputerCreate, Role, Software, Disk, CheckStatus, Computer, VideoCard, Processor, IPAddress, MACAddress
from ..data_collector import WinRMDataCollector, winrm_session

logger = logging.getLogger(__name__)

class ComputerService:
    def __init__(self, db: AsyncSession, repo: ComputerRepository):
        self.db = db
        self.repo = repo

    async def get_hosts_to_scan(self) -> List[str]:
        if settings.test_hosts and settings.test_hosts.strip():
            hosts = [host.strip() for host in settings.test_hosts.split(",") if host.strip()]
            logger.info(f"Используются тестовые хосты из настроек: {hosts}")
            return hosts
        logger.info("Test_hosts не заданы, получаем все хосты из базы данных.")
        return await self._get_all_hosts_from_db()

    async def _get_all_hosts_from_db(self) -> List[str]:
        logger.debug("Получение всех хостов из БД")
        try:
            result = await self.db.execute(select(models.Computer.hostname))
            hosts = [row[0] for row in result.fetchall()]
            return hosts
        except Exception as e:
            logger.error(f"Ошибка получения хостов из БД: {str(e)}")
            raise

    async def prepare_computer_data_for_db(self, comp_data: Dict[str, Any], hostname: str, mode: str = "Full") -> ComputerCreate:
        """Подготовка данных компьютера для сохранения в БД."""
        logger.debug(f"Подготовка данных для компьютера: {hostname}")
        try:
            ip_addresses = [IPAddress(address=ip) for ip in comp_data.get('ip_addresses', []) if ip]
            mac_addresses = [MACAddress(address=mac) for mac in comp_data.get('mac_addresses', []) if mac]
            disks = []
            for disk in comp_data.get('disks', []):
                if not isinstance(disk, dict):
                    logger.warning(f"Некорректный элемент диска для {hostname}: {disk}, ожидался словарь")
                    continue
                model = disk.get('model', '') if not isinstance(disk.get('model'), list) else disk.get('model', [])[0] if disk.get('model') else ''
                serial = disk.get('serial', '') if not isinstance(disk.get('serial'), list) else disk.get('serial', [])[0] if disk.get('serial') else ''
                interface = disk.get('interface', '') if not isinstance(disk.get('interface'), list) else disk.get('interface', [])[0] if disk.get('interface') else ''
                media_type = disk.get('media_type', '')
                device_id = disk.get('device_id')
                total_space = disk.get('total_space', 0)
                free_space = disk.get('free_space', 0)
                volume_label = disk.get('volume_label', '') or ''
                if not device_id or total_space <= 0:
                    logger.warning(f"Пропущен диск для {hostname}: device_id={device_id}, total_space={total_space}")
                    continue
                disks.append(Disk(
                    device_id=device_id,
                    model=model,
                    serial=serial,
                    interface=interface,
                    media_type=media_type,
                    total_space=total_space,
                    free_space=free_space,
                    volume_label=volume_label
                ))
                logger.debug(f"Добавлен диск для {hostname}: device_id={device_id}, model={model}, serial={serial}, interface={interface}, media_type={media_type}, total_space={total_space}, free_space={free_space}, volume_label={volume_label}")
            computer_data = ComputerCreate(
                hostname=hostname,
                ip_addresses=ip_addresses,
                os_name=comp_data.get('os_name', 'Unknown'),
                os_version=comp_data.get('os_version'),
                ram=comp_data.get('ram'),
                mac_addresses=mac_addresses,
                motherboard=comp_data.get('motherboard'),
                last_boot=datetime.fromisoformat(comp_data['last_boot']) if comp_data.get('last_boot') else None,
                is_virtual=comp_data.get('is_virtual', False),
                check_status=comp_data.get('check_status', CheckStatus.success),
                roles=[Role(name=role) for role in comp_data.get('roles', [])],
                software=[Software(**soft) for soft in comp_data.get('software', [])],
                disks=disks,
                video_cards=[VideoCard(**card) for card in comp_data.get('video_cards', [])],
                processors=[Processor(**proc) for proc in comp_data.get('processors', [])]
            )
            logger.info(f"Данные компьютера {hostname} подготовлены успешно")
            return computer_data
        except Exception as e:
            logger.error(f"Ошибка подготовки данных для {hostname}: {str(e)}", exc_info=True)
            raise

    async def upsert_computer_from_schema(self, comp_data: ComputerCreate, hostname: str) -> Computer:
        try:
            computer_id = await self.repo.async_upsert_computer(comp_data, hostname)
            db_computer = await self.repo.async_get_computer_by_id(computer_id)
            if not db_computer:
                logger.error(f"Компьютер {hostname} не найден после сохранения")
                raise ValueError("Компьютер не найден после сохранения")
            logger.info(f"Компьютер {hostname} успешно сохранен с ID {computer_id}")
            return Computer.from_orm(db_computer)
        except Exception as e:
            logger.error(f"Ошибка сохранения компьютера {hostname}: {str(e)}")
            raise

    async def create_scan_task(self, task_id: str) -> models.ScanTask:
        async with get_db() as db:
            try:
                db_task = models.ScanTask(
                    id=task_id,
                    status=models.ScanStatus.running,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(db_task)
                await db.commit()
                await db.refresh(db_task)
                logger.info(f"Задача сканирования {task_id} создана")
                return db_task
            except Exception as e:
                await db.rollback()
                logger.error(f"Ошибка создания задачи сканирования {task_id}: {str(e)}")
                raise

    async def update_scan_task_status(self, task_id: str, status: models.ScanStatus, scanned_hosts: int = 0, successful_hosts: int = 0, error: Optional[str] = None):
        async with get_db() as db:
            try:
                result = await db.execute(select(models.ScanTask).filter(models.ScanTask.id == task_id))
                db_task = result.scalars().first()
                if not db_task:
                    logger.error(f"Задача {task_id} не найдена")
                    raise ValueError("Задача не найдена")
                db_task.status = status
                db_task.scanned_hosts = scanned_hosts
                db_task.successful_hosts = successful_hosts
                db_task.updated_at = datetime.utcnow()
                db_task.error = error
                await db.commit()
                logger.info(f"Статус задачи {task_id} обновлен: {status}, обработано {scanned_hosts} хостов, успешно {successful_hosts}")
            except Exception as e:
                await db.rollback()
                logger.error(f"Ошибка обновления статуса задачи {task_id}: {str(e)}")
                raise

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
        result = await self.db.execute(
            select(models.ADComputer).filter(models.ADComputer.hostname == hostname)
        )
        ad_computer = result.scalars().first()
        return bool(ad_computer and ad_computer.os_name and "server" in ad_computer.os_name.lower())

    async def _update_host_status(self, hostname: str, status: models.CheckStatus = None, error_msg: Optional[str] = None):
        async with get_db() as db:
            repo = ComputerRepository(db)
            try:
                if error_msg:
                    logger.error(f"Ошибка для хоста {hostname}: {error_msg}")
                await repo.async_update_computer_check_status(
                    hostname=hostname,
                    check_status=status.value if status else models.CheckStatus.unreachable.value,
                )
                await db.commit()
            except Exception as e:
                await db.rollback()
                logger.error(f"Ошибка обновления статуса хоста {hostname}: {str(e)}")
                raise


    async def process_single_host(self, host: str, logger_adapter: logging.LoggerAdapter) -> bool:
        async with get_db() as db:
            repo = ComputerRepository(db)
            try:
                db_computer_result = await db.execute(select(models.Computer).filter(models.Computer.hostname == host))
                db_computer = db_computer_result.scalars().first()

                mode = self._determine_scan_mode(db_computer)
                is_server = await self._is_server(host, db_computer)

                collector = WinRMDataCollector(hostname=host, username=settings.ad_username, password=settings.ad_password)
                
                with winrm_session(host, settings.ad_username, settings.ad_password) as session:
                    if mode == "Full":
                        # Передаем сессию явно в методы get_*, чтобы избежать создания новых сессий
                        basic_info_task = collector._execute_script(session, "system_info.ps1")
                        software_info_task = collector._execute_script(session, "software_info_full.ps1")
                        disk_info_task = collector._execute_script(session, "disk_info.ps1")
                        hardware_info_task = collector._execute_script(session, "hardware_info.ps1")

                        results = await asyncio.gather(
                            basic_info_task,
                            software_info_task,
                            disk_info_task,
                            hardware_info_task,
                            return_exceptions=True
                        )
                        basic_info, software_info, disk_info, hardware_info = results
                        
                        logger_adapter.debug(f"Данные disk_info для {host}: {disk_info}")
                        
                        errors = []
                        for info, name in [(basic_info, "basic_info"), (hardware_info, "hardware_info")]:
                            if isinstance(info, Exception):
                                errors.append(f"{name} error: {str(info)}")
                            elif isinstance(info, dict) and info.get("check_status") in ("unreachable", "failed"):
                                errors.append(info.get("error", f"{name} failed"))
                        
                        if isinstance(software_info, Exception):
                            errors.append(f"software_info error: {str(software_info)}")
                        
                        if isinstance(disk_info, Exception):
                            errors.append(f"disk_info error: {str(disk_info)}")
                        
                        if errors:
                            error_msg = "; ".join(errors)
                            status = models.CheckStatus.unreachable if any("unreachable" in e for e in errors) else models.CheckStatus.failed
                            await repo.async_update_computer_check_status(host, status.value)
                            await db.commit()
                            logger_adapter.error(f"Сбор данных для {host} не удался: {error_msg}")
                            return False

                        result_data = {
                            "check_status": "success",
                            "ip_addresses": basic_info.get("ip_addresses", []),
                            "mac_addresses": basic_info.get("mac_addresses", []),
                            "os_name": basic_info.get("os_name", "Unknown"),
                            "os_version": basic_info.get("os_version"),
                            "ram": basic_info.get("ram"),
                            "motherboard": basic_info.get("motherboard"),
                            "last_boot": basic_info.get("last_boot"),
                            "is_virtual": basic_info.get("is_virtual", False),
                            "roles": basic_info.get("roles", []),
                            "software": software_info if isinstance(software_info, list) else [],
                            "disks": disk_info if isinstance(disk_info, list) else [],
                            "video_cards": hardware_info.get("video_cards", []),
                            "processors": hardware_info.get("processors", [])
                        }
                    else:
                        software_info = await collector._execute_script(session, "software_info_changes.ps1")
                        if isinstance(software_info, dict) and software_info.get("check_status") in ("unreachable", "failed"):
                            error_msg = software_info.get("error", "Неизвестная ошибка сбора данных")
                            status = models.CheckStatus.unreachable if software_info.get("check_status") == "unreachable" else models.CheckStatus.failed
                            await repo.async_update_computer_check_status(host, status.value)
                            await db.commit()
                            logger_adapter.error(f"Сбор данных для {host} не удался: {error_msg}")
                            return False
                        result_data = {
                            "check_status": "success",
                            "software": software_info if isinstance(software_info, list) else []
                        }

                    computer_to_create = await self.prepare_computer_data_for_db(result_data, host, mode)
                    await repo.async_upsert_computer(computer_to_create, host, mode)
                    await db.commit()
                    logger_adapter.info(f"Хост {host} успешно обработан.")
                    return True

            except asyncio.CancelledError:
                logger_adapter.error(f"Задача для хоста {host} была отменена")
                raise
            except Exception as e:
                await db.rollback()
                logger_adapter.error(f"Критическая ошибка при обработке хоста {host}: {str(e)}", exc_info=True)
                await repo.async_update_computer_check_status(host, models.CheckStatus.unreachable.value)
                await db.commit()
                return False

    async def run_scan_task(self, task_id: str, logger_adapter: logging.LoggerAdapter):
        hosts = []
        successful = 0
        async with get_db() as db:
            try:
                await self.create_scan_task(task_id)
                hosts = await self.get_hosts_to_scan()
                logger_adapter.info(f"Получено {len(hosts)} хостов для сканирования: {hosts[:5]}...")

                if not hosts:
                    logger_adapter.warning("Список хостов для сканирования пуст. Завершение задачи.")
                    await self.update_scan_task_status(
                        task_id=task_id, status=models.ScanStatus.completed, scanned_hosts=0, successful_hosts=0
                    )
                    return

                semaphore = asyncio.Semaphore(settings.scan_max_workers)

                async def process_host_with_semaphore(host: str):
                    async with semaphore:
                        if await self.process_single_host(host, logger_adapter):
                            nonlocal successful
                            successful += 1

                tasks = [process_host_with_semaphore(host) for host in hosts]
                await asyncio.gather(*tasks)

                await self.update_scan_task_status(
                    task_id=task_id, status=models.ScanStatus.completed, scanned_hosts=len(hosts), successful_hosts=successful
                )
                logger_adapter.info(f"Сканирование завершено. Успешно обработано {successful} из {len(hosts)} хостов")
        
            except Exception as e:
                logger_adapter.error(f"Критическая ошибка в задаче сканирования {task_id}: {str(e)}", exc_info=True)
                await self.update_scan_task_status(
                    task_id=task_id,
                    status=models.ScanStatus.failed,
                    scanned_hosts=len(hosts),
                    successful_hosts=successful,
                    error=str(e)
                )
