# app/routers/auth.py
import logging
from typing import Callable

from argon2 import PasswordHasher
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users import BaseUserManager, FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, CookieTransport
from fastapi_users.authentication.strategy.db import DatabaseStrategy
from fastapi_users.authentication.strategy import Strategy
from fastapi_users.password import PasswordHelper
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from fastapi_users_db_sqlalchemy.access_token import (
    SQLAlchemyAccessTokenDatabase,
)
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import RefreshToken, User
from ..schemas import UserCreate, UserRead, UserUpdate

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])
users_router = APIRouter(tags=["users"])

# --- Крок 1: Створюємо кастомний AuthenticationBackend ---

class AuthenticationBackendWithBody(AuthenticationBackend):
    """
    Розширює стандартний AuthenticationBackend, щоб повертати тіло
    відповіді з даними користувача при успішному логіні.
    """
    async def login(self, strategy: Strategy, user: User) -> Response:
        # Викликаємо оригінальний метод login, щоб отримати відповідь з cookie
        original_response = await super().login(strategy, user)

        # Створюємо Pydantic-схему з даними користувача
        user_read = UserRead.from_orm(user)

        # Створюємо нову JSON-відповідь зі статусом 200 OK
        final_response = JSONResponse(content=user_read.model_dump())

        # Копіюємо заголовки (найголовніше - 'Set-Cookie') з оригінальної відповіді
        final_response.headers.raw.extend(original_response.headers.raw)

        return final_response

# --- Крок 2: Налаштовуємо FastAPIUsers з нашим кастомним backend ---

cookie_transport = CookieTransport(
    cookie_name="auth_token",
    cookie_max_age=604800,  # 7 днів
    cookie_httponly=True,
    cookie_secure=False,  # Для локальної розробки
    cookie_samesite="lax",
)

async def get_refresh_token_db(session: AsyncSession = Depends(get_db)):
    return SQLAlchemyAccessTokenDatabase(session, RefreshToken)

def get_refresh_strategy() -> Callable[[], DatabaseStrategy]:
    def strategy(session: AsyncSession = Depends(get_db)) -> DatabaseStrategy:
        logger.debug("Initializing token database strategy")
        db = SQLAlchemyAccessTokenDatabase(session, RefreshToken)
        logger.info(
            f"Database strategy initialized for table: {RefreshToken.__tablename__}, "
            f"adapter: {type(db).__name__}"
        )
        strategy_instance = DatabaseStrategy(
            database=db,
            lifetime_seconds=604800,  # Час життя refresh-токена (7 днів)
        )
        logger.debug(f"DatabaseStrategy created: {strategy_instance}")
        return strategy_instance
    return strategy

# Використовуємо наш новий AuthenticationBackendWithBody
auth_backend = AuthenticationBackendWithBody(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_refresh_strategy(),
)

# --- Решта файлу залишається майже без змін ---

