import logging
import json
import winrm
from winrm.exceptions import WinRMError
from typing import Optional, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from . import settings
from pathlib import Path
from datetime import datetime, timedelta
import asyncio
import requests
from .repositories.computer_repository import ComputerRepository

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "app/scripts"

_script_cache = {}

def decode_output(output: bytes) -> str:
    """Декодирует вывод PowerShell, пробуя UTF-8 и fallback-кодировку."""
    if not output:
        return ""
    try:
        return output.decode('utf-8')
    except UnicodeDecodeError as e:
        logger.debug(f"Ошибка декодирования UTF-8: {str(e)}, пробуем {settings.powershell_encoding}")
        try:
            return output.decode(settings.powershell_encoding, errors='replace')
        except UnicodeDecodeError as e2:
            logger.error(f"Ошибка декодирования {settings.powershell_encoding}: {str(e2)}, возвращаем замену символов")
            return output.decode('utf-8', errors='replace')

def load_ps_script(file_name: str) -> str:
    """Загружает PowerShell-скрипт без экранирования специальных символов."""
    if file_name not in _script_cache:
        file_path = SCRIPTS_DIR / file_name
        try:
            if not file_path.exists():
                logger.error(f"Файл скрипта {file_path} не найден")
                raise FileNotFoundError(f"Файл {file_path} не найден")
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                script = f.read().rstrip()
            _script_cache[file_name] = script
            logger.debug(f"Загружен и закэширован PowerShell-скрипт из {file_path}, длина: {len(script)} символов")
            if len(script) > 2000:
                logger.warning(f"Скрипт {file_name} имеет длину {len(script)} символов, возможны проблемы с выполнением")
        except FileNotFoundError as e:
            logger.error(f"Ошибка загрузки скрипта {file_path}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Неизвестная ошибка загрузки скрипта {file_path}: {str(e)}")
            raise
    return _script_cache[file_name]

def clear_script_cache():
    """Очищает кэш загруженных скриптов."""
    _script_cache.clear()
    logger.debug("Кэш PowerShell-скриптов очищён")

async def get_hosts_for_polling_from_db(db: AsyncSession) -> tuple[List[str], str]:
    """Получает список хостов из TEST_HOSTS для опроса."""
    logger.debug(f"Значение settings.test_hosts: '{settings.test_hosts}' (тип: {type(settings.test_hosts)}, длина: {len(settings.test_hosts.strip()) if settings.test_hosts else 0})")
    logger.debug(f"Исходное значение TEST_HOSTS из .env или settings.py: '{settings.test_hosts}'")
    if settings.test_hosts and isinstance(settings.test_hosts, str) and settings.test_hosts.strip():
        try:
            hosts = [host.strip() for host in settings.test_hosts.split(",") if host.strip()]
            if not hosts:
                logger.error("TEST_HOSTS пустой или содержит только пустые строки")
                raise ValueError("TEST_HOSTS не содержит валидных хостов")
            simple_username = settings.ad_username.split('\\')[-1]
            logger.info(f"Используются тестовые хосты: {hosts}")
            return hosts, simple_username
        except Exception as e:
            logger.error(f"Ошибка парсинга TEST_HOSTS: {str(e)}")
            raise ValueError(f"Неверный формат TEST_HOSTS: {str(e)}")

    logger.error("TEST_HOSTS не задан или пуст, сканирование всех хостов из базы данных запрещено")
    raise ValueError("TEST_HOSTS должен быть задан в settings.py или .env")

def handle_winrm_errors(func):
    """Декоратор для обработки типовых ошибок WinRM."""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except WinRMError as e:
            logger.error(f"Ошибка WinRM: {str(e)}")
            raise
        except requests.exceptions.ConnectTimeout as e:
            logger.error(f"Тайм-аут подключения: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Неизвестная ошибка: {str(e)}")
            raise
    return wrapper

