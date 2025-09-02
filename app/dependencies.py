from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from .database import get_db_session
from .services.encryption_service import get_encryption_service
from .services.winrm_service import WinRMService
import logging

logger = logging.getLogger(__name__)

# Глобальний екземпляр WinRMService
winrm_service = None

async def get_winrm_service(db: AsyncSession = Depends(get_db_session)):
    """Отримує ініціалізований екземпляр WinRMService."""
    global winrm_service
    if winrm_service is None:
        encryption_service = get_encryption_service()
        winrm_service = WinRMService(encryption_service, db)
        await winrm_service.initialize()
        logger.info("WinRMService ініціалізовано")
    return winrm_service