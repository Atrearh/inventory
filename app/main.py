# app/main.py
import signal
import asyncio
import uuid
import logging
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, APIRouter, Request, BackgroundTasks, Query, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional
from winrm.exceptions import WinRMTransportError, WinRMError
from contextlib import asynccontextmanager
from .database import engine, async_session, get_db, Base
from . import models, schemas
from .settings import settings
from .utils import setup_logging
from .data_collector import _script_cache
from .services.computer_service import ComputerService
from .repositories.computer_repository import ComputerRepository
from .services.ad_service import ADService
from .repositories.statistics import StatisticsRepository
from .schemas import ErrorResponse
from .settings import settings, SettingsRepository
import ipaddress

# Настройка логирования
logger = setup_logging()

# Глобальная переменная для контроля завершения
shutdown_event = asyncio.Event()

def signal_handler(sig, frame):
    """Обработчик сигналов SIGINT и SIGTERM."""
    logger.info(f"Получен сигнал {sig}, инициируется завершение...")
    shutdown_event.set()

async def init_db():
    async with async_session() as session:
        try:
            result = await session.execute(text("SHOW TABLES"))
            tables = [row[0] for row in result.fetchall()]
            if not tables:
                logger.info("Таблицы не найдены, создаём схему базы данных...")
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                await init_settings(session)
            else:
                logger.info(f"Найдены таблицы: {tables}")
            # Загрузка настроек из БД
            await settings.load_from_db()
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {str(e)}")
            raise

async def init_settings(db: AsyncSession):
    """Инициализирует настройки в базе данных из текущих настроек."""
    repo = SettingsRepository(db)
    default_settings = {
        "ad_server_url": settings.ad_server_url,
        "domain": settings.domain,
        "ad_username": settings.ad_username,
        "ad_password": settings.ad_password,
        "api_url": settings.api_url,
        "test_hosts": settings.test_hosts,
        "log_level": settings.log_level,
        "scan_max_workers": str(settings.scan_max_workers),
        "polling_days_threshold": str(settings.polling_days_threshold),
        "winrm_operation_timeout": str(settings.winrm_operation_timeout),
        "winrm_read_timeout": str(settings.winrm_read_timeout),
        "winrm_port": str(settings.winrm_port),
        "winrm_server_cert_validation": settings.winrm_server_cert_validation,
        "winrm_retries": str(settings.winrm_retries),
        "winrm_retry_delay": str(settings.winrm_retry_delay),
        "ping_timeout": str(settings.ping_timeout),
        "powershell_encoding": settings.powershell_encoding,
        "json_depth": str(settings.json_depth),
        "server_port": str(settings.server_port),
        "cors_allow_origins": ",".join(settings.cors_allow_origins),
        "allowed_ips": ",".join(settings.allowed_ips),
    }
    for key, value in default_settings.items():
        await repo.update_setting(key, value, description=f"Setting {key}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Запуск приложения, инициализация базы данных...")
    await init_db()
    yield
    logger.info("Завершение работы приложения...")
    _script_cache.clear()
    await engine.dispose()
    logger.info("Пул соединений aiomysql закрыт")

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

def get_computer_repository(db: AsyncSession = Depends(get_db)) -> ComputerRepository:
    return ComputerRepository(db)

def get_computer_service(repo: ComputerRepository = Depends(get_computer_repository)) -> ComputerService:
    return ComputerService(db=repo.db, repo=repo)

def get_ad_service(repo: ComputerRepository = Depends(get_computer_repository)) -> ADService:
    return ADService(repo)

def get_statistics_repo(db: AsyncSession = Depends(get_db)) -> StatisticsRepository:
    return StatisticsRepository(db)

def get_settings_repo(db: AsyncSession = Depends(get_db)):
    return SettingsRepository(db)

