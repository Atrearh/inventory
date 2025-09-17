import logging
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from ldap3 import ALL, Connection, Server
from ldap3.core.exceptions import LDAPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models import Domain
from ..repositories.computer_repository import ComputerRepository
from ..repositories.domain_repository import DomainRepository
from ..schemas import DomainCreate, DomainRead, DomainUpdate
from ..services.ad_service import ADService
from ..services.encryption_service import EncryptionService, get_encryption_service
from .auth import fastapi_users

logger = logging.getLogger(__name__)

router = APIRouter(tags=["domains"], prefix="/api/domains")


@router.get(
    "/",
    response_model=List[DomainRead],
    dependencies=[Depends(fastapi_users.current_user(active=True, superuser=True))],
)
async def get_all_domains(db: AsyncSession = Depends(get_db)):
    """Отримує список всіх доменів."""
    logger.info("Запит списку всіх доменів")

    try:
        result = await db.execute(select(Domain))
        domains = result.scalars().all()

        logger.debug(f"Знайдено {len(domains)} доменів в БД")

        return [
            DomainRead(
                id=domain.id,
                name=domain.name,
                username=domain.username,
                server_url=domain.server_url,
                ad_base_dn=domain.ad_base_dn,
                last_updated=(domain.last_updated.isoformat() if domain.last_updated else None),
            )
            for domain in domains
        ]

    except Exception as e:
        logger.error(f"Помилка отримання списку доменів: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Помилка отримання доменів: {str(e)}")


def validate_domain_name(name: str) -> None:
    """Валідує ім’я домену."""
    if not name or len(name.strip()) == 0:
        raise ValueError("Ім’я домену не може бути порожнім")
    if len(name) > 255:
        raise ValueError("Ім’я домену занадто довге (макс. 255 символів)")


@router.post(
    "/",
    response_model=DomainRead,
    dependencies=[Depends(fastapi_users.current_user(active=True, superuser=True))],
)
async def create_domain(request: Request, domain: DomainCreate, db: AsyncSession = Depends(get_db)):
    """Створює новий домен з зашифрованим паролем."""
    logger.info(f"Валідовані дані домену (без пароля): {domain.model_dump(exclude={'password'})}")

    try:
        # Валідуємо ім’я домену
        logger.debug(f"Валідація імені домену: {domain.name}")
        validate_domain_name(domain.name)

        # Перевіряємо унікальність імені домену
        domain_repo = DomainRepository(db)
        logger.debug(f"Перевірка унікальності домену: {domain.name}")
        existing_domain = await domain_repo.get_domain_by_name(name=domain.name)
        if existing_domain:
            logger.warning(f"Домен {domain.name} вже існує")
            raise HTTPException(status_code=400, detail=f"Домен з ім'ям {domain.name} вже існує")

        # Шифруємо пароль
        logger.debug(f"Шифрування пароля для домену: {domain.name}")
        encryption_service = EncryptionService(settings.encryption_key)
        encrypted_password = encryption_service.encrypt(domain.password)
        logger.debug(f"Пароль для домену {domain.name} зашифровано")

        # Створюємо домен через репозиторій
        logger.debug(f"Створення домену в репозиторії: {domain.name}")
        db_domain = await domain_repo.create_or_update_domain(
            name=domain.name.strip(),
            username=domain.username,
            encrypted_password=encrypted_password,
            server_url=domain.server_url,
            ad_base_dn=domain.ad_base_dn,
        )
        await db.commit()
        await db.refresh(db_domain)
        logger.info(f"Домен створено: {db_domain.name} (id={db_domain.id})")

        return DomainRead(
            id=db_domain.id,
            name=db_domain.name,
            username=db_domain.username,
            server_url=db_domain.server_url,
            ad_base_dn=db_domain.ad_base_dn,
            last_updated=(db_domain.last_updated.isoformat() if db_domain.last_updated else None),
        )

    except ValidationError as e:
        logger.error(f"Помилка валідації даних домену: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Помилка створення домену: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка створення домену: {str(e)}")


