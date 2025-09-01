import ipaddress
import logging
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from .database import get_db_session, init_db, shutdown_db
from .settings import settings
from .settings_manager import SettingsManager
from .logging_config import setup_logging
from .routers import auth, computers, scan, statistics, scripts, domain_router
from .routers.settings import router as settings_router
from .data_collector import script_cache
from .services.encryption_service import get_encryption_service
from .middlewares import add_correlation_id, log_requests, check_ip_allowed
from .exceptions import global_exception_handler
from .utils.security import setup_cors 

logger = logging.getLogger(__name__)
settings_manager = SettingsManager(settings)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Инициализация приложения...")
    try:
        # Ініціалізація IP-діапазонів
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

        # Ініціалізація encryption_service, log_level та завантаження налаштувань
        async with get_db_session() as db:
            await settings_manager.initialize_encryption_key(db)  # Ініціалізує log_level
            await settings_manager.load_from_db(db)  # Завантажуємо налаштування, включаючи log_level
            setup_logging(log_level=settings_manager.log_level)  # Налаштування логування після завантаження
        app.state.encryption_service = get_encryption_service()
        await init_db()

        # Попереднє завантаження скриптів
        await script_cache.preload_scripts()
        logger.info("Все скрипты предварительно загружены в кэш")

        yield
    except Exception as e:
        logger.error(f"Ошибка инициализации приложения: {str(e)}", exc_info=True)
        raise
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

# Настройка CORS за допомогою утиліти
setup_cors(app, settings)

# Подключение маршрутов
app.include_router(auth.router, prefix="/api/auth")
app.include_router(auth.users_router, prefix="/api/users")
app.include_router(computers.router, prefix="/api")
app.include_router(scan.router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(statistics.router, prefix="/api")
app.include_router(scripts.router, prefix="")
app.include_router(domain_router.router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.server_port)