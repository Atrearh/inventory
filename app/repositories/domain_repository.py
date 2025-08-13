from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from ..models import Domain
import logging

logger = logging.getLogger(__name__)

class DomainRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_domain_by_name(self, name: str) -> Optional[Domain]:
        """Отримує домен за назвою."""
        result = await self.db.execute(select(Domain).filter(Domain.name == name))
        return result.scalar_one_or_none()

    async def create_or_update_domain(self, name: str, username: str, encrypted_password: str) -> Domain:
        """Створює або оновлює домен."""
        logger.info(f"Починаю створення/оновлення домену: {name}")
        
        domain = await self.get_domain_by_name(name)
        
        if domain:
            logger.info(f"Оновлюю існуючий домен: {name}")
            domain.username = username
            domain.encrypted_password = encrypted_password  # ВИПРАВЛЕНО: використовуємо правильне ім'я поля
        else:
            logger.info(f"Створюю новий домен: {name}")
            domain = Domain(
                name=name, 
                username=username, 
                encrypted_password=encrypted_password  # ВИПРАВЛЕНО: використовуємо правильне ім'я поля
            )
            self.db.add(domain)
        
        # Flush для отримання ID
        await self.db.flush()
        
        logger.info(f"Домен збережено у сесії: id={domain.id}, name={domain.name}")
        return domain