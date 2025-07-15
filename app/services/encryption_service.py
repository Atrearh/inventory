
from cryptography.fernet import Fernet
import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class EncryptionService:
    def __init__(self, encryption_key: str):
        if not encryption_key:
            logger.error("ENCRYPTION_KEY отсутствует")
            raise HTTPException(status_code=500, detail="Шифрование не инициализировано")
        try:
            self.cipher = Fernet(encryption_key.encode())
        except Exception as e:
            logger.error(f"Ошибка инициализации шифрования: {str(e)}")
            raise HTTPException(status_code=500, detail="Ошибка инициализации шифрования")

    def encrypt(self, value: str) -> str:
        try:
            return self.cipher.encrypt(value.encode()).decode()
        except Exception as e:
            logger.error(f"Ошибка шифрования: {str(e)}")
            raise HTTPException(status_code=500, detail="Ошибка шифрования")

    def decrypt(self, encrypted_value: str) -> str:
        try:
            return self.cipher.decrypt(encrypted_value.encode()).decode()
        except Exception as e:
            logger.error(f"Ошибка дешифровки: {str(e)}")
            raise HTTPException(status_code=500, detail="Ошибка дешифровки")