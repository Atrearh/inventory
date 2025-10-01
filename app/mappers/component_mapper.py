import logging
from typing import Any, Dict, List, Type, TypeVar
from pydantic import ValidationError
from sqlalchemy.orm import DeclarativeBase
from app.schemas import (
    IPAddress,
    MACAddress,
    PhysicalDisk,
    LogicalDisk,
    Processor,
    VideoCard,
    Role,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=DeclarativeBase)

IDENTIFIER_MAP: Dict[Type[DeclarativeBase], str] = {
    IPAddress: "address",
    MACAddress: "address",
    PhysicalDisk: "serial",
    LogicalDisk: "device_id",
    Processor: "name",
    VideoCard: "name",
    Role: "name",
}

SCHEMA_MAP: Dict[Type[DeclarativeBase], Type] = {
    IPAddress: IPAddress,
    MACAddress: MACAddress,
    PhysicalDisk: PhysicalDisk,
    LogicalDisk: LogicalDisk,
    Processor: Processor,
    VideoCard: VideoCard,
    Role: Role,
}

def map_to_components(cls: Type[T], raw_data: Any, hostname: str) -> List[T]:
    if not isinstance(raw_data, list):
        raw_data = [raw_data] if raw_data else []

    result: List[T] = []
    seen_identifiers = set()

    identifier_key = IDENTIFIER_MAP.get(cls, "name")
    schema_cls = SCHEMA_MAP.get(cls)

    for item in raw_data:
        if not isinstance(item, dict):
            logger.warning(
                f"Некоректні дані для {cls.__name__}: {item}",
                extra={"hostname": hostname},
            )
            continue

        try:
            identifier = item.get(identifier_key)
            if not identifier or identifier in seen_identifiers:
                logger.debug(
                    f"Пропущено дубльований або порожній ідентифікатор {identifier} для {cls.__name__}",
                    extra={"hostname": hostname},
                )
                continue

            # Валідація через Pydantic-схему
            if schema_cls:
                validated_data = schema_cls(**item).model_dump()
            else:
                validated_data = item

            seen_identifiers.add(identifier)
            # Створюємо об'єкт SQLAlchemy без виклику конструктора
            instance = cls.__new__(cls)
            cls.__init__(instance)
            for key, value in validated_data.items():
                object.__setattr__(instance, key, value)
            result.append(instance)
        except ValidationError as e:
            logger.warning(
                f"Помилка валідації даних для {cls.__name__}: {str(e)}",
                extra={"data": item, "hostname": hostname},
            )
            continue
        except Exception as e:
            logger.warning(
                f"Помилка обробки {cls.__name__}: {str(e)}",
                extra={"data": item, "hostname": hostname},
            )
            continue

    return result