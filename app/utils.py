import structlog
import re
import ipaddress
from typing import Optional, Any
from pydantic_core import core_schema
from pydantic import GetCoreSchemaHandler

logger = structlog.get_logger(__name__)

class NonEmptyStr(str):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        return core_schema.str_schema(min_length=1, strip_whitespace=True)

    @classmethod
    def __validate__(cls, v: Any) -> str:
        if not isinstance(v, str):
            raise ValueError("Значення має бути рядком")
        v = v.strip()
        if not v:
            raise ValueError("Рядок не може бути порожнім")
        return v

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        json_schema = handler(core_schema)
        json_schema.update(type="string", minLength=1)
        return json_schema

def validate_mac_address(cls, v: Optional[NonEmptyStr], field_name: str = "MAC address") -> Optional[NonEmptyStr]:
    """Валідація MAC-адреси: має відповідати формату XX:XX:XX:XX:XX:XX або бути None."""
    if v is None:
        return v
    if not re.match(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', v):
        raise ValueError(f"{field_name} має невірний формат")
    return v

def validate_ip_address(cls, v: Optional[NonEmptyStr], field_name: str = "IP address") -> Optional[NonEmptyStr]:
    """Валідація IP-адреси: має бути валідною IPv4/IPv6 або None."""
    if v is None:
        return v
    try:
        ipaddress.ip_address(v)
    except ValueError:
        raise ValueError(f"{field_name} має невірний формат")
    return v

def validate_hostname(cls, v: NonEmptyStr, field_name: str = "hostname") -> NonEmptyStr:
    """Валідація hostname з підтримкою підкреслень для сумісності з реальними даними."""
    if v is None:
        raise ValueError(f"{field_name} не може бути None")
    
    # Перевірка довжини
    if len(v) > 255:
        raise ValueError(f"{field_name} перевищує максимальну довжину 255 символів")
    
    # Перевірка формату (букви, цифри, дефіси, підкреслення, крапки)
    if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-_]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-_]{0,61}[a-zA-Z0-9])?)*$', v):
        raise ValueError(f"{field_name} має невірний формат (допустимі букви, цифри, дефіси, підкреслення і крапки)")
    
    # Перевірка, що hostname не починається і не закінчується крапкою
    if v.startswith('.') or v.endswith('.'):
        raise ValueError(f"{field_name} не може починатися або закінчуватися крапкою")
    
    # Попередження, якщо hostname не відповідає строгому RFC 1123 (наприклад, містить підкреслення)
    if '_' in v and not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$', v):
        logger.warning(f"Hostname '{v}' містить підкреслення, що не відповідає RFC 1123, але допустимо для локальних мереж")
    
    return v