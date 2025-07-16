# app/settings.py
from pydantic_settings import BaseSettings
from pydantic import ConfigDict, field_validator
from typing import Optional, List
from app.utils import NonEmptyStr
import logging
import ipaddress
import os
from pathlib import Path

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    database_url: Optional[NonEmptyStr] = None
    ad_server_url: Optional[NonEmptyStr] = None
    domain: Optional[NonEmptyStr] = None
    ad_username: Optional[NonEmptyStr] = None
    ad_password: Optional[NonEmptyStr] = None
    api_url: Optional[NonEmptyStr] = None
    test_hosts: Optional[str] = None
    log_level: Optional[NonEmptyStr] = "DEBUG"
    scan_max_workers: Optional[int] = None
    polling_days_threshold: Optional[int] = None
    winrm_operation_timeout: Optional[int] = None
    winrm_read_timeout: Optional[int] = None
    winrm_port: Optional[int] = None
    winrm_server_cert_validation: Optional[NonEmptyStr] = None
    ping_timeout: Optional[int] = None
    powershell_encoding: Optional[NonEmptyStr] = None
    json_depth: Optional[int] = None
    server_port: Optional[int] = None
    cors_allow_origins: Optional[NonEmptyStr] = None
    allowed_ips: Optional[NonEmptyStr] = None
    encryption_key: Optional[NonEmptyStr] = None
    secret_key: Optional[NonEmptyStr] = None  # Добавлено поле для JWT

    model_config = ConfigDict(
        env_file=Path(__file__).parent / ".env",  # Путь к .env в директории app
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_allow_origins_list(self) -> List[str]:
        """Преобразует cors_allow_origins в список строк для CORS."""
        if not self.cors_allow_origins:
            return []
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    @property
    def allowed_ips_list(self) -> List[str]:
        """Преобразует allowed_ips в список IP-адресов или диапазонов."""
        if not self.allowed_ips:
            return []
        return [ip.strip() for ip in self.allowed_ips.split(",") if ip.strip()]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        env_file = self.model_config.get("env_file")
        logger.info(f"Чтение .env файла из: {env_file}")
        if not os.path.exists(env_file):
            logger.warning(f"Файл .env не найден по пути: {env_file}")
        
        if not self.database_url:
            logger.warning("DATABASE_URL не задан в конфигурации, проверьте .env файл")
        if not self.allowed_ips:
            logger.warning("ALLOWED_IPS не задан в конфигурации, проверьте .env файл")
        if not self.secret_key:
            logger.warning("SECRET_KEY не задан в конфигурации, проверьте .env файл")

    @field_validator('database_url')
    @classmethod
    def validate_database_url(cls, v):
        if v and not v.startswith(('mysql+', 'postgresql+', 'sqlite+')):
            raise ValueError("database_url должен начинаться с 'mysql+', 'postgresql+' или 'sqlite+'")
        return v

    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v):
        if v and v not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError("Log level должен быть одним из: DEBUG, INFO, WARNING, ERROR, CRITICAL")
        return v

    @field_validator('winrm_server_cert_validation')
    @classmethod
    def validate_cert_validation(cls, v):
        if v and v not in ["validate", "ignore"]:
            raise ValueError("winrm_server_cert_validation должен быть 'validate' или 'ignore'")
        return v

    @field_validator('cors_allow_origins')
    @classmethod
    def validate_cors_origins(cls, v):
        if v:
            origins = [origin.strip() for origin in v.split(",") if origin.strip()]
            if not origins:
                raise ValueError("CORS origins не могут быть пустыми")
            for origin in origins:
                if not origin.startswith(("http://", "https://")):
                    raise ValueError(f"Недопустимый origin: {origin}. Должен начинаться с http:// или https://")
        return v

    @field_validator('allowed_ips')
    @classmethod
    def validate_allowed_ips(cls, v):
        if v:
            ips = [ip.strip() for ip in v.split(",") if ip.strip()]
            if not ips:
                raise ValueError("Allowed IPs не могут быть пустыми")
            for ip in ips:
                try:
                    if '/' in ip:
                        ipaddress.ip_network(ip, strict=False)
                    else:
                        ipaddress.ip_address(ip)
                except ValueError:
                    raise ValueError(f"Недопустимый IP или диапазон: {ip}")
        return v

    @field_validator('secret_key')
    @classmethod
    def validate_secret_key(cls, v):
        if v and len(v) < 32:
            raise ValueError("SECRET_KEY должен быть длиной не менее 32 символов для безопасности")
        return v

settings = Settings() 