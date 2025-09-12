# app/main.py
import uvicorn
from fastapi import FastAPI
from .app_initializer import AppInitializer
from .utils.security import setup_cors
from .config import settings
from .routers import auth, computers, scan, statistics, scripts, domain_router, tasks
from .routers.settings import router as settings_router
from .exceptions import global_exception_handler
from .middlewares import register_middlewares
from .logging_config import setup_logging 


setup_logging(log_level="DEBUG")

app = FastAPI(title="Inventory Management")

# Реєстрація middleware
register_middlewares(app)

# Налаштування CORS
setup_cors(app, settings)

# Реєстрація обробника винятків
app.exception_handler(Exception)(global_exception_handler)

# Підключення маршрутів
app.include_router(auth.router, prefix="/api/auth")
app.include_router(auth.users_router, prefix="/api/users")
app.include_router(computers.router, prefix="/api")
app.include_router(scan.router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(statistics.router, prefix="/api")
app.include_router(scripts.router)
app.include_router(domain_router.router)
app.include_router(tasks.router)

# Ініціалізація додатка
initializer = AppInitializer(app)
app.lifespan = initializer.lifespan

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.server_port)