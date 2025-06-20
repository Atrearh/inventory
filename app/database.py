# app/database.py
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
import logging
from typing import AsyncGenerator
from contextlib import  asynccontextmanager

logger = logging.getLogger(__name__)

Base = declarative_base()
engine = None
async_session = None

def get_settings():
    from .settings import settings
    if settings is None:
        logger.error("Settings не инициализированы")
        raise ValueError("Settings не инициализированы")
    return settings

async def init_db():
    global engine, async_session
    if engine is not None and async_session is not None:
        logger.debug("База данных уже инициализирована")
        return

    settings = get_settings()
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
        logger.info("Database connection established with async connection pool")
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}")
        raise
@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if async_session is None:
        await init_db()
    async with async_session() as session:
        yield session