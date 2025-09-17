import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Domain

logger = logging.getLogger(__name__)


class DomainRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_domain_by_name(self, name: str) -> Optional[Domain]:
        """Отримує домен за назвою, ігноруючи регістр."""
        try:
            logger.debug(f"Виконую запит для пошуку домену: {name}")
            result = await self.db.execute(select(Domain).filter(Domain.name == name.lower().strip()))
            domain = result.scalar_one_or_none()
            logger.debug(f"Пошук домену {name}: {'знайдено' if domain else 'не знайдено'}")
            return domain
        except Exception as e:
            logger.error(f"Помилка пошуку домену {name}: {str(e)}", exc_info=True)
            raise

    async def create_or_update_domain(
        self,
        name: str,
        username: str,
        encrypted_password: str,
        server_url: Optional[str] = None,
        ad_base_dn: Optional[str] = None,
    ) -> Domain:
        """Створює або оновлює домен."""
        name = name.lower().strip()
        logger.info(f"Починаю створення/оновлення домену: {name}")

        try:
            # Перевіряємо, чи існує домен
            domain = await self.get_domain_by_name(name)

            if domain:
                logger.info(f"Оновлюю існуючий домен: {name}")
                domain.username = username
                domain.encrypted_password = encrypted_password
                domain.server_url = server_url
                domain.ad_base_dn = ad_base_dn
            else:
                logger.info(f"Створюю новий домен: {name}")
                domain = Domain(
                    name=name,
                    username=username,
                    encrypted_password=encrypted_password,
                    server_url=server_url,
                    ad_base_dn=ad_base_dn,
                )
                logger.debug(f"Об'єкт домену створено: {domain}")

                self.db.add(domain)
                logger.debug(f"Домен додано до сесії: {name}")

            await self.db.flush()
            logger.debug(f"Flush виконано для домену: {name}, id={domain.id}")
            logger.info(f"✅ Домен успішно збережено у сесії: id={domain.id}, name={domain.name}")

            return domain

        except IntegrityError as e:
            logger.error(
                f"❌ Помилка цілісності при збереженні домену {name}: {str(e)}",
                exc_info=True,
            )
            await self.db.rollback()
            if "Duplicate entry" in str(e) or "UNIQUE constraint failed" in str(e):
                raise ValueError(f"Домен з ім'ям {name} вже існує")
            else:
                raise ValueError(f"Помилка цілісності даних: {str(e)}")

        except OperationalError as e:
            logger.error(
                f"❌ Операційна помилка бази даних при збереженні домену {name}: {str(e)}",
                exc_info=True,
            )
            await self.db.rollback()
            raise ValueError(f"Помилка бази даних: {str(e)}")

        except Exception as e:
            logger.error(
                f"❌ Загальна помилка при збереженні домену {name}: {str(e)}",
                exc_info=True,
            )
            await self.db.rollback()
            raise ValueError(f"Неочікувана помилка: {str(e)}")

        except OperationalError as e:
            logger.error(
                f"❌ Операційна помилка бази даних при збереженні домену {name}: {str(e)}",
                exc_info=True,
            )
            await self.db.rollback()
            raise ValueError(f"Помилка бази даних: {str(e)}")

        except Exception as e:
            logger.error(
                f"❌ Загальна помилка при збереженні домену {name}: {str(e)}",
                exc_info=True,
            )
            await self.db.rollback()
            raise ValueError(f"Неочікувана помилка: {str(e)}")

    async def delete_domain(self, name: str) -> None:
        """Видаляє домен за назвою."""
        logger.info(f"Початок видалення домену: {name}")

        try:
            domain = await self.get_domain_by_name(name)
            if not domain:
                logger.warning(f"Домен {name} не знайдено для видалення")
                raise ValueError(f"Домен {name} не знайдено")

            await self.db.delete(domain)
            await self.db.flush()
            logger.info(f"✅ Домен {name} видалено з сесії")

        except Exception as e:
            logger.error(f"❌ Помилка видалення домену {name}: {str(e)}", exc_info=True)
            await self.db.rollback()
            raise

    async def get_all_domains(self) -> List[Domain]:
        """Отримує всі домени з бази даних."""
        try:
            result = await self.db.execute(select(Domain))
            domains = result.scalars().all()
            logger.debug(f"Отримано {len(domains)} доменів з бази даних")
            return domains
        except Exception as e:
            logger.error(f"Помилка отримання всіх доменів: {str(e)}")
            raise
