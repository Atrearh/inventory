# app/mappers/component_mapper.py
import logging
from typing import Any, List, Type

from sqlmodel import SQLModel

from app.models import IPAddress, LogicalDisk, MACAddress, PhysicalDisk, Software

logger = logging.getLogger(__name__)


def map_to_components(
    cls: Type[SQLModel],
    raw_data: Any,
    hostname: str,
) -> List[SQLModel]:

    if not isinstance(raw_data, list):
        raw_data = [raw_data] if raw_data else []

    result = []
    seen_identifiers = set()

    # Визначаємо, яке поле є ідентифікатором
    identifier_key = "name"
    if cls in [IPAddress, MACAddress]:
        identifier_key = "address"
    elif cls in [PhysicalDisk]:
        identifier_key = "serial"
    elif cls in [LogicalDisk]:
        identifier_key = "device_id"
    elif cls in [Software]:
        # Для ПЗ ідентифікатор композитний (ім'я + версія)
        for item in raw_data:
            if not isinstance(item, dict):
                continue
            try:
                name = item.get("name")
                version = item.get("version")
                identifier = (name, version)
                if not name or identifier in seen_identifiers:
                    continue
                seen_identifiers.add(identifier)
                result.append(cls.model_construct(**item))
            except Exception as e:
                logger.warning(
                    f"Помилка обробки {cls.__name__}: {str(e)}",
                    extra={"data": item, "hostname": hostname},
                )
        return result

    # Стандартна логіка для інших компонентів
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
                continue
            seen_identifiers.add(identifier)
            result.append(cls.model_construct(**item))
        except Exception as e:
            logger.warning(
                f"Помилка обробки {cls.__name__}: {str(e)}",
                extra={"data": item, "hostname": hostname},
            )

    return result
