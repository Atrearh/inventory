import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status

from ..config import settings

logger = logging.getLogger(__name__)


class EncryptionService:
    """Сервис для шифрования и дешифровки данных с использованием Fernet."""

    def __init__(self, encryption_key: Optional[str]) -> None:
        """
        Инициализация сервиса шифрования.

        Args:
            encryption_key: Ключ шифрования в формате строки (base64-encoded, 32 байта).

        Raises:
            HTTPException: Если ключ отсутствует или имеет неверный формат.
        """
        if not encryption_key:
            logger.error("Отсутствует ключ шифрования")
            raise HTTPException(
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ключ шифрования не предоставлен",
            )

        try:
            # Проверка, что ключ соответствует формату Fernet (32 байта в base64)
            Fernet(encryption_key.encode())
            self.cipher = Fernet(encryption_key.encode())
        except (ValueError, InvalidToken) as e:
            logger.error(f"Неверный формат ключа шифрования: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Неверный формат ключа шифрования",
            )
        logger.debug("Сервис шифрования успешно инициализирован")

    def encrypt(self, value: str) -> str:
        """
        Шифрует строку с использованием Fernet.

        Args:
            value: Строка для шифрования.

        Returns:
            str: Зашифрованная строка в формате base64.

        Raises:
            HTTPException: Если шифрование не удалось.
        """
        if not value:
            logger.warning("Попытка шифрования пустой строки")
            return ""

        try:
            encrypted = self.cipher.encrypt(value.encode()).decode()
            logger.debug(f"Успешно зашифровано значение длиной {len(value)} символов")
            return encrypted
        except (ValueError, InvalidToken) as e:
            logger.error(f"Ошибка шифрования: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при шифровании данных",
            )

    def decrypt(self, encrypted_value: str) -> str:
        """
        Дешифрует строку, зашифрованную с использованием Fernet.

        Args:
            encrypted_value: Зашифрованная строка в формате base64.

        Returns:
            str: Дешифрованная строка.

        Raises:
            HTTPException: Если дешифровка не удалась.
        """
        if not encrypted_value:
            logger.warning("Попытка дешифровки пустой строки")
            return ""

        try:
            decrypted = self.cipher.decrypt(encrypted_value.encode()).decode()
            logger.debug(
                f"Успешно дешифровано значение длиной {len(encrypted_value)} символов"
            )
            return decrypted
        except (ValueError, InvalidToken) as e:
            logger.error(f"Ошибка дешифровки: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при дешифровке данных",
            )

    @staticmethod
    def generate_key() -> str:
        """
        Генерирует новый ключ шифрования для Fernet.

        Returns:
            str: Сгенерированный ключ в формате base64.
        """
        try:
            key = Fernet.generate_key().decode()
            logger.info("Сгенерирован новый ключ шифрования")
            return key
        except Exception as e:
            logger.error(f"Ошибка генерации ключа: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при генерации ключа шифрования",
            )


def get_encryption_service() -> EncryptionService:
    """Отримує екземпляр EncryptionService з ініціалізованим ключем шифрування."""
    return EncryptionService(settings.encryption_key)
