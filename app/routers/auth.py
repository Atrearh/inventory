from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_users import FastAPIUsers, BaseUserManager
from fastapi_users.authentication import AuthenticationBackend, JWTStrategy, BearerTransport
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from ..database import get_db
from ..models import User
from ..schemas import UserRead, UserCreate, UserUpdate
from ..settings import settings
from ..logging_config import setup_logging
import structlog
from fastapi.security import OAuth2PasswordRequestForm
from argon2 import PasswordHasher
from fastapi_users.password import PasswordHelper

logger = structlog.get_logger(__name__)
setup_logging(log_level=settings.log_level)

router = APIRouter(tags=["auth"])
users_router = APIRouter(tags=["users"])

bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.secret_key, lifetime_seconds=604800) 

def get_refresh_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.secret_key, lifetime_seconds=30 * 24 * 60 * 60)  # 30 днів для refresh token

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

class UserManager(BaseUserManager[User, int]):
    password_helper = PasswordHelper(PasswordHasher())

    async def authenticate(self, credentials: OAuth2PasswordRequestForm) -> User | None:
        async with self.user_db.session as session:
            result = await session.execute(
                select(User).filter_by(email=credentials.username)
            )
            user = result.scalars().first()
            if user:
                logger.debug(f"Знайдено користувача: {user.email}, тип користувача: {type(user)}")
                try:
                    if self.password_helper.verify_and_update(credentials.password, user.hashed_password)[0]:
                        return user
                    else:
                        logger.debug(f"Перевірка пароля не вдалася для користувача: {user.email}")
                except Exception as e:
                    logger.error(f"Помилка перевірки пароля для користувача {user.email}: {str(e)}")
                    return None
            else:
                logger.debug(f"Користувача з email: {credentials.username} не знайдено")
            return None

    async def create(self, user_create: UserCreate, safe: bool = False, **kwargs) -> User:
        logger.debug(f"Створення користувача з email: {user_create.email}")
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
                logger.info(f"Користувача створено: {user.email}")
                return user
            except Exception as e:
                await session.rollback()
                logger.error(f"Помилка створення користувача {user_create.email}: {str(e)}")
                raise

    async def validate_password(self, password: str, user: UserCreate | User) -> None:
        pass

    def parse_id(self, user_id: str) -> int:
        try:
            return int(user_id)
        except ValueError as e:
            logger.error(f"Помилка перетворення user_id '{user_id}' у int: {str(e)}")
            raise

async def get_user_manager(db: AsyncSession = Depends(get_db)):
    logger.info("Ініціалізація get_user_manager")
    async with db as session:
        logger.debug(f"Тип сесії: {type(session)}")
        user_db = SQLAlchemyUserDatabase(session, User)
        logger.info(f"Створення UserManager для таблиці: {User.__tablename__}")
        try:
            user_manager = UserManager(user_db)
            logger.info(f"UserManager створено: {user_manager}")
            yield user_manager
        except Exception as e:
            logger.error(f"Помилка створення UserManager: {str(e)}")
            raise

fastapi_users = FastAPIUsers[User, int](
    get_user_manager,
    [auth_backend],
)

async def custom_current_user(user: User = Depends(fastapi_users.current_user(active=True))):
    logger.info(f"Виклик custom_current_user, користувач: {user.email}")
    if user is None:
        logger.error("Користувач не знайдений або не активний")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return user

get_current_user = custom_current_user

@router.post("/jwt/login")
async def login(
    credentials: OAuth2PasswordRequestForm = Depends(),
    user_manager: UserManager = Depends(get_user_manager),
):
    user = await user_manager.authenticate(credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невірні облікові дані",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = await get_jwt_strategy().write_token(user)
    refresh_token = await get_refresh_jwt_strategy().write_token(user)
    logger.info(f"Вхід виконано успішно для користувача: {user.email}")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }

@router.post("/jwt/refresh")
async def refresh_token(
    refresh_token: str,
    user_manager: UserManager = Depends(get_user_manager),
):
    logger.info("Запит на оновлення токена")
    try:
        strategy = get_refresh_jwt_strategy()
        user_id = await strategy.read_token(refresh_token, user_manager)
        if not user_id:
            logger.error("Недійсний refresh token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недійсний refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        async with user_manager.user_db.session as session:
            result = await session.execute(select(User).filter_by(id=user_id))
            user = result.scalars().first()
            if not user or not user.is_active:
                logger.error(f"Користувач з id={user_id} не знайдений або не активний")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Недійсний користувач",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        new_access_token = await get_jwt_strategy().write_token(user)
        new_refresh_token = await get_refresh_jwt_strategy().write_token(user)
        logger.info(f"Токен успішно оновлено для користувача: {user.email}")
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
        }
    except Exception as e:
        logger.error(f"Помилка при оновленні токена: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Помилка при оновленні токена",
            headers={"WWW-Authenticate": "Bearer"},
        )

@users_router.get("/", response_model=list[UserRead])
async def get_custom_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"Запит списку користувачів, поточний користувач: {current_user.email}")
    result = await db.execute(select(User))
    users = result.scalars().all()
    logger.info(f"Знайдено користувачів: {len(users)}")
    return [UserRead.model_validate(user) for user in users]

@users_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    user_manager: UserManager = Depends(get_user_manager),
):
    logger.info(f"Запит на видалення користувача з id={user_id}, поточний користувач: {current_user.email}")
    if not current_user.is_superuser:
        logger.error(f"Користувач {current_user.email} не є суперкористувачем")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Тільки суперкористувачі можуть видаляти користувачів")
    if current_user.id == user_id:
        logger.error(f"Користувач {current_user.email} намагається видалити сам себе")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неможливо видалити самого себе")
    
    result = await db.execute(select(User).filter_by(id=user_id))
    user = result.scalars().first()
    if not user:
        logger.error(f"Користувач з id={user_id} не знайдений")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Користувач не знайдений")
    
    await db.execute(delete(User).filter_by(id=user_id))
    await db.commit()
    logger.info(f"Користувач з id={user_id} успішно видалений")
    return None

@users_router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    user_manager: UserManager = Depends(get_user_manager),
):
    logger.info(f"Запит на оновлення користувача з id={user_id}, поточний користувач: {current_user.email}")
    if not current_user.is_superuser and current_user.id != user_id:
        logger.error(f"Користувач {current_user.email} не має прав на оновлення")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостатньо прав")
    
    result = await db.execute(select(User).filter_by(id=user_id))
    user = result.scalars().first()
    if not user:
        logger.error(f"Користувач з id={user_id} не знайдений")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Користувач не знайдений")
    
    updated_user = await user_manager.update(user_update, user, safe=True)
    await db.commit()
    await db.refresh(updated_user)
    logger.info(f"Користувач з id={user_id} успішно оновлений")
    return UserRead.model_validate(updated_user)

router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/jwt",
)
router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
)