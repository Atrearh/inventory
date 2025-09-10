import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..schemas import AppSettingUpdate
from ..database import get_db
from .auth import get_current_user
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=AppSettingUpdate, dependencies=[Depends(get_current_user)])
async def get_settings():
    """Повертає поточні налаштування додатку."""
    logger.info("Отримання поточних налаштувань через API")
    return settings

@router.post("/settings", response_model=AppSettingUpdate, dependencies=[Depends(get_current_user)])
async def update_settings(update: AppSettingUpdate, db: AsyncSession = Depends(get_db)):
    """Оновлює налаштування в БД та в поточному стані додатку."""
    updates = update.model_dump(exclude_unset=True)
    logger.info(f"Оновлення налаштувань через API: {updates}")
    if not updates:
        raise HTTPException(status_code=400, detail="Не надано даних для оновлення")
    
    await settings.save_settings(db, updates)
    
    return settings