# app/utils.py
import logging
import re
import ipaddress
from typing import Optional, Any
from pydantic_core import core_schema
from pydantic import GetCoreSchemaHandler

logger = logging.getLogger(__name__)

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
    """Валидация MAC-адреса: должен соответствовать формату XX:XX:XX:XX:XX:XX или быть None."""
    if v is None:
        return v
    if not re.match(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', v):
        raise ValueError(f"{field_name} имеет неверный формат")
    return v

def validate_ip_address(cls, v: Optional[NonEmptyStr], field_name: str = "IP address") -> Optional[NonEmptyStr]:
    """Валидация IP-адреса: должен быть валидным IPv4/IPv6 или None."""
    if v is None:
        return v
    try:
        ipaddress.ip_address(v)
    except ValueError:
        raise ValueError(f"{field_name} имеет неверный формат")
    return v

def validate_hostname(cls, v: NonEmptyStr, field_name: str = "hostname") -> NonEmptyStr:
    """Валидация hostname с поддержкой подчеркиваний для совместимости с реальными данными."""
    if v is None:
        raise ValueError(f"{field_name} не может быть None")
    
    # Проверка длины
    if len(v) > 255:
        raise ValueError(f"{field_name} превышает максимальную длину 255 символов")
    
    # Проверка формата (буквы, цифры, дефисы, подчеркивания, точки)
    if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-_]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-_]{0,61}[a-zA-Z0-9])?)*$', v):
        raise ValueError(f"{field_name} имеет неверный формат (допустимы буквы, цифры, дефисы, подчеркивания и точки)")
    
    # Проверка, что hostname не начинается и не заканчивается точкой
    if v.startswith('.') or v.endswith('.'):
        raise ValueError(f"{field_name} не может начинаться или заканчиваться точкой")
    
    # Предупреждение, если hostname не соответствует строгому RFC 1123 (например, содержит подчеркивания)
    if '_' in v and not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$', v):
        logger.warning(f"Hostname '{v}' содержит подчеркивания, что не соответствует RFC 1123, но допустимо для локальных сетей")
    
    return v