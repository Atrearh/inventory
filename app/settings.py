import logging
from pydantic_settings import BaseSettings
from pydantic import field_validator
from .utils import validate_non_empty_string

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    db_user: str
    db_password: str
    db_host: str = "localhost"
    db_port: str = "3306"
    db_name: str = "inventory"
    ad_server_url: str = ""
    domain: str = ""
    ad_username: str
    ad_password: str
    api_url: str = ""
    test_hosts: str = "admins.express.local,economist-4.express.local,buhgalter-12.express.local,1c-ogk.express.local"
    log_level: str = "INFO"
    scan_max_workers: int = 10
    polling_days_threshold: int = 1
    winrm_operation_timeout: int = 20
    winrm_read_timeout: int = 30
    winrm_port: int = 5985
    winrm_server_cert_validation: str = "ignore"
    ping_timeout: int = 2
    powershell_encoding: str = "utf-8"
    json_depth: int = 4
    server_port: int = 8000
    cors_allow_origins: list[str] = ["http://localhost:8000", "http://localhost:5173", "http://localhost:8080"]
    allowed_ips: list[str] = ["127.0.0.1", "192.168.1.0/24"]

    @field_validator('ad_username', 'ad_password', 'db_user', 'db_password')
    @classmethod
    def validate_non_empty(cls, v, info):
        return validate_non_empty_string(cls, v, info.field_name)

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

# Создаем экземпляр настроек сразу при импорте модуля
settings = Settings()
logger.info("Настройки успешно инициализированы.")