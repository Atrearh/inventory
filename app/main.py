import signal
import asyncio
import uuid
import logging
import uvicorn
import ipaddress
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .database import engine, get_db, init_db, shutdown_db
from .settings import settings
from .logging_config import setup_logging
from .schemas import ErrorResponse
from .routers import auth, computers, scan, statistics, scripts
from .routers.settings import router as settings_router  # Импортируем только роутер
from .data_collector import script_cache

logger = logging.getLogger(__name__)

setup_logging(log_level=settings.log_level)

shutdown_event = asyncio.Event()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Инициализация приложения...")
    try:
        app.state.allowed_ip_networks = []
        for ip_range in settings.allowed_ips_list:
            try:
                if '/' in ip_range:
                    app.state.allowed_ip_networks.append(ipaddress.ip_network(ip_range, strict=False))
                else:
                    app.state.allowed_ip_networks.append(ipaddress.ip_address(ip_range))
            except ValueError as e:
                logger.error(f"Неверный формат IP-диапазона {ip_range}: {str(e)}")
                raise
        await init_db()
        yield
    finally:
        logger.info("Завершение работы...")
        await shutdown_db()

app = FastAPI(title="Inventory Management", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def signal_handler(sig, frame):
    logger.info(f"Получен сигнал {sig}, завершение...")
    shutdown_event.set()

@app.middleware("http")
async def check_ip_allowed(request: Request, call_next):
    client_ip = request.client.host
    request.state.logger.debug(f"Проверка IP: {client_ip}")
    allowed = False
    try:
        client_ip_addr = ipaddress.ip_address(client_ip)
        for ip_or_network in request.app.state.allowed_ip_networks:
            if isinstance(ip_or_network, ipaddress.IPv4Network) and client_ip_addr in ip_or_network:
                allowed = True
                break
            elif client_ip_addr == ip_or_network:
                allowed = True
                break
    except ValueError as e:
        request.state.logger.error(f"Неверный формат IP клиента {client_ip}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный IP-адрес клиента")
    
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

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Запрос: {request.method} {request.url}, headers: {request.headers}")
    response = await call_next(request)
    logger.info(f"Ответ: {response.status_code}")
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    correlation_id = getattr(request.state, 'correlation_id', "unknown")
    logger = request.state.logger if hasattr(request.state, 'logger') else logging.getLogger(__name__)
    logger.error(f"Необработанное исключение: {exc}, correlation_id={correlation_id}", exc_info=True)

    from winrm.exceptions import WinRMTransportError, WinRMError
    from sqlalchemy.exc import SQLAlchemyError

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

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске приложения."""
    logger.info("Запуск приложения...")
    try:
        script_cache.preload_scripts()
        logger.info(f"Все скрипты предварительно загружены в кэш. Кэш: {list(script_cache._cache.keys())}")
    except Exception as e:
        logger.error(f"Ошибка при предварительной загрузке скриптов: {str(e)}", exc_info=True)
        raise  # Поднимаем исключение, чтобы сервер не запускался при ошибке

# Подключение роутеров
app.include_router(auth.router, prefix="/auth")
app.include_router(auth.users_router, prefix="/api/users")
app.include_router(computers.router, prefix="/api")
app.include_router(scan.router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(statistics.router, prefix="/api")
app.include_router(scripts.router, prefix="")

if __name__ == "__main__":
    logger.info("Запуск приложения")
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    uvicorn.run(app, host="0.0.0.0", port=settings.server_port)