# app/settings_manager.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .models import AppSetting
from .settings import Settings
from .logging_config import setup_logging
from cryptography.fernet import Fernet
import logging
from fastapi import HTTPException
import os

logger = logging.getLogger(__name__)

class SettingsManager:
    """Клас для управління налаштуваннями додатка, включаючи завантаження та збереження в базу даних."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.log_level = None
        # Встановлюємо початковий рівень логування
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Ініціалізація SettingsManager з рівнем логування DEBUG")

    async def initialize_encryption_key(self, db: AsyncSession):
        """Ініціалізує ENCRYPTION_KEY і log_level, якщо вони відсутні."""
        logger.debug("Початок ініціалізації ENCRYPTION_KEY і log_level")

        if not self.settings.encryption_key:
            existing = await db.execute(select(AppSetting).filter_by(key="encryption_key"))
            existing_setting = existing.scalar_one_or_none()
            if existing_setting:
                self.settings.encryption_key = existing_setting.value
                logger.info("ENCRYPTION_KEY завантажено з бази даних")
            else:
                self.settings.encryption_key = Fernet.generate_key().decode()
                new_setting = AppSetting(key="encryption_key", value=self.settings.encryption_key)
                db.add(new_setting)
                await db.commit()
                env_file = os.path.join(os.path.dirname(__file__), ".env")
                with open(env_file, "a", encoding="utf-8") as f:
                    f.write(f"\nENCRYPTION_KEY={self.settings.encryption_key}\n")
                logger.info("ENCRYPTION_KEY згенеровано та збережено в .env і базі даних")

        # Перевіряємо log_level у базі даних
        logger.debug("Завантаження log_level з бази даних")
        log_level_setting = await db.execute(select(AppSetting).filter_by(key="log_level"))
        log_level_setting = log_level_setting.scalar_one_or_none()
        if not log_level_setting:
            default_log_level = "DEBUG"
            new_setting = AppSetting(key="log_level", value=default_log_level)
            db.add(new_setting)
            await db.commit()
            self.log_level = default_log_level
            logger.debug(f"log_level встановлено за замовчуванням: {default_log_level}")
        else:
            self.log_level = log_level_setting.value.upper()
            logger.debug(f"log_level завантажено з бази даних: {self.log_level}")

        # Застосовуємо log_level через setup_logging
        logger.debug(f"Виклик setup_logging з log_level={self.log_level}")
        setup_logging(log_level=self.log_level)
        logger.info(f"Логування налаштовано з рівнем: {self.log_level}. Поточний рівень: {logging.getLevelName(logging.getLogger().level)}")

        # Ініціалізація шифрування
        from .models import cipher
        if cipher is None:
            from .models import ENCRYPTION_KEY
            globals()['ENCRYPTION_KEY'] = self.settings.encryption_key
            globals()['cipher'] = Fernet(self.settings.encryption_key)
            logger.debug("Шифрування ініціалізовано")

    async def initialize_settings(self, db: AsyncSession):
        """Ініціалізує налаштування, включаючи перевірку .env файлу."""
        env_file = self.settings.model_config.get("env_file")
        logger.debug(f"Читання .env файлу з: {env_file}")
        if not os.path.exists(env_file):
            logger.warning(f"Файл .env не знайдено за шляхом: {env_file}")
        if not self.settings.database_url:
            logger.error("DATABASE_URL не задано в конфігурації, перевірте .env файл")
            raise ValueError("DATABASE_URL не задано в конфігурації")
        if not self.settings.allowed_ips:
            logger.warning("ALLOWED_IPS не задано в конфігурації, перевірте .env файл")
        if not self.settings.secret_key:
            logger.warning("SECRET_KEY не задано в конфігурації, перевірте .env файл")
        logger.debug("Виклик initialize_encryption_key")
        await self.initialize_encryption_key(db)

    async def load_from_db(self, db: AsyncSession):
        """Завантажує налаштування з бази даних, зберігаючи значення з .env."""
        try:
            env_allowed_ips = self.settings.allowed_ips
            logger.debug("Завантаження налаштувань з бази даних")
            settings = await db.execute(select(AppSetting))
            settings_dict = {setting.key: setting.value for setting in settings.scalars().all()}
            logger.debug(f"Налаштування з бази даних: {settings_dict}")
            for key, value in settings_dict.items():
                if key == "log_level":
                    self.log_level = value.upper()
                    logger.debug(f"Оновлення log_level з БД: {self.log_level}")
                    setup_logging(log_level=self.log_level)
                    logger.info(f"Рівень логування оновлено з БД: {self.log_level}. Поточний рівень: {logging.getLevelName(logging.getLogger().level)}")
                elif hasattr(self.settings, key):
                    try:
                        if key in [
                            "scan_max_workers",
                            "polling_days_threshold",
                            "winrm_operation_timeout",
                            "winrm_read_timeout",
                            "winrm_port",
                            "ping_timeout",
                            "json_depth",
                            "server_port",
                        ]:
                            setattr(self.settings, key, int(value))
                        elif key == "allowed_ips" and env_allowed_ips:
                            logger.info(f"Збережено ALLOWED_IPS із .env: {env_allowed_ips}")
                            continue
                        else:
                            setattr(self.settings, key, value)
                    except ValueError as e:
                        logger.error(f"Помилка перетворення налаштування {key}: {value}, помилка: {e}")
            logger.info("Налаштування успішно завантажено з бази даних")
        except Exception as e:
            logger.error(f"Помилка завантаження налаштувань з бази даних: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Помилка завантаження налаштувань з бази даних")

    async def save_to_db(self, db: AsyncSession, updates: dict):
        """Зберігає оновлені налаштування в базу даних."""
        try:
            for key, value in updates.items():
                if value is not None and (hasattr(self.settings, key) or key == "log_level"):
                    existing = await db.execute(select(AppSetting).filter_by(key=key))
                    existing_setting = existing.scalar_one_or_none()
                    if existing_setting:
                        existing_setting.value = str(value)
                    else:
                        new_setting = AppSetting(key=key, value=str(value))
                        db.add(new_setting)
                    if key == "log_level":
                        self.log_level = value.upper()
                        setup_logging(log_level=self.log_level)
                        logger.info(f"Рівень логування оновлено: {self.log_level}. Поточний рівень: {logging.getLevelName(logging.getLogger().level)}")
                    else:
                        setattr(self.settings, key, value)
            await db.commit()
            logger.info("Налаштування успішно збережено в базу даних")
        except Exception as e:
            await db.rollback()
            logger.error(f"Помилка збереження налаштувань в базу даних: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Помилка збереження налаштувань в базу даних")