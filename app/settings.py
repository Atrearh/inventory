# app/settings.py
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional, List
from .utils.validators import NonEmptyStr, DatabaseURLStr, WinRMCertValidationStr, CORSOriginsStr, AllowedIPsStr, SecretKeyStr
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    database_url: Optional[DatabaseURLStr] = None
    api_url: Optional[NonEmptyStr] = None
    scan_max_workers: Optional[int] = None
    domain: Optional[NonEmptyStr] = None
    polling_days_threshold: Optional[int] = None
    winrm_operation_timeout: Optional[int] = None
    winrm_read_timeout: Optional[int] = None
    winrm_port: Optional[int] = None
    winrm_server_cert_validation: Optional[WinRMCertValidationStr] = None
    ping_timeout: Optional[int] = None
    powershell_encoding: Optional[NonEmptyStr] = None
    json_depth: Optional[int] = None
    server_port: Optional[int] = None
    cors_allow_origins: Optional[CORSOriginsStr] = None
    allowed_ips: Optional[AllowedIPsStr] = None
    encryption_key: Optional[NonEmptyStr] = None
    secret_key: Optional[SecretKeyStr] = None
    timezone: Optional[NonEmptyStr] = "UTC"
    redis_url: Optional[NonEmptyStr] = "redis://localhost:6379/0"
    
    model_config = ConfigDict(
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_allow_origins_list(self) -> List[str]:
        """Перетворює cors_allow_origins у список рядків для CORS."""
        if not self.cors_allow_origins:
            logger.debug("CORS_ALLOW_ORIGINS не задано")
            return []
        logger.debug(f"CORS_ALLOW_ORIGINS: {self.cors_allow_origins}")
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    @property
    def allowed_ips_list(self) -> List[str]:
        """Перетворює allowed_ips у список IP-адрес або діапазонів."""
        if not self.allowed_ips:
            logger.warning("ALLOWED_IPS не задано в конфігурації")
            return []
        logger.info(f"ALLOWED_IPS: {self.allowed_ips}")
        return [ip.strip() for ip in self.allowed_ips.split(",") if ip.strip()]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        env_file = self.model_config.get("env_file")
        logger.info(f"Спроба зчитування .env файлу з: {env_file}")
        if not os.path.exists(env_file):
            logger.warning(f"Файл .env не знайдено за шляхом: {env_file}")
        logger.debug(f"Зчитано налаштування DATABASE_URL: {self.database_url}")
        logger.debug(f"Зчитано налаштування ALLOWED_IPS: {self.allowed_ips}")

settings = Settings() 