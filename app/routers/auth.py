from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi_users import FastAPIUsers, BaseUserManager
from fastapi_users.authentication import AuthenticationBackend, CookieTransport, JWTStrategy
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from ..database import get_db
from ..models import User
from ..schemas import UserRead, UserCreate, UserUpdate
from ..settings import settings
import logging
from fastapi.security import OAuth2PasswordRequestForm
from argon2 import PasswordHasher
from fastapi_users.password import PasswordHelper

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])
users_router = APIRouter(tags=["users"])

# Налаштування транспорту для access_token
cookie_transport = CookieTransport(
    cookie_name="access_token",
    cookie_max_age=3600,
    cookie_httponly=True,
    cookie_secure=False,  # Для локальної розробки
    cookie_samesite="lax",
)

# Стратегія JWT
def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.secret_key, lifetime_seconds=3600)

# Backend для автентифікації
auth_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

# Налаштування UserManager
class UserManager(BaseUserManager[User, int]):
    password_helper = PasswordHelper(PasswordHasher())

    async def authenticate(self, credentials: OAuth2PasswordRequestForm) -> User | None:
        async with self.user_db.session as session:
            result = await session.execute(
                select(User).filter_by(email=credentials.username)
            )
            user = result.scalars().first()
            if user:
                logger.debug(f"Found user: {user.email}, user type: {type(user)}")
                try:
                    if self.password_helper.verify_and_update(credentials.password, user.hashed_password)[0]:
                        return user
                    else:
                        logger.debug(f"Password verification failed for user: {user.email}")
                except Exception as e:
                    logger.error(f"Password verification error for user {user.email}: {str(e)}")
                    return None
            else:
                logger.debug(f"User with email {credentials.username} not found")
            return None

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

async def get_user_manager(db: AsyncSession = Depends(get_db)):
    logger.info("Initializing get_user_manager")
    async with db as session:
        logger.debug(f"Session type: {type(session)}")
        user_db = SQLAlchemyUserDatabase(session, User)
        logger.info(f"Creating UserManager for table: {User.__tablename__}")
        try:
            user_manager = UserManager(user_db)
            logger.info(f"UserManager created: {user_manager}")
            yield user_manager
        except Exception as e:
            logger.error(f"Error creating UserManager: {str(e)}")
            raise

# Ініціалізація FastAPIUsers
fastapi_users = FastAPIUsers[User, int](
    get_user_manager,
    [auth_backend],
)

# Кастомна залежність для перевірки активного користувача
async def custom_current_user(user: User = Depends(fastapi_users.current_user(active=True))):
    logger.info(f"Calling custom_current_user, user: {user.email if user else 'None'}")
    if user is None:
        logger.error("User not found or not active")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return user

get_current_user = custom_current_user

# Використання стандартного роутера для логіну
router.include_router(
    fastapi_users.get_auth_router(auth_backend, requires_verification=False),
    prefix="/jwt",
)

# Роутер для логауту
@router.post("/jwt/logout")
async def logout(response: Response):
    """Вихід користувача з видаленням cookies."""
    response.delete_cookie("access_token")
    logger.info("User logged out successfully")
    return {"message": "Успішний вихід"}

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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Тільки суперкористувачі можуть видаляти користувачів")
    if current_user.id == user_id:
        logger.error(f"User {current_user.email} attempted to delete themselves")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неможливо видалити самого себе")
    
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