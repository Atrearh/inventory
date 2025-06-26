
from typing import TypeVar, List, Type, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy import select, delete, update, func, Table
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
import logging
from .. import models, schemas
from sqlalchemy.orm import selectinload,joinedload

logger = logging.getLogger(__name__)

T = TypeVar("T")  # Для типизации моделей SQLAlchemy
U = TypeVar("U", bound=schemas.BaseModel)  # Для типизации Pydantic-схем

class ComputerRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_or_create_computer(self, computer_data: dict, hostname: str) -> models.Computer:
        """
        Получает существующий компьютер по hostname или создает новый.

        :param computer_data: Данные компьютера для создания/обновления
        :param hostname: Имя хоста компьютера
        :return: Объект компьютера из базы данных
        """
        try:
            result = await self.db.execute(
                select(models.Computer).where(models.Computer.hostname == hostname)
            )
            db_computer = result.scalars().first()

            if db_computer:
                for key, value in computer_data.items():
                    setattr(db_computer, key, value)
            else:
                db_computer = models.Computer(**computer_data)
                self.db.add(db_computer)

            await self.db.flush()
            return db_computer
        except Exception as e:
            logger.error(f"Ошибка при получении/создании компьютера {hostname}: {str(e)}")
            raise

    async def _update_related_entities_async(
        self,
        db_computer: models.Computer,
        new_entities: List[U],
        model_class: Type[T],
        table: Table,
        unique_field: str,
        update_fields: List[str],
    ) -> None:
        """
        Универсальный метод для обновления связанных сущностей (роли, диски, видеокарты, процессоры, IP, MAC).

        :param db_computer: Объект компьютера в БД
        :param new_entities: Список новых данных (Pydantic-схемы)
        :param model_class: Класс SQLAlchemy модели (например, models.Role)
        :param table: SQLAlchemy таблица (например, models.Role.__table__)
        :param unique_field: Поле для идентификации (например, 'name' или 'device_id')
        :param update_fields: Поля для обновления (например, ['driver_version'])
        """
        try:
            # Получаем новые уникальные идентификаторы
            new_identifiers = {getattr(entity, unique_field) for entity in new_entities}
            new_entities_dict = {getattr(entity, unique_field): entity for entity in new_entities}

            # Загружаем существующие записи
            result = await self.db.execute(
                select(model_class).where(model_class.computer_id == db_computer.id)
            )
            existing_entities_dict = {getattr(e, unique_field): e for e in result.scalars().all()}

            # Определяем, что удалить
            entities_to_delete = set(existing_entities_dict.keys()) - new_identifiers
            if entities_to_delete:
                await self.db.execute(
                    delete(table).where(
                        table.c.computer_id == db_computer.id,
                        table.c[unique_field].in_(entities_to_delete)
                    )
                )
                logger.debug(f"Удалено {len(entities_to_delete)} {table.name} для {db_computer.hostname}")

            # Подготовка новых записей и обновлений
            new_objects = []
            updates = []
            for identifier in new_identifiers:
                new_entity = new_entities_dict[identifier]
                if identifier not in existing_entities_dict:
                    # Создаем новую запись
                    new_objects.append(
                        model_class(
                            computer_id=db_computer.id,
                            **{field: getattr(new_entity, field) for field in update_fields + [unique_field]}
                        )
                    )
                    logger.debug(f"Добавлена новая запись {identifier} в {table.name} для {db_computer.hostname}")
                else:
                    # Проверяем, нужно ли обновить существующую запись
                    existing_entity = existing_entities_dict[identifier]
                    update_data = {}
                    for field in update_fields:
                        new_value = getattr(new_entity, field)
                        old_value = getattr(existing_entity, field)
                        if new_value != old_value:
                            update_data[field] = new_value
                    if update_data:
                        update_data["id"] = existing_entity.id
                        updates.append(update_data)
                        logger.debug(f"Обновлена запись {identifier} в {table.name} для {db_computer.hostname}")

            # Добавляем новые записи
            if new_objects:
                self.db.add_all(new_objects)
                logger.debug(f"Добавлено {len(new_objects)} новых записей в {table.name} для {db_computer.hostname}")

            # Выполняем массовое обновление
            if updates:
                for update_data in updates:
                    await self.db.execute(
                        update(table).where(table.c.id == update_data["id"]).values(
                            {k: v for k, v in update_data.items() if k != "id"}
                        )
                    )
                logger.debug(f"Обновлено {len(updates)} записей в {table.name} для {db_computer.hostname}")

            await self.db.flush()
        except Exception as e:
            logger.error(f"Ошибка при обновлении {table.name} для {db_computer.hostname}: {str(e)}")
            raise

    async def _update_software_async(self, db_computer: models.Computer, new_software: List[schemas.Software], mode: str = "Full") -> None:
        """
        Обновляет программное обеспечение для компьютера, поддерживая режимы Full/Incremental.

        :param db_computer: Объект компьютера
        :param new_software: Список нового ПО
        :param mode: Режим обновления (Full или Incremental)
        """
        if not new_software:
            logger.debug(f"Данные о ПО отсутствуют для {db_computer.hostname}, обновление ПО пропущено")
            return

        try:
            result = await self.db.execute(
                select(models.Software).where(models.Software.computer_id == db_computer.id)
            )
            existing_software = result.scalars().all()
            existing_software_dict = {
                (s.name.lower(), s.version.lower() if s.version else ''): s
                for s in existing_software
            }

            new_entries = []
            updates = []
            change_logs = []

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
                            change_logs.append(
                                models.ChangeLog(
                                    computer_id=db_computer.id,
                                    field=f"software_{soft.name}",
                                    old_value=f"version: {existing.version}, install_date: {existing.install_date}, is_deleted: {existing.is_deleted}",
                                    new_value=f"version: {soft.version}, install_date: {soft.install_date}, is_deleted: False",
                                    changed_at=datetime.utcnow()
                                )
                            )
                            updates.append({
                                "id": existing.id,
                                "version": soft.version,
                                "install_date": soft.install_date,
                                "action": soft.action,
                                "is_deleted": False
                            })
                    else:
                        new_entries.append(
                            models.Software(
                                computer_id=db_computer.id,
                                name=soft.name,
                                version=soft.version,
                                install_date=soft.install_date,
                                action=soft.action,
                                is_deleted=False
                            )
                        )
                elif soft.action == "Uninstalled":
                    if existing and not existing.is_deleted:
                        change_logs.append(
                            models.ChangeLog(
                                computer_id=db_computer.id,
                                field=f"software_{soft.name}",
                                old_value=f"version: {existing.version}, install_date: {existing.install_date}, is_deleted: {existing.is_deleted}",
                                new_value="is_deleted: True",
                                changed_at=datetime.utcnow()
                            )
                        )
                        updates.append({
                            "id": existing.id,
                            "action": soft.action,
                            "is_deleted": True
                        })

            # Пакетное добавление логов изменений
            if change_logs:
                self.db.add_all(change_logs)
                logger.debug(f"Добавлено {len(change_logs)} записей в change_log для {db_computer.hostname}")

            # Добавляем новые записи
            if new_entries:
                self.db.add_all(new_entries)
                logger.debug(f"Добавлено {len(new_entries)} новых ПО для {db_computer.hostname}")

            # Массовая операция обновления
            if updates:
                await self.db.execute(
                    update(models.Software).where(models.Software.id.in_([u["id"] for u in updates])).values(
                        [
                            {
                                "version": u.get("version"),
                                "install_date": u.get("install_date"),
                                "action": u.get("action"),
                                "is_deleted": u["is_deleted"]
                            }
                            for u in updates
                        ]
                    )
                )
                logger.debug(f"Обновлено {len(updates)} ПО для {db_computer.hostname}")

            await self.db.flush()
        except Exception as e:
            logger.error(f"Ошибка при обновлении ПО для {db_computer.hostname}: {str(e)}")
            raise

    async def async_upsert_computer(self, computer: schemas.ComputerCreate, hostname: str, mode: str = "Full") -> int:
        """
        Создает или обновляет компьютер и его связанные сущности.

        :param computer: Pydantic-схема с данными компьютера
        :param hostname: Имя хоста компьютера
        :param mode: Режим обновления (Full или Incremental)
        :return: ID компьютера
        """
        try:
            computer_data = computer.model_dump(
                include={
                    "hostname", "ip", "os_name", "os_version", "cpu", "ram", "mac",
                    "motherboard", "last_boot", "is_virtual", "check_status"
                }
            )
            computer_data["last_updated"] = datetime.utcnow()

            db_computer = await self._get_or_create_computer(computer_data, hostname)
            computer_id = db_computer.id

            # Обновление связанных сущностей
            if computer.roles:
                await self._update_related_entities_async(
                    db_computer, computer.roles, models.Role, models.Role.__table__, "name", ["name"]
                )
            if computer.disks:
                await self._update_related_entities_async(
                    db_computer, computer.disks, models.Disk, models.Disk.__table__, "device_id",
                    ["total_space", "free_space", "model"]
                )
            if computer.software:
                await self._update_software_async(db_computer, computer.software, mode=mode)
            if computer.video_cards:
                await self._update_related_entities_async(
                    db_computer, computer.video_cards, models.VideoCard, models.VideoCard.__table__, "name",
                    ["driver_version"]
                )
            if computer.processors:
                await self._update_related_entities_async(
                    db_computer, computer.processors, models.Processor, models.Processor.__table__, "name",
                    ["number_of_cores", "number_of_logical_processors"]
                )
            if computer.ip_addresses:
                await self._update_related_entities_async(
                    db_computer, computer.ip_addresses, models.IPAddress, models.IPAddress.__table__, "address",
                    ["address"]
                )
            if computer.mac_addresses:
                await self._update_related_entities_async(
                    db_computer, computer.mac_addresses, models.MACAddress, models.MACAddress.__table__, "address",
                    ["address"]
                )

            logger.info(f"Успешно сохранен компьютер: {hostname}")
            return computer_id
        except SQLAlchemyError as e:
            logger.error(f"Ошибка базы данных при сохранении компьютера {hostname}: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Ошибка сохранения компьютера {hostname}: {str(e)}", exc_info=True)
            raise

    async def _computer_to_pydantic(self, computer: models.Computer) -> schemas.ComputerList:
        """
        Преобразует ORM-модель компьютера в Pydantic-схему.

        :param computer: ORM-модель компьютера
        :return: Pydantic-схема ComputerList
        """
        logger.debug(f"Преобразование компьютера {computer.id} в Pydantic-схему")
        try:
            # Логируем данные перед преобразованием
            logger.debug(f"Raw data: roles={len(computer.roles)}, software={len(computer.software)}, disks={len(computer.disks)}")
            
            result = schemas.ComputerList(
                id=computer.id,
                hostname=computer.hostname,
                ip=computer.ip,
                ip_addresses=[ip.address for ip in computer.ip_addresses] if computer.ip_addresses else [],
                os_name=computer.os_name,
                os_version=computer.os_version,
                cpu=computer.cpu,
                ram=computer.ram,
                mac=computer.mac,
                mac_addresses=[mac.address for mac in computer.mac_addresses] if computer.mac_addresses else [],
                motherboard=computer.motherboard,
                last_boot=computer.last_boot,
                is_virtual=computer.is_virtual,
                check_status=computer.check_status.value if computer.check_status else None,
                last_updated=computer.last_updated.isoformat() if computer.last_updated else None,
                disks=[schemas.Disk(
                    device_id=disk.device_id,
                    model=disk.model or "Unknown",
                    total_space=disk.total_space,  # Байты, как в базе
                    free_space=disk.free_space  # Байты, как в базе
                ) for disk in computer.disks] if computer.disks else [],
                software=[schemas.Software(
                    name=soft.name,
                    version=soft.version or "Unknown",
                    install_date=soft.install_date.isoformat() if soft.install_date else None,
                    action=soft.action or "Installed",
                    is_deleted=soft.is_deleted
                ) for soft in computer.software] if computer.software else [],
                roles=[schemas.Role(name=role.name) for role in computer.roles] if computer.roles else [],
                video_cards=[schemas.VideoCard(
                    name=card.name,
                    driver_version=card.driver_version
                ) for card in computer.video_cards] if computer.video_cards else [],
                processors=[schemas.Processor(
                    name=proc.name,
                    number_of_cores=proc.number_of_cores,
                    number_of_logical_processors=proc.number_of_logical_processors
                ) for proc in computer.processors] if computer.processors else []
            )
            logger.debug(f"Transformed data: roles={len(result.roles or [])}, software={len(result.software or [])}, "
                        f"disks={len(result.disks or [])}, "
                        f"disks_data={[{'device_id': d.device_id, 'total_space_gb': d.total_space_gb, 'free_space_gb': d.free_space_gb} for d in result.disks]}")
            return result
        except Exception as e:
            logger.error(f"Ошибка преобразования компьютера {computer.id} в Pydantic-схему: {str(e)}")
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
        """
        Получает список компьютеров с фильтрацией, сортировкой и пагинацией.

        :param hostname: Фильтр по имени хоста
        :param os_name: Фильтр по имени ОС
        :param check_status: Фильтр по статусу проверки
        :param sort_by: Поле для сортировки
        :param sort_order: Порядок сортировки (asc/desc)
        :param page: Номер страницы
        :param limit: Количество записей на страницу
        :param server_filter: Фильтр по типу ОС (server/client)
        :return: Кортеж из списка компьютеров и общего количества
        """
        logger.debug(f"Запрос компьютеров с фильтрами: hostname={hostname}, os_name={os_name}, server_filter={server_filter}")

        try:
            query = select(models.Computer).options(
                selectinload(models.Computer.disks),
                selectinload(models.Computer.software),
                selectinload(models.Computer.roles),
                selectinload(models.Computer.video_cards),
                selectinload(models.Computer.processors),
                selectinload(models.Computer.ip_addresses),
                selectinload(models.Computer.mac_addresses)
            )

            if hostname:
                query = query.filter(models.Computer.hostname.ilike(f"%{hostname}%"))
            if os_name:
                query = query.filter(models.Computer.os_name.ilike(f"%{os_name}%"))
            if check_status:
                query = query.filter(models.Computer.check_status == check_status)
            if server_filter == "server":
                query = query.filter(models.Computer.os_name.ilike("%server%"))
            elif server_filter == "client":
                query = query.filter(~models.Computer.os_name.ilike("%server%"))

            if sort_by in ["hostname", "os_name", "last_updated"]:
                order_column = getattr(models.Computer, sort_by)
                if sort_order.lower() == "desc":
                    order_column = order_column.desc()
                query = query.order_by(order_column)
            else:
                query = query.order_by(models.Computer.hostname)

            count_query = select(func.count()).select_from(query.subquery())
            result = await self.db.execute(count_query)
            total = result.scalar()

            query = query.offset((page - 1) * limit).limit(limit)
            result = await self.db.execute(query)
            computers_result = result.scalars().all()

            computer_list = [await self._computer_to_pydantic(computer) for computer in computers_result]
            logger.debug(f"Найдено {len(computer_list)} компьютеров, общее количество: {total}, SQL: {str(query)}")
            return computer_list, total
        except Exception as e:
            logger.error(f"Ошибка при получении компьютеров: {str(e)}")
            raise

    async def async_log_change(self, computer_id: int, field: str, old_value: str, new_value: str) -> None:
        """
        Логирует изменение поля компьютера.

        :param computer_id: ID компьютера
        :param field: Измененное поле
        :param old_value: Старое значение
        :param new_value: Новое значение
        """
        try:
            change_log = models.ChangeLog(
                computer_id=computer_id,
                field=field,
                old_value=old_value,
                new_value=new_value,
                changed_at=datetime.utcnow()
            )
            self.db.add(change_log)
            await self.db.flush()
        except Exception as e:
            logger.error(f"Ошибка при логировании изменения для computer_id {computer_id}: {str(e)}")
            raise

    async def async_get_computer_by_id(self, computer_id: int) -> Optional[schemas.ComputerList]:
        """
        Получает данные компьютера по ID с загрузкой всех связанных сущностей.

        :param computer_id: ID компьютера
        :return: Pydantic-схема ComputerList или None, если компьютер не найден
        """
        logger.debug(f"Запрос компьютера по ID: {computer_id}")
        try:
            stmt = select(models.Computer).options(
                selectinload(models.Computer.roles),
                selectinload(models.Computer.disks),
                selectinload(models.Computer.software),
                selectinload(models.Computer.ip_addresses),
                selectinload(models.Computer.processors),
                selectinload(models.Computer.mac_addresses),
                selectinload(models.Computer.video_cards)
            ).filter(models.Computer.id == computer_id)

            result = await self.db.execute(stmt)
            computer = result.scalars().first()  # Удаляем .unique(), так как selectinload не требует его

            if computer:
                logger.debug(
                    f"Компьютер {computer.id}: roles={len(computer.roles)}, "
                    f"software={len(computer.software)}, disks={len(computer.disks)}, "
                    f"ip_addresses={len(computer.ip_addresses)}, processors={len(computer.processors)}, "
                    f"mac_addresses={len(computer.mac_addresses)}, video_cards={len(computer.video_cards)}"
                )
                return await self._computer_to_pydantic(computer)
            else:
                logger.warning(f"Компьютер с ID {computer_id} не найден")
                return None
        except SQLAlchemyError as e:
            logger.error(f"Ошибка базы данных при получении компьютера ID {computer_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Неизвестная ошибка при получении компьютера ID {computer_id}: {str(e)}")
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