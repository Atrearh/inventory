import signal
import asyncio
import uuid
import logging
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, APIRouter, Request, BackgroundTasks, Query, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional
from winrm.exceptions import WinRMTransportError, WinRMError
from contextlib import asynccontextmanager
from .database import engine, get_db, init_db, shutdown_db  # Добавляем shutdown_db
from . import models, schemas
from .settings import settings
from .services.computer_service import ComputerService
from .repositories.computer_repository import ComputerRepository
from .services.ad_service import ADService
from .repositories.statistics import StatisticsRepository
from .schemas import ErrorResponse
from .logging_config import setup_logging
import ipaddress

logger = logging.getLogger(__name__)

setup_logging(log_level=settings.log_level)

shutdown_event = asyncio.Event()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Инициализация приложения...")
    try:
        await init_db()  # Инициализация базы данных
        yield
    finally:
        logger.info("Завершение работы...")
        await shutdown_db()  # Используем shutdown_db для корректного завершения
        tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        logger.info("Все асинхронные задачи завершены")

app = FastAPI(title="Inventory Management", lifespan=lifespan)
router = APIRouter(prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def signal_handler(sig, frame):
    logger.info(f"Получен сигнал {sig}, завершение...")
    shutdown_event.set()

@app.middleware("http")
async def check_ip_allowed(request: Request, call_next):
    """Проверяет, является ли IP-адрес клиента разрешенным."""
    client_ip = request.client.host
    request.state.logger.debug(f"Проверка IP: {client_ip}")
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
            request.state.logger.error(f"Неверный формат IP-диапазона {ip_range}: {str(e)}")
    if not allowed:
        request.state.logger.warning(f"Доступ запрещен для IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещен: IP не разрешен"
        )
    return await call_next(request)

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    correlation_id = str(uuid.uuid4())
    request_logger = logging.LoggerAdapter(logger, {"correlation_id": correlation_id})
    request.state.logger = request_logger
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response

async def get_computer_repository(db: AsyncSession = Depends(get_db)) -> ComputerRepository:
    async with db as session:
        return ComputerRepository(session)

def get_computer_service(repo: ComputerRepository = Depends(get_computer_repository)) -> ComputerService:
    return ComputerService(db=repo.db, repo=repo)

def get_ad_service(repo: ComputerRepository = Depends(get_computer_repository)) -> ADService:
    return ADService(repo)

async def get_statistics_repo(db: AsyncSession = Depends(get_db)) -> StatisticsRepository:
    async with db as session:
        return StatisticsRepository(session)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Глобальный обработчик исключений для централизованного управления ошибками."""
    correlation_id = getattr(request.state, 'correlation_id', "unknown")
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
        content=response.model_dump(exclude_none=True),
        headers={"Access-Control-Allow-Origin": "*"}
    )

@router.post("/report", response_model=schemas.Computer, operation_id="create_computer_report")
async def create_computer(
    comp_data: schemas.ComputerCreate,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """Создает или обновляет данные компьютера."""
    logger_adapter = request.state.logger if request else logger
    logger_adapter.info(f"Получен отчет для hostname: {comp_data.hostname}")
    try:
        async with db as session:
            repo = ComputerRepository(session)
            computer_service = ComputerService(db=session, repo=repo)
            return await computer_service.upsert_computer_from_schema(comp_data, comp_data.hostname)
    except Exception as e:
        logger_adapter.error(f"Ошибка создания/обновления компьютера {comp_data.hostname}: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@router.post("/update_check_status", operation_id="update_computer_check_status")
async def update_check_status(
    data: schemas.ComputerUpdateCheckStatus,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """Обновляет check_status компьютера."""
    logger_adapter = request.state.logger if request else logger
    logger_adapter.info(f"Обновление check_status для {data.hostname}")
    try:
        async with db as session:
            repo = ComputerRepository(session)
            db_computer = await repo.async_update_computer_check_status(data.hostname, data.check_status)
            if not db_computer:
                raise HTTPException(status_code=404, detail="Компьютер не найден")
            return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger_adapter.error(f"Ошибка обновления check_status для {data.hostname}: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@router.get("/history/{computer_id}", response_model=List[schemas.ChangeLog])
async def get_history(
    computer_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Получает историю изменений для компьютера."""
    try:
        async with db as session:
            repo = ComputerRepository(session)
            history = await repo.async_get_change_log(computer_id)
            return history
    except Exception as e:
        logger.error(f"Ошибка получения истории изменений: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@router.post("/scan", response_model=dict, operation_id="start_scan")
async def start_scan(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """Запускает сканирование в фоновом режиме."""
    logger_adapter = request.state.logger if request else logger
    task_id = str(uuid.uuid4())
    logger_adapter.info(f"Запуск фонового сканирования с task_id: {task_id}")
    try:
        async with db as session:
            repo = ComputerRepository(session)
            computer_service = ComputerService(db=session, repo=repo)
            background_tasks.add_task(computer_service.run_scan_task, task_id, logger_adapter)
            return {"status": "success", "task_id": task_id}
    except Exception as e:
        logger_adapter.error(f"Ошибка запуска сканирования: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@router.get("/scan/status/{task_id}", response_model=schemas.ScanTask, operation_id="get_scan_status")
async def scan_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """Получает статус задачи сканирования."""
    logger_adapter = request.state.logger if request else logger
    try:
        async with db as session:
            result = await session.execute(select(models.ScanTask).filter(models.ScanTask.id == task_id))
            db_task = result.scalars().first()
            if not db_task:
                logger_adapter.error(f"Задача с task_id {task_id} не найдена")
                raise HTTPException(status_code=404, detail="Task not found")
            return db_task
    except Exception as e:
        logger_adapter.error(f"Ошибка получения статуса задачи {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@router.get("/statistics", response_model=schemas.DashboardStats, operation_id="get_statistics")
async def get_statistics(
    metrics: List[str] = Query(None, description="Список метрик для получения статистики"),
    db: AsyncSession = Depends(get_db),
):
    """Возвращает статистику для дашборда."""
    try:
        async with db as session:
            repo = StatisticsRepository(session)
            if metrics is None:
                metrics = ["total_computers", "os_versions", "low_disk_space", "last_scan_time", "status_stats"]
            return await repo.get_statistics(metrics)
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка сервера")

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
        async with db as session:
            repo = ComputerRepository(session)
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
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """Запускает сканирование Active Directory в фоновом режиме."""
    logger_adapter = request.state.logger if request else logger
    task_id = str(uuid.uuid4())
    logger_adapter.info(f"Запуск фонового сканирования AD с task_id: {task_id}")
    try:
        async with db as session:
            repo = ComputerRepository(session)
            ad_service = ADService(repo)
            background_tasks.add_task(ad_service.scan_and_update_ad, session)
            return {"status": "success", "task_id": task_id}
    except Exception as e:
        logger_adapter.error(f"Ошибка запуска AD сканирования: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@router.post("/clean-deleted-software/", response_model=dict)
async def clean_deleted_software(
    db: AsyncSession = Depends(get_db),
):
    """Удаляет записи о ПО с is_deleted=True, старше 6 месяцев."""
    try:
        async with db as session:
            repo = ComputerRepository(session)
            deleted_count = await repo.clean_old_deleted_software()
            return {"message": f"Удалено {deleted_count} записей о ПО"}
    except Exception as e:
        logger.error(f"Ошибка очистки старых записей ПО: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@router.get("/computers/{computer_id}", response_model=schemas.Computer, operation_id="get_computer_by_id")
async def get_computer_by_id(
    computer_id: int,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """Возвращает полную информацию о компьютере по ID."""
    logger_adapter = request.state.logger if request else logger
    logger_adapter.info(f"Получение данных компьютера с ID: {computer_id}")
    try:
        async with db as session:
            repo = ComputerRepository(session)
            computer = await repo.async_get_computer_by_id(computer_id)
            if not computer:
                logger_adapter.warning(f"Компьютер с ID {computer_id} не найден")
                raise HTTPException(status_code=404, detail="Компьютер не найден")
            return computer
    except HTTPException:
        raise
    except Exception as e:
        logger_adapter.error(f"Ошибка получения компьютера ID {computer_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка сервера")

app.include_router(router)

if __name__ == "__main__":
    logger.info("Запуск приложения")
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    uvicorn.run(app, host="0.0.0.0", port=settings.server_port)
