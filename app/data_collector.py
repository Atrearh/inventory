import json
import winrm
from winrm.exceptions import WinRMError
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime
import asyncio
import requests
from contextlib import contextmanager
from .settings import settings
import os
from functools import lru_cache
import structlog

logger = structlog.get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "app" / "scripts"

class ScriptCache:
    """Управління кешем PowerShell-скриптів."""
    def __init__(self):
        self._cache: Dict[str, str] = {}

    @lru_cache(maxsize=100)
    def get(self, file_name: str) -> str:
        """Отримує вміст скрипта з кешу або диска."""
        file_path = SCRIPTS_DIR / file_name
        if not file_path.exists():
            logger.error(f"Скрипт {file_path} не знайдено")
            raise FileNotFoundError(f"Скрипт {file_path} не знайдено")
        
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            script = f.read().rstrip()
        
        if len(script) > 3000:
            logger.warning(f"Скрипт {file_name} великий", size=len(script))
        return script

    async def preload_scripts(self):
        """Попередньо завантажує всі .ps1 скрипти."""
        scripts_dir = SCRIPTS_DIR
        logger.debug(f"Завантаження скриптів з {scripts_dir}")
        if not scripts_dir.exists():
            logger.warning(f"Папка {scripts_dir} не існує")
            return
        
        script_count = 0
        for script_name in [f for f in os.listdir(scripts_dir) if f.endswith(".ps1")]:
            try:
                self.get(script_name)
                script_count += 1
                logger.debug(f"Скрипт {script_name} завантажено в кеш")
            except Exception as e:
                logger.error(f"Помилка завантаження {script_name}", error=str(e))
        logger.info(f"Завантажено {script_count} скриптів у кеш")

    def clear(self):
        """Очищає кеш скриптів."""
        self._cache.clear()
        self.get.cache_clear()
        logger.info("Кеш скриптів очищено")

script_cache = ScriptCache()

def decode_output(output: bytes) -> str:
    """
    Декодирует байтовый вывод PowerShell, используя сначала UTF-8,
    а затем запасную кодировку из настроек.
    """
    if not output:
        return ""
    try:
        return output.decode('utf-8')
    except UnicodeDecodeError:
        logger.debug(f"Не удалось декодировать как UTF-8, используется запасная кодировка: {settings.powershell_encoding}")
        return output.decode(settings.powershell_encoding, errors='replace')

@contextmanager
def winrm_session(hostname: str, username: str, password: str):
    """
    Контекстный менеджер для создания и управления WinRM-сессией.
    Использует централизованные настройки таймаутов и валидации сертификата.
    """
    session = None
    try:
        logger.debug(f"Создание WinRM-сессии для {hostname} на порту {settings.winrm_port}")
        session = winrm.Session(
            f"http://{hostname}:{settings.winrm_port}/wsman",
            auth=(username, password),
            transport="ntlm",
            server_cert_validation=settings.winrm_server_cert_validation,
            operation_timeout_sec=settings.winrm_operation_timeout,
            read_timeout_sec=settings.winrm_read_timeout
        )
        yield session
    except (WinRMError, requests.exceptions.RequestException) as e:
        logger.error(f"Ошибка подключения WinRM к {hostname}", error=str(e))
        raise ConnectionError(f"Не удалось подключиться к {hostname}: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при создании WinRM-сессии для {hostname}", error=str(e))
        raise
    finally:
        if session:
            logger.debug(f"Закрытие WinRM-сессии для {hostname}")

