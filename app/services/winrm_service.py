from winrm import Session
from typing import Optional
from ..settings import settings
from ..repositories.domain_repository import DomainRepository
from ..services.encryption_service import EncryptionService
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

class WinRMService:
    def __init__(self, encryption_service: EncryptionService, db: AsyncSession):
        self.encryption_service = encryption_service
        self.domain_repo = DomainRepository(db)

    async def get_credentials(self, domain_name: str) -> tuple[str, str]:
        """Витягує та дешифрує облікові дані з БД."""
        domain = await self.domain_repo.get_domain_by_name(domain_name)
        if not domain:
            logger.error(f"Домен {domain_name} не знайдено в БД")
            raise ValueError(f"Домен {domain_name} не знайдено")
        try:
            password = self.encryption_service.decrypt(domain.encrypted_password)
            return domain.username, password
        except Exception as e:
            logger.error(f"Помилка дешифрування для домену {domain_name}: {str(e)}")
            raise

    @asynccontextmanager
    async def create_session(self, hostname: str, domain_name: Optional[str] = None) -> AsyncGenerator[Session, None]:
        """Створює та повертає сесію WinRM, інкапсулюючи credentials."""
        domain_name = domain_name or settings.domain
        username, password = await self.get_credentials(domain_name)  # Асинхронний виклик із await
        try:
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