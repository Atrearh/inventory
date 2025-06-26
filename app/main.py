import signal
import asyncio
import uuid
import logging
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, APIRouter, Request, BackgroundTasks, Query, status
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional
import io
import csv
from winrm.exceptions import WinRMTransportError, WinRMError
from contextlib import asynccontextmanager
from .database import engine, get_db, init_db, shutdown_db
from . import models, schemas
from .settings import settings, Settings
from .services.computer_service import ComputerService
from .repositories.computer_repository import ComputerRepository
from .services.ad_service import ADService
from .repositories.statistics import StatisticsRepository
from .schemas import ErrorResponse, AppSettingUpdate
from .logging_config import setup_logging
import ipaddress
import os
from datetime import datetime

logger = logging.getLogger(__name__)

setup_logging(log_level=settings.log_level)

shutdown_event = asyncio.Event()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управляет жизненным циклом приложения."""
    logger.info("Инициализация приложения...")
    try:
        await init_db()
        yield
    finally:
        logger.info("Завершение работы...")
        await shutdown_db()

app = FastAPI(title="Inventory Management", lifespan=lifespan)
router = APIRouter(prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def signal_handler(sig, frame):
    """Обработчик сигналов завершения."""
    logger.info(f"Получен сигнал {sig}, завершение...")
    shutdown_event.set()

@app.middleware("http")
async def check_ip_allowed(request: Request, call_next):
    """Проверяет, разрешен ли IP клиента."""
    client_ip = request.client.host
    request.state.logger.debug(f"Проверка IP: {client_ip}")
    allowed = False
    for ip_range in settings.allowed_ips_list:
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
    """Добавляет correlation_id к запросу."""
    correlation_id = str(uuid.uuid4())
    request_logger = logging.LoggerAdapter(logger, {"correlation_id": correlation_id})
    request.state.logger = request_logger
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Глобальный обработчик исключений."""
    correlation_id = getattr(request.state, 'correlation_id', "unknown")
    logger = request.state.logger if hasattr(request.state, 'logger') else logging.getLogger(__name__)
    logger.error(f"Необработанное исключение: {exc}, correlation_id={correlation_id}", exc_info=True)

    # Определяем статус код и сообщение об ошибке
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
            error_message = "Внутренняя ошибка сервера"  # Исправляем 'error_file' на 'error_message'

    response = ErrorResponse(
        error=error_message,
        detail=str(exc) if settings.log_level == "DEBUG" else "",
        correlation_id=correlation_id
    )

    # Явно добавляем CORS заголовок для всех ответов
    headers = {
        "Access-Control-Allow-Origin": request.headers.get("Origin", "*"),
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "*"
    }

    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(exclude_none=True),
        headers=headers
    )

@router.get("/settings", response_model=AppSettingUpdate)
async def get_settings():
    """Получает текущие настройки приложения."""
    logger.info("Получение текущих настроек")
    return AppSettingUpdate(
        ad_server_url=settings.ad_server_url,
        domain=settings.domain,
        ad_username=settings.ad_username,
        ad_password="********",
        api_url=settings.api_url,
        test_hosts=settings.test_hosts,
        log_level=settings.log_level,
        scan_max_workers=settings.scan_max_workers,
        polling_days_threshold=settings.polling_days_threshold,
        winrm_operation_timeout=settings.winrm_operation_timeout,
        winrm_read_timeout=settings.winrm_read_timeout,
        winrm_port=settings.winrm_port,
        winrm_server_cert_validation=settings.winrm_server_cert_validation,
        ping_timeout=settings.ping_timeout,
        powershell_encoding=settings.powershell_encoding,
        json_depth=settings.json_depth,
        server_port=settings.server_port,
        cors_allow_origins=settings.cors_allow_origins,
        allowed_ips=settings.allowed_ips,
    )

