import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from .config import settings

logger = logging.getLogger(__name__)

# Ініціалізація engine при завантаженні модуля
SQLALCHEMY_DATABASE_URL = settings.database_url
if not SQLALCHEMY_DATABASE_URL:
    logger.error("DATABASE_URL не найден в настройках")
    raise ValueError("DATABASE_URL не найден в настройках")


# Створюємо асинхронний engine
engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_timeout=10,
    pool_recycle=3600,
    # echo=True  # Для дебагу SQL запитів
)

# Створюємо фабрику сесій з SQLModel AsyncSession
async_session_factory = sessionmaker(
    engine,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            logger.error(
                f"Помилка в сесії {id(session)}, відкат: {str(e)}", exc_info=True
            )
            await session.rollback()
            raise
        finally:
            await session.close()


def get_db_session() -> AsyncSession:
    return async_session_factory()


async def init_db():
    try:
        async with engine.begin() as conn:
            logger.debug("Створення таблиць бази даних")
            # SQLModel.metadata містить всі зареєстровані моделі
            await conn.run_sync(SQLModel.metadata.create_all)
        logger.info("База даних успішно ініціалізована")
    except Exception as e:
        logger.error(f"Помилка ініціалізації бази даних: {str(e)}", exc_info=True)
        raise


async def shutdown_db():
    try:
        logger.debug("Закриття пулу з'єднань бази даних")
        await engine.dispose()
        logger.info("З'єднання з базою даних закрито")
    except Exception as e:
        logger.error(f"Помилка при закритті пулу з'єднань: {str(e)}", exc_info=True)
        raise
