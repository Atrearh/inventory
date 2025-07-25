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
import logging

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "app" / "scripts"

class ScriptCache:
    def __init__(self):
        self._cache: Dict[str, str] = {}

    def _load_script(self, file_name: str) -> str:
        """Завантажує скрипт з диска."""
        file_path = SCRIPTS_DIR / file_name
        logger.debug(f"Завантаження скрипта {file_name}", extra={"file_name": file_name})
        if not file_path.exists():
            logger.error(f"Скрипт {file_path} не знайдено", extra={"file_name": file_name})
            raise FileNotFoundError(f"Скрипт {file_path} не знайдено")

        with open(file_path, 'r', encoding='utf-8-sig') as f:
            script = f.read().rstrip()

        if len(script) > 3000:
            logger.warning(f"Скрипт {file_name} великий, розмір: {len(script)}", extra={"file_name": file_name})
        return script

    def get(self, file_name: str) -> str:
        """Отримує вміст скрипта з кешу або диска."""
        if file_name not in self._cache:
            self._cache[file_name] = self._load_script(file_name)
        return self._cache[file_name]

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
                logger.debug(f"Скрипт {script_name} завантажено в кеш", extra={"script_name": script_name})
            except Exception as e:
                logger.error(f"Помилка завантаження {script_name}: {str(e)}", extra={"script_name": script_name})
        logger.info(f"Завантажено {script_count} скриптів у кеш")

    def clear(self):
        """Очищає кеш скриптів."""
        self._cache.clear()
        logger.info("Кеш скриптів очищено")

script_cache = ScriptCache()

def decode_output(output: bytes) -> str:
    """Декодує байтовий вивід PowerShell, використовуючи спочатку UTF-8, а потім запасну кодування з налаштувань."""
    if not output:
        return ""
    try:
        return output.decode('utf-8')
    except UnicodeDecodeError:
        logger.debug(f"Не вдалося декодувати як UTF-8, використовується запасна кодування: {settings.powershell_encoding}")
        return output.decode(settings.powershell_encoding, errors='replace')

@contextmanager
def winrm_session(hostname: str, username: str, password: str):
    """Контекстний менеджер для створення та управління WinRM-сесією."""
    session = None
    try:
        logger.debug(f"Створення WinRM-сесії для {hostname} на порту {settings.winrm_port}", extra={"hostname": hostname})
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
        logger.error(f"Помилка підключення WinRM до {hostname}: {str(e)}", extra={"hostname": hostname})
        raise ConnectionError(f"Не вдалося підключитися до {hostname}: {e}")
    except Exception as e:
        logger.error(f"Непередбачена помилка при створенні WinRM-сесії для {hostname}: {str(e)}", extra={"hostname": hostname})
        raise
    finally:
        if session:
            logger.debug(f"Закриття WinRM-сесії для {hostname}", extra={"hostname": hostname})

