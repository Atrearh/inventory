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
import os
 
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "app" / "scripts"

class ScriptCache:
    """Управление кэшем PowerShell-скриптов для минимизации операций чтения с диска."""
    def __init__(self):
        self._cache: Dict[str, str] = {}

    def get(self, file_name: str) -> str:
        """
        Получает содержимое скрипта из кэша или загружает с диска.
        
        Args:
            file_name: Имя файла скрипта (например, 'hardware_info.ps1').
        
        Returns:
            Содержимое скрипта в виде строки.
            
        Raises:
            FileNotFoundError: Если файл скрипта не найден.
        """
        if file_name not in self._cache:
            file_path = SCRIPTS_DIR / file_name
            try:
                if not file_path.exists():
                    logger.error(f"Файл скрипта {file_path} не найден.")
                    raise FileNotFoundError(f"Файл {file_path} не найден")
                
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    script = f.read().rstrip()
                
                self._cache[file_name] = script
                logger.debug(f"Скрипт {file_name} загружен и кэширован. Длина: {len(script)} символов.")
                
                if len(script) > 2000:
                    logger.warning(f"Скрипт {file_name} имеет большую длину: {len(script)} символов.")

            except Exception as e:
                logger.error(f"Ошибка при загрузке скрипта {file_path}: {e}", exc_info=True)
                raise
        return self._cache[file_name]

    def preload_scripts(self):
        """
        Предварительно загружает все .ps1 скрипты из папки SCRIPTS_DIR в кэш.
        """
        try:
            scripts_dir = SCRIPTS_DIR
            logger.debug(f"Предварительная загрузка скриптов из папки: {os.path.abspath(scripts_dir)}")
            if not os.path.exists(scripts_dir):
                logger.warning(f"Папка скриптов {scripts_dir} не существует")
                return
            
            scripts = [f for f in os.listdir(scripts_dir) if f.endswith(".ps1")]
            for script_name in scripts:
                try:
                    self.get(script_name)
                    logger.info(f"Скрипт {script_name} предварительно загружен в кэш.")
                except Exception as e:
                    logger.error(f"Ошибка при предварительной загрузке скрипта {script_name}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Ошибка при предварительной загрузке скриптов: {str(e)}", exc_info=True)

    def clear(self):
        """Очищает кэш скриптов."""
        self._cache.clear()
        logger.info("Кэш скриптов очищен.")

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
        logger.debug(f"Создание WinRM-сессии для {hostname} на порту {settings.winrm_port}...")
        session = winrm.Session(
            f"http://{hostname}:{settings.winrm_port}/wsman",
            auth=(username, password),
            transport="ntlm",
            server_cert_validation=settings.winrm_server_cert_validation,
            operation_timeout_sec=settings.winrm_operation_timeout,
            read_timeout_sec=settings.winrm_read_timeout
        )
        logger.debug(f"WinRM-сессия для {hostname} успешно создана.")
        yield session
    except (WinRMError, requests.exceptions.RequestException) as e:
        logger.error(f"Ошибка подключения WinRM к {hostname}: {e}", exc_info=True)
        raise ConnectionError(f"Не удалось подключиться к {hostname}: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при создании WinRM-сессии для {hostname}: {e}", exc_info=True)
        raise
    finally:
        if session:
            logger.debug(f"Закрытие WinRM-сессии для {hostname}.")


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

        logger.debug(f"Выполнение скрипта {script_name} на {self.hostname}.")
        if len(command) > 3000:
                logger.warning(f"Команда для {script_name} на {self.hostname} превышает 3000 символов.")

        try:
            result = await asyncio.to_thread(session.run_ps, command)

            if result.status_code != 0:
                error_message = decode_output(result.std_err)
                logger.error(f"Скрипт {script_name} на {self.hostname} завершился с ошибкой (код {result.status_code}): {error_message}")
                raise RuntimeError(f"Ошибка выполнения скрипта '{script_name}': {error_message}")

            output = decode_output(result.std_out)

            if not output.strip():
                # Для software_info_changes пустой результат ожидаем, если нет изменений.
                log_level = logging.DEBUG if script_name == "software_info_changes.ps1" else logging.WARNING
                logger.log(log_level, f"Скрипт {script_name} на {self.hostname} вернул пустой результат.")
                return [] 

            logger.info(f"Скрипт {script_name} на {self.hostname} выполнен успешно.")
            
            try:
                data = json.loads(output)
                logger.debug(f"JSON из {script_name} успешно распарсен.")
                return data
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON из {script_name} на {self.hostname}. Ошибка: {e}. Вывод: {output[:500]}...")
                raise ValueError(f"Некорректный формат JSON от скрипта {script_name}")

        except Exception as e:
            logger.error(f"Неожиданная ошибка при выполнении {script_name} на {self.hostname}: {e}", exc_info=True)
            raise


    async def get_all_pc_info(self, mode: str = "Full", last_updated: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Собирает полную информацию о ПК, включая оборудование, ПО и роли сервера.
        
        Args:
            mode: 'Full' для полного сбора или 'Update' для сбора только изменений.
            last_updated: Дата последнего обновления, используется в режиме 'Update'.
        
        Returns:
            Словарь с собранной информацией и статусом проверки.
        """
        result: Dict[str, Any] = {"hostname": self.hostname, "check_status": "failed"}
        
        try:
            with winrm_session(self.hostname, self.username, self.password) as session:
                
                # Инициализация структуры данных
                result.update({
                    "ip_addresses": [], "mac_addresses": [], "processors": [],
                    "video_cards": [], "disks": {"physical_disks": [], "logical_disks": []},
                    "software": [], "roles": [], "os_name": "Unknown", "os_version": None,
                    "ram": None, "motherboard": None, "last_boot": None, "is_virtual": False
                })
                
                # --- Шаг 1: Сбор базовой информации об оборудовании ---
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
                
                # --- Шаг 2: Сбор информации о дисках ---
                disk_data = await self._execute_script(session, "disk_info.ps1")
                if disk_data:
                    # Нормализация вывода: оборачиваем словарь в список, если необходимо
                    if isinstance(disk_data, dict):
                         result["disks"]["physical_disks"] = [disk_data.get("physical_disks", {})]
                         result["disks"]["logical_disks"] = [disk_data.get("logical_disks", {})]
                    else:
                        result["disks"] = disk_data
                
                # --- Шаг 3: Сбор информации о ПО ---
                software_script = "software_info_full.ps1" if mode == "Full" else "software_info_changes.ps1"
                software_data = await self._execute_script(session, software_script, last_updated=last_updated)
                if software_data:
                    result["software"] = software_data 
                
                # --- Шаг 4: Сбор информации о ролях (только для серверов) ---
                if "server" in result.get("os_name", "").lower():
                    server_data = await self._execute_script(session, "server_info.ps1")
                    if server_data and server_data.get("roles"):
                        result["roles"] = server_data["roles"]

                essential_data_present = any([
                    result["ip_addresses"],
                    result["mac_addresses"],
                    result["processors"],
                    result.get("disks", {}).get("physical_disks"), # Безопасный доступ
                ])

                if essential_data_present:
                    result["check_status"] = "success"
                    logger.info(f"Сбор данных для {self.hostname} успешно завершен.")
                else:
                    result["check_status"] = "unreachable"
                    logger.warning(f"Для хоста {self.hostname} не удалось собрать ключевые данные. Статус: unreachable.")

        except ConnectionError as e:
            # Ошибка подключения, установленная в winrm_session
            logger.error(f"Не удалось подключиться к {self.hostname}. Статус: unreachable. Ошибка: {e}")
            result["check_status"] = "unreachable"
            result["error"] = str(e)
        
        except Exception as e:
            # Все остальные ошибки (выполнение скрипта, парсинг JSON и т.д.)
            logger.error(f"Критическая ошибка при сборе данных для {self.hostname}: {e}", exc_info=True)
            result["check_status"] = "failed"
            result["error"] = str(e)
        
        return result