# app/data_collector.py
import logging
import json
import winrm
from winrm.exceptions import WinRMTransportError, WinRMError
from typing import Optional, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from . import settings
from pathlib import Path
from datetime import datetime
import asyncio
from .repositories.computer_repository import ComputerRepository
from collections import defaultdict

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "app/scripts"

_script_cache = {}
_session_pool = defaultdict(dict)  # Пул сессий: {hostname: {username: session}}

def decode_output(output: bytes) -> str:
    """Декодирует вывод PowerShell, пробуя UTF-8 и fallback-кодировку."""
    if not output:
        return ""
    try:
        return output.decode('utf-8')
    except UnicodeDecodeError as e:
        logger.debug(
            f"Ошибка декодирования UTF-8: {str(e)}, пробуем {settings.powershell_encoding}")
        try:
            return output.decode(settings.powershell_encoding, errors='replace')
        except UnicodeDecodeError as e2:
            logger.error(
                f"Ошибка декодирования {settings.powershell_encoding}: {str(e2)}, возвращаем замену символов")
            return output.decode('utf-8', errors='replace')

def load_ps_script(file_name: str) -> str:
    """Загружает PowerShell-скрипт из файла и кэширует его."""
    if file_name not in _script_cache:
        file_path = SCRIPTS_DIR / file_name
        try:
            if not file_path.exists():
                logger.error(
                    f"Файл скрипта {file_path} не найден", exc_info=True)
                raise FileNotFoundError(f"Файл {file_path} не найден")
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            cleaned_lines = []
            in_block_comment = False
            for line in lines:
                line = line.rstrip()
                if not line or line.strip().startswith('#'):
                    continue
                if '<#' in line:
                    in_block_comment = True
                    continue
                if in_block_comment:
                    if '#>' in line:
                        in_block_comment = False
                    continue
                if '#' in line and not line.strip().startswith('#'):
                    line = line[:line.index('#')].rstrip()
                if line:
                    cleaned_lines.append(line)
            script = '\n'.join(cleaned_lines)
            _script_cache[file_name] = script
            logger.debug(
                f"Загружен и закэширован PowerShell-скрипт из {file_path}, длина: {len(script)} символов")
        except FileNotFoundError as e:
            logger.error(
                f"Ошибка загрузки скрипта {file_path}: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(
                f"Неизвестная ошибка загрузки скрипта {file_path}: {str(e)}", exc_info=True)
            raise
    return _script_cache[file_name]

async def get_session(hostname: str, username: str, password: str, retries: int = 3) -> Optional[winrm.Session]:
    """Асинхронно возвращает WinRM-сессию, используя WinRMDataCollector."""
    collector = WinRMDataCollector.get_instance(hostname, username, password)
    return await collector._create_winrm_session()

async def get_hosts_for_polling_from_db(db: AsyncSession) -> tuple[List[str], str]:
    """Получает список хостов из базы данных или TEST_HOSTS для опроса."""
    if settings.test_hosts:
        try:
            hosts = [host.strip() for host in settings.test_hosts.split(",")]
            simple_username = settings.ad_username.split('\\')[-1]
            logger.info(f"Используются тестовые хосты: {hosts}")
            return hosts, simple_username
        except Exception as e:
            logger.error(
                f"Ошибка парсинга TEST_HOSTS: {str(e)}", exc_info=True)
            raise ValueError("Неверный формат TEST_HOSTS")

    try:
        repo = ComputerRepository(db)
        hosts = await repo.async_get_hosts_for_polling(db, days_threshold=settings.polling_days_threshold)
        simple_username = settings.ad_username.split('\\')[-1]
        logger.info(f"Найдено {len(hosts)} хостов для опроса из базы данных")
        return hosts, simple_username
    except Exception as e:
        logger.error(
            f"Ошибка базы данных при получения хостов: {str(e)}", exc_info=True)
        raise

async def get_pc_info(hostname: str, user: str, password: str, retries: int = 3, last_updated: Optional[datetime] = None) -> Optional[Dict]:
    """Получает информацию о ПК, переиспользуя WinRMDataCollector."""
    collector = WinRMDataCollector.get_instance(hostname, user, password)
    try:
        return await collector.get_all_pc_info()
    except ConnectionError:
        return {
            "hostname": hostname,
            "check_status": "unreachable",
            "error": f"Не удалось установить WinRM-сессию для {hostname}"
        }

