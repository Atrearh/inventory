from typing import List, Optional, Tuple, Dict, Any, Type, TypeVar, AsyncGenerator
from datetime import datetime
from sqlalchemy import select, func, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
import logging
from .. import models
from sqlalchemy.orm import selectinload
from typing_extensions import List as ListAny
from functools import lru_cache
import hashlib
import time
from ..schemas import PhysicalDisk, LogicalDisk, Processor, VideoCard, IPAddress, MACAddress, Software,  ComputerCreate, ComputerList, ComputerListItem

logger = logging.getLogger(__name__)

T = TypeVar("T")

class ComputerRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_or_create_computer(self, computer_data: dict, hostname: str) -> models.Computer:
        """Получает или создает компьютер в базе данных по hostname."""
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
            return db_computer
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении/создании компьютера {hostname}: {str(e)}", exc_info=True)
            raise

    async def async_upsert_computer(self, computer: ComputerCreate, hostname: str, mode: str = "Full") -> int:
        """Создает или обновляет компьютер в базе данных."""
        try:
            computer_data = computer.model_dump(
                include={
                    "hostname", "os_name", "os_version", "ram",
                    "motherboard", "last_boot", "is_virtual", "check_status"
                }
            )
            logger.debug(f"Входные данные для обновления компьютера {hostname}: {computer_data}")
            computer_data["last_updated"] = datetime.utcnow()
            if mode == "Full":
                computer_data["last_full_scan"] = datetime.utcnow()
            db_computer = await self._get_or_create_computer(computer_data, hostname)
            await self.db.flush()
            await self.db.commit()
            logger.debug(f"Компьютер {hostname} сохранен с ID {db_computer.id}, os_name={db_computer.os_name}, os_version={db_computer.os_version}, ram={db_computer.ram}")
            self.get_computers.cache_clear()  # Сбрасываем кэш при обновлении
            return db_computer.id
        except SQLAlchemyError as e:
            logger.error(f"Ошибка базы данных при сохранении компьютера {hostname}: {str(e)}", exc_info=True)
            await self.db.rollback()
            raise

    async def _computer_to_pydantic(self, computers: List[models.Computer]) -> List[ComputerListItem]:
        """Преобразует список объектов компьютера в Pydantic-схему."""
        try:
            return [ComputerListItem.model_validate(comp, from_attributes=True) for comp in computers]
        except Exception as e:
            logger.error(f"Ошибка преобразования компьютеров в Pydantic-схему: {str(e)}")
            raise



    def _build_computer_query(
        self,
        hostname: Optional[str] = None, # ✨ ИСПРАВЛЕНИЕ: Добавлен недостающий аргумент
        os_name: Optional[str] = None,
        check_status: Optional[str] = None,
        server_filter: Optional[str] = None,
        sort_by: str = "hostname",
        sort_order: str = "asc"
    ) -> Any:
        """Создает SQLAlchemy-запрос для получения компьютеров с фильтрами."""
        query = select(models.Computer)
        if hostname: # ✨ ИСПРАВЛЕНИЕ: Добавлена логика фильтрации по hostname
            query = query.filter(models.Computer.hostname.ilike(f"%{hostname}%"))
        if os_name:
            query = query.filter(models.Computer.os_name.ilike(f"%{os_name}%"))
        if check_status:
            query = query.filter(models.Computer.check_status == check_status)
        if server_filter == "server":
            query = query.filter(models.Computer.os_name.ilike("%server%"))
        elif server_filter == "client":
            query = query.filter(~models.Computer.os_name.ilike("%server%"))
        if sort_by in ["hostname", "os_name", "last_updated", "check_status"]:
            order_column = getattr(models.Computer, sort_by)
            if sort_order.lower() == "desc":
                order_column = order_column.desc()
            query = query.order_by(order_column)
        else:
            query = query.order_by(models.Computer.hostname)
        return query

    def _generate_cache_key(
        self,
        os_name: Optional[str],
        check_status: Optional[str],
        sort_by: str,
        sort_order: str,
        page: int,
        limit: int,
        server_filter: Optional[str]
    ) -> str:
        """Генерирует ключ для кэширования на основе параметров запроса."""
        params = f"{os_name}|{check_status}|{sort_by}|{sort_order}|{page}|{limit}|{server_filter}"
        return hashlib.md5(params.encode()).hexdigest()

    @lru_cache(maxsize=100)
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
        """Получение списка компьютеров с фильтрацией и пагинацией."""
        start_time = time.time()
        cache_key = self._generate_cache_key(os_name, check_status, sort_by, sort_order, page, limit, server_filter)
        try:
            # Создаем запрос с фильтрами
            query = self._build_computer_query(
                os_name=os_name,
                check_status=check_status,
                server_filter=server_filter,
                sort_by=sort_by,
                sort_order=sort_order
            )

            # Подсчет общего количества после фильтрации
            count_query = select(func.count()).select_from(query.subquery())
            total = (await self.db.execute(count_query)).scalar() or 0

            # Пагинация
            query = query.offset((page - 1) * limit).limit(limit)
            result = await self.db.execute(query)
            computers = result.scalars().all()

            # Преобразуем SQLAlchemy объекты в Pydantic
            pydantic_computers = await self._computer_to_pydantic(computers)
            logger.debug(f"Получено {len(pydantic_computers)} компьютеров, всего: {total}, время: {time.time() - start_time:.3f} сек, cache_key: {cache_key}")
            return pydantic_computers, total
        except Exception as e:
            logger.error(f"Ошибка при получении компьютеров: {str(e)}", exc_info=True)
            raise

    async def async_get_computer_by_id(self, computer_id: int) -> Optional[ComputerList]:
        """Получает компьютер по ID."""
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
            # ✨ ИСПРАВЛЕНИЕ: Валидируем одну модель, а не список
            return ComputerList.model_validate(computer, from_attributes=True) if computer else None
        except SQLAlchemyError as e:
            logger.error(f"Ошибка базы данных при получении компьютера ID {computer_id}: {str(e)}")
            raise

    async def async_update_computer_check_status(self, hostname: str, check_status: str) -> Optional[models.Computer]:
        """Обновляет статус проверки компьютера."""
        try:
            result = await self.db.execute(
                select(models.Computer).filter(models.Computer.hostname == hostname)
            )
            db_computer = result.scalars().first()
            if not db_computer:
                return None
            new_check_status = models.CheckStatus(check_status)
            if db_computer.check_status != new_check_status:
                db_computer.check_status = new_check_status
            return db_computer
        except ValueError:
            logger.error(f"Недопустимое значение check_status: {check_status}")
            raise
        except SQLAlchemyError as e:
            logger.error(f"Ошибка обновления check_status для {hostname}: {str(e)}", exc_info=True)
            raise




    async def get_component_history(self, computer_id: int) -> List[Dict[str, Any]]:
        """Получает историю компонентов компьютера."""
        try:
            history = []
            
            # Получение физических дисков
            physical_disks = await self.db.execute(
                select(models.PhysicalDisk)
                .where(models.PhysicalDisk.computer_id == computer_id)
            )
            for disk in physical_disks.scalars().all():
                history.append({
                    "component_type": "physical_disk",
                    "data": PhysicalDisk.model_validate(disk, from_attributes=True).model_dump(),
                    "detected_on": disk.detected_on.isoformat() if disk.detected_on else None,
                    "removed_on": disk.removed_on.isoformat() if disk.removed_on else None
                })
            
            # Получение логических дисков
            logical_disks = await self.db.execute(
                select(models.LogicalDisk)
                .where(models.LogicalDisk.computer_id == computer_id)
            )
            for disk in logical_disks.scalars().all():
                history.append({
                    "component_type": "logical_disk",
                    "data": LogicalDisk.model_validate(disk, from_attributes=True).model_dump(),
                    "detected_on": disk.detected_on.isoformat() if disk.detected_on else None,
                    "removed_on": disk.removed_on.isoformat() if disk.removed_on else None
                })
            
            # Получение процессоров
            processors = await self.db.execute(
                select(models.Processor)
                .where(models.Processor.computer_id == computer_id)
            )
            for proc in processors.scalars().all():
                history.append({
                    "component_type": "processor",
                    "data": Processor.model_validate(proc, from_attributes=True).model_dump(),
                    "detected_on": proc.detected_on.isoformat() if proc.detected_on else None,
                    "removed_on": proc.removed_on.isoformat() if proc.removed_on else None
                })
            
            # Получение видеокарт
            video_cards = await self.db.execute(
                select(models.VideoCard)
                .where(models.VideoCard.computer_id == computer_id)
            )
            for vc in video_cards.scalars().all():
                history.append({
                    "component_type": "video_card",
                    "data": VideoCard.model_validate(vc, from_attributes=True).model_dump(),
                    "detected_on": vc.detected_on.isoformat() if vc.detected_on else None,
                    "removed_on": vc.removed_on.isoformat() if vc.removed_on else None
                })
            
            # Получение IP-адресов
            ip_addresses = await self.db.execute(
                select(models.IPAddress)
                .where(models.IPAddress.computer_id == computer_id)
            )
            for ip in ip_addresses.scalars().all():
                history.append({
                    "component_type": "ip_address",
                    "data": IPAddress.model_validate(ip, from_attributes=True).model_dump(),
                    "detected_on": ip.detected_on.isoformat() if ip.detected_on else None,
                    "removed_on": ip.removed_on.isoformat() if ip.removed_on else None
                })
            
            # Получение MAC-адресов
            mac_addresses = await self.db.execute(
                select(models.MACAddress)
                .where(models.MACAddress.computer_id == computer_id)
            )
            for mac in mac_addresses.scalars().all():
                history.append({
                    "component_type": "mac_address",
                    "data": MACAddress.model_validate(mac, from_attributes=True).model_dump(),
                    "detected_on": mac.detected_on.isoformat() if mac.detected_on else None,
                    "removed_on": mac.removed_on.isoformat() if mac.removed_on else None
                })
            
            # Получение программного обеспечения
            software = await self.db.execute(
                select(models.Software)
                .where(models.Software.computer_id == computer_id)
            )
            for sw in software.scalars().all():
                history.append({
                    "component_type": "software",
                    "data": Software.model_validate(sw, from_attributes=True).model_dump(),
                    "detected_on": sw.detected_on.isoformat() if sw.detected_on else None,
                    "removed_on": sw.removed_on.isoformat() if sw.removed_on else None
                })
            
            # Сортировка по detected_on
            history.sort(key=lambda x: x["detected_on"] or "")
            return history
        except SQLAlchemyError as e:
            logger.error(f"Ошибка базы данных при получении истории компонентов для ID {computer_id}: {str(e)}")
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
        """Универсальная функция для обновления связанных сущностей."""
        try:
            # Получаем новые идентификаторы
            new_identifiers = {entity if isinstance(entity, str) else getattr(entity, unique_field) for entity in new_entities}
            new_entities_dict = {entity if isinstance(entity, str) else getattr(entity, unique_field): entity for entity in new_entities}
            
            # Загружаем все существующие записи, включая помеченные как удаленные
            result = await self.db.execute(
                select(model_class).where(
                    model_class.computer_id == db_computer.id
                )
            )
            existing_entities_dict = {getattr(e, unique_field): e for e in result.scalars().all()}
            
            # Пометить как удаленные записи, которых нет в новых данных
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
            
            # Обновляем или добавляем записи
            new_objects = []
            for identifier in new_identifiers:
                if identifier in existing_entities_dict:
                    # Если запись существует, обновляем её
                    existing_entity = existing_entities_dict[identifier]
                    if existing_entity.removed_on is not None:
                        # Сбрасываем removed_on для восстановления записи
                        existing_entity.removed_on = None
                        existing_entity.detected_on = datetime.utcnow()
                        for field in update_fields:
                            setattr(existing_entity, field, getattr(new_entities_dict[identifier], field))
                        logger.debug(f"Восстановлена и обновлена запись {table.name} с {unique_field}={identifier} для {db_computer.hostname}")
                else:
                    # Создаем новую запись
                    new_entity = new_entities_dict[identifier]
                    if custom_logic:
                        new_objects.append(await custom_logic(db_computer, new_entity))
                    else:
                        new_objects.append(
                            model_class(
                                computer_id=db_computer.id,
                                **{field: getattr(new_entity, field) for field in update_fields + [unique_field]},
                                detected_on=datetime.utcnow(),
                                removed_on=None
                            )
                        )
            if new_objects:
                self.db.add_all(new_objects)
                logger.debug(f"Добавлено {len(new_objects)} новых записей в {table.name} для {db_computer.hostname}")
            
            await self.db.flush()
            logger.debug(f"После обновления {table.name} для {db_computer.hostname}: "
                        f"{[getattr(e, unique_field) for e in (await self.db.execute(select(model_class).where(model_class.computer_id == db_computer.id, model_class.removed_on.is_(None)))).scalars().all()]}")
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при обновлении {table.name} для {db_computer.hostname}: {str(e)}")
            await self.db.rollback()
            raise

    async def _get_physical_disk_id(self, computer_id: int, serial: Optional[str]) -> Optional[int]:
        """Получает ID физического диска по его серийному номеру."""
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
            logger.error(f"Ошибка получения physical_disk_id для serial {serial}: {str(e)}")
            return None

    async def _create_logical_disk(self, db_computer: models.Computer, disk: LogicalDisk) -> models.LogicalDisk:
        """Создает объект логического диска с учетом parent_disk_serial."""
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
        """Обновляет все связанные сущности компьютера."""
        try:
            if computer.ip_addresses is not None:
                await self._update_entities(
                    db_computer, computer.ip_addresses, models.IPAddress, models.IPAddress.__table__,
                    "address", ["address"]
                )
                logger.debug(f"После обновления ip_addresses для {db_computer.hostname}: "
                            f"{[ip.address for ip in (await self.db.execute(select(models.IPAddress).where(models.IPAddress.computer_id == db_computer.id, models.IPAddress.removed_on.is_(None)))).scalars().all()]}")
            
            if computer.mac_addresses is not None:
                await self._update_entities(
                    db_computer, computer.mac_addresses, models.MACAddress, models.MACAddress.__table__,
                    "address", ["address"]
                )
                logger.debug(f"После обновления mac_addresses для {db_computer.hostname}: "
                            f"{[mac.address for mac in (await self.db.execute(select(models.MACAddress).where(models.MACAddress.computer_id == db_computer.id, models.MACAddress.removed_on.is_(None)))).scalars().all()]}")
            
            if computer.processors is not None:
                await self._update_entities(
                    db_computer, computer.processors, models.Processor, models.Processor.__table__,
                    "name", ["name", "number_of_cores", "number_of_logical_processors"]
                )
                logger.debug(f"После обновления processors для {db_computer.hostname}: "
                            f"{[proc.name for proc in (await self.db.execute(select(models.Processor).where(models.Processor.computer_id == db_computer.id, models.Processor.removed_on.is_(None)))).scalars().all()]}")
            
            if computer.video_cards is not None:
                await self._update_entities(
                    db_computer, computer.video_cards, models.VideoCard, models.VideoCard.__table__,
                    "name", ["name", "driver_version"]
                )
                logger.debug(f"После обновления video_cards для {db_computer.hostname}: "
                            f"{[vc.name for vc in (await self.db.execute(select(models.VideoCard).where(models.VideoCard.computer_id == db_computer.id, models.VideoCard.removed_on.is_(None)))).scalars().all()]}")
            
            if computer.physical_disks is not None:
                await self._update_entities(
                    db_computer, computer.physical_disks, models.PhysicalDisk, models.PhysicalDisk.__table__,
                    "serial", ["model", "serial", "interface", "media_type"]
                )
                logger.debug(f"После обновления physical_disks для {db_computer.hostname}: "
                            f"{[pd.serial for pd in (await self.db.execute(select(models.PhysicalDisk).where(models.PhysicalDisk.computer_id == db_computer.id, models.PhysicalDisk.removed_on.is_(None)))).scalars().all()]}")
            
            if computer.logical_disks is not None:
                await self._update_entities(
                    db_computer, computer.logical_disks, models.LogicalDisk, models.LogicalDisk.__table__,
                    "device_id", ["device_id", "volume_label", "total_space", "free_space", "physical_disk_id"],
                    custom_logic=self._create_logical_disk
                )
                logger.debug(f"После обновления logical_disks для {db_computer.hostname}: "
                            f"{[ld.device_id for ld in (await self.db.execute(select(models.LogicalDisk).where(models.LogicalDisk.computer_id == db_computer.id, models.LogicalDisk.removed_on.is_(None)))).scalars().all()]}")
            
            if computer.software is not None:
                await self._update_software_async(db_computer, computer.software, mode)
                logger.debug(f"После обновления software для {db_computer.hostname}: "
                            f"{[sw.name for sw in (await self.db.execute(select(models.Software).where(models.Software.computer_id == db_computer.id, models.Software.removed_on.is_(None)))).scalars().all()]}")
            
            if computer.roles is not None:
                await self._update_entities(
                    db_computer, computer.roles, models.Role, models.Role.__table__,
                    "name", ["name"]
                )
                logger.debug(f"После обновления roles для {db_computer.hostname}: "
                            f"{[role.name for role in (await self.db.execute(select(models.Role).where(models.Role.computer_id == db_computer.id, models.Role.removed_on.is_(None)))).scalars().all()]}")
            
            await self.db.commit()  # Явно фиксируем транзакцию
            logger.debug(f"Транзакция для связанных сущностей {db_computer.hostname} зафиксирована")
        except SQLAlchemyError as e:
            logger.error(f"Ошибка обновления связанных сущностей для {db_computer.hostname}: {str(e)}", exc_info=True)
            await self.db.rollback()
            raise

    async def _update_software_async(self, db_computer: models.Computer, new_software: List[Software], mode: str) -> None:
        """Обновляет программное обеспечение компьютера."""
        if not new_software:
            logger.debug(f"Данные о ПО отсутствуют для {db_computer.hostname}, обновление ПО пропущено")
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
                logger.debug(f"Пометили как удаленные {len(software_to_mark_removed)} ПО для {db_computer.hostname}")
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
                logger.debug(f"Добавлено {len(new_objects)} новых ПО для {db_computer.hostname}")
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при обновлении ПО для {db_computer.hostname}: {str(e)}")
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
        """Потоковая передача компьютеров с фильтрацией."""
        try:
            query = self._build_computer_query(hostname, os_name, check_status, server_filter, sort_by, sort_order)
            
            query = query.options(
                selectinload(models.Computer.physical_disks),
                selectinload(models.Computer.logical_disks),
                selectinload(models.Computer.ip_addresses),
                selectinload(models.Computer.mac_addresses),
                selectinload(models.Computer.video_cards),
                selectinload(models.Computer.processors),  # Добавлено
                selectinload(models.Computer.software),   # Добавлено
                selectinload(models.Computer.roles)       # Добавлено
            )
            
            result = await self.db.stream(query)
            async for row in result:
                computer_obj = row[0]
                yield ComputerList.model_validate(computer_obj, from_attributes=True)
        except SQLAlchemyError as e:
            logger.error(f"Ошибка базы данных при потоковом получении компьютеров: {str(e)}", exc_info=True)
            raise

    
    async def update_scan_task_status(self, task_id: str, status: str, scanned_hosts: int, successful_hosts: int, error: Optional[str]):
        """Обновляет статус задачи сканирования."""
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
            else:
                logger.warning(f"Задача сканирования {task_id} не найдена")
        except Exception as e:
            logger.error(f"Ошибка обновления статуса задачи {task_id}: {str(e)}", exc_info=True)
            raise

    async def clean_old_deleted_software(self) -> int:
        """Очищает старые записи о ПО с removed_on."""
        try:
            result = await self.db.execute(
                update(models.Software.__table__)
                .where(models.Software.removed_on.isnot(None))
                .values(removed_on=datetime.utcnow())
            )
            deleted_count = result.rowcount
            logger.debug(f"Очищено {deleted_count} записей о ПО")
            return deleted_count
        except SQLAlchemyError as e:
            logger.error(f"Ошибка очистки старых записей ПО: {str(e)}")
            raise
        
    async def get_all_hosts(self) -> List[str]:
        """Получает список всех хостов из базы данных."""
        try:
            result = await self.db.execute(select(models.Computer.hostname))
            return [row[0] for row in result.fetchall()]
        except SQLAlchemyError as e:
            logger.error(f"Ошибка получения хостов из БД: {str(e)}")
            raise            