
# app/services/computer_service.py
import logging
import asyncio
from datetime import datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
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
        logger.debug("Получение хостов для опроса")
        try:
            result = await self.db.execute(select(models.Computer.hostname))
            hosts = [row[0] for row in result.fetchall()]
            return hosts
        except Exception as e:
            logger.error(f"Ошибка получения хостов: {str(e)}")
            raise

    async def process_roles(self, roles: List[str], hostname: str) -> List[dict]:
        logger.debug(f"Обработка {len(roles)} ролей для {hostname}")
        return [{"name": role} for role in roles if role]

    async def process_software_list(self, software_list: List[dict], hostname: str) -> List[dict]:
        logger.debug(f"Обработка {len(software_list)} записей ПО для {hostname}")
        valid_software = []
        for soft in software_list:
            try:
                valid_software.append({
                    "name": soft.get("DisplayName"),
                    "version": soft.get("DisplayVersion"),
                    "install_date": soft.get("InstallDate")
                })
            except Exception as e:
                logger.warning(f"Ошибка обработки ПО для {hostname}: {str(e)}")
        return valid_software

    async def process_disks(self, disks: List[dict], hostname: str) -> List[dict]:
        logger.debug(f"Обработка {len(disks)} дисков для {hostname}")
        valid_disks = []
        for disk in disks:
            try:
                valid_disks.append({
                    "device_id": disk.get("DeviceID"),
                    "total_space": int(disk.get("TotalSpace", 0)),
                    "free_space": int(disk.get("FreeSpace", 0))
                })
            except Exception as e:
                logger.warning(f"Ошибка обработки диска для {hostname}: {str(e)}")
        return valid_disks

    async def prepare_computer_data_for_db(self, raw_data: dict, hostname: str) -> ComputerCreate:
        logger.debug(f"Подготовка данных для {hostname}")
        try:
            validated_data = ComputerCreate(
                hostname=hostname,
                ip=raw_data.get("ip"),
                os_name=raw_data.get("os_name"),
                os_version=raw_data.get("os_version"),
                cpu=raw_data.get("cpu"),
                ram=raw_data.get("ram"),
                mac=raw_data.get("mac"),
                motherboard=raw_data.get("motherboard"),
                last_boot=raw_data.get("last_boot"),
                is_virtual=raw_data.get("is_virtual", False),
                check_status=raw_data.get("check_status", "success"),
                roles=await self.process_roles(raw_data.get("roles", []), hostname),
                software=await self.process_software_list(raw_data.get("software", []), hostname),
                disks=await self.process_disks(raw_data.get("disks", []), hostname)
            )
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

    async def upsert_computer_from_schema(self, comp_data: ComputerCreate, hostname: str):
        try:
            logger.debug(f"Upsert компьютера {hostname}")
            computer_id = await self.repo.async_upsert_computer(comp_data, hostname)
            logger.info(f"Компьютер {hostname} успешно сохранен, ID={computer_id}")
            return computer_id
        except Exception as e:
            logger.error(f"Ошибка при upsert компьютера {hostname}: {str(e)}", exc_info=True)
            raise

    async def run_scan_task(self, task_id: str, logger_adapter: logging.LoggerAdapter):
        async with async_session() as db:
            db_task = None
            successful = 0
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
                logger_adapter.info(f"Задача сканирования {task_id} создана")

                hosts = await self.get_hosts_for_polling_from_db()
                logger_adapter.info(f"Получено {len(hosts)} хостов: {hosts[:5]}...")
                semaphore = asyncio.Semaphore(settings.scan_max_workers)

                async def process_host(host: str):
                    nonlocal successful
                    async with async_session() as host_db:
                        try:
                            db_computer = await host_db.execute(
                                select(models.Computer).filter(models.Computer.hostname == host)
                            )
                            db_computer = db_computer.scalars().first()
                            last_updated = db_computer.last_updated if db_computer else None
                            result_data = await get_pc_info(
                                hostname=host,
                                user=settings.ad_username,
                                password=settings.ad_password,
                                last_updated=last_updated,
                            )
                            if result_data is None or not isinstance(result_data, dict):
                                logger_adapter.error(f"Некорректные данные для {host}: {result_data}")
                                await self.repo.async_update_computer_check_status(
                                    hostname=host,
                                    check_status=models.CheckStatus.unreachable.value
                                )
                                await host_db.commit()
                                return
                            if result_data.get("check_status") == models.CheckStatus.unreachable.value:
                                logger_adapter.error(
                                    f"Хост {host} недоступен: {result_data.get('error', 'Неизвестная ошибка')}"
                                )
                                await self.repo.async_update_computer_check_status(
                                    hostname=host,
                                    check_status=models.CheckStatus.unreachable.value
                                )
                                await host_db.commit()
                                return
                            computer_to_create = await self.prepare_computer_data_for_db(
                                raw_data=result_data,
                                hostname=host
                            )
                            if computer_to_create:
                                try:
                                    service = ComputerService(host_db, ComputerRepository(host_db))
                                    computer_id = await service.upsert_computer_from_schema(computer_to_create, host)
                                    if computer_id:
                                        await host_db.commit()
                                        successful += 1
                                    else:
                                        logger_adapter.error(f"Не удалось сохранить данные для {host}")
                                        await self.repo.async_update_computer_check_status(
                                            hostname=host,
                                            check_status=models.CheckStatus.failed.value
                                        )
                                        await host_db.commit()
                                except Exception as e:
                                    logger_adapter.error(f"Ошибка сохранения данных для {host}: {str(e)}")
                                    await host_db.rollback()
                                    await self.repo.async_update_computer_check_status(
                                        hostname=host,
                                        check_status=models.CheckStatus.failed.value
                                    )
                                    await host_db.commit()
                            else:
                                logger_adapter.error(f"Ошибка валидации для {host}: computer_to_create is None")
                                await self.repo.async_update_computer_check_status(
                                    hostname=host,
                                    check_status=models.CheckStatus.failed.value
                                )
                                await host_db.commit()
                        except Exception as e:
                            logger_adapter.error(f"Исключение для хоста {host}: {str(e)}")
                            await host_db.rollback()
                            await self.repo.async_update_computer_check_status(
                                hostname=host,
                                check_status=models.CheckStatus.unreachable.value
                            )
                            await host_db.commit()

                tasks = []
                for host in hosts:
                    async with semaphore:
                        tasks.append(process_host(host))
                await asyncio.gather(*tasks, return_exceptions=True)

                db_task.scanned_hosts = len(hosts)
                db_task.successful_hosts = successful
                db_task.status = models.ScanStatus.completed
                db_task.updated_at = datetime.utcnow()
                await db.commit()
                logger_adapter.info(f"Сканирование завершено. Успешно обработано {successful} из {len(hosts)} хостов")
            except Exception as e:
                logger_adapter.error(f"Критическая ошибка сканирования: {str(e)}", exc_info=True)
                if db_task:
                    db_task.status = models.ScanStatus.failed
                    db_task.error = str(e)
                    db_task.updated_at = datetime.utcnow()
                    await db.commit()
                else:
                    failed_task = models.ScanTask(
                        id=task_id,
                        status=models.ScanStatus.failed,
                        error=str(e),
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    db.add(failed_task)
                    await db.commit()
                raise
            finally:
                await db.close()