class WinRMDataCollector:
    _instances = {}  # Пул экземпляров: {hostname: WinRMDataCollector}

    @classmethod
    def get_instance(cls, hostname: str, username: str, password: str) -> 'WinRMDataCollector':
        """Возвращает существующий экземпляр или создаёт новый."""
        if hostname not in cls._instances:
            cls._instances[hostname] = cls(hostname, username, password)
            logger.debug(f"Создан новый экземпляр WinRMDataCollector для {hostname}")
        else:
            logger.debug(f"Переиспользуется экземпляр WinRMDataCollector для {hostname}")
        return cls._instances[hostname]

    def __init__(self, hostname: str, username: str, password: str):
        """Инициализирует коллектор данных с параметрами подключения."""
        self.hostname = hostname
        self.username = username
        self.password = password
        self.session = None

    async def _create_winrm_session(self) -> Optional[winrm.Session]:
        """Создаёт WinRM-сессию с повторными попытками."""
        # Проверяем, есть ли активная сессия в пуле
        if self.hostname in _session_pool and self.username in _session_pool[self.hostname]:
            logger.debug(f"Переиспользуется существующая WinRM-сессия для {self.hostname} (username: {self.username})")
            return _session_pool[self.hostname][self.username]

        def sync_create_session():
            return winrm.Session(
                f"http://{self.hostname}:{settings.winrm_port}/wsman",
                auth=(self.username, self.password),
                transport="ntlm",
                server_cert_validation=settings.winrm_server_cert_validation,
                operation_timeout_sec=settings.winrm_operation_timeout,
                read_timeout_sec=settings.winrm_read_timeout
            )

        for attempt in range(1, settings.winrm_retries + 1):
            try:
                session = await asyncio.to_thread(sync_create_session)
                logger.debug(
                    f"WinRM-сессия успешно создана для {self.hostname} (username: {self.username}) на попытке {attempt}")
                _session_pool[self.hostname][self.username] = session  # Сохраняем сессию в пул
                return session
            except WinRMTransportError as e:
                logger.warning(
                    f"Попытка {attempt} для {self.hostname} не удалась: транспортная ошибка ({str(e)})")
                if attempt < settings.winrm_retries:
                    await asyncio.sleep(settings.winrm_retry_delay)
                continue
            except WinRMError as e:
                logger.warning(
                    f"Попытка {attempt} для {self.hostname} не удалась: ошибка WinRM ({str(e)})")
                if attempt < settings.winrm_retries:
                    await asyncio.sleep(settings.winrm_retry_delay)
                continue
            except Exception as e:
                logger.warning(
                    f"Попытка {attempt} для {self.hostname} не удалась: {str(e)}")
                if attempt < settings.winrm_retries:
                    await asyncio.sleep(settings.winrm_retry_delay)
                continue
        logger.error(
            f"Не удалось создать WinRM-сессию для {self.hostname} после {settings.winrm_retries} попыток")
        return None

    async def connect(self):
        """Подключается к хосту, используя пул сессий."""
        self.session = await self._create_winrm_session()
        if not self.session:
            raise ConnectionError(f"Failed to create WinRM session for {self.hostname}")

    async def _run_script(self, script_name: str) -> dict:
        """Выполняет PowerShell-скрипт на удалённом хосте."""
        if not self.session:
            await self.connect()
        script_content = load_ps_script(script_name)
        logger.debug(
            f"Выполняется {script_name} для {self.hostname}, длина скрипта: {len(script_content)}")
        try:
            result = await asyncio.to_thread(lambda: self.session.run_ps(script_content))
            if result.status_code != 0:
                error_message = decode_output(result.std_err)
                logger.error(
                    f"Ошибка выполнения {script_name} для {self.hostname}: {error_message}, статус: {result.status_code}")
                raise RuntimeError(
                    f"Ошибка выполнения {script_name}: {error_message}")
            output = decode_output(result.std_out)
            logger.debug(
                f"Вывод {script_name} для {self.hostname}: {output[:500]}...")
            return json.loads(output)
        except json.JSONDecodeError as e:
            logger.error(
                f"Ошибка парсинга JSON из {script_name} для {self.hostname}: {str(e)}, вывод: {output[:500]}...")
            raise
        except Exception as e:
            logger.error(
                f"Ошибка выполнения {script_name} для {self.hostname}: {str(e)}", exc_info=True)
            raise

    async def get_system_info(self) -> dict:
        """Получает системную информацию с помощью PowerShell-скрипта."""
        return await self._run_script("system_info.ps1")

    async def get_software_info(self) -> list:
        """Получает информацию о программном обеспечении с помощью PowerShell-скрипта."""
        data = await self._run_script("software_info.ps1")
        if not isinstance(data, list):
            logger.warning(
                f"software_info.ps1 для {self.hostname} вернул не массив: {data}")
            return []
        return data

    async def get_all_pc_info(self) -> dict:
        """Собирает полную информацию о ПК."""
        try:
            system_data = await self.get_system_info()
            system_data["software"] = await self.get_software_info()
            system_data["hostname"] = self.hostname
            system_data["check_status"] = "success"
            logger.info(f"Успешно собраны данные для {self.hostname}")
            return system_data
        except Exception as e:
            logger.error(
                f"Ошибка сбора данных для {self.hostname}: {str(e)}", exc_info=True)
            return {
                "hostname": self.hostname,
                "check_status": "failed",
                "error": str(e)
            }
        finally:
            self.cleanup()

    def cleanup(self):
        """Очищает сессию, но сохраняет её в пуле для повторного использования."""
        if self.session:
            try:
                if hasattr(self.session.protocol, 'transport'):
                    self.session.protocol.transport.close()
                logger.debug(f"WinRM-сессия для {self.hostname} закрыта")
            except Exception as e:
                logger.warning(
                    f"Ошибка при закрытии WinRM-сессии для {self.hostname}: {str(e)}")
            finally:
                self.session = None
                # Сессия остаётся в _session_pool для повторного использования

    @classmethod
    def clear_pool(cls):
        """Очищает пул экземпляров и сессий."""
        for hostname, instance in cls._instances.items():
            instance.cleanup()
        cls._instances.clear()
        _session_pool.clear()
        logger.debug("Пул WinRMDataCollector и сессий очищен")