class WinRMDataCollector:
    """
    Собирает информацию с удаленных хостов Windows с использованием WinRM.
    """
    def __init__(self, hostname: str, username: str, password: str):
        self.hostname = hostname
        self.username = username
        self.password = password

    async def _execute_script(self, session: winrm.Session, script_name: str, last_updated: Optional[datetime] = None) -> Any:
        """
        Асинхронно выполняет PowerShell-скрипт на удаленном хосте.
        """
        try:
            script_content = script_cache.get(script_name)
        except FileNotFoundError:
            raise

        command = script_content
        if script_name == "software_info_changes.ps1" and last_updated:
            command = f"& {{ {script_content} }} -LastUpdated '{last_updated.isoformat()}'"

        logger.debug(f"Выполнение скрипта {script_name} на {self.hostname}")
        if len(command) > 3000:
            logger.warning(f"Команда для {script_name} на {self.hostname} превышает 3000 символов")

        try:
            result = await asyncio.to_thread(session.run_ps, command)

            if result.status_code != 0:
                error_message = decode_output(result.std_err)
                logger.error(f"Скрипт {script_name} на {self.hostname} завершился с ошибкой", status_code=result.status_code, error=error_message)
                raise RuntimeError(f"Ошибка выполнения скрипта '{script_name}': {error_message}")

            output = decode_output(result.std_out)

            if not output.strip():
                if script_name == "software_info_changes.ps1":
                    logger.debug(f"Скрипт {script_name} на {self.hostname} вернул пустой результат")
                else:
                    logger.warning(f"Скрипт {script_name} на {self.hostname} вернул пустой результат")
                return [] 

            logger.info(f"Скрипт {script_name} на {self.hostname} выполнен успешно")
            
            try:
                data = json.loads(output)
                logger.debug(f"JSON из {script_name} успешно распарсен")
                return data
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON из {script_name} на {self.hostname}", error=str(e), output=output[:500])
                raise ValueError(f"Некорректный формат JSON от скрипта {script_name}")

        except Exception as e:
            logger.error(f"Неожиданная ошибка при выполнении {script_name} на {self.hostname}", error=str(e))
            raise

    async def get_all_pc_info(self, mode: str = "Full", last_updated: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Собирает полную информацию о ПК, включая оборудование, ПО и роли сервера.
        """
        result: Dict[str, Any] = {"hostname": self.hostname, "check_status": "failed"}
        logger = logger.bind(hostname=self.hostname)
        
        try:
            with winrm_session(self.hostname, self.username, self.password) as session:
                logger.info("Начало сбора данных")
                
                # Инициализация структуры данных
                result.update({
                    "ip_addresses": [], "mac_addresses": [], "processors": [],
                    "video_cards": [], "disks": {"physical_disks": [], "logical_disks": []},
                    "software": [], "roles": [], "os_name": "Unknown", "os_version": None,
                    "ram": None, "motherboard": None, "last_boot": None, "is_virtual": False
                })
                
                # Сбор базовой информации об оборудовании
                hardware_data = await self._execute_script(session, "hardware_info.ps1")
                if hardware_data:
                    result.update({
                        "os_name": hardware_data.get("os_name", "Unknown"),
                        "os_version": hardware_data.get("os_version"),
                        "motherboard": hardware_data.get("motherboard"),
                        "ram": hardware_data.get("ram"),
                        "processors": hardware_data.get("processors", []),
                        "ip_addresses": hardware_data.get("ip_addresses", []),
                        "mac_addresses": hardware_data.get("mac_addresses", []),
                        "video_cards": hardware_data.get("video_cards", []),
                        "last_boot": hardware_data.get("last_boot"),
                        "is_virtual": hardware_data.get("is_virtual", False)
                    })
                
                # Сбор информации о дисках
                disk_data = await self._execute_script(session, "disk_info.ps1")
                if disk_data:
                    if isinstance(disk_data, dict):
                        result["disks"]["physical_disks"] = [disk_data.get("physical_disks", {})]
                        result["disks"]["logical_disks"] = [disk_data.get("logical_disks", {})]
                    else:
                        result["disks"] = disk_data
                
                # Сбор информации о ПО
                software_script = "software_info_full.ps1" if mode == "Full" else "software_info_changes.ps1"
                software_data = await self._execute_script(session, software_script, last_updated=last_updated)
                if software_data:
                    result["software"] = software_data 
                
                # Сбор информации о ролях (только для серверов)
                if "server" in result.get("os_name", "").lower():
                    server_data = await self._execute_script(session, "server_info.ps1")
                    if server_data and server_data.get("roles"):
                        result["roles"] = server_data["roles"]

                essential_data_present = any([
                    result["ip_addresses"],
                    result["mac_addresses"],
                    result["processors"],
                    result.get("disks", {}).get("physical_disks"),
                ])

                if essential_data_present:
                    result["check_status"] = "success"
                    logger.info("Сбор данных успешно завершен")
                else:
                    result["check_status"] = "unreachable"
                    logger.warning("Не удалось собрать ключевые данные", status="unreachable")

        except ConnectionError as e:
            logger.error("Не удалось подключиться", error=str(e))
            result["check_status"] = "unreachable"
            result["error"] = str(e)
        
        except Exception as e:
            logger.error("Критическая ошибка при сборе данных", error=str(e))
            result["check_status"] = "failed"
            result["error"] = str(e)
        
        return result