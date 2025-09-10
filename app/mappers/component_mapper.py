# app/mappers/component_mapper.py
import logging
from typing import Any, List
from hashlib import md5
from app.utils.validators import validate_ip_address_format, validate_mac_address_format
from app.schemas import (
    ComponentSchema, Role, Software, PhysicalDisk, LogicalDisk, VideoCard, Processor, IPAddress, MACAddress, IdentifierField
)

logger = logging.getLogger(__name__)

def map_to_components(
    cls: type[ComponentSchema], raw_data: Any, hostname: str, identifier_field: IdentifierField = IdentifierField.NAME
) -> List[ComponentSchema]:
    """Універсальна функція для мапінгу сирих даних у список компонентів.

    Args:
        cls: Клас Pydantic-схеми компонента (наприклад, Role, Software).
        raw_data: Сирі дані (список словників або один словник).
        hostname: Ім'я хоста для контексту логування.
        identifier_field: Унікальний ідентифікатор компонента (Enum).

    Returns:
        List[ComponentSchema]: Список валідованих екземплярів Pydantic-схеми.

    Example:
        >>> map_to_components(Role, [{"Name": "Admin"}], "host1", IdentifierField.NAME)
        [Role(name="Admin")]
    """
    if not isinstance(raw_data, list):
        raw_data = [raw_data] if raw_data else []

    result = []
    seen_identifiers = set()

    for item in raw_data:
        if not isinstance(item, dict):
            logger.warning(f"Некоректні дані для {cls.__name__}: {item}", extra={"hostname": hostname})
            continue
        try:
            identifier = item.get(identifier_field.value, "").strip()
            if not identifier or identifier in seen_identifiers:
                continue
            seen_identifiers.add(identifier)
            result.append(cls.model_validate(item))
        except Exception as e:
            logger.warning(f"Помилка обробки {cls.__name__}: {str(e)}", extra={"data": item, "hostname": hostname})
    
    return result

def map_to_physical_disks(raw_data: Any, hostname: str) -> List[PhysicalDisk]:
    """Мапінг сирих даних у список PhysicalDisk.

    Args:
        raw_data: Сирі дані (список словників або один словник).
        hostname: Ім'я хоста для контексту логування.

    Returns:
        List[PhysicalDisk]: Список валідованих екземплярів PhysicalDisk.
    """
    if not isinstance(raw_data, list):
        raw_data = [raw_data] if raw_data else []

    seen_identifiers = set()
    result = []

    for item in raw_data:
        if not isinstance(item, dict):
            logger.warning(f"Некоректні дані диска: {item}", extra={"hostname": hostname})
            continue
        try:
            serial = item.get("serial", "").strip()
            if not serial:
                model = item.get("model", "")
                serial = md5(f"{model}_{item.get('size', '')}_{hostname}".encode()).hexdigest()[:100]
            if serial in seen_identifiers:
                continue
            seen_identifiers.add(serial)
            result.append(PhysicalDisk(
                model=item.get("model"),
                serial=serial,
                interface=item.get("interface"),
                media_type=item.get("media_type")
            ))
        except Exception as e:
            logger.warning(f"Помилка обробки диска: {str(e)}", extra={"data": item, "hostname": hostname})
    
    return result

def map_to_ip_addresses(raw_data: Any, hostname: str) -> List[IPAddress]:
    """Мапінг сирих даних у список IPAddress.

    Args:
        raw_data: Сирі дані (список рядків, словників або один рядок).
        hostname: Ім'я хоста для контексту логування.

    Returns:
        List[IPAddress]: Список валідованих екземплярів IPAddress.
    """
    if not isinstance(raw_data, (list, str)):
        logger.warning(f"Некоректні дані IP: {raw_data}", extra={"hostname": hostname})
        return []
    
    data_list = [raw_data] if isinstance(raw_data, str) else raw_data
    seen_identifiers = set()
    result = []

    for item in data_list:
        try:
            address = item.strip() if isinstance(item, str) else item.get("address", "").strip()
            if not address or not validate_ip_address_format(address) or address in seen_identifiers:
                continue
            seen_identifiers.add(address)
            result.append(IPAddress(address=address))
        except Exception as e:
            logger.warning(f"Помилка обробки IP: {str(e)}", extra={"data": item, "hostname": hostname})
    
    return result

def map_to_mac_addresses(raw_data: Any, hostname: str) -> List[MACAddress]:
    """Мапінг сирих даних у список MACAddress.

    Args:
        raw_data: Сирі дані (список рядків, словників або один рядок).
        hostname: Ім'я хоста для контексту логування.

    Returns:
        List[MACAddress]: Список валідованих екземплярів MACAddress.
    """
    if not isinstance(raw_data, (list, str)):
        logger.warning(f"Некоректні дані MAC: {raw_data}", extra={"hostname": hostname})
        return []
    
    data_list = [raw_data] if isinstance(raw_data, str) else raw_data
    seen_identifiers = set()
    result = []

    for item in data_list:
        try:
            address = item.strip() if isinstance(item, str) else item.get("address", "").strip()
            if not validate_mac_address_format(address) or address in seen_identifiers:
                continue
            seen_identifiers.add(address)
            result.append(MACAddress(address=address))
        except Exception as e:
            logger.warning(f"Помилка обробки MAC: {str(e)}", extra={"data": item, "hostname": hostname})
    
    return result