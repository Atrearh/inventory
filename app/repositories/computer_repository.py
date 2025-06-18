from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
import logging
from .. import models, schemas
from ..models import Computer, Software, ChangeLog

logger = logging.getLogger(__name__)


class ComputerRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def async_log_change(self, computer_id: int, field: str, old_value: str, new_value: str) -> None:
            try:
                change_log = ChangeLog(
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

    async def _get_or_create_computer(self, computer_data: dict, hostname: str) -> Computer:
            """Получает существующий компьютер или создает новый."""
            existing_computer = await self.db.execute(
                select(Computer).where(Computer.hostname == hostname)
            )
            existing_computer = existing_computer.scalars().first()

            computer_data["last_updated"] = datetime.now()
            if existing_computer:
                for key, value in computer_data.items():
                    setattr(existing_computer, key, value)
                logger.info(f"Обновлены основные данные компьютера: {hostname}")
                return existing_computer
            else:
                new_computer = Computer(**computer_data)
                self.db.add(new_computer)
                await self.db.flush()
                logger.info(f"Создан новый компьютер: {hostname}")
                return new_computer

    async def _update_roles_async(self, db_computer: models.Computer, new_roles: List[schemas.Role]) -> None:
        """Обновляет роли компьютера с использованием массовых операций."""
        new_role_names = {r.name for r in new_roles}

        existing_roles = await self.db.execute(
            select(models.Role).where(
                models.Role.computer_id == db_computer.id)
        )
        existing_role_names = {r.name for r in existing_roles.scalars().all()}

        roles_to_delete = existing_role_names - new_role_names
        if roles_to_delete:
            await self.db.execute(
                delete(models.Role)
                .where(
                    models.Role.computer_id == db_computer.id,
                    models.Role.name.in_(roles_to_delete)
                )
            )
            logger.debug(
                f"Удалено {len(roles_to_delete)} ролей для {db_computer.hostname}")

        roles_to_add = new_role_names - existing_role_names
        if roles_to_add:
            new_role_objects = [
                models.Role(computer_id=db_computer.id, name=role_name)
                for role_name in roles_to_add
            ]
            self.db.add_all(new_role_objects)
            logger.debug(
                f"Добавлено {len(roles_to_add)} новых ролей для {db_computer.hostname}")

        await self.db.flush()

    async def _update_disks_async(self, db_computer: models.Computer, new_disks: List[schemas.Disk]) -> None:
        """Обновляет диски компьютера с использованием массовых операций."""
        new_disk_ids = {d.device_id for d in new_disks}
        new_disks_dict = {d.device_id: d for d in new_disks}

        existing_disks = await self.db.execute(
            select(models.Disk).where(
                models.Disk.computer_id == db_computer.id)
        )
        existing_disks_dict = {
            d.device_id: d for d in existing_disks.scalars().all()}

        disks_to_delete = set(existing_disks_dict.keys()) - new_disk_ids
        if disks_to_delete:
            await self.db.execute(
                delete(models.Disk)
                .where(
                    models.Disk.computer_id == db_computer.id,
                    models.Disk.device_id.in_(disks_to_delete)
                )
            )
            logger.debug(
                f"Удалено {len(disks_to_delete)} дисков для {db_computer.hostname}")

        new_disk_objects = []
        updates = []
        for device_id in new_disk_ids:
            if device_id not in existing_disks_dict:
                new_disk_objects.append(
                    models.Disk(
                        computer_id=db_computer.id,
                        device_id=device_id,
                        total_space=new_disks_dict[device_id].total_space,
                        free_space=new_disks_dict[device_id].free_space
                    )
                )
                logger.debug(
                    f"Добавлен новый диск {device_id} для {db_computer.hostname}")
            else:
                existing_disk = existing_disks_dict[device_id]
                new_disk = new_disks_dict[device_id]
                if (existing_disk.total_space != new_disk.total_space or
                        existing_disk.free_space != new_disk.free_space):
                    updates.append({
                        "id": existing_disk.id,
                        "total_space": new_disk.total_space,
                        "free_space": new_disk.free_space
                    })
                    logger.debug(
                        f"Обновлен диск {device_id} для {db_computer.hostname}")

        if new_disk_objects:
            self.db.add_all(new_disk_objects)
            logger.debug(
                f"Добавлено {len(new_disk_objects)} новых дисков для {db_computer.hostname}")

        if updates:
            for update_data in updates:
                await self.db.execute(
                    update(models.Disk)
                    .where(models.Disk.id == update_data["id"])
                    .values(
                        total_space=update_data["total_space"],
                        free_space=update_data["free_space"]
                    )
                )
            logger.debug(
                f"Обновлено {len(updates)} дисков для {db_computer.hostname}")

        await self.db.flush()

    async def _update_software_async(self, db_computer: models.Computer, new_software: List[schemas.Software], mode: str = "Full") -> None:
        """Обновляет программное обеспечение компьютера с учетом режима."""
        if not new_software:
            logger.debug(
                f"Данные о ПО отсутствуют для {db_computer.hostname}, обновление ПО пропущено")
            return

        for soft in new_software:
            existing_software = await self.db.execute(
                select(models.Software)
                .where(
                    models.Software.computer_id == db_computer.id,
                    models.Software.name.ilike(soft.name),
                    models.Software.version.ilike(
                        soft.version if soft.version else '')
                )
            )
            existing = existing_software.scalars().first()

            if mode == "Full" or soft.action == "Installed":
                if existing:
                    if (existing.version != soft.version or
                            existing.install_date != soft.install_date or
                            existing.is_deleted):
                        await self.async_log_change(
                            db_computer.id,
                            f"software_{soft.name}",
                            f"version: {existing.version}, install_date: {existing.install_date}, is_deleted: {existing.is_deleted}",
                            f"version: {soft.version}, install_date: {soft.install_date}, is_deleted: False"
                        )
                        await self.db.execute(
                            update(models.Software)
                            .where(models.Software.id == existing.id)
                            .values(
                                version=soft.version,
                                install_date=soft.install_date,
                                action=soft.action,
                                is_deleted=False
                            )
                        )
                        logger.debug(
                            f"Обновлено ПО {soft.name} для {db_computer.hostname}")
                else:
                    new_soft = models.Software(
                        computer_id=db_computer.id,
                        name=soft.name,
                        version=soft.version,
                        install_date=soft.install_date,
                        action=soft.action,
                        is_deleted=False
                    )
                    self.db.add(new_soft)
                    logger.debug(
                        f"Добавлено ПО {soft.name} для {db_computer.hostname}")
            elif soft.action == "Uninstalled":
                if existing and not existing.is_deleted:
                    await self.async_log_change(
                        db_computer.id,
                        f"software_{soft.name}",
                        f"version: {existing.version}, install_date: {existing.install_date}, is_deleted: {existing.is_deleted}",
                        "is_deleted: True"
                    )
                    await self.db.execute(
                        update(models.Software)
                        .where(models.Software.id == existing.id)
                        .values(
                            action=soft.action,
                            is_deleted=True
                        )
                    )
                    logger.debug(
                        f"Пометка удаления ПО {soft.name} для {db_computer.hostname}")

        await self.db.flush()

    async def clean_old_deleted_software(self) -> int:
        """Удаляет записи о ПО с is_deleted=True, старше 6 месяцев."""
        try:
            threshold = datetime.utcnow() - timedelta(days=180)
            result = await self.db.execute(
                delete(models.Software)
                .where(
                    models.Software.is_deleted == True,
                    models.Software.install_date < threshold
                )
                .returning(models.Software.id)
            )
            deleted_count = len(result.fetchall())
            await self.db.commit()
            logger.info(
                f"Удалено {deleted_count} записей о ПО с is_deleted=True, старше 6 месяцев")
            return deleted_count
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"Ошибка очистки старых записей ПО: {str(e)}", exc_info=True)
            raise

    async def async_upsert_computer(self, computer: schemas.ComputerCreate, hostname: str, mode: str = "Full") -> int:
        """Добавляет или обновляет компьютер и связанные данные."""
        try:
            computer_data = computer.model_dump(exclude_unset=True, exclude={
                                                "roles", "disks", "software"})
            computer_data["last_updated"] = datetime.now()
            db_computer = await self._get_or_create_computer(computer_data, hostname)
            computer_id = db_computer.id

            if computer.roles:
                await self._update_roles_async(db_computer, computer.roles)
            if computer.disks:
                await self._update_disks_async(db_computer, computer.disks)
            if computer.software:
                await self._update_software_async(db_computer, computer.software, mode=mode)

            await self.db.commit()
            logger.info(f"Успешно сохранен компьютер: {hostname}")
            return computer_id
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(
                f"Ошибка базы данных при сохранении компьютера {hostname}: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"Ошибка сохранения компьютера {hostname}: {str(e)}", exc_info=True)
            raise

    async def async_get_hosts_for_polling(self, days_threshold: int = 1) -> List[str]:
        """Получение списка хостов для проверки."""
        threshold = datetime.now() - timedelta(days=days_threshold)
        query = (
            select(models.ADComputer.hostname)
            .outerjoin(models.Computer, models.ADComputer.hostname == models.Computer.hostname)
            .filter(
                models.ADComputer.enabled == True,
                (models.Computer.last_updated < threshold) | (
                    models.Computer.last_updated == None)
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
                select(models.Computer).filter(
                    models.Computer.hostname == hostname)
            )
            db_computer = result.scalar_one_or_none()
            if db_computer:
                old_status = db_computer.check_status
                try:
                    new_check_status = models.CheckStatus(check_status)
                except ValueError:
                    logger.error(
                        f"Недопустимое значение check_status: {check_status}")
                    return None
                if old_status != new_check_status:
                    db_computer.check_status = new_check_status
                    db_computer.last_updated = datetime.now()
                    await self.async_log_change(db_computer.id, "check_status", str(old_status), str(new_check_status))
                    await self.db.commit()
                    await self.db.refresh(db_computer)
                    logger.info(
                        f"Обновлен check_status для {hostname}: {new_check_status}")
                return db_computer
            return None
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"Ошибка обновления check_status для {hostname}: {str(e)}", exc_info=True)
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
            id: Optional[int] = None,
            hostname: Optional[str] = None,
            os_version: Optional[str] = None,
            check_status: Optional[str] = None,
            page: int = 1,
            limit: int = 10,
            sort_by: str = "hostname",
            sort_order: str = "asc"
        ) -> Tuple[List[Computer], int]:
            """Получает список компьютеров с пагинацией и фильтрацией."""
            logger.debug(
                f"Запрос компьютеров: id={id}, hostname={hostname}, os_version={os_version}, check_status={check_status}, page={page}"
            )
            try:
                # Основной запрос без join с software
                stmt = select(Computer).options(
                    joinedload(Computer.roles),
                    joinedload(Computer.disks),
                    joinedload(Computer.software                   #joinedload(Computer.software.and_(Software.is_deleted.is_(False))).load_only(  
                        #Software.id, Software.computer_id,Software.name, Software.version,Software.install_date, Software.action,   Software.is_deleted
                    )
                )

                # Фильтрация
                if id:
                    stmt = stmt.filter(Computer.id == id)
                if hostname:
                    stmt = stmt.filter(Computer.hostname.ilike(f"%{hostname}%"))
                if os_version:
                    stmt = stmt.filter(Computer.os_version.ilike(f"%{os_version}%"))
                if check_status:
                    stmt = stmt.filter(Computer.check_status == check_status)

                # Подсчёт общего количества записей
                count_stmt = select(func.count()).select_from(Computer)
                if id:
                    count_stmt = count_stmt.filter(Computer.id == id)
                if hostname:
                    count_stmt = count_stmt.filter(Computer.hostname.ilike(f"%{hostname}%"))
                if os_version:
                    count_stmt = count_stmt.filter(Computer.os_version.ilike(f"%{os_version}%"))
                if check_status:
                    count_stmt = count_stmt.filter(Computer.check_status == check_status)

                total = (await self.db.execute(count_stmt)).scalar_one()

                # Сортировка
                sort_column = getattr(Computer, sort_by, Computer.hostname)
                if sort_order.lower() == "desc":
                    sort_column = sort_column.desc()
                stmt = stmt.order_by(sort_column)

                # Пагинация
                stmt = stmt.offset((page - 1) * limit).limit(limit)

                result = await self.db.execute(stmt)
                computers = result.unique().scalars().all()
                for c in computers:
                    logger.debug(f"Компьютер {c.id}: roles={len(c.roles)}, software={len(c.software)}, disks={len(c.disks)}")

                return computers, total
            except SQLAlchemyError as e:
                logger.error(f"Ошибка базы данных при получении компьютеров: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"Неизвестная ошибка при получении компьютеров: {str(e)}")
                raise