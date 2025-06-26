# app/computer_service.py
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..settings import settings
from ..data_collector import get_pc_info
from ..repositories.computer_repository import ComputerRepository
from .. import models
from ..database import get_db
from ..utils import validate_hostname, validate_ip_address, validate_mac_address
from ..schemas import ComputerCreate, Role, Software, Disk, CheckStatus, Computer

logger = logging.getLogger(__name__)

class ComputerService:
    def __init__(self, db: AsyncSession, repo: ComputerRepository):
        self.db = db
        self.repo = repo

    async def get_hosts_to_scan(self) -> List[str]:
        """
        Определяет, какие хосты сканировать.
        Если в настройках заданы test_hosts, использует их.
        В противном случае, получает все хосты из базы данных.
        """
        if settings.test_hosts and settings.test_hosts.strip():
            hosts = [host.strip() for host in settings.test_hosts.split(",") if host.strip()]
            logger.info(f"Используются тестовые хосты из настроек: {hosts}")
            return hosts
        
        logger.info("Test_hosts не заданы, получаем все хосты из базы данных.")
        return await self._get_all_hosts_from_db()

    async def _get_all_hosts_from_db(self) -> List[str]:
        """Получает список всех хостов из базы данных для опроса."""
        logger.debug("Получение всех хостов из БД")
        try:
            result = await self.db.execute(select(models.Computer.hostname))
            hosts = [row[0] for row in result.fetchall()]
            return hosts
        except Exception as e:
            logger.error(f"Ошибка получения хостов из БД: {str(e)}")
            raise


    async def process_disks(self, disks: List[dict], hostname: str) -> List[dict]:
        """Обрабатывает список дисков для хоста."""
        logger.debug(f"Входные данные дисков для {hostname}: {disks}")
        valid_disks = []
        for disk in disks:
            try:
                disk_data = {
                    "device_id": disk.get("device_id") or disk.get("DeviceID"),
                    "total_space": float(disk.get("total_space") or disk.get("TotalSpace")),
                    "free_space": int(disk.get("free_space") or disk.get("FreeSpace")) if disk.get("free_space") or disk.get("FreeSpace") else None
                }
                if disk_data["device_id"] and disk_data["total_space"] is not None:
                    valid_disks.append(disk_data)
                    logger.debug(f"Валидный диск для {hostname}: {disk_data}")
                else:
                    logger.warning(f"Пропущен диск для {hostname}: недостаточно данных {disk_data}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Ошибка обработки диска для {hostname}: {str(e)}")
        return valid_disks
    
    def process_list(self, input_list: List[Dict], key: str, schema: Any, required_fields: Optional[List[str]] = None) -> List[Any]:
            if not input_list:
                return []
            result = []
            required = required_fields or []
            key_lower = key.lower()
            
            for item in input_list:
                try:
                    if not isinstance(item, dict):
                        logger.warning(f"Некорректный формат элемента: {item}")
                        continue
                    
                    # Нормализуем ключи в нижний регистр
                    normalized_item = {k.lower(): v for k, v in item.items()}
                    
                    # Проверяем наличие ключа (в любом регистре)
                    found_key = None
                    for k in normalized_item:
                        if k == key_lower:
                            found_key = k
                            break
                    if not found_key:
                        logger.warning(f"Отсутствует ключ {key} в элементе: {item}")
                        continue
                    
                    # Проверяем обязательные поля с учетом алиасов
                    missing_fields = []
                    formatted_item = {key: normalized_item[found_key]}
                    for f in required:
                        found = False
                        for k in normalized_item:
                            if k == f.lower():
                                normalized_item[f] = normalized_item[k]
                                formatted_item[f] = normalized_item[k]
                                found = True
                                break
                        if not found:
                            missing_fields.append(f)
                    if missing_fields:
                        logger.warning(f"Отсутствуют обязательные поля {missing_fields} в элементе: {item}")
                        continue
                    
                    # Приводим ключи к ожидаемому формату для схемы
                    if schema == Disk:
                        # Специальная обработка для Disk с учетом алиасов
                        formatted_item = {
                            "DeviceID": normalized_item.get("deviceid", normalized_item.get("device_id")),
                            "TotalSpace": normalized_item.get("totalspace", normalized_item.get("total_space")),
                            "FreeSpace": normalized_item.get("freespace", normalized_item.get("free_space"))
                        }
                    else:
                        for f in required:
                            if f.lower() in normalized_item:
                                formatted_item[f] = normalized_item[f.lower()]
                    
                    # Создаем объект схемы
                    result.append(schema(**formatted_item))
                    logger.debug(f"Успешно обработан элемент: {formatted_item}")
                    
                except Exception as e:
                    logger.error(f"Ошибка обработки элемента {item}: {str(e)}")
            return result

    async def prepare_computer_data_for_db(self, comp_data: Dict[str, Any], hostname: str, mode: str = "Full") -> ComputerCreate:
        """Подготовка данных компьютера для сохранения в БД."""
        logger.debug(f"Подготовка данных для компьютера: {hostname}")

        try:
            # Валидация основных полей
            validated_hostname = validate_hostname(None, hostname)
            ip_address = validate_ip_address(None, comp_data.get('ip_address'))
            mac_address = validate_mac_address(None, comp_data.get('mac_address'))

            # Нормализация os_name
            os_name = comp_data.get('os_name', 'Unknown')
            if not os_name or os_name.strip() == '':
                os_name = 'Unknown'
            os_name = os_name.replace('Майкрософт ', '').replace('Microsoft ', '')

            # Преобразование ролей в формат словарей, если они пришли как строки
            raw_roles = comp_data.get('roles', [])
            roles_data = [
                {"Name": role} if isinstance(role, str) else role
                for role in raw_roles
            ]

            # Обработка списков
            roles = self.process_list(roles_data, key="Name", schema=Role, required_fields=["Name"])
            software = self.process_list(comp_data.get('software', []), key="DisplayName", schema=Software, required_fields=["DisplayName"])
            disks = self.process_list(comp_data.get('disks', []), key="DeviceID", schema=Disk, required_fields=["total_space"])

            # Формирование объекта ComputerCreate
            computer_data = ComputerCreate(
                hostname=validated_hostname,
                ip=ip_address,
                os_name=os_name,
                os_version=comp_data.get('os_version'),
                cpu=comp_data.get('cpu'),
                ram=comp_data.get('ram'),
                mac=mac_address,
                motherboard=comp_data.get('motherboard'),
                last_boot=comp_data.get('last_boot'),
                is_virtual=comp_data.get('is_virtual', False),
                check_status=comp_data.get('check_status', CheckStatus.success),
                roles=roles,
                software=software,
                disks=disks 
            )
            logger.info(f"Данные компьютера {hostname} подготовлены успешно")
            return computer_data
        except Exception as e:
            logger.error(f"Ошибка подготовки данных для {hostname}: {str(e)}")
            raise

    async def upsert_computer_from_schema(self, comp_data: ComputerCreate, hostname: str) -> Computer:
            """Оновлення або створення комп'ютера з використанням схеми."""
            try:
                computer_id = await self.repo.async_upsert_computer(comp_data, hostname)
                db_computer = await self.repo.async_get_computer_by_id(computer_id)
                if not db_computer:
                    logger.error(f"Комп'ютер {hostname} не знайдено після збереження")
                    raise ValueError("Комп'ютер не знайдено після збереження")
                logger.info(f"Комп'ютер {hostname} успішно збережено з ID {computer_id}")
                return db_computer
            except Exception as e:
                logger.error(f"Помилка збереження комп'ютера {hostname}: {str(e)}")
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
                    logger.error(f"Задача сканирования {task_id} не найдена")
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
        """Определяет режим сканирования (Full или Changes)."""
        if not db_computer or not db_computer.last_updated:
            return "Full"
        
        is_full_scan_needed = (
            not db_computer.last_full_scan or 
            db_computer.last_full_scan < datetime.utcnow() - timedelta(days=30)
        )
        return "Full" if is_full_scan_needed else "Changes"

    async def _update_host_status(self, hostname: str, status: models.CheckStatus = None, error_msg: Optional[str] = None):
        """Обновляет статус хоста в БД."""
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
        """Обрабатывает один хост: сбор данных, валидация и сохранение."""
        async with get_db() as db:
            repo = ComputerRepository(db)
            try:
                db_computer_result = await db.execute(select(models.Computer).filter(models.Computer.hostname == host))
                db_computer = db_computer_result.scalars().first()

                mode = self._determine_scan_mode(db_computer)
                
                result_data = await get_pc_info(
                    hostname=host,
                    user=settings.ad_username,
                    password=settings.ad_password,
                    last_updated=db_computer.last_updated if db_computer else None,
                    last_full_scan=db_computer.last_full_scan if db_computer else None,
                )

                if result_data and result_data.get("check_status") not in ("unreachable", "failed"):
                    computer_to_create = await self.prepare_computer_data_for_db(result_data, host, mode)
                    await repo.async_upsert_computer(computer_to_create, host, mode)
                    await db.commit()
                    logger_adapter.info(f"Хост {host} успешно обработан.")
                    return True
                else:
                    error_msg = result_data.get('error', 'Неизвестная ошибка сбора данных')
                    status = models.CheckStatus.unreachable if result_data.get("check_status") == "unreachable" else models.CheckStatus.failed
                    logger_adapter.error(f"Сбор данных для {host} не удался: {error_msg}")
                    await repo.async_update_computer_check_status(host, status.value)
                    await db.commit()
                    return False

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
        """Координирует процесс сканирования хостов."""
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