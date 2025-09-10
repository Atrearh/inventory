from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
import logging
from typing import AsyncGenerator
from .config import settings
from .base import Base

logger = logging.getLogger(__name__)

# Инициализация engine и async_session_factory при загрузке модуля
SQLALCHEMY_DATABASE_URL = settings.database_url
if not SQLALCHEMY_DATABASE_URL:
    logger.error("DATABASE_URL не найден в настройках")
    raise ValueError("DATABASE_URL не найден в настройках")

logger.debug(f"Инициализация базы данных с ")
engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_timeout=10,
    pool_recycle=3600,
    #echo=True
)


async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Предоставляет асинхронную сессию базы данных для FastAPI Depends."""
    session = async_session_factory()

    try:
        yield session
        await session.commit()
    except Exception as e:
        logger.error(f"Ошибка в сессии {id(session)}, откат: {str(e)}", exc_info=True)
        await session.rollback()
        raise
    finally:
        await session.close()

def get_db_session() -> AsyncSession:
    """Возвращает сессию базы данных как асинхронный контекстный менеджер для lifespan."""
    return async_session_factory() 

async def init_db():
    """Инициализация базы данных и создание таблиц."""
    try:
        async with engine.begin() as conn:
            logger.debug("Создание таблиц базы данных")
            await conn.run_sync(Base.metadata.create_all)
        logger.info("База данных успешно инициализирована")
    except Exception as e:
        logger.error(f"Ошибка инициализации базы данных: {str(e)}", exc_info=True)
        raise

async def shutdown_db():
    """Закрытие пула соединений базы данных."""
    try:
        logger.debug("Закрытие пула соединений базы данных")
        await engine.dispose()
        logger.info("Соединение с базой данных закрыто")
    except Exception as e:
        logger.error(f"Ошибка при закрытии пула соединений: {str(e)}", exc_info=True)
        raise