import logging
import asyncio
from winrm import Session
from typing import  Dict, Tuple, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from ..config import settings
from ..repositories.domain_repository import DomainRepository
from ..services.encryption_service import EncryptionService

logger = logging.getLogger(__name__)

class WinRMService:
    def __init__(self, encryption_service: EncryptionService, db: AsyncSession):
        self.encryption_service = encryption_service
        self.domain_repo = DomainRepository(db)
        self._credentials_cache: Dict[str, Tuple[str, str]] = {}
        # Ініціалізація кешу відкладена до асинхронного контексту (startup)

    async def initialize(self):
        """Асинхронна ініціалізація кешу облікових даних."""
        await self._load_credentials()

    async def _load_credentials(self):
        """Завантажує та дешифрує облікові дані для всіх доменів."""
        try:
            domains = await self.domain_repo.get_all_domains()
            for domain in domains:
                try:
                    password = self.encryption_service.decrypt(domain.encrypted_password)
                    domain_name = domain.name.lower()
                    self._credentials_cache[domain_name] = (domain.username, password)
                    logger.debug(f"Облікові дані для домену {domain_name} завантажено в кеш")
                except Exception as e:
                    logger.error(f"Помилка дешифрування для домену {domain.name}: {str(e)}", exc_info=True)
                    continue
            logger.info(f"Завантажено {len(self._credentials_cache)} доменів у кеш: {list(self._credentials_cache.keys())}")
        except Exception as e:
            logger.error(f"Помилка завантаження доменів: {str(e)}", exc_info=True)
            raise

    async def get_credentials(self, domain_name: str) -> Tuple[str, str]:
        """Отримує облікові дані з кешу або з бази даних, якщо домен відсутній у кеші."""
        domain_name = domain_name.lower()
        credentials = self._credentials_cache.get(domain_name)
        if credentials is None:
            logger.warning(f"Домен {domain_name} не знайдено в кеші, виконую запит до бази даних")
            try:
                domain = await self.domain_repo.get_domain_by_name(domain_name)
                if not domain:
                    logger.error(f"Домен {domain_name} не знайдено в базі даних")
                    raise ValueError(f"Домен {domain_name} не знайдено")
                password = self.encryption_service.decrypt(domain.encrypted_password)
                credentials = (domain.username, password)
                self._credentials_cache[domain_name] = credentials
                logger.debug(f"Облікові дані для домену {domain_name} додано до кешу")
            except Exception as e:
                logger.error(f"Помилка отримання облікових даних для домену {domain_name}: {str(e)}", exc_info=True)
                raise ValueError(f"Не вдалося отримати облікові дані для домену {domain_name}: {str(e)}")
        else:
            logger.debug(f"Використовуються кешовані облікові дані для домену {domain_name}")
        return credentials

    @asynccontextmanager
    async def create_session(self, hostname: str) -> AsyncGenerator[Session, None]:
        """Контекстний менеджер для створення WinRM-сесії."""
        try:
            domain_name = '.'.join(hostname.split('.')[1:]).lower() if '.' in hostname else None
            if not domain_name:
                logger.error(f"Не вдалося витягнути ім’я домену з {hostname}")
                raise ValueError(f"Не вдалося визначити домен з hostname {hostname}")

            username, password = await self.get_credentials(domain_name)
            session = Session(
                f"http://{hostname}:{settings.winrm_port}/wsman",
                auth=(username, password),
                transport="ntlm",
                server_cert_validation=settings.winrm_server_cert_validation,
                operation_timeout_sec=settings.winrm_operation_timeout,
                read_timeout_sec=settings.winrm_read_timeout
            )
            yield session
        except Exception as e:
            logger.error(f"Помилка створення сесії для {hostname}: {str(e)}")
            raise
        finally:
            logger.debug(f"Сесію для {hostname} закрито")

    async def run_cmd(self, session: Session, command: str, args: list[str] | None = None):
        """Асинхронний виклик команди через WinRM (не блокує event loop)."""
        args = args or []
        return await asyncio.to_thread(session.run_cmd, command, args)