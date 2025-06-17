# app/repositories/computer_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, func
from .. import models, schemas
import logging
from typing import List, Optional,Tuple
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from datetime import timedelta
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import joinedload

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
                changed_at=datetime.now()
            )
            self.db.add(change_log)
            await self.db.flush()
            logger.debug(f"Логировано изменение для computer_id={computer_id}, поле={field}: {old_value} -> {new_value}")
        except Exception as e:
            logger.error(f"Ошибка логирования изменения для computer_id={computer_id}: {str(e)}", exc_info=True)

    async def _get_or_create_computer(self, computer_data: dict, hostname: str) -> models.Computer:
        """Получает существующий компьютер или создает новый."""
        existing_computer = await self.db.execute(
            select(models.Computer).where(models.Computer.hostname == hostname)
        )
        existing_computer = existing_computer.scalars().first()

        computer_data["last_updated"] = datetime.now()
        if existing_computer:
            for key, value in computer_data.items():
                setattr(existing_computer, key, value)
            logger.info(f"Обновлены основные данные компьютера: {hostname}")
            return existing_computer
        else:
            new_computer = models.Computer(**computer_data)
            self.db.add(new_computer)
            await self.db.flush()
            logger.info(f"Создан новый компьютер: {hostname}")
            return new_computer

    async def _update_roles_async(self, db_computer: models.Computer, new_roles: List[schemas.Role]) -> None:
        """Обновляет роли компьютера."""
        existing_roles = await self.db.execute(
            select(models.Role).where(models.Role.computer_id == db_computer.id)
        )
        existing_role_names = {r.name for r in existing_roles.scalars().all()}
        new_role_names = {r.name for r in new_roles}

        if existing_role_names != new_role_names:
            await self.db.execute(
                delete(models.Role).where(models.Role.computer_id == db_computer.id)
            )
            for role in new_roles:
                self.db.add(models.Role(computer_id=db_computer.id, name=role.name))
            await self.db.flush()
            logger.debug(f"Обновлены роли для {db_computer.hostname}")

    async def _update_disks_async(self, db_computer: models.Computer, new_disks: List[schemas.Disk]) -> None:
        """Обновляет диски компьютера."""
        existing_disks = await self.db.execute(
            select(models.Disk).where(models.Disk.computer_id == db_computer.id)
        )
        existing_disks_dict = {d.device_id: d for d in existing_disks.scalars().all()}
        new_disk_ids = {d.device_id for d in new_disks}

        for device_id in existing_disks_dict:
            if device_id not in new_disk_ids:
                await self.db.execute(
                    delete(models.Disk).where(
                        models.Disk.computer_id == db_computer.id,
                        models.Disk.device_id == device_id
                    )
                )
                logger.debug(f"Удалён диск {device_id} для {db_computer.hostname}")

        for disk in new_disks:
            if disk.device_id in existing_disks_dict:
                await self.db.execute(
                    update(models.Disk)
                    .where(
                        models.Disk.computer_id == db_computer.id,
                        models.Disk.device_id == disk.device_id
                    )
                    .values(
                        total_space=disk.total_space,
                        free_space=disk.free_space
                    )
                )
                logger.debug(f"Обновлён диск {disk.device_id} для {db_computer.hostname}")
            else:
                new_disk = models.Disk(
                    computer_id=db_computer.id,
                    device_id=disk.device_id,
                    total_space=disk.total_space,
                    free_space=disk.free_space
                )
                self.db.add(new_disk)
                logger.debug(f"Добавлен новый диск {disk.device_id} для {db_computer.hostname}")

        await self.db.flush()

    async def _update_software_async(self, db_computer: models.Computer, new_software: List[schemas.Software]) -> None:
        """Обновляет программное обеспечение компьютера."""
        if not new_software:
            logger.debug(f"Данные о ПО отсутствуют для {db_computer.hostname}, обновление ПО пропущено")
            return

        existing_software = await self.db.execute(
            select(models.Software).where(models.Software.computer_id == db_computer.id)
        )
        existing_software_dict = {
            (s.name.strip().lower(), s.version.strip().lower() if s.version else ''): s
            for s in existing_software.scalars().all()
        }
        new_software_keys = {
            (soft.name.strip().lower(), soft.version.strip().lower() if soft.version else '')
            for soft in new_software
        }

        for key, soft in existing_software_dict.items():
            if key not in new_software_keys:
                await self.db.delete(soft)
                logger.debug(f"Удалено ПО {soft.name} для {db_computer.hostname}")

        for soft in new_software:
            key = (soft.name.strip().lower(), soft.version.strip().lower() if soft.version else '')
            if key not in existing_software_dict:
                new_soft = models.Software(
                    computer_id=db_computer.id,
                    name=soft.name,
                    version=soft.version,
                    install_date=soft.install_date
                )
                self.db.add(new_soft)
                logger.debug(f"Добавлено ПО {soft.name} для {db_computer.hostname}")
            else:
                existing = existing_software_dict[key]
                if existing.version != soft.version or existing.install_date != soft.install_date:
                    await self.async_log_change(
                        db_computer.id,
                        f"software_{soft.name}",
                        f"version: {existing.version}, install_date: {existing.install_date}",
                        f"version: {soft.version}, install_date: {soft.install_date}"
                    )
                    existing.version = soft.version
                    existing.install_date = soft.install_date

        await self.db.flush()

    async def async_upsert_computer(self, computer: schemas.ComputerCreate, hostname: str) -> int:
        """Добавляет или обновляет компьютер и связанные данные."""
        try:
            # Подготовка данных компьютера
            computer_data = computer.model_dump(exclude_unset=True, exclude={"roles", "disks", "software"})
            computer_data["last_updated"] = datetime.now()
            # Получение или создание записи компьютера
            db_computer = await self._get_or_create_computer(computer_data, hostname)
            computer_id = db_computer.id

            # Обновление связанных данных
            if computer.roles:
                await self._update_roles_async(db_computer, computer.roles)
            if computer.disks:
                await self._update_disks_async(db_computer, computer.disks)
            if computer.software:
                await self._update_software_async(db_computer, computer.software)

            await self.db.commit()
            logger.info(f"Успешно сохранен компьютер: {hostname}")
            return computer_id

        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Ошибка базы данных при сохранении компьютера {hostname}: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Ошибка сохранения компьютера {hostname}: {str(e)}", exc_info=True)
            raise

    async def async_get_hosts_for_polling(self, days_threshold: int = 1) -> List[str]:
        """Получение списка хостов для проверки."""
        threshold = datetime.now() - timedelta(days=days_threshold)
        query = (
            select(models.ADComputer.hostname)
            .outerjoin(models.Computer, models.ADComputer.hostname == models.Computer.hostname)
            .filter(
                models.ADComputer.enabled == True,
                (models.Computer.last_updated < threshold) | (models.Computer.last_updated == None)
            )
        )
        result = await self.db.execute(query)
        hosts = [row.hostname for row in result.all()]
        logger.info(f"Найдено {len(hosts)} хостов для проверки")
        return hosts
    
    async def async_update_computer_check_status(self, hostname: str, check_status: str) -> Optional[models.Computer]:
        """Обновляет check_status для компьютера."""
        try:
            result = await self.db.execute(
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
                    db_computer.last_updated = datetime.now()
                    await self.async_log_change(db_computer.id, "check_status", str(old_status), str(new_check_status))
                    await self.db.commit()
                    await self.db.refresh(db_computer)
                    logger.info(f"Обновлен check_status для {hostname}: {new_check_status}")
                return db_computer
            return None
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Ошибка обновления check_status для {hostname}: {str(e)}", exc_info=True)
            return None
        
    async def async_get_change_log(self, computer_id: int) -> List[models.ChangeLog]:
        """Получает историю изменений."""
        logger.debug(f"Запрос истории для computer_id: {computer_id}")
        result = await self.db.execute(
            select(models.ChangeLog)
            .filter(models.ChangeLog.computer_id == computer_id)
            .order_by(models.ChangeLog.changed_at.desc())
        )
        return result.scalars().all()
    
    async def async_upsert_ad_computer(self, computer_data: dict) -> models.Computer:
        """Добавляет или обновляет запись о компьютере из AD."""
        try:
            result = await self.db.execute(
                select(models.ADComputer).filter(
                    models.ADComputer.hostname == computer_data["hostname"])
            )
            db_comp = result.scalar_one_or_none()
            current_time = datetime.now()
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
                self.db.add(db_comp)

            await self.db.commit()
            await self.db.refresh(db_comp)
            logger.info(
                f"{'Обновлен' if db_comp.id else 'Создан'} AD компьютер: {computer_data['hostname']}")
            return db_comp
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"Ошибка при обновлении AD компьютера {computer_data['hostname']}: {str(e)}")
            raise    

    async def get_computers(
            self,
            sort_by: str,
            sort_order: str,
            hostname: Optional[str],
            os_version: Optional[str],
            check_status: Optional[str],
            page: int,
            limit: int,
            id: Optional[int] = None
        ) -> Tuple[List[models.Computer], int]:
            """Получает список компьютеров с фильтрацией, сортировкой и пагинацией."""
            logger.debug(f"Запрос компьютеров: id={id}, hostname={hostname}, page={page}")
            query = select(models.Computer).options(
                joinedload(models.Computer.disks),
                joinedload(models.Computer.roles),
                joinedload(models.Computer.software)
            )
            if id is not None:
                query = query.filter(models.Computer.id == id)
            if hostname and hostname.strip():
                query = query.filter(models.Computer.hostname.ilike(f"%{hostname.strip()}%"))
            if os_version and os_version.strip():
                query = query.filter(models.Computer.os_version.ilike(f"%{os_version.strip()}%"))
            if check_status is not None:
                query = query.filter(models.Computer.check_status == check_status)

            count_query = select(func.count()).select_from(query.subquery())
            total = (await self.db.execute(count_query)).scalar() or 0

            if sort_by in models.Computer.__table__.columns:
                sort_column = getattr(models.Computer, sort_by)
                query = query.order_by(
                    sort_column.asc() if sort_order.lower() == "asc" else sort_column.desc()
                )

            query = query.offset((page - 1) * limit).limit(limit)
            result = await self.db.execute(query)
            computers = result.scalars().unique().all()
            for comp in computers:
                logger.debug(f"Компьютер {comp.id}: roles={len(comp.roles)}, software={len(comp.software)}, disks={len(comp.disks)}")
            return computers, total