class WinRMDataCollector:
    def __init__(self, hostname: str, username: str, password: str):
        """Инициализирует коллектор данных с параметрами подключения."""
        self.hostname = hostname
        self.username = username
        self.password = password

    @handle_winrm_errors
    async def _create_winrm_session(self) -> winrm.Session:
        """Создаёт новую WinRM-сессию."""
        def sync_create_session():
            return winrm.Session(
                f"http://{self.hostname}:{settings.winrm_port}/wsman",
                auth=(self.username, self.password),
                transport="ntlm",
                server_cert_validation=settings.winrm_server_cert_validation,
                operation_timeout_sec=getattr(settings, 'winrm_operation_timeout', 60),
                read_timeout_sec=getattr(settings, 'winrm_read_timeout', 90)
            )

        for attempt in range(1, settings.winrm_retries + 1):
            logger.debug(f"Попытка {attempt} создания WinRM-сессии для {self.hostname}")
            try:
                session = await asyncio.to_thread(sync_create_session)
                logger.debug(f"WinRM-сессия создана для {self.hostname} на попытке {attempt}")
                return session
            except (WinRMError, requests.exceptions.ConnectTimeout) as e:
                logger.warning(f"Попытка {attempt} подключения к {self.hostname} не удалась: {str(e)}")
                if attempt < settings.winrm_retries:
                    await asyncio.sleep(settings.winrm_retry_delay)
                continue
            except Exception as e:
                logger.error(f"Неизвестная ошибка при создании сессии для {self.hostname}: {str(e)}")
                if attempt < settings.winrm_retries:
                    await asyncio.sleep(settings.winrm_retry_delay)
                continue
        logger.error(f"Не удалось создать WinRM-сессию для {self.hostname} после {settings.winrm_retries} попыток")
        raise ConnectionError(f"Не удалось создать сессию для {self.hostname}")

    @handle_winrm_errors
    async def _run_script(self, script_name: str, mode: str = "Full", last_updated: Optional[datetime] = None) -> dict:
        """Выполняет PowerShell-скрипт на удалённом хосте с тайм-аутом."""
        if script_name == "software_info.ps1":
            script_name = "software_info_full.ps1" if mode == "Full" else "software_info_changes.ps1"
        script_content = load_ps_script(script_name)
        session = await self._create_winrm_session()

        logger.debug(f"Выполняется {script_name} для {self.hostname}, длина скрипта: {len(script_content)} символов")
        if len(script_content) > 2000:
            logger.warning(f"Длина скрипта {script_name} для {self.hostname}: {len(script_content)} символов")

        try:
            async def run_ps_with_timeout():
                command = script_content
                if script_name == "software_info_changes.ps1" and last_updated:
                    last_updated_str = last_updated.isoformat()
                    command = f"& {{ {script_content} }} -LastUpdated '{last_updated_str}'"
                logger.debug(f"Длина команды для {script_name}: {len(command)} символов")
                if len(command) > 6000:
                    logger.warning(f"Команда для {script_name} превышает 6000 символов: {len(command)}")
                return await asyncio.to_thread(lambda: session.run_ps(command))

            result = await asyncio.wait_for(
                run_ps_with_timeout(),
                timeout=settings.winrm_operation_timeout + settings.winrm_read_timeout
            )

            if result.status_code != 0:
                error_message = decode_output(result.std_err)
                logger.error(f"Ошибка выполнения {script_name} для {self.hostname}: {error_message}, статус: {result.status_code}")
                raise RuntimeError(f"Ошибка выполнения {script_name}: {error_message}")

            output = decode_output(result.std_out)
            if not output.strip():
                logger.error(f"Пустой вывод от {script_name} для {self.hostname}")
                raise RuntimeError(f"Скрипт {script_name} вернул пустой вывод")
            logger.debug(f"Вывод {script_name} для {self.hostname}: {output[:500]}...")
            logger.info(f"Скрипт {script_name} выполнен успешно для {self.hostname}")
            return json.loads(output)

        except asyncio.TimeoutError:
            logger.error(f"Тайм-аут выполнения скрипта {script_name} для {self.hostname}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON из {script_name} для {self.hostname}: {str(e)}, вывод: {output[:500]}...")
            raise

    async def get_system_info(self) -> dict:
        """Получает системную информацию с помощью PowerShell-скрипта."""
        return await self._run_script("system_info.ps1")

    async def get_software_info(self, mode: str = "Full", last_updated: Optional[datetime] = None) -> list:
        """Получает информацию о программном обеспечении с помощью PowerShell-скрипта."""
        data = await self._run_script("software_info.ps1", mode=mode, last_updated=last_updated)
        if not isinstance(data, list):
            logger.warning(f"software_info.ps1 для {self.hostname} вернул не массив: {data}")
            return []
        return data

    async def get_all_pc_info(self, mode: str = "Full", last_updated: Optional[datetime] = None) -> dict:
        """Собирает полную информацию о ПК, сохраняя частичные данные при ошибках."""
        result = {
            "hostname": self.hostname,
            "check_status": "partial",
            "error": None
        }

        try:
            # Пытаемся получить системную информацию
            system_data = await self.get_system_info()
            result.update(system_data)
            result["check_status"] = "success"
        except Exception as e:
            logger.error(f"Ошибка получения system_info для {self.hostname}: {str(e)}")
            result["error"] = f"System info error: {str(e)}"
            result["check_status"] = "failed"

        try:
            # Пытаемся получить информацию о ПО
            software_data = await self.get_software_info(mode=mode, last_updated=last_updated)
            result["software"] = software_data
            if result["check_status"] != "failed":
                result["check_status"] = "success"
        except Exception as e:
            logger.error(f"Ошибка получения software_info для {self.hostname}: {str(e)}")
            if result["error"]:
                result["error"] += f"; Software info error: {str(e)}"
            else:
                result["error"] = f"Software info error: {str(e)}"
            if result["check_status"] == "success":
                result["check_status"] = "partial"

        if result["check_status"] == "success":
            logger.info(f"Успешно собраны все данные для {self.hostname} в режиме {mode}")
        elif result["check_status"] == "partial":
            logger.warning(f"Собраны частичные данные для {self.hostname} в режиме {mode}: {result['error']}")
        else:
            logger.error(f"Не удалось собрать данные для {self.hostname}: {result['error']}")

        return result

async def get_pc_info(hostname: str, user: str, password: str, retries: int = 3, last_updated: Optional[datetime] = None, last_full_scan: Optional[datetime] = None) -> Optional[Dict]:
    """Получает информацию о ПК, используя WinRMDataCollector."""
    collector = WinRMDataCollector(hostname, user, password)
    try:
        mode = "Full" if last_updated is None or (
            last_full_scan is None or last_full_scan < datetime.utcnow() - timedelta(days=30)
        ) else "Changes"
        return await collector.get_all_pc_info(mode=mode, last_updated=last_updated)
    except ConnectionError as e:
        logger.error(f"Ошибка подключения для {hostname}: {str(e)}")
        return {
            "hostname": hostname,
            "check_status": "unreachable",
            "error": str(e)
        }