async def check_ip_allowed(request: Request):
    """Проверяет, является ли IP-адрес клиента разрешенным."""
    client_ip = request.client.host
    logger.debug(f"Проверка IP: {client_ip}")
    allowed = False
    for ip_range in settings.allowed_ips:
        try:
            if '/' in ip_range:
                network = ipaddress.ip_network(ip_range, strict=False)
                if ipaddress.ip_address(client_ip) in network:
                    allowed = True
                    break
            elif client_ip == ip_range:
                allowed = True
                break
        except ValueError as e:
            logger.error(f"Неверный формат IP-диапазона {ip_range}: {str(e)}")
    if not allowed:
        logger.warning(f"Доступ запрещен для IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещен: IP не разрешен"
        )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Глобальный обработчик исключений для централизованного управления ошибками."""
    correlation_id = request.headers.get("X-Correlation-ID", "unknown")
    logger = request.state.logger if hasattr(request.state, 'logger') else logging.getLogger(__name__)
    logger.error(f"Необработанное исключение: {exc}, correlation_id={correlation_id}", exc_info=True)

    match exc:
        case HTTPException(status_code=status_code, detail=detail):
            status_code = status_code
            error_message = detail
        case SQLAlchemyError():
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            error_message = "Ошибка базы данных"
        case WinRMTransportError() | WinRMError():
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            error_message = "Ошибка подключения к WinRM"
        case ValueError():
            status_code = status.HTTP_400_BAD_REQUEST
            error_message = str(exc)
        case _:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            error_message = "Внутренняя ошибка сервера"

    response = ErrorResponse(
        error=error_message,
        detail=str(exc) if settings.log_level == "DEBUG" else "",
        correlation_id=correlation_id
    )

    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(exclude_none=True)
    )

@router.post("/report", response_model=schemas.Computer, operation_id="create_computer_report")
async def create_computer(
    comp_data: schemas.ComputerCreate,
    computer_service: ComputerService = Depends(get_computer_service),
    request: Request = None,
):
    """Создает или обновляет данные компьютера."""
    request.state.logger.info(f"Получен отчет для hostname: {comp_data.hostname}")
    return await computer_service.upsert_computer_from_schema(comp_data, comp_data.hostname)

@router.post("/update_check_status", operation_id="update_computer_check_status")
async def update_check_status(
    data: schemas.ComputerUpdateCheckStatus,
    computer_service: ComputerService = Depends(get_computer_service),
    request: Request = None,
):
    """Обновляет check_status компьютера."""
    request.state.logger.info(f"Обновление check_status для {data.hostname}")
    try:
        db_computer = await computer_service.repo.async_update_computer_check_status(data.hostname, data.check_status)
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
    request: Request = None,
):
    request.state.logger.info(f"Получение истории для computer_id: {computer_id}")
    history = await computer_service.repo.async_get_change_log(computer_id)
    request.state.logger.debug(f"Возвращена история для computer_id={computer_id}: {len(history)} записей, данные: {history}")
    return history

@router.post("/scan", response_model=dict, operation_id="start_scan")
async def start_scan(
    background_tasks: BackgroundTasks,
    computer_service: ComputerService = Depends(get_computer_service),
    request: Request = None,
):
    logger_adapter = request.state.logger if request else logger
    task_id = str(uuid.uuid4())
    logger_adapter.info(f"Запуск фонового сканирования с task_id: {task_id}")
    background_tasks.add_task(computer_service.run_scan_task, task_id, logger_adapter)
    return {"status": "success", "task_id": task_id}

@router.get("/scan/status/{task_id}", response_model=schemas.ScanTask, operation_id="get_scan_status")
async def scan_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """Получает статус задачи сканирования."""
    logger_adapter = request.state.logger if request else logger
    result = await db.execute(select(models.ScanTask).filter(models.ScanTask.id == task_id))
    db_task = result.scalars().first()
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
        regex=r"^(success|failed|unreachable)?$"
    ),
    page: int = Query(1, ge=1, description="Номер страницы"),
    limit: int = Query(50, ge=1, le=100, description="Количество на странице"),
    id: Optional[int] = Query(None, description="ID компьютера")
):
    """Возвращает список компьютеров с сортировкой, фильтрацией и пагинацией."""
    try:
        logger.info(f"Запрос компьютеров: id={id}, hostname={hostname}, page={page}")
        if check_status == "":
            check_status = None
        repo = ComputerRepository(db)
        computers, total = await repo.get_computers(
            sort_by=sort_by,
            sort_order=sort_order,
            hostname=hostname,
            os_version=os_version,
            check_status=check_status,
            page=page,
            limit=limit,
            id=id
        )
        logger.debug(f"Возвращено {len(computers)} компьютеров, всего: {total}, IDs: {[c.id for c in computers]}")
        return schemas.ComputersResponse(data=computers, total=total)
    except Exception as e:
        logger.error(f"Ошибка получения списка компьютеров: {str(e)}", exc_info=True)
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

@router.post("/clean-deleted-software/", response_model=dict)
async def clean_deleted_software(repo: ComputerRepository = Depends(get_computer_repository)):
    """Удаляет записи о ПО с is_deleted=True, старше 6 месяцев."""
    try:
        deleted_count = await repo.clean_old_deleted_software()
        return {"message": f"Удалено {deleted_count} записей о ПО"}
    except Exception as e:
        logger.error(f"Ошибка очистки старых записей ПО: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@router.post("/settings", response_model=dict, operation_id="update_settings")
async def update_settings(
    settings_data: schemas.AppSettingUpdate,
    repo: SettingsRepository = Depends(get_settings_repo),
    request: Request = None,
    _=Depends(check_ip_allowed),
):
    """Обновляет настройки приложения."""
    logger_adapter = request.state.logger if request else logger
    logger_adapter.info("Обновление настроек приложения")
    try:
        settings_dict = settings_data.model_dump(exclude_unset=True)
        for key, value in settings_dict.items():
            if isinstance(value, list):
                value = ",".join(value)
            elif isinstance(value, (int, bool)):
                value = str(value)
            await repo.update_setting(key, value)
        await settings.load_from_db()
        return {"status": "success", "message": "Настройки успешно обновлены"}
    except Exception as e:
        logger_adapter.error(f"Ошибка обновления настроек: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

app.include_router(router)

if __name__ == "__main__":
    logger.info("Запуск приложения")
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    uvicorn.run(app, host="0.0.0.0", port=settings.server_port)