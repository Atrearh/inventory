from typing import List, Optional, Tuple, Dict, Any, Type, TypeVar, AsyncGenerator, Callable
from datetime import datetime
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.exc import SQLAlchemyError
import logging
from .. import models
from ..schemas import PhysicalDisk, LogicalDisk, Processor, VideoCard, IPAddress, MACAddress, Software, ComputerCreate, ComputerList, ComputerListItem
from ..decorators import log_function_call
from typing import Union, Callable
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)

T = TypeVar("T")

class ComputerRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _get_base_computer_query(self):
        """Повертає базовий запит з усіма пов'язаними сутностями."""
        return select(models.Computer).options(
            selectinload(models.Computer.ip_addresses),
            selectinload(models.Computer.mac_addresses),
            selectinload(models.Computer.processors),
            selectinload(models.Computer.video_cards),
            selectinload(models.Computer.physical_disks).selectinload(models.PhysicalDisk.logical_disks),
            selectinload(models.Computer.software),
            selectinload(models.Computer.roles)
        )

    @log_function_call
    async def get_computer_by_guid(self, db: AsyncSession, object_guid: str) -> Optional[models.Computer]:
        """Отримує комп'ютер за object_guid."""
        try:
            query = self._get_base_computer_query().filter(models.Computer.object_guid == object_guid)
            result = await db.execute(query)
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

    async def get_all_computers_with_guid(self, db: AsyncSession, domain_id: Optional[int] = None) -> List[models.Computer]:
        """Отримує всі комп'ютери з ненульовим object_guid, з можливістю фільтрації за domain_id."""
        try:
            query = select(models.Computer).options(
                joinedload(models.Computer.ip_addresses),
                joinedload(models.Computer.mac_addresses),
                joinedload(models.Computer.processors),
                joinedload(models.Computer.physical_disks),
                joinedload(models.Computer.logical_disks),
                joinedload(models.Computer.video_cards),
                joinedload(models.Computer.software),
                joinedload(models.Computer.roles)
            ).filter(models.Computer.object_guid.isnot(None))
            if domain_id is not None:
                query = query.filter(models.Computer.domain_id == domain_id)
            result = await db.execute(query)
            computers = result.unique().scalars().all()
            logger.debug(f"Знайдено {len(computers)} комп'ютерів для domain_id={domain_id}")
            return computers
        except SQLAlchemyError as e:
            logger.error(f"Помилка отримання комп'ютерів: {str(e)}", exc_info=True)
            raise

    async def get_or_create_computer(self, computer_data: dict, hostname: str) -> models.Computer:
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
                    "motherboard", "last_boot", "check_status",
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
            
            db_computer = await self.get_or_create_computer(computer_data, hostname)
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

    def _build_computer_query_light(
        self,
        hostname: Optional[str] = None,
        os_name: Optional[str] = None,
        check_status: Optional[str] = None,
        server_filter: Optional[str] = None,
    ):
        """
        Створює 'легкий' SQLAlchemy-запит, завантажуючи лише необхідні для таблиці поля.
        """
        query = select(models.Computer).options(
            selectinload(models.Computer.ip_addresses),
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

        return query

    @log_function_call
    async def get_computers_list(
        self,
        page: int,
        limit: int,
        sort_by: str,
        sort_order: str,
        hostname: Optional[str] = None,
        os_name: Optional[str] = None,
        check_status: Optional[str] = None,
        server_filter: Optional[str] = None,
    ) -> Tuple[List[ComputerList], int]:
        """
        Отримання списку комп'ютерів з фільтрацією та пагінацією ('легкий' запит).
        """
        query = self._build_computer_query_light(
            hostname=hostname, os_name=os_name, check_status=check_status, server_filter=server_filter
        )

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        order_column = getattr(models.Computer, sort_by, models.Computer.hostname)
        if sort_order.lower() == "desc":
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column.asc())

        query = query.offset((page - 1) * limit).limit(limit)
        result = await self.db.execute(query)
        computers = result.unique().scalars().all()

        pydantic_computers = [ComputerList.model_validate(c) for c in computers]
        return pydantic_computers, total

    @log_function_call
    async def get_computer_details_by_id(self, computer_id: int) -> Optional[models.Computer]:
        """Отримує повну інформацію про комп'ютер за ID з використанням selectinload."""
        try:
            query = self._get_base_computer_query().filter(models.Computer.id == computer_id)
            result = await self.db.execute(query)
            computer = result.unique().scalars().first()
            
            if computer:
                # Примусово завантажуємо всі пов’язані дані
                await self.db.refresh(computer, [
                    "ip_addresses", "mac_addresses", "processors", "video_cards",
                    "physical_disks", "logical_disks", "software", "roles"
                ])
                # Переконуємося, що logical_disks для physical_disks завантажені
                for disk in computer.physical_disks:
                    await self.db.refresh(disk, ["logical_disks"])
            
            logger.debug(f"Комп'ютер отримано за ID: {'знайдено' if computer else 'не знайдено'}", extra={"computer_id": computer_id})
            return computer
        except SQLAlchemyError as e:
            logger.error(f"Помилка отримання комп'ютера за ID: {str(e)}", extra={"computer_id": computer_id})
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

    async def _create_logical_disk(self, db_computer: models.Computer, pydantic_model: LogicalDisk) -> models.LogicalDisk:
        """Створює логічний диск із прив’язкою до фізичного диску."""
        entity_data = pydantic_model.model_dump()
        # Видаляємо computer_id, detected_on і removed_on, щоб уникнути дублювання
        entity_data.pop('computer_id', None)
        entity_data.pop('detected_on', None)
        entity_data.pop('removed_on', None)
        new_logical_disk = models.LogicalDisk(
            **entity_data,
            computer_id=db_computer.id,
            detected_on=datetime.utcnow(),
            removed_on=None
        )
        # Додаткові перевірки для physical_disk_id
        if pydantic_model.parent_disk_serial:
            result = await self.db.execute(
                select(models.PhysicalDisk)
                .filter(models.PhysicalDisk.computer_id == db_computer.id)
                .filter(models.PhysicalDisk.serial == pydantic_model.parent_disk_serial)
            )
            physical_disk = result.scalars().first()
            if physical_disk:
                new_logical_disk.physical_disk_id = physical_disk.id
        return new_logical_disk

    @log_function_call
    async def update_related_entities(
        self,
        db_computer: models.Computer,
        new_entities: List[T],
        model_class: Type[DeclarativeBase],
        unique_field: Union[str, Tuple[str, ...]],
        collection_name: str,
        update_fields: Optional[List[str]] = None,
        custom_logic: Optional[Callable[[models.Computer, T], Any]] = None,
    ) -> None:
        """Оновлює пов’язані сутності для вказаного комп’ютера."""
        try:
            # Перевіряємо, чи сутності попередньо завантажено
            current_entities = getattr(db_computer, collection_name)
            if current_entities is None:
                logger.warning(f"Пов’язані сутності {collection_name} не завантажено для комп’ютера з ID {db_computer.id}")
                current_entities = []

            # Формуємо словник поточних сутностей
            current_entities_map = {}
            if isinstance(unique_field, str):
                current_entities_map = {getattr(entity, unique_field): entity for entity in current_entities if getattr(entity, unique_field) is not None}
            else:
                current_entities_map = {tuple(getattr(entity, field) for field in unique_field): entity for entity in current_entities if all(getattr(entity, field) is not None for field in unique_field)}

            # Формуємо словник нових сутностей
            new_entities_map = {}
            new_keys = []
            for entity in new_entities:
                key = getattr(entity, unique_field) if isinstance(unique_field, str) else tuple(getattr(entity, field) for field in unique_field)
                new_entities_map[key] = entity
                new_keys.append(key)

            current_keys = list(current_entities_map.keys())

            # Позначаємо видалені сутності
            for key in current_keys:
                if key not in new_keys:
                    entity_to_remove = current_entities_map[key]
                    if entity_to_remove.removed_on is None:
                        entity_to_remove.removed_on = datetime.utcnow()
                        logger.debug(f"Позначено як видалене: {model_class.__name__} з {unique_field}={key}", extra={"computer_id": db_computer.id})

            # Додати нові або оновити існуючі
            for key in new_keys:
                pydantic_model = new_entities_map[key]
                if key not in current_keys:
                    if custom_logic:
                        new_db_entity = await custom_logic(db_computer, pydantic_model)
                    else:
                        # Перевіряємо, чи існує запис у базі даних
                        entity_data = pydantic_model.model_dump()
                        entity_data.pop('computer_id', None)
                        entity_data.pop('detected_on', None)
                        entity_data.pop('removed_on', None)

                        # Для моделі Software перевіряємо унікальний ключ
                        if model_class.__name__ == "Software":
                            query = select(model_class).filter(
                                model_class.computer_id == db_computer.id,
                                model_class.name == key[0],
                                model_class.version == key[1]
                            )
                            result = await self.db.execute(query)
                            existing_entity = result.scalars().first()
                            if existing_entity:
                                if existing_entity.removed_on is not None:
                                    existing_entity.removed_on = None
                                    logger.debug(f"Відновлено сутність: {model_class.__name__} з {unique_field}={key}", extra={"computer_id": db_computer.id})
                                for field in update_fields or entity_data.keys():
                                    if hasattr(pydantic_model, field):
                                        setattr(existing_entity, field, getattr(pydantic_model, field))
                                continue  # Пропускаємо створення нового запису

                        new_db_entity = model_class(
                            **entity_data,
                            computer_id=db_computer.id,
                            detected_on=datetime.utcnow(),
                            removed_on=None
                        )
                    getattr(db_computer, collection_name).append(new_db_entity)
                    logger.debug(f"Додано нову сутність: {model_class.__name__} з {unique_field}={key}", extra={"computer_id": db_computer.id})
                else:
                    existing_entity = current_entities_map[key]
                    if existing_entity.removed_on is not None:
                        existing_entity.removed_on = None
                        logger.debug(f"Відновлено сутність: {model_class.__name__} з {unique_field}={key}", extra={"computer_id": db_computer.id})
                    # Оновити лише вказані поля
                    fields_to_update = update_fields or pydantic_model.model_dump().keys()
                    for field in fields_to_update:
                        if hasattr(pydantic_model, field):
                            setattr(existing_entity, field, getattr(pydantic_model, field))

            await self.db.flush()
            logger.debug(f"Оновлено {collection_name}", extra={"computer_id": db_computer.id})
        except SQLAlchemyError as e:
            logger.error(f"Помилка оновлення {collection_name}: {str(e)}", extra={"computer_id": db_computer.id})
            await self.db.rollback()
            raise

    async def update_computer_entities(self, db_computer: models.Computer, computer: ComputerCreate) -> None:
        """Оновлює всі пов'язані сутності комп'ютера."""
        try:
            if computer.ip_addresses is not None:
                await self.update_related_entities(
                    db_computer, computer.ip_addresses, models.IPAddress, "address", "ip_addresses",
                    update_fields=["address"]
                )
            if computer.mac_addresses is not None:
                await self.update_related_entities(
                    db_computer, computer.mac_addresses, models.MACAddress, "address", "mac_addresses",
                    update_fields=["address"]
                )
            if computer.processors is not None:
                await self.update_related_entities(
                    db_computer, computer.processors, models.Processor, "name", "processors",
                    update_fields=["name", "number_of_cores", "number_of_logical_processors"]
                )
            if computer.video_cards is not None:
                await self.update_related_entities(
                    db_computer, computer.video_cards, models.VideoCard, "name", "video_cards",
                    update_fields=["name", "driver_version"]
                )
            if computer.physical_disks is not None:
                await self.update_related_entities(
                    db_computer, computer.physical_disks, models.PhysicalDisk, "serial", "physical_disks",
                    update_fields=["model", "serial", "interface", "media_type"]
                )
            if computer.logical_disks is not None:
                await self.update_related_entities(
                    db_computer, computer.logical_disks, models.LogicalDisk, "device_id", "logical_disks",
                    update_fields=["device_id", "volume_label", "total_space", "free_space"],
                    custom_logic=self._create_logical_disk
                )
            if computer.software is not None:
                await self.update_related_entities(
                    db_computer, computer.software, models.Software, ("name", "version"), "software",
                    update_fields=["name", "version", "install_date"]
                )
            if computer.roles is not None:
                await self.update_related_entities(
                    db_computer, computer.roles, models.Role, "name", "roles",
                    update_fields=["name"]
                )
            await self.db.commit()
            logger.debug(f"Транзакцію для пов’язаних сутностей зафіксовано", extra={"computer_id": db_computer.id})
        except SQLAlchemyError as e:
            logger.error(f"Помилка оновлення пов’язаних сутностей для комп’ютера з ID {db_computer.id}: {str(e)}")
            await self.db.rollback()
            raise 

    async def stream_computers(
        self,
        hostname: Optional[str],
        os_name: Optional[str],
        check_status: Optional[str],
        server_filter: Optional[str]
    ) -> AsyncGenerator[ComputerList, None]:
        """Потокова передача комп'ютерів з фільтрацією."""
        try:
            query = self._build_computer_query_light(hostname, os_name, check_status, server_filter)
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

    async def get_computer_by_hostname(self, db: AsyncSession, hostname: str) -> Optional[models.Computer]:
        """Отримує комп'ютер за hostname з усіма пов’язаними сутностями."""
        try:
            query = self._get_base_computer_query().options(
                selectinload(models.Computer.domain)
            ).filter(models.Computer.hostname == hostname)
            result = await db.execute(query)
            computer = result.scalars().first()
            logger.debug(f"Комп'ютер отримано за hostname: {'знайдено' if computer else 'не знайдено'}", extra={"hostname": hostname})
            return computer
        except SQLAlchemyError as e:
            logger.error(f"Помилка отримання комп'ютера за hostname: {str(e)}", extra={"hostname": hostname})
            raise