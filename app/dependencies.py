# app/dependencies.py
import logging

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db_session
from .services.encryption_service import get_encryption_service
from .services.winrm_service import WinRMService

logger = logging.getLogger(__name__)


async def get_winrm_service(
    db: AsyncSession = Depends(get_db_session),
    encryption_service=Depends(get_encryption_service),
):
    """Отримує ініціалізований екземпляр WinRMService."""
    winrm_service = WinRMService(encryption_service, db)
    await winrm_service.initialize()
    logger.info("WinRMService ініціалізовано")
    return winrm_service
