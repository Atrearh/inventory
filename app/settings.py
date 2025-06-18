# app/settings.py
from pydantic_settings import BaseSettings
from pydantic import field_validator
from sqlalchemy import select , insert, update
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from .utils import validate_non_empty_string
from typing import Dict, Optional

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
    winrm_retries: int = 3
    winrm_retry_delay: int = 5
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

    async def load_from_db(self):
        """Загружает настройки из базы данных."""
        from .models import AppSetting  # Отложенный импорт
        from .database import async_session
        async with async_session() as db:
            try:
                result = await db.execute(select(AppSetting))
                settings = {row.key: row.value for row in result.scalars().all()}
                for key, value in settings.items():
                    if hasattr(self, key):
                        try:
                            field_type = self.__annotations__.get(key)
                            if field_type == list[str]:
                                setattr(self, key, value.split(",") if value else [])
                            elif field_type == int:
                                setattr(self, key, int(value))
                            elif field_type == str:
                                setattr(self, key, value)
                            logger.debug(f"Загружена настройка {key}={value}")
                        except (ValueError, TypeError) as e:
                            logger.error(f"Ошибка преобразования настройки {key}: {str(e)}")
            except Exception as e:
                logger.error(f"Ошибка загрузки настроек из БД: {str(e)}")
                raise

    @property
    def database_url(self):
        return f"mysql+aiomysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def ad_base_dn(self):
        return ",".join(f"DC={part.capitalize()}" for part in self.domain.split('.') if part) if self.domain else ""

    @property
    def ad_fqdn_suffix(self):
        return f".{self.domain}" if self.domain else ""

class SettingsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_settings(self) -> Dict[str, str]:
        """Получает все настройки из базы данных."""
        from .models import AppSetting  # Отложенный импорт
        try:
            result = await self.db.execute(select(AppSetting))
            settings = {row.key: row.value for row in result.scalars().all()}
            logger.debug(f"Получено {len(settings)} настроек из базы данных")
            return settings
        except Exception as e:
            logger.error(f"Ошибка получения настроек: {str(e)}")
            raise

    async def update_setting(self, key: str, value: str, description: Optional[str] = None) -> None:
        """Обновляет или создает настройку."""
        from .models import AppSetting  # Отложенный импорт
        try:
            existing = await self.db.execute(
                select(AppSetting).filter(AppSetting.key == key)
            )
            existing_setting = existing.scalars().first()
            if existing_setting:
                await self.db.execute(
                    update(AppSetting)
                    .where(AppSetting.key == key)
                    .values(value=value, description=description)
                )
                logger.debug(f"Обновлена настройка {key}={value}")
            else:
                await self.db.execute(
                    insert(AppSetting)
                    .values(key=key, value=value, description=description)
                )
                logger.debug(f"Создана новая настройка {key}={value}")
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Ошибка обновления настройки {key}: {str(e)}")
            raise

settings = Settings()