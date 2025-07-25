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
    """Клас для управління налаштуваннями додатка, включаючи завантаження та збереження в базу даних."""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def initialize_encryption_key(self, db: AsyncSession):
        """Ініціалізує ENCRYPTION_KEY, якщо він відсутній."""
        if not self.settings.encryption_key:
            # Перевіряємо в базі даних
            existing = await db.execute(select(AppSetting).filter_by(key="encryption_key"))
            existing_setting = existing.scalar_one_or_none()
            if existing_setting:
                self.settings.encryption_key = existing_setting.value
                logger.info("ENCRYPTION_KEY завантажено з бази даних")
            else:
                # Генеруємо новий ключ і зберігаємо в .env та БД
                self.settings.encryption_key = Fernet.generate_key().decode()
                new_setting = AppSetting(key="encryption_key", value=self.settings.encryption_key)
                db.add(new_setting)
                await db.commit()
                # Зберігаємо в .env
                env_file = os.path.join(os.path.dirname(__file__), ".env")
                with open(env_file, "a", encoding="utf-8") as f:
                    f.write(f"\nENCRYPTION_KEY={self.settings.encryption_key}\n")
                logger.info("ENCRYPTION_KEY згенеровано та збережено в .env і базі даних")
        from .models import cipher
        if cipher is None:
            from .models import ENCRYPTION_KEY
            globals()['ENCRYPTION_KEY'] = self.settings.encryption_key
            globals()['cipher'] = Fernet(self.settings.encryption_key)

    async def load_from_db(self, db: AsyncSession):
        """Завантажує налаштування з бази даних."""
        try:
            await self.initialize_encryption_key(db)  # Переконаємося, що ключ шифрування ініціалізовано
            settings = await db.execute(select(AppSetting))
            settings_dict = {setting.key: setting.value for setting in settings.scalars().all()}
            for key, value in settings_dict.items():
                if hasattr(self.settings, key):
                    try:
                        # Приведення типів для числових полів
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
                            # Використовуємо значення за замовчуванням, якщо в БД порожній рядок
                            setattr(self.settings, key, "localhost")
                            logger.debug(f"Порожнє значення test_hosts в БД, використано значення за замовчуванням: localhost")
                        else:
                            setattr(self.settings, key, value)
                    except ValueError as e:
                        logger.error(f"Помилка перетворення налаштування {key}: {value}, помилка: {e}")
            logger.info("Налаштування успішно завантажено з бази даних")
        except Exception as e:
            logger.error(f"Помилка завантаження налаштувань з бази даних: {str(e)}")
            raise HTTPException(status_code=500, detail="Помилка завантаження налаштувань з бази даних")

    async def save_to_db(self, db: AsyncSession, updates: dict):
        """Зберігає оновлені налаштування в базу даних."""
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
            logger.info("Налаштування успішно збережено в базу даних")
        except Exception as e:
            await db.rollback()
            logger.error(f"Помилка збереження налаштувань в базу даних: {str(e)}")
            raise HTTPException(status_code=500, detail="Помилка збереження налаштувань в базу даних")