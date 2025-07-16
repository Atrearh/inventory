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
import logging
from fastapi.security import OAuth2PasswordRequestForm
from argon2 import PasswordHasher
from fastapi_users.password import PasswordHelper


logger = logging.getLogger(__name__)
setup_logging(log_level=settings.log_level)

router = APIRouter(tags=["auth"])
users_router = APIRouter(tags=["users"])

bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.secret_key, lifetime_seconds=604800) 

def get_refresh_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.secret_key, lifetime_seconds=30 * 24 * 60 * 60)  # 30 дней для refresh token

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
                logger.debug(f"Found user: {user.email}, user type: {type(user)}")
                try:
                    if self.password_helper.verify_and_update(credentials.password, user.hashed_password)[0]:
                        return user
                    else:
                        logger.debug(f"Password verification failed for user: {user.email}")
                except Exception as e:
                    logger.error(f"Error verifying password for user {user.email}: {str(e)}")
                    return None
            else:
                logger.debug(f"No user found with email: {credentials.username}")
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
                logger.error(f"Error creating user user_create.email: {str(e)}")
                raise

    async def validate_password(self, password: str, user: UserCreate | User) -> None:
        pass

    def parse_id(self, user_id: str) -> int:
        try:
            return int(user_id)
        except ValueError as e:
            logger.error(f"Ошибка преобразования user_id '{user_id}' в int: {str(e)}")
            raise

async def get_user_manager(db: AsyncSession = Depends(get_db)):
    logger.info("Инициализация get_user_manager")
    async with db as session:
        logger.debug(f"Тип сессии: {type(session)}")
        user_db = SQLAlchemyUserDatabase(session, User)
        logger.info(f"Создание UserManager для таблицы: {User.__tablename__}")
        try:
            user_manager = UserManager(user_db)
            logger.info(f"UserManager создан: {user_manager}")
            yield user_manager
        except Exception as e:
            logger.error(f"Ошибка создания UserManager: {str(e)}")
            raise

fastapi_users = FastAPIUsers[User, int](
    get_user_manager,
    [auth_backend],
)

async def custom_current_user(user: User = Depends(fastapi_users.current_user(active=True))):
    logger.info(f"Вызов custom_current_user, пользователь: {user.email}")
    if user is None:
        logger.error("Пользователь не найден или не активен")
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
            detail="Неверные учетные данные",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = await get_jwt_strategy().write_token(user)
    refresh_token = await get_refresh_jwt_strategy().write_token(user)
    logger.info(f"Login successful for user: {user.email}")
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
    logger.info("Запрос на обновление токена")
    try:
        strategy = get_refresh_jwt_strategy()
        user_id = await strategy.read_token(refresh_token, user_manager)
        if not user_id:
            logger.error("Недействительный refresh token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительный refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        async with user_manager.user_db.session as session:
            result = await session.execute(select(User).filter_by(id=user_id))
            user = result.scalars().first()
            if not user or not user.is_active:
                logger.error(f"Пользователь с id={user_id} не найден или не активен")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Недействительный пользователь",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        new_access_token = await get_jwt_strategy().write_token(user)
        new_refresh_token = await get_refresh_jwt_strategy().write_token(user)
        logger.info(f"Токен успешно обновлен для пользователя: {user.email}")
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
        }
    except Exception as e:
        logger.error(f"Ошибка при обновлении токена: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ошибка при обновлении токена",
            headers={"WWW-Authenticate": "Bearer"},
        )

@users_router.get("/", response_model=list[UserRead])
async def get_custom_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"Запрос списка пользователей, текущий пользователь: {current_user.email}")
    result = await db.execute(select(User))
    users = result.scalars().all()
    logger.info(f"Найдено пользователей: {len(users)}")
    return [UserRead.model_validate(user) for user in users]

@users_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    user_manager: UserManager = Depends(get_user_manager),
):
    logger.info(f"Запрос на удаление пользователя с id={user_id}, текущий пользователь: {current_user.email}")
    if not current_user.is_superuser:
        logger.error(f"Пользователь {current_user.email} не является суперпользователем")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только суперпользователи могут удалять пользователей")
    if current_user.id == user_id:
        logger.error(f"Пользователь {current_user.email} пытается удалить сам себя")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя удалить самого себя")
    
    result = await db.execute(select(User).filter_by(id=user_id))
    user = result.scalars().first()
    if not user:
        logger.error(f"Пользователь с id={user_id} не найден")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    
    await db.execute(delete(User).filter_by(id=user_id))
    await db.commit()
    logger.info(f"Пользователь с id={user_id} успешно удален")
    return None

@users_router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    user_manager: UserManager = Depends(get_user_manager),
):
    logger.info(f"Запрос на обновление пользователя с id={user_id}, текущий пользователь: {current_user.email}")
    if not current_user.is_superuser and current_user.id != user_id:
        logger.error(f"Пользователь {current_user.email} не имеет прав на обновление")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
    
    result = await db.execute(select(User).filter_by(id=user_id))
    user = result.scalars().first()
    if not user:
        logger.error(f"Пользователь с id={user_id} не найден")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    
    updated_user = await user_manager.update(user_update, user, safe=True)
    await db.commit()
    await db.refresh(updated_user)
    logger.info(f"Пользователь с id={user_id} успешно обновлен")
    return UserRead.model_validate(updated_user)

router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/jwt",
)
router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
)