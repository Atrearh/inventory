from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..schemas import AppSettingUpdate
from ..settings import settings
from ..settings_manager import SettingsManager
from ..database import get_db
from ..logging_config import setup_logging
from .auth import get_current_user
import logging

logger = logging.getLogger(__name__)
setup_logging(log_level=settings.log_level)
router = APIRouter(tags=["settings"])
settings_manager = SettingsManager(settings)

@router.get("/settings", response_model=AppSettingUpdate, dependencies=[Depends(get_current_user)])
async def get_settings(db: AsyncSession = Depends(get_db)):
    logger.info("Получение текущих настроек")
    await settings_manager.load_from_db(db)
    return AppSettingUpdate(
        ad_server_url=settings.ad_server_url,
        domain=settings.domain,
        ad_username=settings.ad_username,
        ad_password="********",
        api_url=settings.api_url,
        test_hosts=settings.test_hosts,
        log_level=settings.log_level,
        scan_max_workers=settings.scan_max_workers,
        polling_days_threshold=settings.polling_days_threshold,
        winrm_operation_timeout=settings.winrm_operation_timeout,
        winrm_read_timeout=settings.winrm_read_timeout,
        winrm_port=settings.winrm_port,
        winrm_server_cert_validation=settings.winrm_server_cert_validation,
        ping_timeout=settings.ping_timeout,
        powershell_encoding=settings.powershell_encoding,
        json_depth=settings.json_depth,
        server_port=settings.server_port,
        cors_allow_origins=settings.cors_allow_origins,
        allowed_ips=settings.allowed_ips,
        encryption_key="********",  # Не возвращаем реальный ключ
    )

@router.post("/settings", response_model=AppSettingUpdate, dependencies=[Depends(get_current_user)])
async def update_settings(update: AppSettingUpdate, db: AsyncSession = Depends(get_db)):
    logger.info("Обновление настроек: %s", update.model_dump(exclude_unset=True))
    updates = update.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Не предоставлены данные для обновления")
    if "encryption_key" in updates:
        logger.warning("Обновление ENCRYPTION_KEY может сделать существующие зашифрованные данные нечитаемыми")
    await settings_manager.save_to_db(db, updates)
    logger.info("Настройки успешно обновлены: %s", updates)
    return update