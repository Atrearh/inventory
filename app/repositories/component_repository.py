import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from .. import models
from ..decorators import log_function_call
from ..schemas import ComputerCreate

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=SQLModel)

class ComponentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_physical_disk_id(self, computer_id: int, serial: Optional[str]) -> Optional[int]:
        # Перенесено з ComputerRepository без змін
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
        # Перенесено з ComputerRepository без змін
        entity_data = pydantic_model.dict(exclude={"total_space_gb", "free_space_gb"})
        entity_data.pop("parent_disk_serial", None)
        entity_data.pop("computer_id", None)
        entity_data.pop("detected_on", None)
        entity_data.pop("removed_on", None)

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
        model_class: Type[SQLModel],
        unique_field: str | Tuple[str, ...],
        collection_name: str,
        update_fields: Optional[List[str]] = None,
        custom_logic: Optional[Callable[[models.Computer, T], Any]] = None,
    ) -> None:
        # Перенесено з ComputerRepository без змін
        try:
            current_entities = getattr(db_computer, collection_name) or []
            current_entities_map = (
                {
                    getattr(entity, unique_field): entity
                    for entity in current_entities
                    if getattr(entity, unique_field) is not None
                }
                if isinstance(unique_field, str)
                else {
                    tuple(getattr(entity, field) for field in unique_field): entity
                    for entity in current_entities
                    if all(getattr(entity, field) is not None for field in unique_field)
                }
            )

            new_entities_map = {
                (
                    getattr(entity, unique_field)
                    if isinstance(unique_field, str)
                    else tuple(getattr(entity, field) for field in unique_field)
                ): entity
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
                            **{
                                k: v
                                for k, v in pydantic_model.dict().items()
                                if k not in ["computer_id", "detected_on", "removed_on"]
                            },
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
            logger.debug(
                f"Оновлено {collection_name}", extra={"computer_id": db_computer.id}
            )
        except SQLAlchemyError as e:
            logger.error(
                f"Помилка оновлення {collection_name}: {str(e)}",
                extra={"computer_id": db_computer.id},
            )
            await self.db.rollback()
            raise

    async def update_computer_entities(self, db_computer: models.Computer, computer: ComputerCreate) -> None:
        # Перенесено з ComputerRepository без змін
        try:
            if computer.ip_addresses is not None:
                await self.update_related_entities(
                    db_computer,
                    computer.ip_addresses,
                    models.IPAddress,
                    "address",
                    "ip_addresses",
                    update_fields=["address"],
                )
            if computer.mac_addresses is not None:
                await self.update_related_entities(
                    db_computer,
                    computer.mac_addresses,
                    models.MACAddress,
                    "address",
                    "mac_addresses",
                    update_fields=["address"],
                )
            if computer.processors is not None:
                await self.update_related_entities(
                    db_computer,
                    computer.processors,
                    models.Processor,
                    "name",
                    "processors",
                    update_fields=[
                        "name",
                        "number_of_cores",
                        "number_of_logical_processors",
                    ],
                )
            if computer.video_cards is not None:
                await self.update_related_entities(
                    db_computer,
                    computer.video_cards,
                    models.VideoCard,
                    "name",
                    "video_cards",
                    update_fields=["name", "driver_version"],
                )
            if computer.physical_disks is not None:
                await self.update_related_entities(
                    db_computer,
                    computer.physical_disks,
                    models.PhysicalDisk,
                    "serial",
                    "physical_disks",
                    update_fields=["model", "serial", "interface", "media_type"],
                )
            if computer.logical_disks is not None:
                await self.update_related_entities(
                    db_computer,
                    computer.logical_disks,
                    models.LogicalDisk,
                    "device_id",
                    "logical_disks",
                    update_fields=[
                        "device_id",
                        "volume_label",
                        "total_space",
                        "free_space",
                    ],
                    custom_logic=self._create_logical_disk,
                )
            if computer.roles is not None:
                await self.update_related_entities(
                    db_computer,
                    computer.roles,
                    models.Role,
                    "name",
                    "roles",
                    update_fields=["name"],
                )
            await self.db.commit()
            logger.debug(
                f"Транзакцію для пов’язаних сутностей зафіксовано",
                extra={"computer_id": db_computer.id},
            )
        except SQLAlchemyError as e:
            logger.error(
                f"Помилка оновлення пов’язаних сутностей для комп’ютера з ID {db_computer.id}: {str(e)}"
            )
            await self.db.rollback()
            raise

    async def get_component_history(self, computer_id: int) -> List[Dict[str, Any]]:
        # Перенесено з ComputerRepository без змін
        try:
            history = []
            for component_type, model in [
                ("physical_disk", models.PhysicalDisk),
                ("logical_disk", models.LogicalDisk),
                ("processor", models.Processor),
                ("video_card", models.VideoCard),
                ("ip_address", models.IPAddress),
                ("mac_address", models.MACAddress),
                ("software", models.Software),
            ]:
                result = await self.db.execute(
                    select(model).where(model.computer_id == computer_id)
                )
                for item in result.scalars().all():
                    history.append(
                        {
                            "component_type": component_type,
                            "data": item.dict(),
                            "detected_on": (
                                item.detected_on.isoformat()
                                if item.detected_on
                                else None
                            ),
                            "removed_on": (
                                item.removed_on.isoformat() if item.removed_on else None
                            ),
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