# app/repositories/related_entity_repository.py
from typing import TypeVar, List, Type, Any
from sqlalchemy import select, update, func, tuple_ 
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
import logging
from .. import models, schemas
from datetime import datetime

logger = logging.getLogger(__name__)

T = TypeVar("T")

class RelatedEntityRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _update_related_entities_async(
        self,
        db_computer: models.Computer, 
        new_entities: List[Any],
        model_class: Type[T],
        table: Any,
        unique_field: str,
        update_fields: List[str],
    ) -> None:
        try:
            # Формуємо список унікальних ідентифікаторів нових компонентів
            new_identifiers = {entity if isinstance(entity, str) else getattr(entity, unique_field) for entity in new_entities}
            new_entities_dict = {entity if isinstance(entity, str) else getattr(entity, unique_field): entity for entity in new_entities}

            # Отримуємо активні компоненти з БД (де removed_on IS NULL)
            result = await self.db.execute(
                select(model_class).where(
                    model_class.computer_id == db_computer.id,
                    model_class.removed_on.is_(None)
                )
            )
            existing_entities_dict = {getattr(e, unique_field): e for e in result.scalars().all()}

            # Визначаємо компоненти, які потрібно позначити як видалені
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
                logger.debug(f"Позначено як видалені {len(entities_to_mark_removed)} {table.name} для {db_computer.hostname}")

            # Створюємо нові компоненти
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
                    logger.debug(f"Додано новий компонент {identifier} до {table.name} для {db_computer.hostname}")

            if new_objects:
                self.db.add_all(new_objects)
                logger.debug(f"Додано {len(new_objects)} нових записів до {table.name} для {db_computer.hostname}")

            await self.db.flush()
        except Exception as e:
            logger.error(f"Помилка при оновленні {table.name} для {db_computer.hostname}: {str(e)}")
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

    async def update_related_entities(self, db_computer: models.Computer, computer: schemas.ComputerCreate):
        try:
            if computer.roles:
                await self._update_related_entities_async(
                    db_computer, computer.roles, models.Role, models.Role.__table__, "name", ["name"]
                )
            if computer.disks:
                await self._update_related_entities_async(
                    db_computer, computer.disks, models.Disk, models.Disk.__table__, "device_id",
                    ["total_space", "model", "serial", "interface", "media_type", "volume_label"]
                )
            if computer.software:
                await self._update_software_async(db_computer, computer.software)
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
        except SQLAlchemyError as e:
            logger.error(f"Помилка бази даних при оновленні пов’язаних сутностей для {db_computer.hostname}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Помилка оновлення пов’язаних сутностей для {db_computer.hostname}: {str(e)}")
            raise