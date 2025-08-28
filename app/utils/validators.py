import logging
import re
import ipaddress
from typing import Annotated
from pydantic import AfterValidator, PlainValidator

logger = logging.getLogger(__name__)


def validate_non_empty_str(v: str) -> str:
    """Перевіряє, що рядок не є порожнім після видалення пробілів."""
    if not isinstance(v, str) or not v.strip():
        raise ValueError("Рядок не може бути порожнім")
    return v.strip()

NonEmptyStr = Annotated[str, PlainValidator(validate_non_empty_str)]

def validate_mac_address_format(v: str) -> str:
    """Валідація MAC-адреси: має відповідати формату XX:XX:XX:XX:XX:XX."""
    if v and not re.match(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', v):
        raise ValueError("MAC-адреса має невірний формат")
    return v

def validate_ip_address_format(v: str) -> str:
    """Валідація IP-адреси: має бути валідною IPv4/IPv6."""
    try:
        ipaddress.ip_address(v)
    except ValueError:
        raise ValueError("IP-адреса має невірний формат")
    return v

def validate_hostname_format(v: str) -> str:
    """Валідація hostname з підтримкою підкреслень."""
    if len(v) > 255:
        raise ValueError("Hostname перевищує максимальну довжину 255 символів")
    
    if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-_]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-_]{0,61}[a-zA-Z0-9])?)*$', v):
        raise ValueError("Hostname має невірний формат (допустимі букви, цифри, дефіси, підкреслення і крапки)")
    
    if v.startswith('.') or v.endswith('.'):
        raise ValueError("Hostname не може починатися або закінчуватися крапкою")
    
    if '_' in v and not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$', v):
        logger.warning(f"Hostname '{v}' містить підкреслення, що не відповідає RFC 1123, але допустимо для локальних мереж")
    
    return v

def validate_domain_name_format(v: str) -> str:
    """Валідує server_url як доменне ім'я."""
    DOMAIN_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\-]*(\.[a-zA-Z0-9][a-zA-Z0-9\-]*)+$')
    if not DOMAIN_NAME_PATTERN.match(v):
        logger.error(f"Невалідне доменне ім'я: {v}")
        raise ValueError("Доменне ім'я має містити лише літери, цифри, дефіси та точки (наприклад, server.com)")
    return v



HostnameStr = Annotated[NonEmptyStr, AfterValidator(validate_hostname_format)]
MACAddressStr = Annotated[NonEmptyStr, AfterValidator(validate_mac_address_format)]
IPAddressStr = Annotated[NonEmptyStr, AfterValidator(validate_ip_address_format)]
DomainNameStr = Annotated[NonEmptyStr, AfterValidator(validate_domain_name_format)]
