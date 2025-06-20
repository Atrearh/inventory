# app/utils.py
import logging
import re
import ipaddress
from typing import Optional

logger = logging.getLogger(__name__)

def validate_non_empty_string(cls, v: str, field_name: str) -> str:
    """Общая функция валидации непустых строк."""
    #logger.debug(f"Валидация {field_name}: {v}")
    if not v or not v.strip():
        raise ValueError(f"{field_name} не может быть пустым")
    return v.strip()

def validate_mac_address(cls, v: Optional[str], field_name: str = "MAC address") -> Optional[str]:
    """Валидация MAC-адреса: должен соответствовать формату XX:XX:XX:XX:XX:XX или быть None."""
    if v is None:
        return v
    v = validate_non_empty_string(cls, v, field_name)
    if not re.match(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', v):
        raise ValueError(f"{field_name} имеет неверный формат")
    return v

def validate_ip_address(cls, v: Optional[str], field_name: str = "IP address") -> Optional[str]:
    """Валидация IP-адреса: должен быть валидным IPv4/IPv6 или None."""
    if v is None:
        return v
    v = validate_non_empty_string(cls, v, field_name)
    try:
        ipaddress.ip_address(v)
    except ValueError:
        raise ValueError(f"{field_name} имеет неверный формат")
    return v

def validate_hostname(cls, v: str, field_name: str = "hostname") -> str:
    """Валидирует имя хоста, проверяя, что оно не пустое и соответствует формату."""
    v = validate_non_empty_string(cls, v, field_name)
    # Разрешены буквы, цифры, дефисы и подчёркивания
    if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-_]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-_]{0,61}[a-zA-Z0-9])?)*$', v):
        logger.error(f"Ошибка валидации {field_name}: '{v}' не соответствует формату имени хоста")
        raise ValueError(f"{field_name} имеет неверный формат")
    return v