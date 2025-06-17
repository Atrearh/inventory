# app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.settings import Settings
import logging

logger = logging.getLogger(__name__)

settings = Settings()
SQLALCHEMY_DATABASE_URL = settings.database_url

if not SQLALCHEMY_DATABASE_URL:
    logger.error("DATABASE_URL not found in settings")
    raise ValueError("DATABASE_URL not found in settings")

logger.info(f"Using DATABASE_URL: {SQLALCHEMY_DATABASE_URL}")

try:
    engine = create_async_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_size=20,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=300,
        #echo=True  # Для отладки SQL-запросов
    )
    logger.info("Database connection established with async connection pool")
except Exception as e:
    logger.error(f"Failed to connect to database: {str(e)}")
    raise

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False
)
Base = declarative_base()

async def get_db():
    async with async_session() as session:
        yield session