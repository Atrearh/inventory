import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..settings import settings
from ..database import async_session
from ..data_collector import get_pc_info
from ..repositories.computer_repository import ComputerRepository
from ..schemas import ComputerCreate
from .. import models


logger = logging.getLogger(__name__)

class ComputerService:
    def __init__(self, db: AsyncSession, repo: ComputerRepository):
        self.db = db
        self.repo = repo

    async def get_hosts_for_polling_from_db(self) -> List[str]:
        """Получает список хостов для опроса."""
        logger.debug("Получение хостов для опроса")
        try:
            result = await self.db.execute(select(models.Computer.hostname))
            hosts = [row[0] for row in result.fetchall()]
            return hosts
        except Exception as e:
            logger.error(f"Ошибка получения хостов: {str(e)}")
            raise

    async def process_list(self, items: List[dict], hostname: str, fields: List[str], log_name: str) -> List[dict]:
        """Универсальная функция для обработки списков данных."""
        logger.debug(f"Обработка {len(items)} записей {log_name} для {hostname}")
        valid_items = []
        for item in items:
            try:
                valid_item = {field: item.get(field) for field in fields}
                if all(valid_item.get(field) is not None for field in fields if field != "is_deleted"):
                    valid_item["is_deleted"] = False
                    valid_items.append(valid_item)
            except Exception as e:
                logger.warning(f"Ошибка обработки записи {log_name} для {hostname}: {str(e)}")
        return valid_items

    async def process_roles(self, roles: List[str], hostname: str) -> List[dict]:
        """Обрабатывает список ролей для хоста."""
        return await self.process_list(
            items=[{"name": role} for role in roles if role],
            hostname=hostname,
            fields=["name"],
            log_name="ролей"
        )

    async def process_software_list(self, software_list: List[dict], hostname: str) -> List[dict]:
        """Обрабатывает список программного обеспечения для хоста."""
        return await self.process_list(
            items=software_list,
            hostname=hostname,
            fields=["name", "version", "install_date", "action", "is_deleted"],
            log_name="ПО"
        )

    async def process_disks(self, disks: List[dict], hostname: str) -> List[dict]:
        """Обрабатывает список дисков для хоста."""
        return await self.process_list(
            items=disks,
            hostname=hostname,
            fields=["device_id", "total_space", "free_space"],
            log_name="дисков"
        )

    async def prepare_computer_data_for_db(self, raw_data: dict, hostname: str, mode: str) -> ComputerCreate:
        """Подготавливает данные компьютера для сохранения в базе данных."""
        logger.debug(f"Подготовка данных для {hostname}")
        try:
            computer_data = {
                "hostname": hostname,
                "ip": raw_data.get("ip"),
                "os_name": raw_data.get("os_name"),
                "os_version": raw_data.get("os_version"),
                "cpu": raw_data.get("cpu"),
                "ram": raw_data.get("ram"),
                "mac": raw_data.get("mac"),
                "motherboard": raw_data.get("motherboard"),
                "last_boot": raw_data.get("last_boot"),
                "is_virtual": raw_data.get("is_virtual", False),
                "check_status": raw_data.get("check_status", "success"),
                "roles": await self.process_roles(raw_data.get("roles", []), hostname),
                "software": await self.process_software_list(raw_data.get("software", []), hostname),
                "disks": await self.process_disks(raw_data.get("disks", []), hostname),
            }
            if mode == "Full":
                computer_data["last_full_scan"] = datetime.utcnow()
            validated_data = ComputerCreate(**computer_data)
            logger.debug(
                f"Подготовлены данные для {hostname}: "
                f"roles={len(validated_data.roles)}, "
                f"software={len(validated_data.software)}, "
                f"disks={len(validated_data.disks)}"
            )
            return validated_data
        except Exception as e:
            logger.error(f"Ошибка подготовки данных для {hostname}: {str(e)}")
            raise

    async def upsert_computer_from_schema(self, comp_data: ComputerCreate, hostname: str, mode: str):
        """Сохраняет или обновляет данные компьютера в базе данных."""
        try:
            logger.debug(f"Upsert компьютера {hostname}")
            computer_id = await self.repo.async_upsert_computer(comp_data, hostname, mode=mode)
            logger.info(f"Компьютер {hostname} успешно сохранен, ID={computer_id}")
            return computer_id
        except Exception as e:
            logger.error(f"Ошибка при upsert компьютера {hostname}: {str(e)}", exc_info=True)
            raise

    async def create_scan_task(self, task_id: str) -> models.ScanTask:
        """Создает новую задачу сканирования в базе данных."""
        async with async_session() as db:
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
                logger.error(f"Ошибка создания задачи сканирования {task_id}: {str(e)}")
                await db.rollback()
                raise

    async def update_scan_task_status(self, task_id: str, status: models.ScanStatus, scanned_hosts: int = 0, successful_hosts: int = 0, error: Optional[str] = None):
        """Обновляет статус задачи сканирования."""
        async with async_session() as db:
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
                logger.error(f"Ошибка обновления статуса задачи {task_id}: {str(e)}")
                await db.rollback()
                raise

    async def process_single_host(self, host: str, repo: ComputerRepository, logger_adapter: logging.LoggerAdapter) -> bool:
        """Обрабатывает данные одного хоста."""
        async with async_session() as db:
            try:
                db_computer = await db.execute(
                    select(models.Computer).filter(models.Computer.hostname == host)
                )
                db_computer = db_computer.scalars().first()
                last_updated = db_computer.last_updated if db_computer else None
                last_full_scan = db_computer.last_full_scan if db_computer else None
                result_data = await get_pc_info(
                    hostname=host,
                    user=settings.ad_username,
                    password=settings.ad_password,
                    last_updated=last_updated,
                    last_full_scan=last_full_scan,
                )
                if result_data is None or not isinstance(result_data, dict):
                    logger_adapter.error(f"Некорректные данные для {host}: {result_data}")
                    await repo.async_update_computer_check_status(
                        hostname=host,
                        check_status=models.CheckStatus.unreachable.value
                    )
                    await db.commit()
                    return False

                if result_data.get("check_status") == models.CheckStatus.unreachable.value:
                    logger_adapter.error(
                        f"Хост {host} недоступен: {result_data.get('error', 'Неизвестная ошибка')}"
                    )
                    await repo.async_update_computer_check_status(
                        hostname=host,
                        check_status=models.CheckStatus.unreachable.value
                    )
                    await db.commit()
                    return False

                mode = "Full" if last_updated is None or (
                    last_full_scan is None or last_full_scan < datetime.utcnow() - timedelta(days=30)
                ) else "Changes"
                computer_to_create = await self.prepare_computer_data_for_db(
                    raw_data=result_data,
                    hostname=host,
                    mode=mode
                )
                if computer_to_create:
                    try:
                        computer_id = await self.upsert_computer_from_schema(computer_to_create, host, mode)
                        if computer_id:
                            await db.commit()
                            logger_adapter.info(f"Хост {host} успешно обработан, ID={computer_id}")
                            return True
                        else:
                            logger_adapter.error(f"Не удалось сохранить данные для {host}")
                            await repo.async_update_computer_check_status(
                                hostname=host,
                                check_status=models.CheckStatus.failed.value
                            )
                            await db.commit()
                            return False
                    except Exception as e:
                        logger_adapter.error(f"Ошибка сохранения данных для {host}: {str(e)}")
                        await db.rollback()
                        await repo.async_update_computer_check_status(
                            hostname=host,
                            check_status=models.CheckStatus.failed.value
                        )
                        await db.commit()
                        return False
                else:
                    logger_adapter.error(f"Ошибка валидации для {host}: computer_to_create is None")
                    await repo.async_update_computer_check_status(
                        hostname=host,
                        check_status=models.CheckStatus.failed.value
                    )
                    await db.commit()
                    return False
            except Exception as e:
                logger_adapter.error(f"Исключение для хоста {host}: {str(e)}")
                await db.rollback()
                await repo.async_update_computer_check_status(
                    hostname=host,
                    check_status=models.CheckStatus.unreachable.value
                )
                await db.commit()
                return False

    async def run_scan_task(self, task_id: str, logger_adapter: logging.LoggerAdapter):
        """Координирует процесс сканирования хостов."""
        try:
            await self.create_scan_task(task_id)
            hosts = await self.get_hosts_for_polling_from_db()
            logger_adapter.info(f"Получено {len(hosts)} хостов: {hosts[:5]}...")

            successful = 0
            repo = ComputerRepository(self.db)
            semaphore = asyncio.Semaphore(settings.scan_max_workers)

            async def process_host_with_semaphore(host: str):
                async with semaphore:
                    success = await self.process_single_host(host, repo, logger_adapter)
                    if success:
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
        except Exception as e:
            logger_adapter.error(f"Критическая ошибка сканирования: {str(e)}", exc_info=True)
            await self.update_scan_task_status(
                task_id=task_id,
                status=models.ScanStatus.failed,
                scanned_hosts=len(hosts) if 'hosts' in locals() else 0,
                successful_hosts=successful if 'successful' in locals() else 0,
                error=str(e)
            )
            raise