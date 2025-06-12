# app/services/computer_service.py
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from .. import schemas, models
from ..settings import settings
import logging
from sqlalchemy import select
from ..repositories.computer_repository import ComputerRepository

logger = logging.getLogger(__name__)

class ComputerService:
    def __init__(self, repo: ComputerRepository):
        self.repo = repo
        self.db = repo.db

    def normalize_hostname(self, hostname: str) -> str:
        """Нормализует hostname, добавляя суффикс домена, если необходимо."""
        if not hostname or not isinstance(hostname, str):
            logger.error("Отсутствует или невалидное поле hostname")
            raise ValueError("Hostname не может быть пустым или невалидным")
        hostname = hostname.strip().lower()
        suffix = settings.ad_fqdn_suffix.lower()
        if not hostname.endswith(suffix):
            hostname = f"{hostname}{suffix}"
        logger.debug(f"Нормализованный hostname: {hostname}")
        return hostname

    async def process_software_list(self, raw_software: List, hostname: str) -> List[schemas.Software]:
        logger.debug(f"Начало обработки ПО для {hostname}, получено {len(raw_software)} записей: {raw_software[:5]}...")
        unique_software = set()
        for soft in raw_software:
            if not isinstance(soft, dict):
                logger.warning(f"Некорректный формат записи ПО для {hostname}: {soft}")
                continue
            try:
                # Pydantic сам обработает DisplayName -> name, DisplayVersion -> version
                soft_data = schemas.Software.model_validate(soft)
                unique_software.add((soft_data.name, soft_data.version or "", soft_data.install_date))
            except Exception as e:
                logger.warning(f"Ошибка обработки ПО для {hostname}: {str(e)}")
                continue

        software_list = []
        for name, version, install_date in unique_software:
            software_list.append(schemas.Software(
                name=name,
                version=version if version else None,
                install_date=install_date
            ))
            logger.debug(f"Добавлена запись ПО для {hostname}: {name}, версия: {version}, дата: {install_date}")
        logger.info(f"Обработано {len(software_list)} записей ПО для {hostname}")
        return software_list

    async def process_disks(self, raw_disks: List[dict], hostname: str) -> List[schemas.Disk]:
        disks = []
        logger.debug(f"Обработка дисков для {hostname}: {raw_disks}")
        for disk in raw_disks:
            if not isinstance(disk, dict) or not disk.get("DeviceID") or not str(disk.get("DeviceID")).strip():
                logger.warning(f"Некорректный формат диска для {hostname}: {disk}")
                continue
            try:
                # Pydantic сам обработает DeviceID -> device_id, TotalSpace -> total_space
                disk_data = schemas.Disk.model_validate(disk)
                disks.append(disk_data)
                logger.debug(f"Добавлен диск для {hostname}: {disk_data}")
            except (ValueError, TypeError) as e:
                logger.error(f"Ошибка обработки диска для {hostname}: {str(e)}", exc_info=True)
                continue
        logger.debug(f"Обработано {len(disks)} дисков для {hostname}")
        return disks

    async def process_roles(self, raw_roles: List[str], hostname: str) -> List[schemas.Role]:
        """Обрабатывает список ролей."""
        roles = [schemas.Role(Name=str(role)) for role in raw_roles if str(role).strip()]
        logger.debug(f"Обработано {len(roles)} ролей для {hostname}")
        return roles

    async def prepare_computer_data_for_db(self, db: AsyncSession, raw_data: dict) -> Optional[schemas.ComputerCreate]:
        """Подготовка данных компьютера для сохранения в БД."""
        logger.debug(f"Получены сырые данные: {raw_data}")
        if not isinstance(raw_data, dict) or not raw_data:
            logger.error("Переданы невалидные или пустые данные")
            return None

        try:
            hostname = self.normalize_hostname(raw_data.get('hostname'))
            result = await db.execute(
                select(models.ADComputer).filter(models.ADComputer.hostname == hostname)
            )
            ad_comp = result.scalar_one_or_none()
            os_name = ad_comp.os_name if ad_comp else "Unknown"

            ip = raw_data.get("ip_address")
            if isinstance(ip, list):
                ip = ip[0] if ip else None
            mac = raw_data.get("mac_address")
            if isinstance(mac, list):
                mac = mac[0] if mac else None
            validated_data = schemas.ComputerCreate(
                hostname=hostname,
                ip=ip,
                os_name=os_name,
                os_version=str(raw_data.get("os_version", "")),
                cpu=str(raw_data.get("cpu", "")),
                ram=int(raw_data.get("ram", 0)) if raw_data.get("ram") else None,
                mac=mac,
                motherboard=str(raw_data.get("motherboard", "")),
                last_boot=str(raw_data.get("last_boot", "")),
                is_virtual=bool(raw_data.get("is_virtual", False)),
                check_status=raw_data.get("check_status", models.CheckStatus.unreachable.value),
                roles=await self.process_roles(raw_data.get("roles", []), hostname),
                software=await self.process_software_list(raw_data.get("software", []), hostname),
                disks=await self.process_disks(raw_data.get("disks", []), hostname)
            )
            logger.info(f"Подготовлены данные для {hostname}: {len(validated_data.software)} записей ПО")
            return validated_data
        except Exception as e:
            logger.error(f"Ошибка подготовки данных для {hostname}: {str(e)}", exc_info=True)
            return None

    async def upsert_computer_from_schema(self, comp_data: schemas.ComputerCreate, db: AsyncSession) -> Optional[models.Computer]:
        try:
            hostname = self.normalize_hostname(comp_data.hostname)
            logger.debug(f"Попытка upsert компьютера с hostname: {hostname}, данные: {comp_data.model_dump()}")
            computer_id = await self.repo.async_upsert_computer(comp_data, hostname)
            result = await db.execute(
                select(models.Computer).filter(models.Computer.id == computer_id)
            )
            db_computer = result.scalar_one_or_none()
            if db_computer:
                logger.info(f"Успешно сохранен компьютер: {hostname}")
            else:
                logger.error(f"Компьютер {hostname} не найден после сохранения")
            return db_computer
        except Exception as e:
            logger.error(f"Ошибка при upsert компьютера {hostname}: {str(e)}", exc_info=True)
            return None