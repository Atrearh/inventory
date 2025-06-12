from fastapi import FastAPI, Depends, HTTPException, APIRouter, Request, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func
from typing import List, Optional
import signal
import asyncio
import uuid
import logging
from .database import AsyncSessionLocal, engine, Base
from . import models, schemas
from .settings import settings
from .logging_config import setup_logging
from .data_collector import get_hosts_for_polling_from_db, get_pc_info, load_ps_script, _script_cache
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .services.computer_service import ComputerService
from .repositories.computer_repository import ComputerRepository
from .services.ad_service import ADService
from .repositories.statistics import StatisticsRepository
from datetime import datetime
from sqlalchemy.orm import selectinload
from .data_collector import WinRMDataCollector
# Настройка логирования
logger = setup_logging()

# Глобальная переменная для контроля завершения
shutdown_event = asyncio.Event()

def signal_handler(sig, frame):
    """Обработчик сигналов SIGINT и SIGTERM."""
    logger.info(f"Получен сигнал {sig}, инициируется завершение...")
    shutdown_event.set()

# Инициализация базы данных
async def init_db():
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(text("SHOW TABLES"))
            tables = [row[0] for row in result.fetchall()]
            if not tables:
                logger.info("Таблицы не найдены, создаём схему базы данных...")
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
            else:
                logger.info(f"Найдены таблицы: {tables}")
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {str(e)}")
            raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Запуск приложения, инициализация базы данных...")
    await init_db()
    logger.info("Загрузка PowerShell скриптов...")
    _script_cache["system_info"] = load_ps_script("system_info.ps1")
    _script_cache["software_info"] = load_ps_script("software_info.ps1")
    yield
    logger.info("Завершение работы приложения...")
    WinRMDataCollector.clear_pool()

app = FastAPI(title="Inventory Management", lifespan=lifespan)
router = APIRouter(prefix="/api")

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    correlation_id = str(uuid.uuid4())
    request_logger = logging.LoggerAdapter(logger, {"correlation_id": correlation_id})
    request.state.logger = request_logger
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

def get_computer_repository(db: AsyncSession = Depends(get_db)) -> ComputerRepository:
    return ComputerRepository(db)

def get_computer_service(repo: ComputerRepository = Depends(get_computer_repository)) -> ComputerService:
    return ComputerService(repo)

def get_ad_service(repo: ComputerRepository = Depends(get_computer_repository)) -> ADService:
    return ADService(repo)

def get_statistics_repo(db: AsyncSession = Depends(get_db)) -> StatisticsRepository:
    return StatisticsRepository(db)

