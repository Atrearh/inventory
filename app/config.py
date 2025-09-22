# app/config.py
import logging
from pathlib import Path
from typing import List, Optional
from fastapi import HTTPException
from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .logging_config import setup_logging
from app.models import AppSetting
from .utils.validators import (
    AllowedIPsStr,
    CORSOriginsStr,
    DatabaseURLStr,
    NonEmptyStr,
    SecretKeyStr,
    WinRMCertValidationStr,
)

logger = logging.getLogger(__name__)

class AppSettings(BaseSettings):
    """
    Єдиний клас для керування всіма налаштуваннями додатку.
    Поєднує статичну конфігурацію з .env та динамічну з бази даних.
    """

    # --- Поля налаштувань з .env (статичні) ---
    database_url: Optional[DatabaseURLStr] = None
    secret_key: SecretKeyStr
    encryption_key: NonEmptyStr
    log_level: NonEmptyStr = "DEBUG"  
    timezone: NonEmptyStr = "UTC"

    # --- Поля налаштувань, які можуть бути динамічними (з БД) ---
    api_url: Optional[NonEmptyStr] = None
    scan_max_workers: int = 10
    polling_days_threshold: int = 30
    winrm_operation_timeout: int = 120
    winrm_read_timeout: int = 180
    winrm_port: int = 5985
    winrm_server_cert_validation: WinRMCertValidationStr = "ignore"
    ping_timeout: int = 1
    powershell_encoding: NonEmptyStr = "cp866"
    json_depth: int = 10
    server_port: int = 8000
    cors_allow_origins: CORSOriginsStr = "http://localhost:8080"
    allowed_ips: AllowedIPsStr = "127.0.0.1"

    model_config = ConfigDict(
        env_file=Path(__file__).parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_allow_origins_list(self) -> List[str]:
        """Перетворює cors_allow_origins у список для CORS middleware."""
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    @property
    def allowed_ips_list(self) -> List[str]:
        """Перетворює allowed_ips у список IP-адрес або діапазонів."""
        return [ip.strip() for ip in self.allowed_ips.split(",") if ip.strip()]

    async def load_dynamic_settings(self, db: AsyncSession):
        """
        Завантажує налаштування з бази даних і оновлює поточні значення.
        Значення з .env мають пріоритет для базових налаштувань.
        """
        logger.info("Завантаження динамічних налаштувань з бази даних...")

        # 1. Ініціалізація ключа шифрування (критично важливий крок)
        await self._initialize_encryption_key(db)

        # 2. Завантаження всіх налаштувань з БД
        try:
            result = await db.execute(select(AppSetting))
            db_settings = {setting.key: setting.value for setting in result.scalars().all()}

            for key, value in db_settings.items():
                if hasattr(self, key):
                    try:
                        # Встановлюємо значення, конвертуючи до правильного типу
                        field_type = self.__annotations__.get(key)
                        if field_type == int:
                            setattr(self, key, int(value))
                        else:
                            setattr(self, key, value)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Не вдалося конвертувати налаштування '{key}' зі значенням '{value}': {e}")

            logger.info("Динамічні налаштування успішно завантажені та застосовані.")

        except Exception as e:
            logger.error(f"Помилка завантаження налаштувань з БД: {e}", exc_info=True)
            # Не перериваємо роботу, використовуємо значення за замовчуванням / з .env

    async def save_settings(self, db: AsyncSession, updates: dict):
        """Зберігає оновлені налаштування в базу даних."""
        logger.info(f"Збереження налаштувань в БД: {updates}")
        try:
            for key, value in updates.items():
                if value is not None and hasattr(self, key):
                    result = await db.execute(select(AppSetting).filter_by(key=key))
                    existing_setting = result.scalar_one_or_none()

                    if existing_setting:
                        existing_setting.value = str(value)
                    else:
                        db.add(AppSetting(key=key, value=str(value)))

                    # Оновлюємо значення в поточному об'єкті
                    setattr(self, key, value)

            await db.commit()
            logger.info("Налаштування успішно збережені.")
        except Exception as e:
            await db.rollback()
            logger.error(f"Помилка збереження налаштувань: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Помилка збереження налаштувань")

# Створюємо єдиний екземпляр налаштувань для всього додатку
settings = AppSettings()

# Налаштовуємо логування з початковим рівнем
setup_logging(log_level=settings.log_level)