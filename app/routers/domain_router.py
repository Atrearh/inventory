from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..database import get_db
from ..models import Domain
from ..schemas import DomainCreate, DomainUpdate
from ..repositories.domain_repository import DomainRepository
from ..services.encryption_service import EncryptionService
from ..settings import settings
from .auth import fastapi_users
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["domains"], prefix="/api/domains")

@router.post("/", response_model=DomainUpdate, dependencies=[Depends(fastapi_users.current_user(active=True, superuser=True))])
async def create_domain(domain: DomainCreate, db: AsyncSession = Depends(get_db)):
    """Створює новий домен з зашифрованим паролем."""
    logger.info(f"Початок створення домену: {domain.name}")
    
    try:
        # Шифруємо пароль
        encryption_service = EncryptionService(settings.encryption_key)
        encrypted_password = encryption_service.encrypt(domain.password)
        logger.debug(f"Пароль для домену {domain.name} зашифровано")
        
        # Створюємо домен через репозиторій
        domain_repo = DomainRepository(db)
        db_domain = await domain_repo.create_or_update_domain(
            name=domain.name,
            username=domain.username,
            encrypted_password=encrypted_password
        )
        
        # ВАЖЛИВО: Явно викликаємо commit
        await db.commit()
        logger.info(f"Транзакцію закоммічено для домену {domain.name}")
        
        # Оновлюємо об'єкт з БД
        await db.refresh(db_domain)
        logger.info(f"Домен оновлено з БД: id={db_domain.id}")
        
        # Додаткова перевірка
        verification_result = await db.execute(select(Domain).filter(Domain.name == domain.name))
        verification_domain = verification_result.scalar_one_or_none()
        
        if verification_domain:
            logger.info(f"✅ Верифікація успішна: домен {domain.name} знайдено в БД з id={verification_domain.id}")
        else:
            logger.error(f"❌ ПОМИЛКА: домен {domain.name} не знайдено в БД після commit!")
            raise HTTPException(status_code=500, detail="Домен не збережено в базу даних")
        
        return DomainUpdate(name=db_domain.name, username=db_domain.username)
        
    except Exception as e:
        logger.error(f"Помилка створення домену {domain.name}: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка створення домену: {str(e)}")

@router.get("/{name}", response_model=DomainUpdate, dependencies=[Depends(fastapi_users.current_user(active=True, superuser=True))])
async def get_domain(name: str, db: AsyncSession = Depends(get_db)):
    """Отримує інформацію про домен."""
    logger.info(f"Запит інформації про домен: {name}")
    
    domain_repo = DomainRepository(db)
    domain = await domain_repo.get_domain_by_name(name)
    
    if not domain:
        logger.warning(f"Домен {name} не знайдено")
        raise HTTPException(status_code=404, detail=f"Домен {name} не знайдено")
    
    logger.info(f"Домен знайдено: {domain.name} (id={domain.id})")
    return DomainUpdate(name=domain.name, username=domain.username)

@router.get("/", response_model=list[DomainUpdate], dependencies=[Depends(fastapi_users.current_user(active=True, superuser=True))])
async def get_all_domains(db: AsyncSession = Depends(get_db)):
    """Отримує список всіх доменів."""
    logger.info("Запит списку всіх доменів")
    
    try:
        result = await db.execute(select(Domain))
        domains = result.scalars().all()
        
        logger.info(f"Знайдено {len(domains)} доменів в БД")
        
        return [DomainUpdate(name=domain.name, username=domain.username) for domain in domains]
        
    except Exception as e:
        logger.error(f"Помилка отримання списку доменів: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Помилка отримання доменів: {str(e)}")