@router.post("/report", response_model=schemas.Computer, operation_id="create_computer_report")
async def create_computer(
    comp_data: schemas.ComputerCreate,
    computer_service: ComputerService = Depends(get_computer_service),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """Создаёт или обновляет данные компьютера."""
    request.state.logger.info(f"Получен отчет для hostname: {comp_data.hostname}")
    return await computer_service.upsert_computer_from_schema(comp_data, db)

@router.post("/update_check_status", operation_id="update_computer_check_status")
async def update_check_status(
    data: schemas.ComputerUpdateCheckStatus,
    computer_service: ComputerService = Depends(get_computer_service),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """Обновляет check_status компьютера."""
    request.state.logger.info(f"Обновление check_status для {data.hostname}")
    try:
        db_computer = await computer_service.repo.async_update_computer_check_status(db, data.hostname, data.check_status)
        if not db_computer:
            raise HTTPException(status_code=404, detail="Компьютер не найден")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Ошибка обновления check_status для {data.hostname}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/{computer_id}", response_model=List[schemas.ChangeLog], operation_id="get_computer_history")
async def get_history(
    computer_id: int,
    computer_service: ComputerService = Depends(get_computer_service),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """Получает историю изменений компьютера."""
    request.state.logger.info(f"Получение истории для computer_id: {computer_id}")
    return await computer_service.repo.async_get_change_log(db, computer_id)

async def run_scan_task(task_id: str, logger_adapter: logging.LoggerAdapter, computer_service: ComputerService):
    async with AsyncSessionLocal() as db:
        db_task = None
        try:
            db_task = models.ScanTask(id=task_id, status=models.ScanStatus.running)
            db.add(db_task)
            await db.commit()
            await db.refresh(db_task)

            hosts, simple_username = await get_hosts_for_polling_from_db(db=db)
            logger_adapter.info(f"Получено {len(hosts)} хостов: {hosts[:5]}...")
            successful = 0
            semaphore = asyncio.Semaphore(settings.scan_max_workers)

            async def process_host(host: str):
                nonlocal successful
                async with semaphore:
                    if shutdown_event.is_set():
                        return
                    try:
                        db_computer = await db.execute(
                            select(models.Computer).filter(models.Computer.hostname == host)
                        )
                        db_computer = db_computer.scalar_one_or_none()
                        last_updated = db_computer.last_updated if db_computer else None
                        result_data = await get_pc_info(
                            hostname=host,
                            user=settings.ad_username,
                            password=settings.ad_password,
                            last_updated=last_updated,
                        )
                        if result_data is None or not isinstance(result_data, dict):
                            logger_adapter.error(f"Некорректные данные для {host}: {result_data}", exc_info=False)
                            await computer_service.repo.async_update_computer_check_status(
                                db, hostname=host, check_status=models.CheckStatus.unreachable.value
                            )
                            await db.commit()
                            return
                        if result_data.get("check_status") == models.CheckStatus.unreachable.value:
                            logger_adapter.error(
                                f"Хост {host} недоступен: {result_data.get('error', 'Неизвестная ошибка')}", exc_info=False
                            )
                            await computer_service.repo.async_update_computer_check_status(
                                db, hostname=host, check_status=models.CheckStatus.unreachable.value
                            )
                            await db.commit()
                            return
                        computer_to_create = await computer_service.prepare_computer_data_for_db(db, result_data)
                        if computer_to_create:
                            try:
                                db_computer = await computer_service.upsert_computer_from_schema(computer_to_create, db)
                                if db_computer:
                                    await db.commit()
                                    successful += 1
                                else:
                                    logger_adapter.error(f"Не удалось сохранить данные для {host}", exc_info=False)
                                    await computer_service.repo.async_update_computer_check_status(
                                        db, hostname=host, check_status=models.CheckStatus.failed.value
                                    )
                                    await db.commit()
                            except Exception as e:
                                logger_adapter.error(f"Ошибка сохранения данных для {host}: {str(e)}", exc_info=True)
                                await db.rollback()
                                await computer_service.repo.async_update_computer_check_status(
                                    db, hostname=host, check_status=models.CheckStatus.failed.value
                                )
                                await db.commit()
                        else:
                            logger_adapter.error(f"Ошибка валидации для {host}", exc_info=False)
                            await computer_service.repo.async_update_computer_check_status(
                                db, hostname=host, check_status=models.CheckStatus.failed.value
                            )
                            await db.commit()
                    except Exception as e:
                        logger_adapter.error(f"Исключение для хоста {host}: {str(e)}", exc_info=True)
                        await computer_service.repo.async_update_computer_check_status(
                            db, hostname=host, check_status=models.CheckStatus.unreachable.value
                        )
                        await db.commit()

            tasks = [process_host(host) for host in hosts]
            await asyncio.gather(*tasks, return_exceptions=True)

            db_task.scanned_hosts = len(hosts)
            db_task.successful_hosts = successful
            db_task.status = models.ScanStatus.completed
            await db.commit()
            logger_adapter.info(f"Сканирование завершено. Успешно обработано {successful} из {len(hosts)} хостов")
        except Exception as e:
            logger_adapter.error(f"Критическая ошибка сканирования: {str(e)}", exc_info=True)
            if db_task:
                db_task.status = models.ScanStatus.failed
                db_task.error = str(e)
                db.add(db_task)
            else:
                failed_task = models.ScanTask(id=task_id, status=models.ScanStatus.failed, error=str(e))
                db.add(failed_task)
            await db.commit()
        finally:
            await db.close()

@router.post("/scan", response_model=dict, operation_id="start_scan")
async def start_scan(
    background_tasks: BackgroundTasks,
    computer_service: ComputerService = Depends(get_computer_service),  # Добавляем зависимость
    request: Request = None,
):
    logger_adapter = request.state.logger if request else logger
    task_id = str(uuid.uuid4())
    logger_adapter.info(f"Запуск фонового сканирования с task_id: {task_id}")
    background_tasks.add_task(run_scan_task, task_id, logger_adapter, computer_service)  # Передаем computer_service
    return {"status": "success", "task_id": task_id}

@router.get("/scan/status/{task_id}", response_model=schemas.ScanTask, operation_id="get_scan_status")
async def scan_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """Получает статус задачи сканирования."""
    logger_adapter = request.state.logger if request else logger
    db_task = await db.execute(
        select(models.ScanTask).filter(models.ScanTask.id == task_id)
    )
    db_task = db_task.scalar_one_or_none()
    if not db_task:
        logger_adapter.error(f"Задача с task_id {task_id} не найдена")
        raise HTTPException(status_code=404, detail="Task not found")
    return db_task

@router.get("/statistics", response_model=schemas.DashboardStats, operation_id="get_statistics")
async def get_statistics(
    metrics: List[str] = Query(None, description="Список метрик для получения статистики"),
    db: AsyncSession = Depends(get_db),
):
    repo = StatisticsRepository(db)
    if metrics is None:
        metrics = ["total_computers", "os_versions", "low_disk_space", "last_scan_time", "status_stats"]
    return await repo.get_statistics(metrics)

@router.get("/computers", response_model=schemas.ComputersResponse, operation_id="get_computers")
async def get_computers(
    db: AsyncSession = Depends(get_db),
    sort_by: str = Query("hostname", description="Поле для сортировки"),
    sort_order: str = Query("asc", description="Порядок: asc или desc"),
    hostname: Optional[str] = Query(None, description="Фильтр по hostname"),
    os_version: Optional[str] = Query(None, description="Фильтр по версии ОС"),
    check_status: Optional[schemas.CheckStatus] = Query(
        None,
        description="Фильтр по check_status",
        alias="check_status",
        # Добавляем валидацию для обработки пустой строки
        regex=r"^(success|failed|unreachable)?$"
    ),
    page: int = Query(1, ge=1, description="Номер страницы"),
    limit: int = Query(50, ge=1, le=100, description="Количество на странице")
):
    """Возвращает список компьютеров с сортировкой, фильтрацией и пагинацией."""
    try:
        # Если check_status пустая строка, преобразуем в None
        if check_status == "":
            check_status = None

        # Асинхронный запрос для подсчета общего количества
        count_query = select(func.count(models.Computer.id))
        if hostname and hostname.strip():
            count_query = count_query.filter(models.Computer.hostname.ilike(f"%{hostname.strip()}%"))
        if os_version and os_version.strip():
            count_query = count_query.filter(models.Computer.os_version.ilike(f"%{os_version.strip()}%"))
        if check_status is not None:
            count_query = count_query.filter(models.Computer.check_status == check_status)
        total = await db.execute(count_query)
        total = total.scalar()

        # Асинхронный запрос для выборки данных
        query = select(models.Computer).options(selectinload(models.Computer.disks))
        if hostname and hostname.strip():
            query = query.filter(models.Computer.hostname.ilike(f"%{hostname.strip()}%"))
        if os_version and os_version.strip():
            query = query.filter(models.Computer.os_version.ilike(f"%{os_version.strip()}%"))
        if check_status is not None:
            query = query.filter(models.Computer.check_status == check_status)

        sort_field = getattr(models.Computer, sort_by, models.Computer.hostname)
        if sort_order.lower() == "desc":
            query = query.order_by(sort_field.desc())
        else:
            query = query.order_by(sort_field.asc())

        offset = (page - 1) * limit
        result = await db.execute(query.offset(offset).limit(limit))
        computers = result.scalars().all()

        return schemas.ComputersResponse(data=computers, total=total)
    except Exception as e:
        logger.error(f"Ошибка получения списка компьютеров: {str(e)}", exc_info=False)
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@router.post("/ad/scan", response_model=dict, operation_id="start_ad_scan")
async def start_ad_scan(
    background_tasks: BackgroundTasks,
    ad_service: ADService = Depends(get_ad_service),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """Запускает сканирование Active Directory в фоновом режиме."""
    logger_adapter = request.state.logger if request else logger
    task_id = str(uuid.uuid4())
    logger_adapter.info(f"Запуск фонового сканирования AD с task_id: {task_id}")
    background_tasks.add_task(ad_service.scan_and_update_ad, db)
    return {"status": "success", "task_id": task_id}

app.include_router(router)

if __name__ == "__main__":
    logger.info("Запуск приложения")
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    uvicorn.run(app, host="0.0.0.0", port=settings.server_port)