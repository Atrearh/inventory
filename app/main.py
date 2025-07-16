import asyncio
import ipaddress
import logging
import uvicorn
from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .database import engine, get_db, get_db_session, init_db, shutdown_db
from .settings import settings
from .settings_manager import SettingsManager
from .logging_config import setup_logging
from .routers import auth, computers, scan, statistics, scripts
from .routers.settings import router as settings_router
from .data_collector import script_cache
from .services.encryption_service import EncryptionService
from .middlewares import add_correlation_id, log_requests, check_ip_allowed
from .exceptions import global_exception_handler

logger = logging.getLogger(__name__)
setup_logging(log_level=settings.log_level)
settings_manager = SettingsManager(settings)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Инициализация приложения...")
    try:
        # Инициализация IP-диапазонов
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

        # Инициализация encryption_service и загрузка скриптов
        async with get_db_session() as db:
            await settings_manager.initialize_encryption_key(db)
            await settings_manager.load_from_db(db)
        app.state.encryption_service = EncryptionService(settings.encryption_key)
        await init_db()
        
        # Предварительная загрузка скриптов
        try:
            script_cache.preload_scripts()
            logger.info(f"Все скрипты предварительно загружены в кэш. Кэш: {list(script_cache._cache.keys())}")
        except Exception as e:
            logger.error(f"Ошибка при предварительной загрузке скриптов: {str(e)}", exc_info=True)
            raise

        yield
    finally:
        logger.info("Завершение работы...")
        await shutdown_db()
 
app = FastAPI(title="Inventory Management", lifespan=lifespan)

# Регистрация middleware в правильном порядке
app.middleware("http")(add_correlation_id)
app.middleware("http")(log_requests)
app.middleware("http")(check_ip_allowed)

# Регистрация обработчика исключений
app.exception_handler(Exception)(global_exception_handler)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Зависимость для получения encryption_service
def get_encryption_service(request: Request) -> EncryptionService:
    return request.app.state.encryption_service

# Подключение маршрутов
app.include_router(auth.router, prefix="/auth")
app.include_router(auth.users_router, prefix="/api/users")
app.include_router(computers.router, prefix="/api")
app.include_router(scan.router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(statistics.router, prefix="/api")
app.include_router(scripts.router, prefix="")

if __name__ == "__main__":
    logger.info("Запуск приложения")
    uvicorn.run(app, host="0.0.0.0", port=settings.server_port)