import logging
import json
import winrm
from winrm.exceptions import WinRMError
from typing import Optional, Dict
from pathlib import Path
from datetime import datetime, timedelta
import asyncio
import requests
from contextlib import contextmanager
from .settings import settings

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "app/scripts"
logger.debug(f"Settings attributes: {dir(settings)}, winrm_port: {getattr(settings, 'winrm_port', 'Not found')}")

class ScriptCache:
    """Управление кэшем PowerShell-скриптов."""
    def __init__(self):
        self._cache = {}

    def get(self, file_name: str) -> str:
        if file_name not in self._cache:
            file_path = SCRIPTS_DIR / file_name
            try:
                if not file_path.exists():
                    logger.error(f"Файл скрипта {file_path} не найден")
                    raise FileNotFoundError(f"Файл {file_path} не найден")
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    script = f.read().rstrip()
                self._cache[file_name] = script
                logger.debug(f"Загружен и закэширован скрипт {file_path}, длина: {len(script)} символов")
                if len(script) > 2000:
                    logger.warning(f"Скрипт {file_name} длиннее 2000 символов: {len(script)}")
            except Exception as e:
                logger.error(f"Ошибка загрузки скрипта {file_path}: {str(e)}")
                raise
        return self._cache[file_name]

    def clear(self):
        self._cache.clear()
        logger.debug("Кэш скриптов очищен")

script_cache = ScriptCache()

def decode_output(output: bytes) -> str:
    """Декодирует вывод PowerShell."""
    if not output:
        return ""
    try:
        return output.decode('utf-8')
    except UnicodeDecodeError:
        logger.debug(f"Ошибка декодирования UTF-8, пробуем {settings.powershell_encoding}")
        return output.decode(settings.powershell_encoding, errors='replace')

@contextmanager
def winrm_session(hostname: str, username: str, password: str):
    """Создаёт WinRM-сессию с обработкой ошибок."""
    session = None
    try:
        logger.debug(f"Создание WinRM-сессии для {hostname}, порт: {settings.winrm_port}")
        session = winrm.Session(
            f"http://{hostname}:{settings.winrm_port}/wsman",
            auth=(username, password),
            transport="ntlm",
            server_cert_validation=settings.winrm_server_cert_validation,
            operation_timeout_sec=settings.winrm_operation_timeout,
            read_timeout_sec=settings.winrm_read_timeout
        )
        logger.debug(f"WinRM-сессия создана для {hostname}")
        yield session
    except (WinRMError, requests.exceptions.ConnectTimeout) as e:
        logger.error(f"Не удалось создать WinRM-сессию для {hostname}: {str(e)}", exc_info=True)
        raise ConnectionError(f"Не удалось подключиться к {hostname}: {str(e)}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при создании WinRM-сессии для {hostname}: {str(e)}", exc_info=True)
        raise
    finally:
        if session:
            logger.debug(f"Закрытие WinRM-сессии для {hostname}")

class WinRMDataCollector:
    def __init__(self, hostname: str, username: str, password: str):
        self.hostname = hostname
        self.username = username
        self.password = password

    async def _run_script(self, script_name: str, mode: str = "Full", last_updated: Optional[datetime] = None) -> dict:
        """Выполняет PowerShell-скрипт на удалённом хосте."""
        script_name = (
            "software_info_full.ps1" if script_name == "software_info.ps1" and mode == "Full"
            else "software_info_changes.ps1" if script_name == "software_info.ps1"
            else script_name
        )
        script_content = script_cache.get(script_name)

        async def run_ps_with_timeout(session):
            command = script_content
            if script_name == "software_info_changes.ps1" and last_updated:
                command = f"& {{ {script_content} }} -LastUpdated '{last_updated.isoformat()}'"
            logger.debug(f"Выполняется команда для {script_name}, длина: {len(command)}")
            if len(command) > 6000:
                logger.warning(f"Команда для {script_name} превышает 6000 символов")
            result = await asyncio.to_thread(lambda: session.run_ps(command))
            return result

        with winrm_session(self.hostname, self.username, self.password) as session:
            try:
                result = await asyncio.wait_for(
                    run_ps_with_timeout(session),
                    timeout=settings.winrm_operation_timeout + settings.winrm_read_timeout
                )
                if result.status_code != 0:
                    error_message = decode_output(result.std_err)
                    logger.error(f"Ошибка выполнения {script_name} для {self.hostname}: {error_message}", exc_info=True)
                    raise RuntimeError(f"Ошибка выполнения скрипта: {error_message}")
                output = decode_output(result.std_out)
                if not output.strip():
                    logger.error(f"Пустой вывод от {script_name} для {self.hostname}")
                    raise RuntimeError(f"Скрипт вернул пустой вывод")
                logger.info(f"Скрипт {script_name} выполнен успешно для {self.hostname}")
                return json.loads(output)
            except asyncio.TimeoutError:
                logger.error(f"Тайм-аут выполнения скрипта {script_name} для {self.hostname}", exc_info=True)
                raise
            except Exception as e:
                logger.error(f"Неожиданная ошибка при выполнении {script_name} для {self.hostname}: {str(e)}", exc_info=True)
                raise

    async def get_system_info(self) -> dict:
        return await self._run_script("system_info.ps1")

    async def get_software_info(self, mode: str = "Full", last_updated: Optional[datetime] = None) -> list:
        data = await self._run_script("software_info.ps1", mode=mode, last_updated=last_updated)
        if not isinstance(data, list):
            logger.warning(f"software_info.ps1 вернул не массив: {data}")
            return []
        return data

    async def get_all_pc_info(self, mode: str = "Full", last_updated: Optional[datetime] = None) -> dict:
        result = {
            "hostname": self.hostname,
            "check_status": "partial",
            "error": None
        }
        try:
            system_data = await self.get_system_info()
            result.update(system_data)
            logger.info( f"Собраны данные для {self.hostname} raw data: {system_data}")
            result["check_status"] = "success"
        except Exception as e:
            result["error"] = f"System info error: {str(e)}"
            result["check_status"] = "failed"
        try:
            software_data = await self.get_software_info(mode=mode, last_updated=last_updated)
            result["software"] = software_data
            if result["check_status"] != "failed":
                result["check_status"] = "success"
        except Exception as e:
            error_msg = f"Software info error: {str(e)}"
            result["error"] = f"{result['error']}; {error_msg}" if result["error"] else error_msg
            if result["check_status"] == "success":
                result["check_status"] = "partial"
        logger.info(f"Собраны данные для {self.hostname} в режиме {mode}: {result['check_status']}")
        return result

async def get_pc_info(hostname: str, user: str, password: str, retries: int = 3, last_updated: Optional[datetime] = None, last_full_scan: Optional[datetime] = None) -> Optional[Dict]:
    collector = WinRMDataCollector(hostname, user, password)
    for attempt in range(1, retries + 1):
        try:
            mode = "Full" if last_updated is None or (
                last_full_scan is None or last_full_scan < datetime.utcnow() - timedelta(days=30)
            ) else "Changes"
            return await collector.get_all_pc_info(mode=mode, last_updated=last_updated)
        except ConnectionError as e:
            logger.warning(f"Попытка {attempt}/{retries} не удалась для {hostname}: {str(e)}")
            if attempt == retries:
                return {
                    "hostname": hostname,
                    "check_status": "unreachable",
                    "error": str(e)
                }
            await asyncio.sleep(1)
