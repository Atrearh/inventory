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
    return v