@router.put(
    "/{id}",
    response_model=DomainRead,
    dependencies=[Depends(fastapi_users.current_user(active=True, superuser=True))],
)
async def update_domain(
    id: int,
    domain: DomainUpdate,
    db: AsyncSession = Depends(get_db),
    encryption_service: EncryptionService = Depends(get_encryption_service),
):
    """Оновлює домен за id, зберігаючи пароль, якщо він не наданий."""
    logger.info(f"Початок оновлення домену з id={id}")

    try:
        domain_repo = DomainRepository(db)
        db_domain = await db.execute(select(Domain).filter(Domain.id == id))
        db_domain = db_domain.scalar_one_or_none()
        if not db_domain:
            logger.warning(f"Домен з id={id} не знайдено")
            raise HTTPException(status_code=404, detail=f"Домен з id={id} не знайдено")

        # Валідуємо ім’я домену, якщо воно надано
        if domain.name:
            name = domain.name.strip()
            logger.debug(f"Валідація імені домену: {name}")
            validate_domain_name(name)
            existing_domain = await domain_repo.get_domain_by_name(name)
            if existing_domain and existing_domain.id != id:
                logger.warning(f"Домен з ім'ям {name} вже існує")
                raise HTTPException(status_code=400, detail=f"Домен з ім'ям {name} вже існує")

        # Оновлюємо поля, якщо вони надані
        if domain.name:
            db_domain.name = name.lower()
        if domain.username:
            db_domain.username = domain.username
        if domain.server_url:
            db_domain.server_url = domain.server_url
        if domain.ad_base_dn:
            db_domain.ad_base_dn = domain.ad_base_dn
        if domain.password:
            logger.debug(f"Шифрування нового пароля для домену: {db_domain.name}")
            db_domain.encrypted_password = encryption_service.encrypt(domain.password)

        logger.debug(f"Оновлення домену в репозиторії: {db_domain.name}")
        await db.flush()
        await db.commit()
        await db.refresh(db_domain)
        logger.info(f"Домен оновлено: {db_domain.name} (id={db_domain.id})")

        return DomainRead(
            id=db_domain.id,
            name=db_domain.name,
            username=db_domain.username,
            server_url=db_domain.server_url,
            ad_base_dn=db_domain.ad_base_dn,
            last_updated=(db_domain.last_updated.isoformat() if db_domain.last_updated else None),
        )

    except Exception as e:
        logger.error(f"Помилка оновлення домену з id={id}: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка оновлення домену: {str(e)}")


@router.delete(
    "/{id}",
    dependencies=[Depends(fastapi_users.current_user(active=True, superuser=True))],
)
async def delete_domain(id: int, db: AsyncSession = Depends(get_db)):
    """Видаляє домен за id."""
    logger.info(f"Початок видалення домену з id={id}")

    try:
        domain = await db.execute(select(Domain).filter(Domain.id == id))
        domain = domain.scalar_one_or_none()
        if not domain:
            logger.warning(f"Домен з id={id} не знайдено")
            raise HTTPException(status_code=404, detail=f"Домен з id={id} не знайдено")

        await db.delete(domain)
        await db.commit()
        logger.info(f"Домен видалено: {domain.name} (id={id})")

    except Exception as e:
        logger.error(f"Помилка видалення домену з id={id}: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка видалення домену: {str(e)}")


@router.post("/validate", dependencies=[Depends(fastapi_users.current_user(active=True, superuser=True))])
async def validate_domain_connection(
    request: Request,
    domain: DomainCreate,
    db: AsyncSession = Depends(get_db),
    encryption_service: EncryptionService = Depends(get_encryption_service),
):
    """Перевіряє підключення до LDAP-сервера."""
    logger.info(f"Перевірка підключення до домену: {domain.name}")

    try:
        if not domain.server_url or not domain.username or not domain.password:
            logger.warning(f"Не вказано server_url, username або password для домену {domain.name}")
            raise HTTPException(
                status_code=400,
                detail="server_url, username і password є обов’язковими для перевірки LDAP",
            )

        server_url = domain.server_url
        if not server_url.startswith(("ldap://", "ldaps://")):
            if ":" in server_url:
                host, port = server_url.split(":", 1)
                server_url = f"ldap://{host}:{port.strip()}"
            else:
                server_url = f"ldap://{server_url}:389"

        logger.debug(f"Спроба підключення до LDAP-сервера: {server_url}, користувач: {domain.username}")

        server = Server(server_url, get_info=ALL)
        conn = Connection(server, user=domain.username, password=domain.password, auto_bind=True)
        logger.info(f"Підключення до {server_url} успішне")
        conn.unbind()
        return {"status": "success", "message": f"Підключення до {server_url} успішне"}

    except LDAPException as e:
        logger.error(f"Помилка LDAP для домену {domain.name}: {str(e)}", exc_info=True)
        if "invalidCredentials" in str(e):
            raise HTTPException(status_code=400, detail="Невірні облікові дані для LDAP")
        elif "invalidServer" in str(e):
            raise HTTPException(status_code=400, detail=f"Невірний server_url: {server_url}")
        else:
            raise HTTPException(status_code=400, detail=f"Помилка LDAP: {str(e)}")

    except Exception as e:
        logger.error(
            f"Непередбачена помилка при перевірці домену {domain.name}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Помилка перевірки домену: {str(e)}")


