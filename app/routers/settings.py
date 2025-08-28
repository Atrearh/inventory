import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..schemas import AppSettingUpdate
from ..settings import settings
from ..settings_manager import SettingsManager
from ..database import get_db
from .auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["settings"])
settings_manager = SettingsManager(settings)

@router.get("/settings", response_model=AppSettingUpdate, dependencies=[Depends(get_current_user)])
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Отримує налаштування з БД."""
    logger.info("Отримання поточних налаштувань")
    await settings_manager.load_from_db(db)
    return AppSettingUpdate(
        log_level=settings.log_level,
        scan_max_workers=settings.scan_max_workers,
        polling_days_threshold=settings.polling_days_threshold,
        ping_timeout=settings.ping_timeout,
        timezone=settings.timezone 
    )

@router.post("/settings", response_model=AppSettingUpdate, dependencies=[Depends(get_current_user)])
async def update_settings(update: AppSettingUpdate, db: AsyncSession = Depends(get_db)):
    """Оновлює налаштування в БД."""
    updates = update.model_dump(exclude_unset=True)
    logger.info(f"Оновлення налаштувань: {updates}")
    if not updates:
        raise HTTPException(status_code=400, detail="Не надано даних для оновлення")
    await settings_manager.save_to_db(db, updates)
    logger.info(f"Налаштування успішно оновлено: {updates}")
    return update