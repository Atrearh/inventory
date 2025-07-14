import asyncio
import httpx
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select
from app.models import User  # Импортируйте вашу модель User

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_user(email: str, password: str, username: str, is_superuser: bool = True, api_url: str = "http://192.168.0.143:8000"):
    """
    Создаёт пользователя через endpoint /auth/register.

    Args:
        email: Email пользователя.
        password: Пароль пользователя.
        username: Имя пользователя.
        is_superuser: Флаг суперпользователя (по умолчанию True).
        api_url: URL сервера FastAPI (по умолчанию http://192.168.0.143:8000).
    """
    url = f"{api_url}/auth/register"
    user_data = {
        "email": email,
        "password": password,
        "username": username,
        "is_superuser": is_superuser,
        "is_active": True,
        "is_verified": True
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=user_data)
            response.raise_for_status()
            logger.info(f"Пользователь успешно создан: {response.json()}")
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Ошибка при создании пользователя: {e.response.status_code} {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Ошибка сети: {str(e)}")
            raise

async def login_user(email: str, password: str, api_url: str = "http://192.168.0.143:8000"):
    """
    Выполняет вход пользователя через /auth/jwt/login и возвращает JWT-токен.

    Args:
        email: Email пользователя.
        password: Пароль пользователя.
        api_url: URL сервера FastAPI.
    """
    url = f"{api_url}/auth/jwt/login"
    form_data = {
        "username": email,
        "password": password
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, data=form_data, headers={"Content-Type": "application/x-www-form-urlencoded"})
            response.raise_for_status()
            token_data = response.json()
            logger.info(f"Успешный вход, JWT-токен: {token_data['access_token']}")
            return token_data["access_token"]
        except httpx.HTTPStatusError as e:
            logger.error(f"Ошибка при входе: {e.response.status_code} {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Ошибка сети: {str(e)}")
            raise

async def check_user_hash(email: str, database_url: str = "mysql+aiomysql://user:password@localhost/inventory"):
    """
    Проверяет хэш пароля пользователя в базе данных.

    Args:
        email: Email пользователя для проверки.
        database_url: URL базы данных.
    """
    engine = create_async_engine(database_url, echo=False)
    async with AsyncSession(engine) as session:
        try:
            result = await session.execute(select(User).filter_by(email=email))
            user = result.scalars().first()
            if user:
                logger.info(f"Хэш пароля для {user.email}: {user.hashed_password}")
                logger.info(f"Флаг суперпользователя: {user.is_superuser}")
                return user.hashed_password, user.is_superuser
            else:
                logger.warning(f"Пользователь с email {email} не найден")
                return None, None
        except Exception as e:
            logger.error(f"Ошибка при проверке хэша: {str(e)}")
            raise
        finally:
            await engine.dispose()

async def main():
    email = "admin@example.com"
    password = "admin123"
    username = "admin"
    try:
        # Создаём суперпользователя
        await create_user(email=email, password=password, username=username, is_superuser=True)
        # Проверяем хэш пароля и флаг суперпользователя
        hashed_password, is_superuser = await check_user_hash(email=email)
        if hashed_password and hashed_password.startswith("$argon2id$"):
            logger.info("Хэш пароля использует argon2")
        else:
            logger.error(f"Хэш пароля не в формате argon2: {hashed_password}")
        if is_superuser:
            logger.info("Пользователь является суперпользователем")
        else:
            logger.error("Пользователь не является суперпользователем")
        # Выполняем вход и получаем JWT-токен
        token = await login_user(email=email, password=password)
        logger.info(f"JWT-токен для использования: Bearer {token}")
    except Exception as e:
        logger.error(f"Не удалось создать пользователя или войти: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())