import os
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..settings import settings
from .auth import get_current_user
from typing import List, Dict
from ..data_collector import WinRMDataCollector,  SCRIPTS_DIR
from pydantic import BaseModel, ValidationError
from ..services.encryption_service import EncryptionService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scripts"], prefix="/api/scripts")

class ExecuteScriptRequest(BaseModel):
    hostname: str

@router.get("/list", response_model=List[str], dependencies=[Depends(get_current_user)])
async def get_scripts_list():
    """Отримання списку доступних PowerShell-скриптів."""
    scripts_dir = SCRIPTS_DIR
    try:
        logger.debug(f"Перевірка існування папки скриптів: {os.path.abspath(scripts_dir)}")
        if not os.path.exists(scripts_dir):
            logger.warning(f"Папка скриптів {scripts_dir} не існує")
            return []
        
        scripts = [f for f in os.listdir(scripts_dir) if f.endswith(".ps1")]
        logger.info(f"Знайдено {len(scripts)} скриптів: {scripts}")
        return scripts
    except Exception as e:
        logger.error(f"Помилка при отриманні списку скриптів: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Помилка сервера: {str(e)}")

@router.post("/execute/{script_name}", response_model=Dict[str, str], dependencies=[Depends(get_current_user)])
async def execute_script(
    script_name: str,
    request_body: ExecuteScriptRequest,
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    """Виконання вказаного скрипта на хості."""
    logger_adapter = request.state.logger if request else logger
    try:
        hostname = request_body.hostname
        logger_adapter.info(f"Запит на виконання скрипта {script_name} на хості {hostname}")
    except ValidationError as e:
        logger_adapter.error(f"Помилка валідації тіла запиту: {e.errors()}")
        raise HTTPException(status_code=422, detail=e.errors())
    
    scripts_dir = SCRIPTS_DIR
    script_path = os.path.join(scripts_dir, script_name)
    
    # Валідація імені скрипта
    if not script_name.endswith(".ps1"):
        logger_adapter.error(f"Недопустиме розширення файлу: {script_name}")
        raise HTTPException(status_code=400, detail="Скрипт повинен мати розширення .ps1")
    
    if not os.path.exists(script_path):
        logger_adapter.error(f"Скрипт {script_name} не знайдено в папці {os.path.abspath(scripts_dir)}")
        raise HTTPException(status_code=404, detail="Скрипт не знайдено")
    
    try:
        encryption_service = EncryptionService(settings.encryption_key)
        collector = WinRMDataCollector(hostname=hostname, db=db, encryption_service=encryption_service)
        with collector.winrm_service.create_session(hostname) as session:
            result = await collector._execute_script(script_name)
            logger_adapter.info(f"Скрипт {script_name} успішно виконано на {hostname}")
            return {"output": result.get("stdout", ""), "error": result.get("stderr", "")}
    except Exception as e:
        logger_adapter.error(f"Помилка виконання скрипта {script_name} на {hostname}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Помилка виконання скрипта: {str(e)}")