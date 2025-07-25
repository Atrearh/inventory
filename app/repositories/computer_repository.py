from typing import List, Optional, Tuple, Dict, Any, Type, TypeVar, AsyncGenerator
from datetime import datetime
from sqlalchemy import select, func, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
import logging
from .. import models
from ..schemas import PhysicalDisk, LogicalDisk, Processor, VideoCard, IPAddress, MACAddress, Software, ComputerCreate, ComputerList, ComputerListItem
from typing_extensions import List as ListAny
import time

logger = logging.getLogger(__name__)

T = TypeVar("T")

class ComputerRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_computer_by_guid(self, db: AsyncSession, object_guid: str) -> Optional[models.Computer]:
        """Отримує комп'ютер за object_guid."""
        try:
            result = await db.execute(
                select(models.Computer)
                .options(
                    joinedload(models.Computer.ip_addresses),
                    joinedload(models.Computer.mac_addresses),
                    joinedload(models.Computer.processors),
                    joinedload(models.Computer.physical_disks),
                    joinedload(models.Computer.logical_disks),
                    joinedload(models.Computer.video_cards),
                    joinedload(models.Computer.software),
                    joinedload(models.Computer.roles)
                )
                .filter(models.Computer.object_guid == object_guid)
            )
            computer = result.unique().scalars().first()
            logger.debug("Комп'ютер отримано за object_guid" if computer else "Комп'ютер не знайдено", extra={"object_guid": object_guid})
            return computer
        except SQLAlchemyError as e:
            logger.error(f"Помилка отримання комп'ютера за object_guid: {str(e)}", extra={"object_guid": object_guid})
            raise

    async def async_update_computer_by_guid(self, db: AsyncSession, object_guid: str, data: Dict[str, Any]) -> None:
        """Оновлює комп'ютер за object_guid."""
        try:
            await db.execute(
                update(models.Computer)
                .where(models.Computer.object_guid == object_guid)
                .values(**data)
            )
            logger.debug("Комп'ютер оновлено за object_guid", extra={"object_guid": object_guid})
        except SQLAlchemyError as e:
            logger.error(f"Помилка оновлення комп'ютера за object_guid: {str(e)}", extra={"object_guid": object_guid})
            await db.rollback()
            raise

    async def async_create_computer(self, db: AsyncSession, data: Dict[str, Any]) -> models.Computer:
        """Створює новий комп'ютер."""
        try:
            computer = models.Computer(**data)
            db.add(computer)
            await db.flush()
            logger.debug(f"Комп'ютер створено з ID {computer.id}", extra={"hostname": data.get("hostname")})
            return computer
        except SQLAlchemyError as e:
            logger.error(f"Помилка створення комп'ютера: {str(e)}", extra={"hostname": data.get("hostname")})
            await db.rollback()
            raise

    async def get_all_computers_with_guid(self, db: AsyncSession) -> List[models.Computer]:
        """Отримує всі комп'ютери з ненульовим object_guid."""
        try:
            result = await db.execute(
                select(models.Computer)
                .options(
                    joinedload(models.Computer.ip_addresses),
                    joinedload(models.Computer.mac_addresses),
                    joinedload(models.Computer.processors),
                    joinedload(models.Computer.physical_disks),
                    joinedload(models.Computer.logical_disks),
                    joinedload(models.Computer.video_cards),
                    joinedload(models.Computer.software),
                    joinedload(models.Computer.roles)
                )
                .filter(models.Computer.object_guid.isnot(None))
            )
            computers = result.unique().scalars().all()
            logger.debug(f"Отримано {len(computers)} комп'ютерів з object_guid")
            return computers
        except SQLAlchemyError as e:
            logger.error(f"Помилка отримання комп'ютерів з object_guid: {str(e)}")
            raise

    async def _get_or_create_computer(self, computer_data: dict, hostname: str) -> models.Computer:
        """Отримує або створює комп'ютер у базі даних за hostname."""
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
            logger.debug("Комп’ютер отримано або створено", extra={"hostname": hostname})
            return db_computer
        except SQLAlchemyError as e:
            logger.error(f"Помилка при отриманні/створенні комп’ютера: {str(e)}", extra={"hostname": hostname})
            raise

    async def async_upsert_computer(self, computer: ComputerCreate, hostname: str, mode: str = "Full") -> int:
        """Створює або оновлює комп'ютер у базі даних, зберігаючи існуючі значення полів AD."""
        try:
            computer_data = computer.model_dump(
                include={
                    "hostname", "os_name", "os_version", "ram",
                    "motherboard", "last_boot", "is_virtual", "check_status",
                    "object_guid", "when_created", "when_changed", "enabled", "ad_notes", "local_notes"
                }
            )
            logger.debug(f"Дані для оновлення: {computer_data}", extra={"hostname": hostname})
            
            # Виключаємо поля AD, якщо вони None, щоб не перезаписувати існуючі значення
            protected_fields = ["when_created", "when_changed", "enabled", "ad_notes"]
            computer_data = {k: v for k, v in computer_data.items() if k not in protected_fields or v is not None}
            
            if not computer_data.get("when_created"):
                logger.debug("Відсутній when_created у даних сканування, пропускаємо оновлення", extra={"hostname": hostname})
            if not computer_data.get("ad_notes"):
                logger.debug("Відсутній ad_notes у даних сканування, пропускаємо оновлення", extra={"hostname": hostname})
            
            computer_data["last_updated"] = datetime.utcnow()
            if mode == "Full":
                computer_data["last_full_scan"] = datetime.utcnow()
            
            db_computer = await self._get_or_create_computer(computer_data, hostname)
            await self.db.flush()
            await self.db.commit()
            logger.debug(f"Комп’ютер збережено з ID {db_computer.id}", extra={"hostname": hostname})

            return db_computer.id
        except SQLAlchemyError as e:
            logger.error(f"Помилка збереження комп’ютера: {str(e)}", extra={"hostname": hostname})
            await self.db.rollback()
            raise

    async def _computer_to_pydantic(self, computers: List[models.Computer]) -> List[ComputerListItem]:
        """Перетворює список об'єктів комп'ютера в Pydantic-схему."""
        try:
            return [ComputerListItem.model_validate(comp, from_attributes=True) for comp in computers]
        except Exception as e:
            logger.error(f"Помилка перетворення в Pydantic-схему: {str(e)}")
            raise

    def _build_computer_query(
        self,
        hostname: Optional[str] = None,
        os_name: Optional[str] = None,
        check_status: Optional[str] = None,
        server_filter: Optional[str] = None,
        sort_by: str = "hostname",
        sort_order: str = "asc"
    ) -> Any:
        """Створює SQLAlchemy-запит для отримання комп'ютерів з фільтрами."""
        query = select(models.Computer).options(
            joinedload(models.Computer.ip_addresses),
            joinedload(models.Computer.mac_addresses),
            joinedload(models.Computer.processors),
            joinedload(models.Computer.physical_disks),
            joinedload(models.Computer.logical_disks),
            joinedload(models.Computer.video_cards),
            joinedload(models.Computer.software),
            joinedload(models.Computer.roles)
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
        if sort_by in ["hostname", "os_name", "last_updated", "check_status", "enabled"]:
            order_column = getattr(models.Computer, sort_by)
            if sort_order.lower() == "desc":
                order_column = order_column.desc()
            query = query.order_by(order_column)
        else:
            query = query.order_by(models.Computer.hostname)
        return query

    async def get_computers(
        self,
        os_name: Optional[str] = None,
        check_status: Optional[str] = None,
        sort_by: Optional[str] = "hostname",
        sort_order: Optional[str] = "asc",
        page: Optional[int] = 1,
        limit: Optional[int] = 1000,
        server_filter: Optional[str] = None
    ) -> Tuple[List[ComputerListItem], int]:
        """Отримання списку комп'ютерів з фільтрацією та пагінацією."""
        start_time = time.time()
        cache_key = self._generate_cache_key(os_name, check_status, sort_by, sort_order, page, limit, server_filter)
        try:
            query = self._build_computer_query(
                os_name=os_name,
                check_status=check_status,
                server_filter=server_filter,
                sort_by=sort_by,
                sort_order=sort_order
            )
            count_query = select(func.count()).select_from(query.subquery())
            total = (await self.db.execute(count_query)).scalar() or 0
            query = query.offset((page - 1) * limit).limit(limit)
            result = await self.db.execute(query)
            computers = result.scalars().all()
            pydantic_computers = await self._computer_to_pydantic(computers)
            logger.debug(f"Отримано {len(pydantic_computers)} комп’ютерів, всього: {total}, час: {time.time() - start_time:.3f} сек")
            return pydantic_computers, total
        except Exception as e:
            logger.error(f"Помилка отримання комп’ютерів: {str(e)}")
            raise

    async def async_get_computer_by_id(self, computer_id: int) -> Optional[ComputerList]:
        """Отримує комп'ютер за ID."""
        try:
            stmt = select(models.Computer).options(
                joinedload(models.Computer.roles),
                joinedload(models.Computer.physical_disks),
                joinedload(models.Computer.logical_disks),
                joinedload(models.Computer.software),
                joinedload(models.Computer.ip_addresses),
                joinedload(models.Computer.processors),
                joinedload(models.Computer.mac_addresses),
                joinedload(models.Computer.video_cards)
            ).filter(models.Computer.id == computer_id)
            result = await self.db.execute(stmt)
            computer = result.scalars().first()
            return ComputerList.model_validate(computer, from_attributes=True) if computer else None
        except SQLAlchemyError as e:
            logger.error(f"Помилка отримання комп’ютера: {str(e)}", extra={"computer_id": computer_id})
            raise

    async def async_update_computer_check_status(self, hostname: str, check_status: str) -> Optional[models.Computer]:
        """Оновлює статус перевірки комп'ютера."""
        try:
            result = await self.db.execute(
                select(models.Computer).filter(models.Computer.hostname == hostname)
            )
            db_computer = result.scalars().first()
            if not db_computer:
                logger.warning("Комп’ютер не знайдено", extra={"hostname": hostname})
                return None
            new_check_status = models.CheckStatus(check_status)
            if db_computer.check_status != new_check_status:
                db_computer.check_status = new_check_status
                logger.debug(f"Статус оновлено до {check_status}", extra={"hostname": hostname})
            return db_computer
        except ValueError:
            logger.error(f"Недопустиме значення check_status: {check_status}", extra={"hostname": hostname})
            raise
        except SQLAlchemyError as e:
            logger.error(f"Помилка оновлення статусу: {str(e)}", extra={"hostname": hostname})
            raise

    async def get_component_history(self, computer_id: int) -> List[Dict[str, Any]]:
        """Отримує історію компонентів комп'ютера."""
        try:
            history = []
            for component_type, model, schema in [
                ("physical_disk", models.PhysicalDisk, PhysicalDisk),
                ("logical_disk", models.LogicalDisk, LogicalDisk),
                ("processor", models.Processor, Processor),
                ("video_card", models.VideoCard, VideoCard),
                ("ip_address", models.IPAddress, IPAddress),
                ("mac_address", models.MACAddress, MACAddress),
                ("software", models.Software, Software)
            ]:
                result = await self.db.execute(
                    select(model).where(model.computer_id == computer_id)
                )
                for item in result.scalars().all():
                    history.append({
                        "component_type": component_type,
                        "data": schema.model_validate(item, from_attributes=True).model_dump(),
                        "detected_on": item.detected_on.isoformat() if item.detected_on else None,
                        "removed_on": item.removed_on.isoformat() if item.removed_on else None
                    })
            history.sort(key=lambda x: x["detected_on"] or "")
            logger.debug(f"Отримано історію компонентів: {len(history)} записів", extra={"computer_id": computer_id})
            return history
        except SQLAlchemyError as e:
            logger.error(f"Помилка отримання історії компонентів: {str(e)}", extra={"computer_id": computer_id})
            raise

    async def _update_entities(
        self,
        db_computer: models.Computer,
        new_entities: ListAny,
        model_class: Type[T],
        table: Any,
        unique_field: str,
        update_fields: List[str],
        custom_logic: Optional[callable] = None
    ) -> None:
        """Універсальна функція для оновлення пов'язаних сутностей."""
        try:
            new_identifiers = {getattr(entity, unique_field) if not isinstance(entity, str) else entity for entity in new_entities}
            new_entities_dict = {getattr(entity, unique_field) if not isinstance(entity, str) else entity: entity for entity in new_entities}

            entities_to_mark_removed = {row[0] for row in (await self.db.execute(
                select(table.c[unique_field]).where(
                    table.c.computer_id == db_computer.id,
                    table.c.removed_on.is_(None)
                )
            )).fetchall()} - new_identifiers
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
                logger.debug(f"Позначено як видалені {len(entities_to_mark_removed)} записів", extra={"hostname": db_computer.hostname, "table": table.name})

            new_objects = []
            existing_identifiers = {row[0] for row in (await self.db.execute(
                select(table.c[unique_field]).where(table.c.computer_id == db_computer.id)
            )).fetchall()}
            for identifier in new_identifiers:
                entity_data = {field: getattr(new_entities_dict[identifier], field) for field in update_fields}
                entity_data["computer_id"] = db_computer.id
                entity_data["detected_on"] = datetime.utcnow()
                entity_data["removed_on"] = None
                entity_data[unique_field] = identifier
                if identifier in existing_identifiers:
                    await self.db.execute(
                        update(table)
                        .where(
                            table.c.computer_id == db_computer.id,
                            table.c[unique_field] == identifier
                        )
                        .values(**entity_data)
                    )
                else:
                    new_objects.append(
                        model_class(**entity_data) if not custom_logic else await custom_logic(db_computer, new_entities_dict[identifier])
                    )
            if new_objects:
                self.db.add_all(new_objects)
                logger.debug(f"Додано {len(new_objects)} нових записів", extra={"hostname": db_computer.hostname, "table": table.name})
            await self.db.flush()
            logger.debug(f"Оновлено {table.name}", extra={"hostname": db_computer.hostname})
        except SQLAlchemyError as e:
            logger.error(f"Помилка оновлення: {str(e)}", extra={"hostname": db_computer.hostname, "table": table.name})
            await self.db.rollback()
            raise

    async def _get_physical_disk_id(self, computer_id: int, serial: Optional[str]) -> Optional[int]:
        """Отримує ID фізичного диска за його серійним номером."""
        if not serial:
            return None
        try:
            result = await self.db.execute(
                select(models.PhysicalDisk.id).where(
                    models.PhysicalDisk.computer_id == computer_id,
                    models.PhysicalDisk.serial == serial,
                    models.PhysicalDisk.removed_on.is_(None)
                )
            )
            return result.scalars().first()
        except SQLAlchemyError as e:
            logger.error(f"Помилка отримання physical_disk_id для serial {serial}: {str(e)}", extra={"computer_id": computer_id})
            return None

    async def _create_logical_disk(self, db_computer: models.Computer, disk: LogicalDisk) -> models.LogicalDisk:
        """Створює об'єкт логічного диска з урахуванням parent_disk_serial."""
        physical_disk_id = await self._get_physical_disk_id(db_computer.id, disk.parent_disk_serial)
        return models.LogicalDisk(
            computer_id=db_computer.id,
            device_id=disk.device_id,
            volume_label=disk.volume_label,
            total_space=disk.total_space,
            free_space=disk.free_space,
            physical_disk_id=physical_disk_id,
            detected_on=datetime.utcnow(),
            removed_on=None
        )

    async def update_related_entities(self, db_computer: models.Computer, computer: ComputerCreate, mode: str = "Full") -> None:
        """Оновлює всі пов'язані сутності комп'ютера."""
        try:
            if computer.ip_addresses is not None:
                await self._update_entities(
                    db_computer, computer.ip_addresses, models.IPAddress, models.IPAddress.__table__,
                    "address", ["address"]
                )
            if computer.mac_addresses is not None:
                await self._update_entities(
                    db_computer, computer.mac_addresses, models.MACAddress, models.MACAddress.__table__,
                    "address", ["address"]
                )
            if computer.processors is not None:
                await self._update_entities(
                    db_computer, computer.processors, models.Processor, models.Processor.__table__,
                    "name", ["name", "number_of_cores", "number_of_logical_processors"]
                )
            if computer.video_cards is not None:
                await self._update_entities(
                    db_computer, computer.video_cards, models.VideoCard, models.VideoCard.__table__,
                    "name", ["name", "driver_version"]
                )
            if computer.physical_disks is not None:
                await self._update_entities(
                    db_computer, computer.physical_disks, models.PhysicalDisk, models.PhysicalDisk.__table__,
                    "serial", ["model", "serial", "interface", "media_type"]
                )
            if computer.logical_disks is not None:
                await self._update_entities(
                    db_computer, computer.logical_disks, models.LogicalDisk, models.LogicalDisk.__table__,
                    "device_id", ["device_id", "volume_label", "total_space", "free_space"],
                    custom_logic=self._create_logical_disk
                )
            if computer.software is not None:
                await self._update_software_async(db_computer, computer.software, mode)
            if computer.roles is not None:
                await self._update_entities(
                    db_computer, computer.roles, models.Role, models.Role.__table__,
                    "name", ["name"]
                )
            await self.db.commit()
            logger.debug("Транзакцію для пов’язаних сутностей зафіксовано", extra={"hostname": db_computer.hostname})
        except SQLAlchemyError as e:
            logger.error(f"Помилка оновлення пов’язаних сутностей: {str(e)}", extra={"hostname": db_computer.hostname})
            await self.db.rollback()
            raise

    async def _update_software_async(self, db_computer: models.Computer, new_software: List[Software], mode: str) -> None:
        """Оновлює програмне забезпечення комп'ютера."""
        if not new_software:
            logger.debug("Дані про ПО відсутні, оновлення пропущено", extra={"hostname": db_computer.hostname})
            return
        try:
            new_identifiers = {(soft.name.lower(), soft.version.lower() if soft.version else '') for soft in new_software}
            new_software_dict = {(soft.name.lower(), soft.version.lower() if soft.version else ''): soft for soft in new_software}
            result = await self.db.execute(
                select(models.Software).where(
                    models.Software.computer_id == db_computer.id,
                    models.Software.removed_on.is_(None)
                )
            )
            existing_software_dict = {
                (s.name.lower(), s.version.lower() if s.version else ''): s
                for s in result.scalars().all()
            }
            software_to_mark_removed = set(existing_software_dict.keys()) - new_identifiers
            if software_to_mark_removed:
                await self.db.execute(
                    update(models.Software.__table__)
                    .where(
                        models.Software.computer_id == db_computer.id,
                        tuple_(func.lower(models.Software.name), func.coalesce(func.lower(models.Software.version), '')).in_(software_to_mark_removed),
                        models.Software.removed_on.is_(None)
                    )
                    .values(removed_on=datetime.utcnow())
                )
                logger.debug(f"Позначено як видалені {len(software_to_mark_removed)} ПО", extra={"hostname": db_computer.hostname})
            new_objects = [
                models.Software(
                    computer_id=db_computer.id,
                    name=new_software_dict[identifier].name.lower(),
                    version=new_software_dict[identifier].version.lower() if new_software_dict[identifier].version else None,
                    install_date=new_software_dict[identifier].install_date,
                    detected_on=datetime.utcnow(),
                    removed_on=None
                )
                for identifier in new_identifiers if identifier not in existing_software_dict
            ]
            if new_objects:
                self.db.add_all(new_objects)
                logger.debug(f"Додано {len(new_objects)} нових ПО", extra={"hostname": db_computer.hostname})
        except SQLAlchemyError as e:
            logger.error(f"Помилка оновлення ПО: {str(e)}", extra={"hostname": db_computer.hostname})
            raise

    async def stream_computers(
        self,
        hostname: Optional[str],
        os_name: Optional[str],
        check_status: Optional[str],
        sort_by: str,
        sort_order: str,
        server_filter: Optional[str]
    ) -> AsyncGenerator[ComputerList, None]:
        """Потокова передача комп'ютерів з фільтрацією."""
        try:
            query = self._build_computer_query(hostname, os_name, check_status, server_filter, sort_by, sort_order)
            result = await self.db.stream(query)
            async for row in result:
                computer_obj = row[0]
                yield ComputerList.model_validate(computer_obj, from_attributes=True)
        except SQLAlchemyError as e:
            logger.error(f"Помилка потокового отримання комп’ютерів: {str(e)}")
            raise

    async def update_scan_task_status(self, task_id: str, status: str, scanned_hosts: int, successful_hosts: int, error: Optional[str]):
        """Оновлює статус задачі сканування."""
        try:
            result = await self.db.execute(
                select(models.ScanTask).filter(models.ScanTask.id == task_id)
            )
            scan_task = result.scalars().first()
            if scan_task:
                scan_task.status = status
                scan_task.scanned_hosts = scanned_hosts
                scan_task.successful_hosts = successful_hosts
                scan_task.error = error
                logger.debug(f"Статус задачі оновлено: {status}", extra={"task_id": task_id})
            else:
                logger.warning("Задача сканування не знайдена", extra={"task_id": task_id})
        except Exception as e:
            logger.error(f"Помилка оновлення статусу задачі: {str(e)}", extra={"task_id": task_id})
            raise

    async def clean_old_deleted_software(self) -> int:
        """Очищає старі записи про ПО з removed_on."""
        try:
            result = await self.db.execute(
                update(models.Software.__table__)
                .where(models.Software.removed_on.isnot(None))
                .values(removed_on=datetime.utcnow())
            )
            deleted_count = result.rowcount
            logger.debug(f"Очищено {deleted_count} записів ПО")
            return deleted_count
        except SQLAlchemyError as e:
            logger.error(f"Помилка очищення ПО: {str(e)}")
            raise

    async def get_all_hosts(self) -> List[str]:
        """Отримує список усіх хостів із бази даних."""
        try:
            result = await self.db.execute(select(models.Computer.hostname))
            return [row[0] for row in result.fetchall()]
        except SQLAlchemyError as e:
            logger.error(f"Помилка отримання хостів: {str(e)}")
            raise