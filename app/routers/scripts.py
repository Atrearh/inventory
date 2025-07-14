import os
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from .. import models
from ..settings import settings
from .auth import get_current_user
from typing import List, Dict
from ..data_collector import WinRMDataCollector, winrm_session, SCRIPTS_DIR  # Импортируем SCRIPTS_DIR
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scripts"], prefix="/api/scripts")

class ExecuteScriptRequest(BaseModel):
    hostname: str

@router.get("/list", response_model=List[str], dependencies=[Depends(get_current_user)])
async def get_scripts_list():
    """Получение списка доступных PowerShell-скриптов."""
    scripts_dir = SCRIPTS_DIR  # Используем путь из data_collector.py
    try:
        logger.debug(f"Проверка существования папки скриптов: {os.path.abspath(scripts_dir)}")
        if not os.path.exists(scripts_dir):
            logger.warning(f"Папка скриптов {scripts_dir} не существует")
            return []
        
        scripts = [f for f in os.listdir(scripts_dir) if f.endswith(".ps1")]
        logger.info(f"Найдено {len(scripts)} скриптов: {scripts}")
        return scripts
    except Exception as e:
        logger.error(f"Ошибка при получении списка скриптов: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")

@router.post("/execute/{script_name}", response_model=Dict[str, str], dependencies=[Depends(get_current_user)])
async def execute_script(
    script_name: str,
    request_body: ExecuteScriptRequest,
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    """Выполнение указанного скрипта на хосте."""
    logger_adapter = request.state.logger if request else logger
    try:
        hostname = request_body.hostname
        logger_adapter.info(f"Запрос на выполнение скрипта {script_name} на хосте {hostname}")
    except ValidationError as e:
        logger_adapter.error(f"Ошибка валидации тела запроса: {e.errors()}")
        raise HTTPException(status_code=422, detail=e.errors())
    
    scripts_dir = SCRIPTS_DIR  # Используем путь из data_collector.py
    script_path = os.path.join(scripts_dir, script_name)
    
    # Валидация имени скрипта
    if not script_name.endswith(".ps1"):
        logger_adapter.error(f"Недопустимое расширение файла: {script_name}")
        raise HTTPException(status_code=400, detail="Скрипт должен иметь расширение .ps1")
    
    if not os.path.exists(script_path):
        logger_adapter.error(f"Скрипт {script_name} не найден в папке {os.path.abspath(scripts_dir)}")
        raise HTTPException(status_code=404, detail="Скрипт не найден")
    
    try:
        collector = WinRMDataCollector(hostname=hostname, username=settings.ad_username, password=settings.ad_password)
        with winrm_session(hostname, settings.ad_username, settings.ad_password) as session:
            # Выполнение скрипта через _execute_script
            result = await collector._execute_script(session, script_name)
            logger_adapter.info(f"Скрипт {script_name} успешно выполнен на {hostname}")
            return {"output": result.get("stdout", ""), "error": result.get("stderr", "")}
    except Exception as e:
        logger_adapter.error(f"Ошибка выполнения скрипта {script_name} на {hostname}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка выполнения скрипта: {str(e)}") 