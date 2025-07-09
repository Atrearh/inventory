from typing import List, Optional, Tuple, Dict, Any, Type, TypeVar, AsyncGenerator
from datetime import datetime
from sqlalchemy import select, func, tuple_, update, literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
import logging
from .. import models, schemas
from sqlalchemy.orm import selectinload
from sqlalchemy import union_all
from typing_extensions import List as ListAny

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

    async def async_upsert_computer(self, computer: schemas.ComputerCreate, hostname: str, mode: str = "Full") -> int:
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
            return db_computer.id
        except SQLAlchemyError as e:
            logger.error(f"Ошибка базы данных при сохранении компьютера {hostname}: {str(e)}", exc_info=True)
            await self.db.rollback()
            raise

    async def _computer_to_pydantic(self, computer: models.Computer) -> schemas.ComputerList:
        """Преобразует объект компьютера в Pydantic-схему."""
        try:
            return schemas.ComputerList.model_validate(computer, from_attributes=True)
        except Exception as e:
            logger.error(f"Ошибка преобразования компьютера {computer.id} в Pydantic-схему: {str(e)}")
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
        """Создает SQLAlchemy-запрос для получения компьютеров с фильтрами."""
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
        return query

    async def get_computers(
        self,
        hostname: Optional[str],
        os_name: Optional[str],
        check_status: Optional[str],
        sort_by: str,
        sort_order: str,
        page: int,
        limit: int,
        server_filter: Optional[str]
    ) -> Tuple[List[schemas.ComputerList], int]:
        """Получает список компьютеров с пагинацией и фильтрацией."""
        try:
            query = self._build_computer_query(hostname, os_name, check_status, server_filter, sort_by, sort_order)
            count_query = select(func.count()).select_from(query.subquery())
            result = await self.db.execute(count_query)
            total = result.scalar()
            if limit > 0:
                query = query.offset((page - 1) * limit).limit(limit)
            result = await self.db.execute(query)
            computers = result.scalars().all()
            pydantic_computers = [await self._computer_to_pydantic(computer) for computer in computers]
            return pydantic_computers, total
        except SQLAlchemyError as e:
            logger.error(f"Ошибка базы данных при получении списка компьютеров: {str(e)}", exc_info=True)
            raise

    async def async_get_computer_by_id(self, computer_id: int) -> Optional[schemas.ComputerList]:
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
            return await self._computer_to_pydantic(computer) if computer else None
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
        """Получает историю компонентов компьютера с помощью UNION ALL."""
        try:
            component_queries = [
                (select(
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
                ).where(models.PhysicalDisk.computer_id == computer_id)),
                (select(
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
                ).where(models.LogicalDisk.computer_id == computer_id)),
                (select(
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
                ).where(models.Processor.computer_id == computer_id)),
                (select(
                    literal('video_card').label('component_type'),
                    func.JSON_OBJECT(
                        'name', models.VideoCard.name,
                        'driver_version', models.VideoCard.driver_version,
                        'detected_on', models.VideoCard.detected_on,
                        'removed_on', models.VideoCard.removed_on
                    ).label('data'),
                    models.VideoCard.detected_on,
                    models.VideoCard.removed_on
                ).where(models.VideoCard.computer_id == computer_id)),
                (select(
                    literal('ip_address').label('component_type'),
                    func.JSON_OBJECT(
                        'address', models.IPAddress.address,
                        'detected_on', models.IPAddress.detected_on,
                        'removed_on', models.IPAddress.removed_on
                    ).label('data'),
                    models.IPAddress.detected_on,
                    models.IPAddress.removed_on
                ).where(models.IPAddress.computer_id == computer_id)),
                (select(
                    literal('mac_address').label('component_type'),
                    func.JSON_OBJECT(
                        'address', models.MACAddress.address,
                        'detected_on', models.MACAddress.detected_on,
                        'removed_on', models.MACAddress.removed_on
                    ).label('data'),
                    models.MACAddress.detected_on,
                    models.MACAddress.removed_on
                ).where(models.MACAddress.computer_id == computer_id)),
                (select(
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
                ).where(models.Software.computer_id == computer_id))
            ]
            union_query = union_all(*component_queries).order_by('detected_on')
            result = await self.db.execute(union_query)
            return [
                {
                    "component_type": row.component_type,
                    "data": row.data,
                    "detected_on": row.detected_on.isoformat() if row.detected_on else None,
                    "removed_on": row.removed_on.isoformat() if row.removed_on else None
                }
                for row in result.fetchall()
            ]
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

    async def _create_logical_disk(self, db_computer: models.Computer, disk: schemas.LogicalDisk) -> models.LogicalDisk:
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

    async def update_related_entities(self, db_computer: models.Computer, computer: schemas.ComputerCreate, mode: str = "Full") -> None:
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

    async def _update_software_async(self, db_computer: models.Computer, new_software: List[schemas.Software], mode: str) -> None:
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
    ) -> AsyncGenerator[schemas.ComputerList, None]:
        """Потоковая передача компьютеров с фильтрацией."""
        try:
            query = self._build_computer_query(hostname, os_name, check_status, server_filter, sort_by, sort_order)
            async for computer in await self.db.stream(query):
                yield await self._computer_to_pydantic(computer.scalars().first())
        except SQLAlchemyError as e:
            logger.error(f"Ошибка базы данных при потоковом получении компьютеров: {str(e)}", exc_info=True)
            raise

    async def get_all_hosts(self) -> List[str]:
        """Получает список всех хостов из базы данных."""
        try:
            result = await self.db.execute(select(models.Computer.hostname))
            return [row[0] for row in result.fetchall()]
        except SQLAlchemyError as e:
            logger.error(f"Ошибка получения хостов из БД: {str(e)}")
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