@router.post("/settings", response_model=dict)
async def update_settings(settings_data: AppSettingUpdate, request: Request):
    """Обновляет настройки приложения."""
    logger_adapter = request.state.logger
    logger_adapter.info("Обновление настроек приложения")
    try:
        env_file = r"app\.env"
        env_vars = {}
        
        # Читаем текущий .env
        if os.path.exists(env_file):
            try:
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            env_vars[key.strip()] = value.strip()
            except Exception as e:
                logger_adapter.error(f"Ошибка чтения .env: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Ошибка чтения .env: {str(e)}")
        else:
            logger_adapter.warning(".env не найден, будет создан новый")

        # Обновляем настройки
        settings_dict = settings_data.model_dump(exclude_unset=True)
        if not settings_dict:
            logger_adapter.error("Не предоставлены данные для обновления настроек")
            raise HTTPException(status_code=400, detail="Не предоставлены данные для обновления")

        for key, value in settings_dict.items():
            if value is not None:
                env_vars[key.upper()] = str(value)

        # Записываем обновленные настройки
        try:
            with open(env_file, 'w', encoding='utf-8') as f:
                for key, value in env_vars.items():
                    f.write(f"{key}={value}\n")
        except Exception as e:
            logger_adapter.error(f"Ошибка записи .env: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка записи .env: {str(e)}")

        global settings
        settings = Settings()
        logger_adapter.info("Настройки успешно обновлены")
        return {"message": "Настройки обновлены"}

    except Exception as e:
        logger_adapter.error(f"Ошибка обновления настроек: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@router.get("/computers/export/csv", response_model=None)
async def export_computers_to_csv(
    db: AsyncSession = Depends(get_db),
    hostname: Optional[str] = Query(None, description="Фильтр по hostname"),
    os_version: Optional[str] = Query(None, description="Фильтр по версии ОС"),
    os_name: Optional[str] = Query(None, description="Фильтр по имени ОС"),
    check_status: Optional[schemas.CheckStatus] = Query(None, description="Фильтр по check_status"),
    sort_by: str = Query("hostname", description="Поле для сортировки"),
    sort_order: str = Query("asc", description="Порядок: asc или desc"),
):
    """Экспортирует список компьютеров в CSV."""
    logger.info(f"Экспорт компьютеров в CSV с параметрами: hostname={hostname}, os_name={os_name}, os_version={os_version}, check_status={check_status}")
    try:
        async with db as session:
            repo = ComputerRepository(session)
            # Получаем все компьютеры без пагинации
            computers, _ = await repo.get_computers(
                hostname=hostname,
                os_name=os_name,
                check_status=check_status,
                sort_by=sort_by,
                sort_order=sort_order,
                page=1,
                limit=10000  # Большое значение, чтобы получить все данные
            )

            # Подготовка CSV с учетом BOM для UTF-8 и явным разделителем ';'
            output = io.StringIO()
            writer = csv.writer(output, delimiter=';', lineterminator='\n', quoting=csv.QUOTE_ALL)
            # Добавляем BOM для корректного отображения кириллицы в Excel
            output.write('\ufeff')
            # Заголовки
            writer.writerow(['IP', 'Назва', 'Процесор', 'RAM', 'MAC', 'Материнська плата', 'Имя ОС', 'Время последней проверки'])
            # Данные, фильтруем пустые записи
            for computer in computers:
                # Проверяем, есть ли хоть одно заполненное поле
                if any([computer.ip, computer.hostname, computer.cpu, computer.ram, computer.mac, computer.motherboard, computer.os_name, computer.last_updated]):
                    writer.writerow([
                        computer.ip or '',
                        computer.hostname or '',
                        computer.cpu or '',
                        str(computer.ram) if computer.ram is not None else '',
                        computer.mac or '',
                        computer.motherboard or '',
                        computer.os_name or '',
                        computer.last_updated.strftime('%Y-%m-%d %H:%M:%S') if computer.last_updated else ''
                    ])

            # Создаем StreamingResponse
            output.seek(0)
            headers = {
                'Content-Disposition': 'attachment; filename="computers.csv"',
                'Content-Type': 'text/csv; charset=utf-8-sig'
            }
            return StreamingResponse(output, headers=headers)

    except Exception as e:
        logger.error(f"Ошибка экспорта компьютеров в CSV: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка сервера")
    
@router.post("/report", response_model=schemas.Computer, operation_id="create_computer_report")
async def create_computer(
    comp_data: schemas.ComputerCreate,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """Создает или обновляет отчет о компьютере."""
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
    """Обновляет статус проверки компьютера."""
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
    """Запускает фоновое сканирование компьютеров."""
    logger_adapter = request.state.logger if request else logger
    task_id = str(uuid.uuid4())
    logger_adapter.info(f"Запуск фонового сканирования с task_id: {task_id}")
    try:
        async with db as session:
            repo = ComputerRepository(session)
            computer_service = ComputerService(db=session, repo=repo)
            background_tasks.add_task(computer_service.run_scan_task, task_id, logger_adapter)
            return {"task_id": task_id}
    except Exception as e:
        logger_adapter.error(f"Ошибка запуска сканирования: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@router.get("/scan/status/{task_id}", response_model=schemas.ScanTask)
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
                logger_adapter.error(f"Задача {task_id} не найдена")
                raise HTTPException(status_code=404, detail="Задача не найдена")
            return db_task
    except Exception as e:
        logger_adapter.error(f"Ошибка получения статуса задачи {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@router.get("/statistics", response_model=schemas.DashboardStats, operation_id="get_statistics")
async def get_statistics(
    metrics: List[str] = Query(None, description="Список метрик для получения статистики"),
    db: AsyncSession = Depends(get_db),
):
    """Получает статистику для дашборда."""
    try:
        async with db as session:
            repo = StatisticsRepository(session)
            if metrics is None:
                metrics = ["total_computers", "os_distribution", "low_disk_space_with_volumes", "last_scan_time", "status_stats"]
            return await repo.get_statistics(metrics)
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@router.get("/computers", response_model=schemas.ComputersResponse, operation_id="get_computers")
async def get_computers(
    hostname: Optional[str] = Query(None),
    os_name: Optional[str] = Query(None),
    check_status: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("hostname", description="Поле для сортировки"),
    sort_order: Optional[str] = Query("asc", description="Порядок сортировки: asc или desc"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    limit: int = Query(10, ge=1, le=100, description="Количество записей на странице"),
    server_filter: Optional[str] = Query(None, description="Фильтр для серверных ОС"),
    db: AsyncSession = Depends(get_db),
):
    """Получение списка компьютеров с фильтрацией и пагинацией."""
    logger.info(f"Запрос списка компьютеров с параметрами: hostname={hostname}, os_name={os_name}, server_filter={server_filter}")
    try:
        async with db as session:
            repo = ComputerRepository(session)
            computers, total = await repo.get_computers(
                hostname=hostname,
                os_name=os_name,
                check_status=check_status,
                sort_by=sort_by,
                sort_order=sort_order,
                page=page,
                limit=limit,
                server_filter=server_filter,
            )
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
    """Запускает фоновое сканирование Active Directory."""
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
    """Очищает старые записи о программном обеспечении."""
    try:
        async with db as session:
            repo = ComputerRepository(session)
            deleted_count = await repo.clean_old_deleted_software()
            return {"message": f"Удалено {deleted_count} записей о ПО"}
    except Exception as e:
        logger.error(f"Ошибка очистки старых записей ПО: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@router.get("/computers/{computer_id}", response_model=schemas.ComputerList, operation_id="get_computer_by_id")
async def get_computer_by_id(
    computer_id: int,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
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