import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession
from .. import models
from ..decorators import log_function_call
from ..schemas import ComputerCreate

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=models.Base)

# Конфігурація компонентів для спрощення оновлення пов’язаних сутностей
COMPONENT_CONFIG = {
    "ip_addresses": {
        "model": models.IPAddress,
        "unique_field": "address",
        "update_fields": ["address"],
    },
    "mac_addresses": {
        "model": models.MACAddress,
        "unique_field": "address",
        "update_fields": ["address"],
    },
    "processors": {
        "model": models.Processor,
        "unique_field": "name",
        "update_fields": ["name", "cores", "threads", "speed_ghz"],
    },
    "video_cards": {
        "model": models.VideoCard,
        "unique_field": "name",
        "update_fields": ["name", "vram", "driver_version"],
    },
    "physical_disks": {
        "model": models.PhysicalDisk,
        "unique_field": "serial",
        "update_fields": ["model", "serial", "interface", "media_type"],
    },
    "logical_disks": {
        "model": models.LogicalDisk,
        "unique_field": "device_id",
        "update_fields": ["device_id", "volume_label", "total_space", "free_space"],
        "custom_logic": "_create_logical_disk",
    },
    "roles": {
        "model": models.Role,
        "unique_field": "name",
        "update_fields": ["name"],
    },
}

class ComponentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_physical_disk_id(self, computer_id: int, serial: Optional[str]) -> Optional[int]:
        if not serial:
            return None
        try:
            result = await self.db.execute(
                select(models.PhysicalDisk.id).where(
                    models.PhysicalDisk.computer_id == computer_id,
                    models.PhysicalDisk.serial == serial,
                    models.PhysicalDisk.removed_on.is_(None),
                )
            )
            return result.scalars().first()
        except SQLAlchemyError as e:
            logger.error(
                f"Помилка отримання physical_disk_id для serial {serial}: {str(e)}",
                extra={"computer_id": computer_id},
            )
            return None

    async def _create_logical_disk(self, db_computer: models.Computer, pydantic_model: models.LogicalDisk) -> models.LogicalDisk:
        entity_data = pydantic_model.dict(exclude={"total_space_gb", "free_space_gb", "parent_disk_serial", "computer_id", "detected_on", "removed_on"})
        
        logger.debug(
            f"Дані для створення LogicalDisk: {entity_data}",
            extra={"computer_id": db_computer.id},
        )

        new_logical_disk = models.LogicalDisk(
            **entity_data,
            computer_id=db_computer.id,
            detected_on=datetime.utcnow(),
            removed_on=None,
        )
        if pydantic_model.parent_disk_serial:
            result = await self.db.execute(
                select(models.PhysicalDisk)
                .where(models.PhysicalDisk.computer_id == db_computer.id)
                .where(models.PhysicalDisk.serial == pydantic_model.parent_disk_serial)
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
        model_class: Type[models.Base],
        unique_field: str | Tuple[str, ...],
        collection_name: str,
        update_fields: Optional[List[str]] = None,
        custom_logic: Optional[Callable[[models.Computer, T], Any]] = None,
    ) -> None:
        try:
            current_entities = getattr(db_computer, collection_name) or []
            current_entities_map = (
                {getattr(entity, unique_field): entity for entity in current_entities if getattr(entity, unique_field) is not None}
                if isinstance(unique_field, str)
                else {
                    tuple(getattr(entity, field) for field in unique_field): entity
                    for entity in current_entities
                    if all(getattr(entity, field) is not None for field in unique_field)
                }
            )

            new_entities_map = {
                (getattr(entity, unique_field) if isinstance(unique_field, str) else tuple(getattr(entity, field) for field in unique_field)): entity
                for entity in new_entities
            }

            # Позначення видалених сутностей
            for key, entity in current_entities_map.items():
                if key not in new_entities_map and entity.removed_on is None:
                    entity.removed_on = datetime.utcnow()
                    logger.debug(
                        f"Позначено як видалене: {model_class.__name__} з {unique_field}={key}",
                        extra={"computer_id": db_computer.id},
                    )

            # Оновлення або створення нових сутностей
            for key, pydantic_model in new_entities_map.items():
                if key not in current_entities_map:
                    new_db_entity = (
                        await custom_logic(db_computer, pydantic_model)
                        if custom_logic
                        else model_class(
                            **{k: v for k, v in pydantic_model.dict().items() if k not in ["computer_id", "detected_on", "removed_on"]},
                            computer_id=db_computer.id,
                            detected_on=datetime.utcnow(),
                            removed_on=None,
                        )
                    )
                    getattr(db_computer, collection_name).append(new_db_entity)
                    logger.debug(
                        f"Додано нову сутність: {model_class.__name__} з {unique_field}={key}",
                        extra={"computer_id": db_computer.id},
                    )
                else:
                    existing_entity = current_entities_map[key]
                    if existing_entity.removed_on is not None:
                        existing_entity.removed_on = None
                        logger.debug(
                            f"Відновлено сутність: {model_class.__name__} з {unique_field}={key}",
                            extra={"computer_id": db_computer.id},
                        )
                    for field in update_fields or pydantic_model.dict().keys():
                        if field != "id" and hasattr(pydantic_model, field):
                            setattr(existing_entity, field, getattr(pydantic_model, field))

            await self.db.flush()
            logger.debug(f"Оновлено {collection_name}", extra={"computer_id": db_computer.id})
        except SQLAlchemyError as e:
            logger.error(
                f"Помилка оновлення {collection_name}: {str(e)}",
                extra={"computer_id": db_computer.id},
            )
            await self.db.rollback()
            raise

    async def update_computer_entities(self, db_computer: models.Computer, computer: ComputerCreate) -> None:
        try:
            for collection_name, config in COMPONENT_CONFIG.items():
                new_entities = getattr(computer, collection_name)
                if new_entities is not None:
                    custom_logic_func = getattr(self, config["custom_logic"], None) if "custom_logic" in config else None
                    
                    await self.update_related_entities(
                        db_computer,
                        new_entities,
                        config["model"],
                        config["unique_field"],
                        collection_name,
                        update_fields=config["update_fields"],
                        custom_logic=custom_logic_func,
                    )
            
            await self.db.commit()
            logger.debug(f"Транзакцію для пов’язаних сутностей зафіксовано", extra={"computer_id": db_computer.id})
        except SQLAlchemyError as e:
            logger.error(f"Помилка оновлення пов’язаних сутностей для комп’ютера з ID {db_computer.id}: {str(e)}")
            await self.db.rollback()
            raise

    async def get_component_history(self, computer_id: int) -> List[Dict[str, Any]]:
        try:
            history = []
            for component_type, model in [
                ("physical_disk", models.PhysicalDisk),
                ("logical_disk", models.LogicalDisk),
                ("processor", models.Processor),
                ("video_card", models.VideoCard),
                ("ip_address", models.IPAddress),
                ("mac_address", models.MACAddress),
                ("software", models.InstalledSoftware),  # Оновлено з Software на InstalledSoftware
            ]:
                result = await self.db.execute(
                    select(model).where(model.computer_id == computer_id)
                )
                for item in result.scalars().all():
                    history.append(
                        {
                            "component_type": component_type,
                            "data": item.__dict__,
                            "detected_on": (item.detected_on.isoformat() if item.detected_on else None),
                            "removed_on": (item.removed_on.isoformat() if item.removed_on else None),
                        }
                    )
            history.sort(key=lambda x: x["detected_on"] or "")
            logger.debug(
                f"Отримано історію компонентів: {len(history)} записів",
                extra={"computer_id": computer_id},
            )
            return history
        except SQLAlchemyError as e:
            logger.error(
                f"Помилка отримання історії компонентів: {str(e)}",
                extra={"computer_id": computer_id},
            )
            raise