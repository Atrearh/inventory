# app/utils.py
import logging
import sys
import re
import ipaddress
from logging.handlers import TimedRotatingFileHandler
from typing import Optional

logger = logging.getLogger(__name__)


def validate_non_empty_string(cls, v: str, field_name: str) -> str:
    """Общая функция валидации непустых строк."""
    logger.debug(f"Валидация {field_name}: {v}")
    if not v or not v.strip():
        raise ValueError(f"{field_name} не может быть пустым")
    return v.strip()

def setup_logging():
    """Настраивает логирование для приложения."""
    from .settings import settings
    logger = logging.getLogger()
    if logger.handlers:
        logger.handlers.clear()

    valid_log_levels = {'NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
    log_level = settings.log_level.upper()
    if log_level not in valid_log_levels:
        logger.warning(f"Недопустимый уровень логирования: {log_level}. Установлен уровень по умолчанию: DEBUG")
        log_level = 'DEBUG'

    logger.setLevel(getattr(logging, log_level))

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s,%(msecs)03d %(levelname)s:%(name)s:%(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(console_handler)

    file_handler = TimedRotatingFileHandler(
        'logs/app.log',
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s,%(msecs)03d %(levelname)s:%(name)s:%(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(file_handler)

    return logger

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