class WinRMDataCollector:
    """Збирає інформацію з віддалених хостів Windows за допомогою WinRM."""
    def __init__(self, hostname: str, username: str, password: str):
        self.hostname = hostname
        self.username = username
        self.password = password

    async def _execute_script(self, session: winrm.Session, script_name: str, last_updated: Optional[datetime] = None) -> Any:
        """Асинхронно виконує PowerShell-скрипт на віддаленому хості."""
        try:
            script_content = script_cache.get(script_name)
        except FileNotFoundError as e:
            logger.error(f"Помилка виконання скрипта: {str(e)}", extra={"hostname": self.hostname, "script_name": script_name})
            raise

        command = script_content
        if script_name == "software_info_changes.ps1" and last_updated:
            command = f"& {{ {script_content} }} -LastUpdated '{last_updated.isoformat()}'"

        logger.debug(f"Виконання скрипта {script_name} на {self.hostname}", extra={"hostname": self.hostname, "script_name": script_name})
        if len(command) > 3000:
            logger.warning(f"Команда для {script_name} на {self.hostname} перевищує 3000 символів", extra={"hostname": self.hostname, "script_name": script_name})

        try:
            result = await asyncio.to_thread(session.run_ps, command)

            if result.status_code != 0:
                error_message = decode_output(result.std_err)
                logger.error(f"Скрипт {script_name} на {self.hostname} завершився з помилкою, код: {result.status_code}, помилка: {error_message}", extra={"hostname": self.hostname, "script_name": script_name})
                return {"error": f"Помилка виконання скрипта '{script_name}': {error_message}", "check_status": "failed"}

            output = decode_output(result.std_out)
            logger.debug(f"Сирий вивід скрипта {script_name}: {output[:1000]}", extra={"hostname": self.hostname, "script_name": script_name})

            if not output.strip():
                if script_name == "software_info_changes.ps1":
                    logger.debug(f"Скрипт {script_name} на {self.hostname} повернув порожній результат", extra={"hostname": self.hostname, "script_name": script_name})
                    return {}
                else:
                    logger.warning(f"Скрипт {script_name} на {self.hostname} повернув порожній результат", extra={"hostname": self.hostname, "script_name": script_name})
                    return {"error": f"Скрипт {script_name} повернув порожній результат", "check_status": "failed"}

            try:
                data = json.loads(output)
                logger.debug(f"JSON із {script_name} успішно розпарсено", extra={"hostname": self.hostname, "script_name": script_name})
                return data
            except json.JSONDecodeError as e:
                logger.error(f"Помилка парсингу JSON із {script_name} на {self.hostname}: {str(e)}, вивід: {output[:500]}", extra={"hostname": self.hostname, "script_name": script_name})
                return {"error": f"Некоректний формат JSON від скрипта {script_name}: {str(e)}", "check_status": "failed"}

        except Exception as e:
            logger.error(f"Непередбачена помилка при виконанні {script_name} на {self.hostname}: {str(e)}", extra={"hostname": self.hostname, "script_name": script_name})
            return {"error": str(e), "check_status": "failed"}

    async def get_all_pc_info(self, mode: str = "Full", last_updated: Optional[datetime] = None) -> Dict[str, Any]:
        """Збирає повну інформацію про ПК, включаючи обладнання, ПЗ і ролі сервера."""
        result: Dict[str, Any] = {"hostname": self.hostname, "check_status": "failed", "errors": []}
        logger.info(f"Початок збору даних для {self.hostname}", extra={"hostname": self.hostname})

        try:
            with winrm_session(self.hostname, self.username, self.password) as session:
                logger.info("Початок збору даних", extra={"hostname": self.hostname})

                # Ініціалізація структури даних
                result.update({
                    "ip_addresses": [], "mac_addresses": [], "processors": [],
                    "video_cards": [], "disks": {"physical_disks": [], "logical_disks": []},
                    "software": [], "roles": [], "os_name": "Unknown", "os_version": None,
                    "ram": None, "motherboard": None, "last_boot": None, "is_virtual": False
                })

                successful_components = 0
                failed_components = 0

                # Збір базової інформації про обладнання
                hardware_data = await self._execute_script(session, "system_info.ps1")
                if isinstance(hardware_data, dict) and "error" not in hardware_data:
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
                        "is_virtual": hardware_data.get("is_virtual", False),
                        "roles": hardware_data.get("roles", [])  # Додаємо ролі з першого виклику
                    })
                    successful_components += 1
                    logger.debug("Дані system_info.ps1 зібрано успішно", extra={"hostname": self.hostname})
                else:
                    failed_components += 1
                    result["errors"].append(hardware_data.get("error", "Невідома помилка system_info.ps1"))

                # Збір інформації про диски
                disk_data = await self._execute_script(session, "disk_info.ps1")
                if isinstance(disk_data, dict) and "error" not in disk_data:
                    result["disks"]["physical_disks"] = disk_data.get("physical_disks", [])
                    result["disks"]["logical_disks"] = disk_data.get("logical_disks", [])
                    successful_components += 1
                    logger.debug("Дані disk_info.ps1 зібрано успішно", extra={"hostname": self.hostname})
                else:
                    failed_components += 1
                    result["errors"].append(disk_data.get("error", "Невідома помилка disk_info.ps1"))
                    logger.error(f"Помилка збору даних disk_info.ps1: {disk_data.get('error', 'Невідома помилка')}", extra={"hostname": self.hostname})

                # Збір інформації про ПЗ
                software_script = "software_info_full.ps1" if mode == "Full" else "software_info_changes.ps1"
                software_data = await self._execute_script(session, software_script, last_updated=last_updated)
                if isinstance(software_data, list):
                    result["software"] = software_data
                    successful_components += 1
                    logger.debug("Дані ПЗ зібрано успішно", extra={"hostname": self.hostname})
                elif isinstance(software_data, dict) and "error" not in software_data:
                    result["software"] = software_data.get("software", [])
                    successful_components += 1
                    logger.debug("Дані ПЗ зібрано успішно", extra={"hostname": self.hostname})
                else:
                    failed_components += 1
                    result["errors"].append(software_data.get("error", f"Невідома помилка {software_script}"))
                    logger.error(f"Помилка збору даних {software_script}: {software_data.get('error', 'Невідома помилка')}", extra={"hostname": self.hostname})

                # Визначення статусу
                essential_data_present = any([
                    result["ip_addresses"],
                    result["mac_addresses"],
                    result["processors"],
                    result["disks"]["physical_disks"],
                    result["disks"]["logical_disks"],
                    result["software"],
                    result["roles"]
                ])

                if successful_components > 0 and failed_components > 0:
                    result["check_status"] = "partially_successful"
                    logger.info(f"Частково успішний збір даних: {successful_components} успішних, {failed_components} невдалих компонентів", extra={"hostname": self.hostname})
                elif successful_components > 0 and essential_data_present:
                    result["check_status"] = "success"
                    logger.info("Збір даних успішно завершено", extra={"hostname": self.hostname})
                else:
                    result["check_status"] = "unreachable"
                    logger.warning("Не вдалося зібрати ключові дані, статус: unreachable", extra={"hostname": self.hostname})

        except ConnectionError as e:
            logger.error(f"Не вдалося підключитися: {str(e)}", extra={"hostname": self.hostname})
            result["check_status"] = "unreachable"
            result["errors"].append(str(e))

        except Exception as e:
            logger.error(f"Критична помилка при зборі даних: {str(e)}", extra={"hostname": self.hostname})
            result["check_status"] = "failed"
            result["errors"].append(str(e))

        return result