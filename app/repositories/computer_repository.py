# app/repositories/computer_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
import logging
from .. import models, schemas
from ..models import Computer

logger = logging.getLogger(__name__)

class ComputerRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def async_log_change(self, computer_id: int, field: str, old_value: str, new_value: str) -> None:
        """Логирует изменение данных компьютера."""
        try:
            change_log = models.ChangeLog(
                computer_id=computer_id,
                field=field,
                old_value=str(old_value)[:255],
                new_value=str(new_value)[:255],
                changed_at=datetime.utcnow()
            )
            self.db.add(change_log)
            logger.debug(f"Логировано изменение: computer_id={computer_id}, field={field}")
        except Exception as e:
            logger.error(f"Ошибка логирования: {str(e)}")
            raise

    async def _get_or_create_computer(self, computer_data: dict, hostname: str) -> Computer:
        """Получает существующий компьютер или создает новый."""
        try:
            result = await self.db.execute(
                select(Computer).where(Computer.hostname == hostname)
            )
            existing_computer = result.scalars().first()

            # Обновляем last_full_scan для полного сканирования
            computer_data["last_updated"] = datetime.utcnow()
            if computer_data.get("check_status") == "success":
                computer_data["last_full_scan"] = datetime.utcnow()

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
        except Exception as e:
            logger.error(f"Ошибка при получении/создании компьютера {hostname}: {str(e)}")
            raise

    async def _update_roles_async(self, db_computer: models.Computer, new_roles: List[schemas.Role]) -> None:
        """Обновляет роли компьютера с использованием массовых операций."""
        try:
            new_role_names = {r.name for r in new_roles}

            result = await self.db.execute(
                select(models.Role).where(models.Role.computer_id == db_computer.id)
            )
            existing_role_names = {r.name for r in result.scalars().all()}

            roles_to_delete = existing_role_names - new_role_names
            if roles_to_delete:
                await self.db.execute(
                    delete(models.Role)
                    .where(
                        models.Role.computer_id == db_computer.id,
                        models.Role.name.in_(roles_to_delete)
                    )
                )
                logger.debug(f"Удалено {len(roles_to_delete)} ролей для {db_computer.hostname}")

            roles_to_add = new_role_names - existing_role_names
            if roles_to_add:
                new_role_objects = [
                    models.Role(computer_id=db_computer.id, name=role_name)
                    for role_name in roles_to_add
                ]
                self.db.add_all(new_role_objects)
                logger.debug(f"Добавлено {len(roles_to_add)} новых ролей для {db_computer.hostname}")

            await self.db.flush()
        except Exception as e:
            logger.error(f"Ошибка при обновлении ролей для {db_computer.hostname}: {str(e)}")
            raise

    async def _update_disks_async(self, db_computer: models.Computer, new_disks: List[schemas.Disk]) -> None:
        """Обновляет диски компьютера с использованием массовых операций."""
        try:
            new_disk_ids = {d.device_id for d in new_disks}
            new_disks_dict = {d.device_id: d for d in new_disks}

            result = await self.db.execute(
                select(models.Disk).where(models.Disk.computer_id == db_computer.id)
            )
            existing_disks_dict = {d.device_id: d for d in result.scalars().all()}

            disks_to_delete = set(existing_disks_dict.keys()) - new_disk_ids
            if disks_to_delete:
                await self.db.execute(
                    delete(models.Disk)
                    .where(
                        models.Disk.computer_id == db_computer.id,
                        models.Disk.device_id.in_(disks_to_delete)
                    )
                )
                logger.debug(f"Удалено {len(disks_to_delete)} дисков для {db_computer.hostname}")

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
                    logger.debug(f"Добавлен новый диск {device_id} для {db_computer.hostname}")
                else:
                    existing_disk = existing_disks_dict[device_id]
                    new_disk = new_disks_dict[device_id]
                    if (
                        existing_disk.total_space != new_disk.total_space or
                        existing_disk.free_space != new_disk.free_space
                    ):
                        updates.append({
                            "id": existing_disk.id,
                            "total_space": new_disk.total_space,
                            "free_space": new_disk.free_space
                        })
                        logger.debug(f"Обновлен диск {device_id} для {db_computer.hostname}")

            if new_disk_objects:
                self.db.add_all(new_disk_objects)
                logger.debug(f"Добавлено {len(new_disk_objects)} новых дисков для {db_computer.hostname}")

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
                logger.debug(f"Обновлено {len(updates)} дисков для {db_computer.hostname}")

            await self.db.flush()
        except Exception as e:
            logger.error(f"Ошибка при обновлении дисков для {db_computer.hostname}: {str(e)}")
            raise

    async def _update_software_async(self, db_computer: models.Computer, new_software: List[schemas.Software], mode: str = "Full") -> None:
        """Обновляет программное обеспечение компьютера с учетом режима."""
        if not new_software:
            logger.debug(f"Данные о ПО отсутствуют для {db_computer.hostname}, обновление ПО пропущено")
            return

        try:
            # Получаем все существующие записи ПО для компьютера одним запросом
            result = await self.db.execute(
                select(models.Software).where(models.Software.computer_id == db_computer.id)
            )
            existing_software = result.scalars().all()
            # Создаем словарь для быстрого доступа: ключ — (name, version), значение — объект Software
            existing_software_dict = {
                (s.name.lower(), s.version.lower() if s.version else ''): s
                for s in existing_software
            }

            new_entries = []
            updates = []

            for soft in new_software:
                key = (soft.name.lower(), soft.version.lower() if soft.version else '')
                existing = existing_software_dict.get(key)

                if mode == "Full" or soft.action == "Installed":
                    if existing:
                        if (
                            existing.version != soft.version or
                            existing.install_date != soft.install_date or
                            existing.is_deleted
                        ):
                            await self.async_log_change(
                                db_computer.id,
                                f"software_{soft.name}",
                                f"version: {existing.version}, install_date: {existing.install_date}, is_deleted: {existing.is_deleted}",
                                f"version: {soft.version}, install_date: {soft.install_date}, is_deleted: False"
                            )
                            updates.append({
                                "id": existing.id,
                                "version": soft.version,
                                "install_date": soft.install_date,
                                "action": soft.action,
                                "is_deleted": False
                            })
                            logger.debug(f"Обновлено ПО {soft.name} для {db_computer.hostname}")
                    else:
                        new_soft = models.Software(
                            computer_id=db_computer.id,
                            name=soft.name,
                            version=soft.version,
                            install_date=soft.install_date,
                            action=soft.action,
                            is_deleted=False
                        )
                        new_entries.append(new_soft)
                        logger.debug(f"Добавлено ПО {soft.name} для {db_computer.hostname}")
                elif soft.action == "Uninstalled":
                    if existing and not existing.is_deleted:
                        await self.async_log_change(
                            db_computer.id,
                            f"software_{soft.name}",
                            f"version: {existing.version}, install_date: {existing.install_date}, is_deleted: {existing.is_deleted}",
                            "is_deleted: True"
                        )
                        updates.append({
                            "id": existing.id,
                            "action": soft.action,
                            "is_deleted": True
                        })
                        logger.debug(f"Пометка удаления ПО {soft.name} для {db_computer.hostname}")

            # Добавляем новые записи
            if new_entries:
                self.db.add_all(new_entries)
                logger.debug(f"Добавлено {len(new_entries)} новых ПО для {db_computer.hostname}")

            # Выполняем массовое обновление существующих записей
            if updates:
                for update_data in updates:
                    await self.db.execute(
                        update(models.Software)
                        .where(models.Software.id == update_data["id"])
                        .values(
                            version=update_data.get("version"),
                            install_date=update_data.get("install_date"),
                            action=update_data.get("action"),
                            is_deleted=update_data["is_deleted"]
                        )
                    )
                logger.debug(f"Обновлено {len(updates)} ПО для {db_computer.hostname}")

            await self.db.flush()
        except Exception as e:
            logger.error(f"Ошибка при обновлении ПО для {db_computer.hostname}: {str(e)}")
            raise

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
            logger.info(f"Удалено {deleted_count} записей о ПО с is_deleted=True, старше 6 месяцев")
            return deleted_count
        except Exception as e:
            logger.error(f"Ошибка очистки старых записей ПО: {str(e)}", exc_info=True)
            raise

    async def async_upsert_computer(self, computer: schemas.ComputerCreate, hostname: str, mode: str = "Full") -> int:
        """Добавляет или обновляет компьютер и связанные данные."""
        try:
            computer_data = computer.model_dump(exclude_unset=True, exclude={"roles", "disks", "software"})
            computer_data["last_updated"] = datetime.utcnow()
            db_computer = await self._get_or_create_computer(computer_data, hostname)
            computer_id = db_computer.id

            if computer.roles:
                await self._update_roles_async(db_computer, computer.roles)
            if computer.disks:
                await self._update_disks_async(db_computer, computer.disks)
            if computer.software:
                await self._update_software_async(db_computer, computer.software, mode=mode)

            logger.info(f"Успешно сохранен компьютер: {hostname}")
            return computer_id
        except SQLAlchemyError as e:
            logger.error(f"Ошибка базы данных при сохранении компьютера {hostname}: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Ошибка сохранения компьютера {hostname}: {str(e)}", exc_info=True)
            raise

    async def async_get_hosts_for_polling(self, days_threshold: int = 1) -> List[str]:
        """Получение списка хостов для проверки."""
        try:
            threshold = datetime.utcnow() - timedelta(days=days_threshold)
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
        except Exception as e:
            logger.error(f"Ошибка получения хостов для проверки: {str(e)}")
            raise

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
                    db_computer.last_updated = datetime.utcnow()
                    await self.async_log_change(db_computer.id, "check_status", str(old_status), str(new_check_status))
                    logger.info(f"Обновлен check_status для {hostname}: {new_check_status}")
                return db_computer
            return None
        except Exception as e:
            logger.error(f"Ошибка обновления check_status для {hostname}: {str(e)}", exc_info=True)
            raise

    async def async_get_change_log(self, computer_id: int) -> List[models.ChangeLog]:
        """Получает историю изменений."""
        logger.debug(f"Запрос истории для computer_id: {computer_id}")
        try:
            result = await self.db.execute(
                select(models.ChangeLog)
                .filter(models.ChangeLog.computer_id == computer_id)
                .order_by(models.ChangeLog.changed_at.desc())
            )
            logs = result.scalars().all()
            return [schemas.ChangeLog(**log.__dict__) for log in logs]
        except Exception as e:
            logger.error(f"Ошибка при получении истории изменений: {str(e)}")
            raise

    async def async_upsert_ad_computer(self, computer_data: dict) -> models.Computer:
        """Добавляет или обновляет запись о компьютере из AD."""
        try:
            result = await self.db.execute(
                select(models.ADComputer).filter(models.ADComputer.hostname == computer_data["hostname"])
            )
            db_comp = result.scalar_one_or_none()
            current_time = datetime.utcnow()
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

            logger.info(f"{'Обновлен' if db_comp.id else 'Создан'} AD компьютер: {computer_data['hostname']}")
            return db_comp
        except Exception as e:
            logger.error(f"Ошибка при обновлении AD компьютера {computer_data['hostname']}: {str(e)}")
            raise

    async def get_computers(
        self,
        hostname: Optional[str] = None,
        os_name: Optional[str] = None,
        check_status: Optional[str] = None,
        sort_by: str = "hostname",
        sort_order: str = "asc",
        page: int = 1,
        limit: int = 10,
        server_filter: Optional[str] = None,
    ) -> Tuple[List[schemas.ComputerList], int]:
        """Получение списка компьютеров с фильтрацией и пагинацией."""
        logger.debug(f"Запрос компьютеров с фильтрами: hostname={hostname}, os_name={os_name}, server_filter={server_filter}")

        try:
            query = select(models.Computer).options(
                selectinload(models.Computer.disks),
                selectinload(models.Computer.software),
                selectinload(models.Computer.roles)
            )

            if hostname:
                query = query.filter(models.Computer.hostname.ilike(f"%{hostname}%"))
            if os_name:
                query = query.filter(models.Computer.os_name.ilike(f"%{os_name}%"))
            if check_status:
                query = query.filter(models.Computer.check_status == check_status)
            if server_filter == 'server':
                query = query.filter(
                    models.Computer.os_name.ilike('%Server%') | models.Computer.os_name.ilike('%Hyper-V%')
                )

            # Подсчет общего количества записей
            count_query = select(func.count()).select_from(query.subquery())
            count_result = await self.db.execute(count_query)
            total = count_result.scalar_one()

            # Сортировка
            if sort_by in models.Computer.__table__.columns:
                sort_column = getattr(models.Computer, sort_by)
                if sort_order.lower() == "desc":
                    sort_column = sort_column.desc()
                query = query.order_by(sort_column)
            else:
                query = query.order_by(models.Computer.hostname)

            # Пагинация
            query = query.offset((page - 1) * limit).limit(limit)
            result = await self.db.execute(query)
            computers = result.unique().scalars().all()  # Добавляем .unique()

            computer_list = [
                schemas.ComputerList(
                    id=computer.id,
                    hostname=computer.hostname,
                    ip=computer.ip,
                    os_name=computer.os_name,
                    os_version=computer.os_version,
                    cpu=computer.cpu,
                    ram=computer.ram,
                    mac=computer.mac,
                    motherboard=computer.motherboard,
                    last_boot=computer.last_boot,
                    is_virtual=computer.is_virtual,
                    check_status=computer.check_status.value if computer.check_status else None,
                    last_updated=computer.last_updated.isoformat(),
                    disks=[schemas.Disk(DeviceID=disk.device_id, TotalSpace=disk.total_space, FreeSpace=disk.free_space) 
                           for disk in computer.disks],
                    software=[schemas.Software(DisplayName=soft.name, DisplayVersion=soft.version,
                                            InstallDate=soft.install_date.isoformat() if soft.install_date else None,
                                            Action=soft.action, is_deleted=soft.is_deleted)
                            for soft in computer.software],
                    roles=[schemas.Role(Name=role.name) for role in computer.roles]
                )
                for computer in computers
            ]

            logger.debug(f"Найдено {len(computer_list)} компьютеров, общее количество: {total}")
            return computer_list, total
        except Exception as e:
            logger.error(f"Ошибка при получении компьютеров: {str(e)}")
            raise

    async def async_get_computer_by_id(self, computer_id: int) -> Optional[Computer]:
        """Получает данные компьютера по ID с загрузкой связанных сущностей."""
        logger.debug(f"Запрос компьютера по ID: {computer_id}")
        try:
            stmt = select(Computer).options(
                joinedload(Computer.roles),
                joinedload(Computer.disks),
                joinedload(Computer.software)
            ).filter(Computer.id == computer_id)

            result = await self.db.execute(stmt)
            computer = result.unique().scalars().first()

            if computer:
                logger.debug(
                    f"Компьютер {computer.id}: roles={len(computer.roles)}, "
                    f"software={len(computer.software)}, disks={len(computer.disks)}"
                )
            else:
                logger.warning(f"Компьютер с ID {computer_id} не найден")

            return computer
        except SQLAlchemyError as e:
            logger.error(f"Ошибка базы данных при получении компьютера ID {computer_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Неизвестная ошибка при получении компьютера ID {computer_id}: {str(e)}")
            raise   