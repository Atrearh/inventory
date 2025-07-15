from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .models import AppSetting
from .settings import Settings
from cryptography.fernet import Fernet
import logging
from fastapi import HTTPException
import os

logger = logging.getLogger(__name__)

class SettingsManager:
    """Класс для управления настройками приложения, включая загрузку и сохранение в базу данных."""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def initialize_encryption_key(self, db: AsyncSession):
        """Инициализирует ENCRYPTION_KEY, если он отсутствует."""
        if not self.settings.encryption_key:
            # Проверяем в базе данных
            existing = await db.execute(select(AppSetting).filter_by(key="encryption_key"))
            existing_setting = existing.scalar_one_or_none()
            if existing_setting:
                self.settings.encryption_key = existing_setting.value
                logger.info("ENCRYPTION_KEY загружен из базы данных")
            else:
                # Генерируем новый ключ и сохраняем в .env и БД
                self.settings.encryption_key = Fernet.generate_key().decode()
                new_setting = AppSetting(key="encryption_key", value=self.settings.encryption_key)
                db.add(new_setting)
                await db.commit()
                # Сохраняем в .env
                env_file = os.path.join(os.path.dirname(__file__), ".env")
                with open(env_file, "a", encoding="utf-8") as f:
                    f.write(f"\nENCRYPTION_KEY={self.settings.encryption_key}\n")
                logger.info("ENCRYPTION_KEY сгенерирован и сохранен в .env и базе данных")
        from .models import cipher
        if cipher is None:
            from .models import ENCRYPTION_KEY
            globals()['ENCRYPTION_KEY'] = self.settings.encryption_key
            globals()['cipher'] = Fernet(self.settings.encryption_key)
            logger.info("Шифрование инициализировано с ENCRYPTION_KEY")

    async def load_from_db(self, db: AsyncSession):
        """Загружает настройки из базы данных."""
        try:
            await self.initialize_encryption_key(db)  # Убедимся, что ключ шифрования инициализирован
            settings = await db.execute(select(AppSetting))
            settings_dict = {setting.key: setting.value for setting in settings.scalars().all()}
            for key, value in settings_dict.items():
                if hasattr(self.settings, key):
                    try:
                        # Приведение типов для числовых полей
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
                        elif key == "test_hosts" and value == "":
                            # Используем значение по умолчанию, если в БД пустая строка
                            setattr(self.settings, key, "localhost")
                            logger.debug(f"Пустое значение test_hosts в БД, использовано значение по умолчанию: localhost")
                        else:
                            setattr(self.settings, key, value)
                    except ValueError as e:
                        logger.error(f"Ошибка преобразования настройки {key}: {value}, ошибка: {e}")
            logger.info("Настройки успешно загружены из базы данных")
        except Exception as e:
            logger.error(f"Ошибка загрузки настроек из базы данных: {str(e)}")
            raise HTTPException(status_code=500, detail="Ошибка загрузки настроек из базы данных")

    async def save_to_db(self, db: AsyncSession, updates: dict):
        """Сохраняет обновленные настройки в базу данных."""
        try:
            for key, value in updates.items():
                if value is not None and hasattr(self.settings, key):
                    existing = await db.execute(select(AppSetting).filter_by(key=key))
                    existing_setting = existing.scalar_one_or_none()
                    if existing_setting:
                        existing_setting.value = str(value)
                    else:
                        new_setting = AppSetting(key=key, value=str(value))
                        db.add(new_setting)
                    setattr(self.settings, key, value)
            await db.commit()
            logger.info("Настройки успешно сохранены в базу данных")
        except Exception as e:
            await db.rollback()
            logger.error(f"Ошибка сохранения настроек в базу данных: {str(e)}")
            raise HTTPException(status_code=500, detail="Ошибка сохранения настроек в базу данных")