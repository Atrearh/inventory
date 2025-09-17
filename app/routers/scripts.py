import asyncio
import json
import logging
import os
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from ..data_collector import SCRIPTS_DIR, script_cache
from ..database import get_db_session
from ..dependencies import get_winrm_service
from ..services.winrm_service import WinRMService
from .auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scripts"], prefix="/api/scripts")


class ExecuteScriptRequest(BaseModel):
    hostname: str
    params: dict = {}


@router.get("/list", response_model=List[str], dependencies=[Depends(get_current_user)])
async def get_scripts_list():
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


@router.post(
    "/execute/{script_name}",
    response_model=Dict[str, str],
    dependencies=[Depends(get_current_user)],
)
async def execute_script(
    script_name: str,
    request_body: ExecuteScriptRequest,
    db: AsyncSession = Depends(get_db_session),
    winrm_service: WinRMService = Depends(get_winrm_service),
    request: Request = None,
):
    logger_adapter = request.state.logger if request else logger
    try:
        hostname = request_body.hostname
        params = request_body.params
        logger_adapter.info(f"Запит на виконання скрипта {script_name} на хості {hostname} з параметрами {params}")
    except ValidationError as e:
        logger_adapter.error(f"Помилка валідації тіла запиту: {e.errors()}")
        raise HTTPException(status_code=422, detail=e.errors())

    scripts_dir = SCRIPTS_DIR
    script_path = os.path.join(scripts_dir, script_name)

    if not script_name.endswith(".ps1"):
        logger_adapter.error(f"Недопустиме розширення файлу: {script_name}")
        raise HTTPException(status_code=400, detail="Скрипт повинен мати розширення .ps1")

    if not os.path.exists(script_path):
        logger_adapter.error(f"Скрипт {script_name} не знайдено в папці {os.path.abspath(scripts_dir)}")
        raise HTTPException(status_code=404, detail="Скрипт не знайдено")

    try:
        param_string = ""
        for key, value in params.items():
            param_string += f"${key} = '{value}'; "

        script_content = script_cache.get(script_name)
        command = f"{param_string}{script_content}"

        async with winrm_service.create_session(hostname) as session:
            result = await asyncio.to_thread(session.run_ps, command)
            output = json.loads(result.std_out) if result.std_out else {"Success": False, "Errors": ["No output"]}
            if result.status_code != 0:
                error_message = result.std_err.decode("utf-8", errors="replace") if result.std_err else "Unknown error"
                logger_adapter.error(f"Скрипт {script_name} завершився з помилкою: {error_message}")
                output["Errors"] = output.get("Errors", []) + [error_message]
                output["Success"] = False
            else:
                logger_adapter.info(f"Скрипт {script_name} успішно виконано на {hostname}")

            return output
    except Exception as e:
        logger_adapter.error(
            f"Помилка виконання скрипта {script_name} на {hostname}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Помилка виконання скрипта: {str(e)}")
