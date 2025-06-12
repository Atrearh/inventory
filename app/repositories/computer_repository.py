# app/repositories/computer_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from .. import models, schemas
import logging
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, delete, update
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class ComputerRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def async_log_change(self, computer_id: int, field: str, old_value: str, new_value: str) -> None:
        try:
            change_log = models.ChangeLog(
                computer_id=computer_id,
                field=field,
                old_value=str(old_value)[:255],
                new_value=str(new_value)[:255],
                changed_at=datetime.now(timezone.utc)
            )
            self.db.add(change_log)
            await self.db.flush()
            logger.debug(
                f"Логировано изменение для computer_id={computer_id}, поле={field}: {old_value} -> {new_value}")
        except Exception as e:
            logger.error(
                f"Ошибка логирования изменения для computer_id={computer_id}: {str(e)}", exc_info=True)

    async def _update_roles_async(self, db: AsyncSession, db_comp: models.Computer, new_roles: List[schemas.Role]) -> None:
        result = await db.execute(
            select(models.Role).filter(models.Role.computer_id == db_comp.id)
        )
        # Остаётся r.name, так как это модель SQLAlchemy
        existing_roles = {r.name: r for r in result.scalars().all()}
        # Остаётся r.Name, так как это Pydantic-схема
        new_role_names = {r.Name for r in new_roles}

        if existing_roles and set(existing_roles.keys()) == new_role_names:
            logger.debug(
                f"Роли для {db_comp.hostname} уже актуальны, пропуск обновления")
            return

        roles_to_delete = [
            r for name, r in existing_roles.items() if name not in new_role_names]
        if roles_to_delete:
            for role in roles_to_delete:
                await db.delete(role)
            await db.flush()
            logger.debug(
                f"Удалено {len(roles_to_delete)} ролей для {db_comp.hostname}")

        new_roles_to_add = [
            # Остаётся role.Name
            models.Role(computer_id=db_comp.id, name=role.Name)
            for role in new_roles
            if role.Name not in existing_roles
        ]
        if new_roles_to_add:
            db.add_all(new_roles_to_add)
            await db.flush()
            logger.debug(
                f"Добавлено {len(new_roles_to_add)} новых ролей для {db_comp.hostname}")

    async def _update_disks_async(self, db: AsyncSession, db_comp: models.Computer, new_disks: List[schemas.Disk]) -> None:
        result = await db.execute(
            select(models.Disk).filter(models.Disk.computer_id == db_comp.id)
        )
        # Изменено с DeviceID на device_id
        existing_disks = {d.device_id: d for d in result.scalars().all()}
        new_disk_ids = {d.device_id for d in new_disks}  # Изменено с DeviceID

        disks_to_delete = [
            d for device_id, d in existing_disks.items() if device_id not in new_disk_ids]
        if disks_to_delete:
            for disk in disks_to_delete:
                await db.delete(disk)
            await db.flush()
            logger.debug(
                f"Удалено {len(disks_to_delete)} дисков для {db_comp.hostname}")

        new_disks_to_add = [
            models.Disk(
                computer_id=db_comp.id,
                device_id=disk.device_id,  # Изменено с DeviceID
                total_space=disk.TotalSpace,
                free_space=disk.FreeSpace
            )
            for disk in new_disks
            if disk.device_id not in existing_disks  # Изменено с DeviceID
        ]
        if new_disks_to_add:
            db.add_all(new_disks_to_add)
            await db.flush()
            logger.debug(
                f"Добавлено {len(new_disks_to_add)} новых дисков для {db_comp.hostname}")

    async def _update_software_async(self, db: AsyncSession, db_comp: models.Computer, new_software: List[schemas.Software]) -> None:
        """Обновляет программное обеспечение компьютера пакетно."""
        if not new_software:
            logger.debug(f"Данные о ПО отсутствуют для {db_comp.hostname}, обновление ПО пропущено")
            return

        # Получаем существующее ПО
        result = await db.execute(
            select(models.Software).filter(models.Software.computer_id == db_comp.id)
        )
        existing_software = {
            (s.name.strip().lower(), s.version.strip().lower() if s.version else ''): s
            for s in result.scalars().all()
        }
        new_software_keys = {
            (soft.name.strip().lower(), soft.version.strip().lower() if soft.version else '')  # Исправлено: soft.name и soft.version
            for soft in new_software
        }

        # Удаляем ПО, которое больше не нужно
        software_to_delete = [
            s for key, s in existing_software.items() if key not in new_software_keys]
        if software_to_delete:
            for soft in software_to_delete:
                await db.delete(soft)
            await db.flush()
            logger.debug(f"Удалено {len(software_to_delete)} записей ПО для {db_comp.hostname}")

        # Добавляем или обновляем ПО
        software_to_add = []
        for soft in new_software:
            key = (soft.name.strip().lower(), soft.version.strip().lower() if soft.version else '')  # Исправлено: soft.name и soft.version
            if key not in existing_software:
                software_to_add.append(
                    models.Software(
                        computer_id=db_comp.id,
                        name=soft.name,  # Исправлено: soft.name
                        version=soft.version,  # Исправлено: soft.version
                        install_date=soft.install_date
                    )
                )
            else:
                existing = existing_software[key]
                if existing.version != soft.version or existing.install_date != soft.install_date:
                    await self.async_log_change(
                        db_comp.id,  # Исправлено: убрали db, так как метод использует self.db
                        f"software_{soft.name}",  # Исправлено: soft.name
                        f"version: {existing.version}, install_date: {existing.install_date}",
                        f"version: {soft.version}, install_date: {soft.install_date}"
                    )
                    existing.version = soft.version
                    existing.install_date = soft.install_date

        if software_to_add:
            db.add_all(software_to_add)
            await db.flush()
            logger.debug(f"Добавлено {len(software_to_add)} новых записей ПО для {db_comp.hostname}")

    async def async_upsert_computer(self, computer: schemas.ComputerCreate, hostname: str) -> int:
            try:
                existing_computer = await self.db.execute(
                    select(models.Computer).where(models.Computer.hostname == hostname)
                )
                existing_computer = existing_computer.scalars().first()
                computer_data = computer.model_dump(exclude_unset=True, exclude={"roles", "disks", "software"})
                computer_data["last_updated"] = datetime.now(timezone.utc)

                if existing_computer:
                    for key, value in computer_data.items():
                        setattr(existing_computer, key, value)
                    computer_id = existing_computer.id
                    logger.info(f"Обновлены основные данные компьютера: {hostname}")
                else:
                    new_computer = models.Computer(**computer_data)
                    self.db.add(new_computer)
                    await self.db.flush()
                    computer_id = new_computer.id
                    logger.info(f"Создан новый компьютер: {hostname}")

                # Обновление ролей
                if computer.roles:
                    existing_roles = await self.db.execute(
                        select(models.Role).where(models.Role.computer_id == computer_id)
                    )
                    existing_role_names = {role.name for role in existing_roles.scalars().all()}
                    new_role_names = {role.name for role in computer.roles}  # Исправлено: role.name вместо role.Name

                    if existing_role_names != new_role_names:
                        await self.db.execute(
                            delete(models.Role).where(models.Role.computer_id == computer_id)
                        )
                        for role in computer.roles:
                            self.db.add(models.Role(computer_id=computer_id, name=role.name))  # Исправлено: role.name
                        logger.debug(f"Обновлены роли для {hostname}")
                    else:
                        logger.debug(f"Роли для {hostname} уже актуальны, пропуск обновления")

                # Обновление дисков
                if computer.disks:
                    logger.debug(f"Обновление дисков для {hostname}: {computer.disks}")
                    existing_disks = await self.db.execute(
                        select(models.Disk).where(models.Disk.computer_id == computer_id)
                    )
                    existing_disks_dict = {disk.device_id: disk for disk in existing_disks.scalars().all()}

                    for disk in computer.disks:
                        logger.debug(f"Обработка диска {disk.device_id} для {hostname}: TotalSpace={disk.total_space}, FreeSpace={disk.free_space}")
                        if disk.device_id in existing_disks_dict:
                            await self.db.execute(
                                update(models.Disk)
                                .where(
                                    models.Disk.computer_id == computer_id,
                                    models.Disk.device_id == disk.device_id
                                )
                                .values(
                                    total_space=disk.total_space,
                                    free_space=disk.free_space
                                )
                            )
                            logger.debug(f"Обновлён диск {disk.device_id} для {hostname}")
                        else:
                            new_disk = models.Disk(
                                computer_id=computer_id,
                                device_id=disk.device_id,
                                total_space=disk.total_space,
                                free_space=disk.free_space
                            )
                            self.db.add(new_disk)
                            logger.debug(f"Добавлен новый диск {disk.device_id} для {hostname}")

                        for device_id in existing_disks_dict:
                            if device_id not in {disk.device_id for disk in computer.disks}:
                                await self.db.execute(
                                    delete(models.Disk).where(
                                        models.Disk.computer_id == computer_id,
                                        models.Disk.device_id == device_id
                                    )
                                )
                                logger.debug(f"Удалён диск {device_id} для {hostname}")
                else:
                    logger.warning(f"Данные о дисках отсутствуют для {hostname}")

                # Обновление ПО
                if computer.software:
                    await self._update_software_async(self.db, existing_computer or new_computer, computer.software)
                    logger.debug(f"Обновлено ПО для {hostname}")
                else:
                    logger.debug(f"Данные о ПО отсутствуют для {hostname}, обновление ПО пропущено")

                await self.db.commit()
                logger.info(f"Успешно сохранен компьютер: {hostname}")
                return computer_id
            except SQLAlchemyError as e:
                await self.db.rollback()
                logger.error(f"Ошибка базы данных при сохранении компьютера {hostname}: {str(e)}",ighest=True)
                raise
            except Exception as e:
                await self.db.rollback()
                logger.error(f"Ошибка сохранения компьютера {hostname}: {str(e)}", exc_info=True)
                raise

    async def async_update_computer_check_status(self, db: AsyncSession, hostname: str, check_status: str) -> Optional[models.Computer]:
        """Обновляет check_status для компьютера."""
        try:
            result = await db.execute(
                select(models.Computer).filter(models.Computer.hostname == hostname)
            )
            db_computer = result.scalar_one_or_none()
            if db_computer:
                old_status = db_computer.check_status
                try:
                    new_check_status = models.CheckStatus(check_status)
                except ValueError:
                    logger.error(f"Недопустимое значение check_status: {check_status}")
                    return None
                if old_status != new_check_status:
                    db_computer.check_status = new_check_status
                    db_computer.last_updated = datetime.now(timezone.utc)
                    await self.async_log_change(db_computer.id, "check_status", str(old_status), str(new_check_status))  # Исправлено: убрали db
                    await db.commit()
                    await db.refresh(db_computer)
                    logger.info(f"Обновлен check_status для {hostname}: {new_check_status}")
                return db_computer
            return None
        except Exception as e:
            await db.rollback()
            logger.error(f"Ошибка обновления check_status для {hostname}: {str(e)}", exc_info=True)
            return None

    async def async_get_change_log(self, db: AsyncSession, computer_id: int) -> List[models.ChangeLog]:
        """Получает историю изменений."""
        result = await db.execute(
            select(models.ChangeLog)
            .filter(models.ChangeLog.computer_id == computer_id)
            .order_by(models.ChangeLog.changed_at.desc())
        )
        return result.scalars().all()

    async def async_upsert_ad_computer(self, db: AsyncSession, computer_data: dict) -> models.Computer:
        """Добавляет или обновляет запись о компьютере из AD."""
        try:
            result = await db.execute(
                select(models.ADComputer).filter(
                    models.ADComputer.hostname == computer_data["hostname"])
            )
            db_comp = result.scalar_one_or_none()
            current_time = datetime.now(timezone.utc)
            if db_comp:
                db_comp.os_name = computer_data["os_name"]
                db_comp.object_guid = computer_data["object_guid"]
                db_comp.when_created = computer_data["when_created"]
                db_comp.when_changed = computer_data["when_changed"]
                db_comp.enabled = computer_data["enabled"]
                db_comp.last_updated = current_time
            else:
                db_comp = models.ADComputer(
                    hostname=computer_data["hostname"],
                    os_name=computer_data["os_name"],
                    object_guid=computer_data["object_guid"],
                    when_created=computer_data["when_created"],
                    when_changed=computer_data["when_changed"],
                    enabled=computer_data["enabled"],
                    last_updated=current_time
                )
                db.add(db_comp)

            await db.commit()
            await db.refresh(db_comp)
            logger.info(
                f"{'Обновлен' if db_comp.id else 'Создан'} AD компьютер: {computer_data['hostname']}")
            return db_comp
        except Exception as e:
            await db.rollback()
            logger.error(
                f"Ошибка при обновлении AD компьютера {computer_data['hostname']}: {str(e)}")
            raise

    async def async_get_hosts_for_polling(self, db: AsyncSession, days_threshold: int = 1) -> List[str]:
        """Получение списка хостов для проверки."""
        threshold = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        query = (
            select(models.ADComputer.hostname)
            .outerjoin(models.Computer, models.ADComputer.hostname == models.Computer.hostname)
            .filter(
                models.ADComputer.enabled == True,
                (models.Computer.last_updated < threshold) | (
                    models.Computer.last_updated == None)
            )
        )
        result = await db.execute(query)
        hosts = [row.hostname for row in result.all()]
        logger.info(f"Найдено {len(hosts)} хостов для проверки")
        return hosts