@router.get(
    "/{id}",
    response_model=DomainRead,
    dependencies=[Depends(fastapi_users.current_user(active=True, superuser=True))],
)
async def get_domain(id: int, db: AsyncSession = Depends(get_db)):
    """Отримує інформацію про домен за id."""
    logger.info(f"Запит інформації про домен з id={id}")

    try:
        result = await db.execute(select(Domain).filter(Domain.id == id))
        domain = result.scalar_one_or_none()

        if not domain:
            logger.warning(f"Домен з id={id} не знайдено")
            raise HTTPException(status_code=404, detail=f"Домен з id={id} не знайдено")

        logger.info(f"Домен знайдено: {domain.name} (id={domain.id})")
        return DomainRead(
            id=domain.id,
            name=domain.name,
            username=domain.username,
            server_url=domain.server_url,
            ad_base_dn=domain.ad_base_dn,
            last_updated=(domain.last_updated.isoformat() if domain.last_updated else None),
        )

    except Exception as e:
        logger.error(f"Помилка отримання домену з id={id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Помилка отримання домену: {str(e)}")


@router.post(
    "/scan",
    response_model=dict,
    dependencies=[Depends(fastapi_users.current_user(active=True, superuser=True))],
)
async def scan_domains(
    domain_id: int | None = Query(
        None,
        description="ID домену для сканування. Якщо не вказано, скануються всі домени",
    ),
    db: AsyncSession = Depends(get_db),
    encryption_service: EncryptionService = Depends(get_encryption_service),
):
    """Запускає сканування AD для конкретного домену (якщо вказано domain_id) або всіх доменів."""
    logger.info(f"Запуск сканування AD, domain_id={domain_id}")

    try:
        ad_service = ADService(ComputerRepository(db), encryption_service)

        if domain_id is not None:
            # Сканування одного домену
            result = await db.execute(select(Domain).filter(Domain.id == domain_id))
            domain = result.scalar_one_or_none()
            if not domain:
                logger.warning(f"Домен з id={domain_id} не знайдено")
                raise HTTPException(status_code=404, detail=f"Домен з id={domain_id} не знайдено")

            task_id = str(uuid.uuid4())
            logger.debug(f"Створено задачу сканування з task_id={task_id} для домену {domain.name}")
            await ad_service.scan_and_update_ad(db, domain)
            logger.info(f"Сканування AD завершено для домену {domain.name}")
            return {"status": "success", "task_id": task_id}

        else:
            # Сканування всіх доменів
            result = await db.execute(select(Domain))
            domains = result.scalars().all()
            if not domains:
                logger.warning("Домени не знайдено")
                raise HTTPException(status_code=404, detail="Домени не знайдено")

            task_ids = []
            for domain in domains:
                task_id = str(uuid.uuid4())
                logger.debug(f"Створено задачу сканування з task_id={task_id} для домену {domain.name}")
                await ad_service.scan_and_update_ad(db, domain)
                task_ids.append(task_id)

            logger.info(f"Сканування AD завершено для {len(domains)} доменів")
            return {"status": "success", "task_ids": task_ids}

    except Exception as e:
        logger.error(f"Помилка сканування доменів (domain_id={domain_id}): {str(e)}")
        raise HTTPException(status_code=500, detail=f"Помилка сканування доменів: {str(e)}")
