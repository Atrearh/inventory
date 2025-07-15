import logging
from pydantic_settings import BaseSettings
from .utils import NonEmptyStr
import os

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    db_user: NonEmptyStr = "default_user"
    db_password: NonEmptyStr = "default_password"
    db_host: NonEmptyStr = "localhost"
    db_port: NonEmptyStr = "3306"
    db_name: NonEmptyStr = "inventory"
    ad_server_url: NonEmptyStr = ""
    domain: NonEmptyStr = ""
    ad_username: NonEmptyStr = "admin"
    ad_password: NonEmptyStr = "password"
    api_url: NonEmptyStr = ""
    test_hosts: str = ""
    log_level: NonEmptyStr = "INFO"
    scan_max_workers: int = 10
    polling_days_threshold: int = 1
    winrm_operation_timeout: int = 20
    winrm_read_timeout: int = 30
    winrm_port: int = 5985
    winrm_server_cert_validation: NonEmptyStr = "ignore"
    ping_timeout: int = 2
    powershell_encoding: NonEmptyStr = "utf-8"
    json_depth: int = 4
    server_port: int = 8000
    cors_allow_origins: NonEmptyStr = "http://localhost:8000,http://localhost:5173,http://localhost:8080,http://192.168.0.143:8080,http://192.168.0.143:8000,http://192.168.0.143:5173"
    allowed_ips: NonEmptyStr = "127.0.0.1,192.168.0.0/23"
    secret_key: NonEmptyStr = os.getenv("SECRET_KEY", "your-very-secret-key-here")
    encryption_key: NonEmptyStr = os.getenv("ENCRYPTION_KEY", "")

    class Config:
        env_file = "app/.env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def database_url(self):
        return f"mysql+aiomysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def ad_base_dn(self):
        return ",".join(f"DC={part.capitalize()}" for part in self.domain.split('.') if part) if self.domain else ""

    @property
    def ad_fqdn_suffix(self):
        return f".{self.domain}" if self.domain else ""

    @property
    def cors_allow_origins_list(self) -> list[str]:
        """Преобразует строку cors_allow_origins в список."""
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    @property
    def allowed_ips_list(self) -> list[str]:
        """Преобразует строку allowed_ips в список."""
        return [ip.strip() for ip in self.allowed_ips.split(",") if ip.strip()]

settings = Settings()
logger.info("Настройки успешно инициализированы.")