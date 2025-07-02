# app/data_collector.py
import logging
import json
import winrm
from winrm.exceptions import WinRMError
from typing import Optional, Dict, List, Any
from pathlib import Path
from datetime import datetime
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

    async def _execute_script(self, session: winrm.Session, script_name: str, last_updated: Optional[datetime] = None) -> Any:
        """Выполняет PowerShell-скрипт на удалённом хосте, используя существующую сессию."""
        script_content = script_cache.get(script_name)

        async def run_ps_with_timeout():
            command = script_content
            if script_name == "software_info_changes.ps1" and last_updated:
                command = f"& {{ {script_content} }} -LastUpdated '{last_updated.isoformat()}'"
            logger.debug(f"Выполняется команда для {script_name} в сессии {self.hostname}, длина: {len(command)}")
            if len(command) > 6000:
                logger.warning(f"Команда для {script_name} превышает 6000 символов")
            result = await asyncio.to_thread(lambda: session.run_ps(command))
            return result

        try:
            result = await asyncio.wait_for(
                run_ps_with_timeout(),
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
            try:
                data = json.loads(output)
                logger.debug(f"Успешно распарсен JSON из {script_name}: {data}")
                # Нормализация вывода disk_info: оборачиваем словарь в список
                if script_name == "disk_info.ps1" and isinstance(data, dict):
                    data = [data]
                return data
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON в {script_name}: {str(e)}. Сырой вывод: {output}")
                raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при выполнении {script_name} для {self.hostname}: {str(e)}", exc_info=True)
            raise

    async def _is_server(self, session: winrm.Session) -> bool:
        """Проверяет, является ли хост сервером, по версии ОС."""
        try:
            os_data = await self._execute_script(session, "hardware_info.ps1")
            os_name = os_data.get("os_name", "").lower()
            return "server" in os_name
        except Exception as e:
            logger.error(f"Ошибка проверки версии ОС для {self.hostname}: {str(e)}")
            return False

    async def get_all_pc_info(self, session: winrm.Session, mode: str = "Full", last_updated: Optional[datetime] = None) -> Dict[str, Any]:
        """Собирает полную информацию о компьютере, используя одну WinRM-сессию."""
        result = {
            "hostname": self.hostname,
            "check_status": "partial",
            "error": None,
            "ip_addresses": [],
            "mac_addresses": [],
            "processors": [],
            "video_cards": [],
            "disks": [],
            "software": [],
            "roles": []
        }

        try:
            # Проверяем, является ли хост сервером
            is_server = await self._is_server(session)
            script_name = "server_info.ps1" if is_server else "hardware_info.ps1"
            
            # Выполняем основной скрипт
            hardware_data = await self._execute_script(session, script_name)
            result.update({
                "os_name": hardware_data.get("os_name", "Unknown"),
                "os_version": hardware_data.get("os_version"),
                "ram": hardware_data.get("ram"),
                "motherboard": hardware_data.get("motherboard"),
                "last_boot": hardware_data.get("last_boot"),
                "is_virtual": hardware_data.get("is_virtual", False),
                "ip_addresses": hardware_data.get("ip_addresses", []),
                "mac_addresses": hardware_data.get("mac_addresses", []),
                "processors": hardware_data.get("processors", []),
                "video_cards": hardware_data.get("video_cards", []),
                "roles": hardware_data.get("roles", []) if is_server else []
            })

            # Сбор данных о дисках
            disk_data = await self._execute_script(session, "disk_info.ps1")
            result["disks"] = disk_data if isinstance(disk_data, list) else [disk_data] if disk_data else []

            # Сбор данных о софте
            if mode == "Full":
                software_data = await self._execute_script(session, "software_info_full.ps1")
            else:  # Режим 'Changes'
                software_data = await self._execute_script(session, "software_info_changes.ps1", last_updated=last_updated)
            # Фильтруем install_date из software_data
            result["software"] = [
                {k: v for k, v in soft.items() if k != "install_date"}
                for soft in (software_data if isinstance(software_data, list) else [])
            ]

            result["check_status"] = "success"
        except Exception as e:
            result["error"] = f"Ошибка сбора данных: {str(e)}"
            result["check_status"] = "failed"
            logger.error(f"Ошибка сбора данных для {self.hostname}: {str(e)}", exc_info=True)

        logger.info(f"Собраны данные для {self.hostname} в режиме {mode}: {result['check_status']}")
        logger.debug(f"Подробные данные для {self.hostname}: {result}")
        return result 