class UserManager(BaseUserManager[User, int]):
    password_helper = PasswordHelper(PasswordHasher())
    
    # ... (Весь код UserManager залишається таким самим, як був)
    async def authenticate(self, credentials: OAuth2PasswordRequestForm) -> User | None:
        logger.debug(f"Authenticating user with email: {credentials.username}")
        async with self.user_db.session as session:
            try:
                result = await session.execute(select(User).filter_by(email=credentials.username))
                user = result.scalars().first()
                if not user:
                    logger.debug(f"User with email {credentials.username} not found")
                    return None
                
                logger.debug(f"Found user: {user.email}, user type: {type(user)}")
                try:
                    verified, updated_hash = self.password_helper.verify_and_update(
                        credentials.password, user.hashed_password
                    )
                    if verified:
                        if updated_hash:
                            user.hashed_password = updated_hash
                            session.add(user)
                            await session.commit()
                        logger.info(f"User {user.email} authenticated successfully")
                        return user
                    else:
                        logger.debug(f"Password verification failed for user: {user.email}")
                        return None
                except Exception as e:
                    logger.error(f"Password verification error for user {user.email}: {str(e)}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Помилка перевірки пароля",
                    )
            except Exception as e:
                logger.error(f"Database or authentication error: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Внутрішня помилка сервера під час автентифікації",
                )

    async def create(self, user_create: UserCreate, safe: bool = False, **kwargs) -> User:
        logger.debug(f"Creating user with email: {user_create.email}")
        async with self.user_db.session as session:
            user = User(
                email=user_create.email,
                username=user_create.username,
                hashed_password=self.password_helper.hash(user_create.password),
                is_active=user_create.is_active,
                is_superuser=user_create.is_superuser,
                is_verified=user_create.is_verified,
            )
            session.add(user)
            try:
                await session.commit()
                await session.refresh(user)
                logger.info(f"User created: {user.email}")
                return user
            except Exception as e:
                await session.rollback()
                logger.error(f"Error creating user {user_create.email}: {str(e)}")
                raise

    async def validate_password(self, password: str, user: UserCreate | User) -> None:
        pass

    def parse_id(self, user_id: str) -> int:
        try:
            return int(user_id)
        except ValueError as e:
            logger.error(f"Error parsing user_id '{user_id}' to int: {str(e)}")
            raise

async def get_user_db(session: AsyncSession = Depends(get_db)):
    yield SQLAlchemyUserDatabase(session, User)

async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)

fastapi_users = FastAPIUsers[User, int](
    get_user_manager,
    [auth_backend],
)

get_current_user = fastapi_users.current_user()

# --- Крок 3: Використовуємо стандартний роутер, який тепер працюватиме з нашим backend ---

# Тепер цей стандартний роутер автоматично підхопить наш кастомний backend
# і буде повертати відповідь з тілом JSON
router.include_router(
    fastapi_users.get_auth_router(auth_backend, requires_verification=False),
    prefix="/jwt",
)

# Роути для роботи з користувачами
@users_router.get("/", response_model=list[UserRead])
async def get_custom_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"Requesting user list, current user: {current_user.email}")
    result = await db.execute(select(User))
    users = result.scalars().all()
    logger.info(f"Found {len(users)} users")
    return [UserRead.model_validate(user) for user in users]

@users_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    user_manager: UserManager = Depends(get_user_manager),
):
    logger.info(f"Request to delete user with id={user_id}, current user: {current_user.email}")
    if not current_user.is_superuser:
        logger.error(f"User {current_user.email} is not a superuser")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Тільки суперкористувачі можуть видаляти користувачів",
        )
    if current_user.id == user_id:
        logger.error(f"User {current_user.email} attempted to delete themselves")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неможливо видалити самого себе",
        )

    result = await db.execute(select(User).filter_by(id=user_id))
    user = result.scalars().first()
    if not user:
        logger.error(f"User with id={user_id} not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Користувач не знайдений")

    await db.execute(delete(User).filter_by(id=user_id))
    await db.commit()
    logger.info(f"User with id={user_id} deleted successfully")
    return None

@users_router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    user_manager: UserManager = Depends(get_user_manager),
):
    logger.info(f"Request to update user with id={user_id}, current user: {current_user.email}")
    if not current_user.is_superuser and current_user.id != user_id:
        logger.error(f"User {current_user.email} lacks permission to update")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостатньо прав")

    result = await db.execute(select(User).filter_by(id=user_id))
    user = result.scalars().first()
    if not user:
        logger.error(f"User with id={user_id} not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Користувач не знайдений")

    updated_user = await user_manager.update(user_update, user, safe=True)
    await db.commit()
    await db.refresh(updated_user)
    logger.info(f"User with id={user_id} updated successfully")
    return UserRead.model_validate(updated_user)


# Додаємо роутер для реєстрації
router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/jwt",
)

@users_router.get("/me", response_model=UserRead)
async def read_users_me(
    current_user: User = Depends(fastapi_users.current_user(active=True)),
):
    return current_user