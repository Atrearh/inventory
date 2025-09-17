# app/utils/validators.py
import ipaddress
import logging
import re
from typing import Annotated

from pydantic import AfterValidator, PlainValidator

from .security import validate_allowed_ips

logger = logging.getLogger(__name__)


def validate_non_empty_str(v: str) -> str:
    """Перевіряє, що рядок не є порожнім після видалення пробілів."""
    if not isinstance(v, str) or not v.strip():
        raise ValueError("Рядок не може бути порожнім")
    return v.strip()


def validate_mac_address_format(v: str) -> str:
    """Валідація MAC-адреси: має відповідати формату XX:XX:XX:XX:XX:XX."""
    if v and not re.match(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$", v):
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

    if not re.match(
        r"^[a-zA-Z0-9]([a-zA-Z0-9\-_]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-_]{0,61}[a-zA-Z0-9])?)*$",
        v,
    ):
        raise ValueError("Hostname має невірний формат (допустимі букви, цифри, дефіси, підкреслення і крапки)")

    if v.startswith(".") or v.endswith("."):
        raise ValueError("Hostname не може починатися або закінчуватися крапкою")

    if "_" in v and not re.match(
        r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$",
        v,
    ):
        logger.warning(f"Hostname '{v}' містить підкреслення, що не відповідає RFC 1123, але допустимо для локальних мереж")

    return v


def validate_domain_name_format(v: str) -> str:
    """Валідує server_url як доменне ім'я."""
    DOMAIN_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*(\.[a-zA-Z0-9][a-zA-Z0-9\-]*)+$")
    if not DOMAIN_NAME_PATTERN.match(v):
        logger.error(f"Невалідне доменне ім'я: {v}")
        raise ValueError("Доменне ім'я має містити лише літери, цифри, дефіси та точки (наприклад, server.com)")
    return v


def validate_database_url_format(v: str) -> str:
    """Валідація database_url: має починатися з 'mysql+', 'postgresql+' або 'sqlite+'."""
    if v and not v.startswith(("mysql+", "postgresql+", "sqlite+")):
        raise ValueError("database_url повинен починатися з 'mysql+', 'postgresql+' або 'sqlite+'")
    return v


def validate_log_level_format(v: str) -> str:
    """Валідація log_level: має бути одним із 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'."""
    if v and v not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        raise ValueError("Log level повинен бути одним із: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    return v


def validate_winrm_cert_validation_format(v: str) -> str:
    """Валідація winrm_server_cert_validation: має бути 'validate' або 'ignore'."""
    if v and v not in ["validate", "ignore"]:
        raise ValueError("winrm_server_cert_validation має бути 'validate' або 'ignore'")
    return v


def validate_cors_origins_format(v: str) -> str:
    """Валідація cors_allow_origins: має містити валідні origins."""
    if v:
        origins = [origin.strip() for origin in v.split(",") if origin.strip()]
        if not origins:
            raise ValueError("CORS origins не можуть бути порожніми")
        for origin in origins:
            if not origin.startswith(("http://", "https://")):
                raise ValueError(f"Недопустимий origin: {origin}. Повинен починатися з http:// або https://")
    return v


def validate_secret_key_format(v: str) -> str:
    """Валідація secret_key: має бути довжиною не менше 32 символів."""
    if v and len(v) < 32:
        raise ValueError("SECRET_KEY повинен бути довжиною не менше 32 символів для безпеки")
    return v


# Кастомні типи з валідацією
NonEmptyStr = Annotated[str, PlainValidator(validate_non_empty_str)]
HostnameStr = Annotated[NonEmptyStr, AfterValidator(validate_hostname_format)]
MACAddressStr = Annotated[NonEmptyStr, AfterValidator(validate_mac_address_format)]
IPAddressStr = Annotated[NonEmptyStr, AfterValidator(validate_ip_address_format)]
DomainNameStr = Annotated[NonEmptyStr, AfterValidator(validate_domain_name_format)]
DatabaseURLStr = Annotated[NonEmptyStr, AfterValidator(validate_database_url_format)]
LogLevelStr = Annotated[NonEmptyStr, AfterValidator(validate_log_level_format)]
WinRMCertValidationStr = Annotated[NonEmptyStr, AfterValidator(validate_winrm_cert_validation_format)]
CORSOriginsStr = Annotated[NonEmptyStr, AfterValidator(validate_cors_origins_format)]
SecretKeyStr = Annotated[NonEmptyStr, AfterValidator(validate_secret_key_format)]
AllowedIPsStr = Annotated[NonEmptyStr, AfterValidator(validate_allowed_ips)]
