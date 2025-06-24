# database.py
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
import logging
from typing import AsyncGenerator
from contextlib import asynccontextmanager
from .settings import settings

logger = logging.getLogger(__name__)

Base = declarative_base()
engine = None
async_session = None
_is_shutting_down = False  # Флаг для предотвращения повторного shutdown

async def init_db():
    global engine, async_session
    if engine is not None and async_session is not None:
        logger.debug("База данных уже инициализирована")
        return

    SQLALCHEMY_DATABASE_URL = settings.database_url
    if not SQLALCHEMY_DATABASE_URL:
        logger.error("DATABASE_URL не найден в настройках")
        raise ValueError("DATABASE_URL не найден в настройках")
    try:
        engine = create_async_engine(
            SQLALCHEMY_DATABASE_URL,
            pool_size=20,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=300,
        )
        async_session = async_sessionmaker(
            engine,
            class_=AsyncSession,
            autoflush=True,
            autocommit=False,
            expire_on_commit=False
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info(f"Database connection established with async connection pool:")
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}", exc_info=True)
        engine = None
        async_session = None
        raise

async def shutdown_db():
    global engine, async_session, _is_shutting_down
    if _is_shutting_down:
        logger.debug("Повторный вызов shutdown_db, пропуск")
        return
    if engine is not None:
        try:
            _is_shutting_down = True
            await engine.dispose()
            logger.info("Соединение с базой данных закрыто")
        except Exception as e:
            logger.error(f"Ошибка при закрытии пула соединений: {str(e)}", exc_info=True)
        finally:
            engine = None
            async_session = None
            _is_shutting_down = False
    else:
        logger.warning("Engine не инициализирован, пропуск dispose")

@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Предоставляет асинхронную сессию базы данных."""
    global async_session
    if async_session is None:
        await init_db()
    session = async_session()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Ошибка в сессии базы данных: {str(e)}")
        raise
    finally:
        await session.close()
        logger.debug("Сессия базы данных закрыта")