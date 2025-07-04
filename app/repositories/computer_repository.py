from typing import List, Optional, Tuple, Dict, Any, Type, TypeVar
from datetime import datetime
from sqlalchemy import select, func, tuple_  
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
import logging
from .. import models, schemas
from sqlalchemy.orm import selectinload
from sqlalchemy import union_all, update, literal
from typing_extensions import List as ListAny
logger = logging.getLogger(__name__)

T = TypeVar("T")

class ComputerRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_or_create_computer(self, computer_data: dict, hostname: str) -> models.Computer:
        try:
            result = await self.db.execute(
                select(models.Computer).where(models.Computer.hostname == hostname)
            )
            db_computer = result.scalars().first()

            if db_computer:
                # Оновлюємо лише змінені поля
                for key, value in computer_data.items():
                    setattr(db_computer, key, value)
            else:
                db_computer = models.Computer(**computer_data)
                self.db.add(db_computer)

            await self.db.flush()
            return db_computer
        except Exception as e:
            logger.error(f"Помилка при отриманні/створенні комп’ютера {hostname}: {str(e)}")
            raise

    async def async_upsert_computer(self, computer: schemas.ComputerCreate, hostname: str, mode: str = "Full") -> int:
        try:
            computer_data = computer.model_dump(
                include={
                    "hostname", "os_name", "os_version", "ram",
                    "motherboard", "last_boot", "is_virtual", "check_status"
                }
            )
            computer_data["last_updated"] = datetime.utcnow()
            if mode == "Full":
                computer_data["last_full_scan"] = datetime.utcnow()

            db_computer = await self._get_or_create_computer(computer_data, hostname)
            return db_computer.id
        except SQLAlchemyError as e:
            logger.error(f"Помилка бази даних при збереженні комп’ютера {hostname}: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Помилка збереження комп’ютера {hostname}: {str(e)}", exc_info=True)
            raise

    async def _computer_to_pydantic(self, computer: models.Computer) -> schemas.ComputerList:
        logger.debug(f"Преобразование компьютера {computer.id} в Pydantic-схему")
        try:
            return schemas.ComputerList.model_validate(computer, from_attributes=True)
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
        logger.debug(f"Запрос компьютеров с фильтрами: hostname={hostname}, os_name={os_name}, server_filter={server_filter}")

        try:
            query = select(models.Computer).options(
                selectinload(models.Computer.physical_disks),
                selectinload(models.Computer.logical_disks),
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

            if limit > 0:  # Додаємо перевірку для limit=0
                query = query.offset((page - 1) * limit).limit(limit)
            result = await self.db.execute(query)
            computers = result.scalars().all()

            pydantic_computers = [await self._computer_to_pydantic(computer) for computer in computers]
            return pydantic_computers, total
        except SQLAlchemyError as e:
            logger.error(f"Ошибка базы данных при получении списка компьютеров: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении списка компьютеров: {str(e)}", exc_info=True)
            raise

    async def async_get_computer_by_id(self, computer_id: int) -> Optional[schemas.ComputerList]:
        logger.debug(f"Запрос компьютера по ID: {computer_id}")
        try:
            stmt = select(models.Computer).options(
                selectinload(models.Computer.roles),
                selectinload(models.Computer.physical_disks),
                selectinload(models.Computer.logical_disks),
                selectinload(models.Computer.software),
                selectinload(models.Computer.ip_addresses),
                selectinload(models.Computer.processors),
                selectinload(models.Computer.mac_addresses),
                selectinload(models.Computer.video_cards)
            ).filter(models.Computer.id == computer_id)

            result = await self.db.execute(stmt)
            computer = result.scalars().first()

            if computer:
                logger.debug(
                    f"Компьютер {computer.id}: roles={len(computer.roles)}, "
                    f"software={len(computer.software)}, physical_disks={len(computer.physical_disks)}, "
                    f"logical_disks={len(computer.logical_disks)}, ip_addresses={len(computer.ip_addresses)}, "
                    f"processors={len(computer.processors)}, mac_addresses={len(computer.mac_addresses)}, "
                    f"video_cards={len(computer.video_cards)}"
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

    async def async_update_computer_check_status(self, hostname: str, check_status: str) -> Optional[models.Computer]:
        try:
            result = await self.db.execute(
                select(models.Computer).filter(models.Computer.hostname == hostname)
            )
            db_computer = result.scalar_one_or_none()
            if db_computer:
                try:
                    new_check_status = models.CheckStatus(check_status)
                except ValueError:
                    logger.error(f"Недопустиме значення check_status: {check_status}")
                    return None
                if db_computer.check_status != new_check_status:
                    db_computer.check_status = new_check_status
                    db_computer.last_updated = datetime.utcnow()
                    logger.info(f"Оновлено check_status для {hostname}: {new_check_status}")
                return db_computer
            return None
        except Exception as e:
            logger.error(f"Помилка оновлення check_status для {hostname}: {str(e)}", exc_info=True)
            raise

    async def get_component_history(self, computer_id: int) -> List[Dict[str, Any]]:
        """Отримує історію всіх компонентів комп'ютера за один запит з використанням UNION ALL."""
        logger.debug(f"Запит історії компонентів для комп'ютера з ID: {computer_id}")
        try:
            # Створюємо запити для кожної таблиці компонентів
            disk_query = (
                select(
                    literal('physical_disk').label('component_type'),
                    func.JSON_OBJECT(
                        'model', models.PhysicalDisk.model,
                        'serial', models.PhysicalDisk.serial,
                        'interface', models.PhysicalDisk.interface,
                        'media_type', models.PhysicalDisk.media_type,
                        'detected_on', models.PhysicalDisk.detected_on,
                        'removed_on', models.PhysicalDisk.removed_on
                    ).label('data'),
                    models.PhysicalDisk.detected_on,
                    models.PhysicalDisk.removed_on
                )
                .where(models.PhysicalDisk.computer_id == computer_id)
            )

            logical_disk_query = (
                select(
                    literal('logical_disk').label('component_type'),
                    func.JSON_OBJECT(
                        'device_id', models.LogicalDisk.device_id,
                        'volume_label', models.LogicalDisk.volume_label,
                        'total_space', models.LogicalDisk.total_space,
                        'free_space', models.LogicalDisk.free_space,
                        'physical_disk_id', models.LogicalDisk.physical_disk_id,
                        'detected_on', models.LogicalDisk.detected_on,
                        'removed_on', models.LogicalDisk.removed_on
                    ).label('data'),
                    models.LogicalDisk.detected_on,
                    models.LogicalDisk.removed_on
                )
                .where(models.LogicalDisk.computer_id == computer_id)
            )

            processor_query = (
                select(
                    literal('processor').label('component_type'),
                    func.JSON_OBJECT(
                        'name', models.Processor.name,
                        'number_of_cores', models.Processor.number_of_cores,
                        'number_of_logical_processors', models.Processor.number_of_logical_processors,
                        'detected_on', models.Processor.detected_on,
                        'removed_on', models.Processor.removed_on
                    ).label('data'),
                    models.Processor.detected_on,
                    models.Processor.removed_on
                )
                .where(models.Processor.computer_id == computer_id)
            )

            video_card_query = (
                select(
                    literal('video_card').label('component_type'),
                    func.JSON_OBJECT(
                        'name', models.VideoCard.name,
                        'driver_version', models.VideoCard.driver_version,
                        'detected_on', models.VideoCard.detected_on,
                        'removed_on', models.VideoCard.removed_on
                    ).label('data'),
                    models.VideoCard.detected_on,
                    models.VideoCard.removed_on
                )
                .where(models.VideoCard.computer_id == computer_id)
            )

            ip_address_query = (
                select(
                    literal('ip_address').label('component_type'),
                    func.JSON_OBJECT(
                        'address', models.IPAddress.address,
                        'detected_on', models.IPAddress.detected_on,
                        'removed_on', models.IPAddress.removed_on
                    ).label('data'),
                    models.IPAddress.detected_on,
                    models.IPAddress.removed_on
                )
                .where(models.IPAddress.computer_id == computer_id)
            )

            mac_address_query = (
                select(
                    literal('mac_address').label('component_type'),
                    func.JSON_OBJECT(
                        'address', models.MACAddress.address,
                        'detected_on', models.MACAddress.detected_on,
                        'removed_on', models.MACAddress.removed_on
                    ).label('data'),
                    models.MACAddress.detected_on,
                    models.MACAddress.removed_on
                )
                .where(models.MACAddress.computer_id == computer_id)
            )

            software_query = (
                select(
                    literal('software').label('component_type'),
                    func.JSON_OBJECT(
                        'DisplayName', models.Software.name,
                        'DisplayVersion', models.Software.version,
                        'InstallDate', models.Software.install_date,
                        'detected_on', models.Software.detected_on,
                        'removed_on', models.Software.removed_on
                    ).label('data'),
                    models.Software.detected_on,
                    models.Software.removed_on
                )
                .where(models.Software.computer_id == computer_id)
            )

            # Об'єднуємо запити через UNION ALL
            union_query = union_all(
                disk_query,
                logical_disk_query,
                processor_query,
                video_card_query,
                ip_address_query,
                mac_address_query,
                software_query
            ).order_by('detected_on')

            result = await self.db.execute(union_query)
            rows = result.fetchall()

            # Формуємо історію
            history = []
            for row in rows:
                history.append({
                    "component_type": row.component_type,
                    "data": row.data,
                    "detected_on": row.detected_on.isoformat() if row.detected_on else None,
                    "removed_on": row.removed_on.isoformat() if row.removed_on else None
                })

            return history
        except SQLAlchemyError as e:
            logger.error(f"Помилка бази даних при отриманні історії компонентів для ID {computer_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Неочікувана помилка при отриманні історії компонентів для ID {computer_id}: {str(e)}")
            raise


    async def _update_related_entities_async(
        self,
        db_computer: models.Computer,
        new_entities: ListAny,
        model_class: Type[T],
        table: Any,
        unique_field: str,
        update_fields: List[str],
    ) -> None:
        try:
            # Формируем список уникальных идентификаторов новых компонентов
            new_identifiers = {entity if isinstance(entity, str) else getattr(entity, unique_field) for entity in new_entities}
            new_entities_dict = {entity if isinstance(entity, str) else getattr(entity, unique_field): entity for entity in new_entities}

            # Получаем активные компоненты из БД (где removed_on IS NULL)
            result = await self.db.execute(
                select(model_class).where(
                    model_class.computer_id == db_computer.id,
                    model_class.removed_on.is_(None)
                )
            )
            existing_entities_dict = {getattr(e, unique_field): e for e in result.scalars().all()}

            # Определяем компоненты, которые нужно пометить как удаленные
            entities_to_mark_removed = set(existing_entities_dict.keys()) - new_identifiers
            if entities_to_mark_removed:
                await self.db.execute(
                    update(table)
                    .where(
                        table.c.computer_id == db_computer.id,
                        table.c[unique_field].in_(entities_to_mark_removed),
                        table.c.removed_on.is_(None)
                    )
                    .values(removed_on=datetime.utcnow())
                )
                logger.debug(f"Пометили как удаленные {len(entities_to_mark_removed)} {table.name} для {db_computer.hostname}")

            # Создаем новые компоненты
            new_objects = []
            for identifier in new_identifiers:
                if identifier not in existing_entities_dict:
                    new_entity = new_entities_dict[identifier]
                    if isinstance(new_entity, str):
                        new_objects.append(
                            model_class(
                                computer_id=db_computer.id,
                                **{unique_field: new_entity},
                                detected_on=datetime.utcnow(),
                                removed_on=None
                            )
                        )
                    else:
                        new_objects.append(
                            model_class(
                                computer_id=db_computer.id,
                                **{field: getattr(new_entity, field) for field in update_fields + [unique_field]},
                                detected_on=datetime.utcnow(),
                                removed_on=None
                            )
                        )
                    logger.debug(f"Добавлен новый компонент {identifier} в {table.name} для {db_computer.hostname}")

            if new_objects:
                self.db.add_all(new_objects)
                logger.debug(f"Добавлено {len(new_objects)} новых записей в {table.name} для {db_computer.hostname}")

            await self.db.flush()
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Ошибка при обновлении {table.name} для {db_computer.hostname}: {str(e)}")
            raise

    async def _update_logical_disks_async(self, db_computer: models.Computer, logical_disks: List[schemas.LogicalDisk]) -> None:
        """Обновляет логические диски с учетом связи с физическими дисками."""
        try:
            # Получаем существующие физические диски для связи
            result = await self.db.execute(
                select(models.PhysicalDisk).where(
                    models.PhysicalDisk.computer_id == db_computer.id,
                    models.PhysicalDisk.removed_on.is_(None)
                )
            )
            physical_disks = {p.serial: p for p in result.scalars().all()}

            # Формируем уникальные идентификаторы логических дисков
            new_identifiers = {disk.device_id for disk in logical_disks}
            new_disks_dict = {disk.device_id: disk for disk in logical_disks}

            # Получаем существующие логические диски
            result = await self.db.execute(
                select(models.LogicalDisk).where(
                    models.LogicalDisk.computer_id == db_computer.id,
                    models.LogicalDisk.removed_on.is_(None)
                )
            )
            existing_disks_dict = {d.device_id: d for d in result.scalars().all()}

            # Пометить удаленные логические диски
            disks_to_mark_removed = set(existing_disks_dict.keys()) - new_identifiers
            if disks_to_mark_removed:
                await self.db.execute(
                    update(models.LogicalDisk.__table__)
                    .where(
                        models.LogicalDisk.computer_id == db_computer.id,
                        models.LogicalDisk.device_id.in_(disks_to_mark_removed),
                        models.LogicalDisk.removed_on.is_(None)
                    )
                    .values(removed_on=datetime.utcnow())
                )
                logger.debug(f"Пометили как удаленные {len(disks_to_mark_removed)} logical_disks для {db_computer.hostname}")

            # Создаем или обновляем логические диски
            new_objects = []
            for device_id in new_identifiers:
                if device_id not in existing_disks_dict:
                    new_disk = new_disks_dict[device_id]
                    physical_disk_id = physical_disks.get(new_disk.serial, None).id if new_disk.serial in physical_disks else None
                    new_objects.append(
                        models.LogicalDisk(
                            computer_id=db_computer.id,
                            device_id=new_disk.device_id,
                            volume_label=new_disk.volume_label,
                            total_space=new_disk.total_space,
                            free_space=new_disk.free_space,
                            physical_disk_id=physical_disk_id,
                            detected_on=datetime.utcnow(),
                            removed_on=None
                        )
                    )
                    logger.debug(f"Добавлен новый логический диск {device_id} для {db_computer.hostname}")

            if new_objects:
                self.db.add_all(new_objects)
                logger.debug(f"Добавлено {len(new_objects)} новых логических дисков для {db_computer.hostname}")

            await self.db.flush()
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Ошибка при обновлении logical_disks для {db_computer.hostname}: {str(e)}")
            raise

    async def update_related_entities(self, db_computer: models.Computer, computer: schemas.ComputerCreate, mode: str = "Full") -> None:
        """
        Обновляет все связанные сущности компьютера, вызывая правильные асинхронные методы.
        """
        try:
            # Обновление IP-адресов
            if computer.ip_addresses is not None:
                await self._update_related_entities_async(
                    db_computer, computer.ip_addresses, models.IPAddress, models.IPAddress.__table__,
                    "address", ["address"]
                )

            # Обновление MAC-адресов
            if computer.mac_addresses is not None:
                await self._update_related_entities_async(
                    db_computer, computer.mac_addresses, models.MACAddress, models.MACAddress.__table__,
                    "address", ["address"]
                )

            # Обновление процессоров
            if computer.processors is not None:
                await self._update_related_entities_async(
                    db_computer, computer.processors, models.Processor, models.Processor.__table__,
                    "name", ["name", "number_of_cores", "number_of_logical_processors"]
                )

            # Обновление видеокарт
            if computer.video_cards is not None:
                await self._update_related_entities_async(
                    db_computer, computer.video_cards, models.VideoCard, models.VideoCard.__table__,
                    "name", ["name", "driver_version"]
                )

            # Обновление физических дисков
            if computer.physical_disks is not None:
                await self._update_related_entities_async(
                    db_computer, computer.physical_disks, models.PhysicalDisk, models.PhysicalDisk.__table__,
                    "serial", ["model", "serial", "interface", "media_type"]
                )

            # Обновление логических дисков
            if computer.logical_disks is not None:
                await self._update_logical_disks_async(db_computer, computer.logical_disks)

            # Обновление программного обеспечения
            if computer.software is not None:
                await self._update_software_async(db_computer, computer.software, mode)

            # Обновление ролей
            if computer.roles is not None:
                await self._update_related_entities_async(
                    db_computer, computer.roles, models.Role, models.Role.__table__,
                    "name", ["name"]
                )

            logger.debug(f"Обновление связанных сущностей для {db_computer.hostname} завершено.")
        except Exception as e:
            logger.error(f"Ошибка обновления связанных сущностей для {db_computer.hostname}: {str(e)}", exc_info=True)
            await self.db.rollback()
            raise

    async def _update_software_async(self, db_computer: models.Computer, new_software: List[schemas.Software], mode: str = "Full") -> None:
        if not new_software:
            logger.debug(f"Дані про ПЗ відсутні для {db_computer.hostname}, оновлення ПЗ пропущено")
            return

        try:
            # Формуємо список унікальних ідентифікаторів нового ПЗ
            new_identifiers = {(soft.name.lower(), soft.version.lower() if soft.version else '') for soft in new_software}
            new_software_dict = {(soft.name.lower(), soft.version.lower() if soft.version else ''): soft for soft in new_software}

            # Отримуємо активне ПЗ (де removed_on IS NULL)
            result = await self.db.execute(
                select(models.Software)
                .where(
                    models.Software.computer_id == db_computer.id,
                    models.Software.removed_on.is_(None)
                )
            )
            existing_software_dict = {
                (s.name.lower(), s.version.lower() if s.version else ''): s
                for s in result.scalars().all()
            }

            # Позначити видалене ПЗ
            software_to_mark_removed = set(existing_software_dict.keys()) - new_identifiers
            if software_to_mark_removed:
                await self.db.execute(
                    update(models.Software.__table__)
                    .where(
                        models.Software.computer_id == db_computer.id,
                        tuple_(
                            func.lower(models.Software.name),
                            func.coalesce(func.lower(models.Software.version), '')
                        ).in_(software_to_mark_removed),
                        models.Software.removed_on.is_(None)
                    )
                    .values(removed_on=datetime.utcnow())
                )
                logger.debug(f"Позначено як видалені {len(software_to_mark_removed)} ПЗ для {db_computer.hostname}")

            # Додати нове ПЗ
            new_objects = []
            for identifier in new_identifiers:
                if identifier not in existing_software_dict:
                    new_soft = new_software_dict[identifier]
                    new_objects.append(
                        models.Software(
                            computer_id=db_computer.id,
                            name=new_soft.name.lower(),
                            version=new_soft.version.lower() if new_soft.version else None,
                            install_date=new_soft.install_date,
                            detected_on=datetime.utcnow(),
                            removed_on=None
                        )
                    )
                    logger.debug(f"Додано нове ПЗ: {new_soft.name} {new_soft.version} для {db_computer.hostname}")

            if new_objects:
                self.db.add_all(new_objects)
                logger.debug(f"Додано {len(new_objects)} нових ПЗ для {db_computer.hostname}")

            await self.db.flush()
        except Exception as e:
            logger.error(f"Помилка при оновленні ПЗ для {db_computer.hostname}: {str(e)}")
            raise

