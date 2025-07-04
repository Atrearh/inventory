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
                logger.warning(f"Пустой вывод от {script_name} для {self.hostname}, возвращается пустой список")
                return []  # Возвращаем пустой список вместо вызова ошибки
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
        result = {
            "hostname": self.hostname,
            "check_status": "partial",
            "ip_addresses": [],
            "mac_addresses": [],
            "processors": [],
            "video_cards": [],
            "disks": {"physical_disks": [], "logical_disks": []},
            "software": [],
            "roles": [],
            "os_name": "Unknown",
            "os_version": None,
            "ram": None,
            "motherboard": None,
            "last_boot": None,
            "is_virtual": False,
        }

        try:
            is_server = await self._is_server(session)
            script_name = "server_info.ps1" if is_server else "hardware_info.ps1"
            hardware_data = await self._execute_script(session, script_name)
            result.update({
                "os_name": hardware_data.get("os_name", "Unknown"),
                "os_version": hardware_data.get("os_version"),
                "ram": hardware_data.get("ram"),
                "motherboard": hardware_data.get("motherboard"),
                "last_boot": hardware_data.get("last_boot"),
                "is_virtual": hardware_data.get("is_virtual", False),
                "ip_addresses": list(set(hardware_data.get("ip_addresses", []))),  # Удаляем дубли
                "mac_addresses": list(set(hardware_data.get("mac_addresses", []))),  # Удаляем дубли
                "processors": list({proc['name']: proc for proc in hardware_data.get("processors", [])}.values()),  # Удаляем дубли по имени
                "video_cards": list({card['name']: card for card in hardware_data.get("video_cards", [])}.values()),  # Удаляем дубли по имени
                "roles": hardware_data.get("roles", []) if is_server else []
            })

            disk_data = await self._execute_script(session, "disk_info.ps1")
            # Фильтруем некорректные диски
            physical_disks = [disk for disk in disk_data.get("physical_disks", []) if disk.get("serial")]
            logical_disks = [disk for disk in disk_data.get("logical_disks", []) if disk.get("device_id") and disk.get("total_space", 0) > 0]
            result["disks"] = {
                "physical_disks": list({disk['serial']: disk for disk in physical_disks}.values()),  # Удаляем дубли по serial
                "logical_disks": list({disk['device_id']: disk for disk in logical_disks}.values())  # Удаляем дубли по device_id
            }

            software_data = []
            if mode == "Full":
                software_data = await self._execute_script(session, "software_info_full.ps1")
            else:
                try:
                    software_data = await self._execute_script(session, "software_info_changes.ps1", last_updated=last_updated)
                except RuntimeError as e:
                    logger.warning(f"Ошибка при получении данных software_info для {self.hostname}: {str(e)}")
                    software_data = []
            result["software"] = list({(soft.get("DisplayName", "").lower(), soft.get("DisplayVersion", "").lower()): soft for soft in software_data}.values())  # Удаляем дубли по имени и версии
            result["check_status"] = "success"
        except Exception as e:
            result["error"] = f"Ошибка сбора данных: {str(e)}"
            result["check_status"] = "failed"
            logger.error(f"Ошибка сбора данных для {self.hostname}: {str(e)}", exc_info=True)

        logger.info(f"Собраны данные для {self.hostname} в режиме {mode}: {result['check_status']}")
        logger.debug(f"Подробные данные для {self.hostname}: {result}")
        return result