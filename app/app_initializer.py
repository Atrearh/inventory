# app/app_initializer.py
import ipaddress
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .config import settings
from .data_collector import script_cache
from .database import get_db_session, init_db, shutdown_db
from .dependencies import get_winrm_service
from .services.encryption_service import get_encryption_service

logger = logging.getLogger(__name__)


class AppInitializer:
    """Клас для ініціалізації додатка."""

    def __init__(self, app: FastAPI):
        self.app = app
        self.settings_manager = settings
        # Синхронна ініціалізація IP-діапазонів
        self._initialize_ip_networks_sync()

    def _initialize_ip_networks_sync(self):
        """Синхронно ініціалізує дозволені IP-діапазони."""
        logger.info("Синхронна ініціалізація дозволених IP-діапазонів...")
        self.app.state.allowed_ip_networks = []
        allowed_ips_list = self.settings_manager.allowed_ips_list
        logger.debug(f"ALLOWED_IPS_LIST: {allowed_ips_list}")
        if not allowed_ips_list:
            logger.warning("ALLOWED_IPS не задано, дозволено всі IP-адреси")
            return
        for ip_range in allowed_ips_list:
            try:
                if "/" in ip_range:
                    network = ipaddress.ip_network(ip_range, strict=False)
                    self.app.state.allowed_ip_networks.append(network)
                    logger.debug(f"Додано IP-мережу: {network}")
                else:
                    address = ipaddress.ip_address(ip_range)
                    self.app.state.allowed_ip_networks.append(address)
                    logger.debug(f"Додано IP-адресу: {address}")
            except ValueError as e:
                logger.error(f"Невірний формат IP-діапазону {ip_range}: {str(e)}")
                continue
        logger.info(f"Ініціалізовано {len(self.app.state.allowed_ip_networks)} IP-діапазонів: {self.app.state.allowed_ip_networks}")

    async def initialize(self):
        logger.info("Асинхронна ініціалізація додатка...")
        try:
            # Ініціалізація налаштувань
            async with get_db_session() as db:
                await self.settings_manager.initialize_settings(db)

            # Ініціалізація encryption_service
            self.app.state.encryption_service = get_encryption_service()

            # Ініціалізація бази даних
            await init_db()

            # Ініціалізація WinRMService
            self.app.state.winrm_service = await get_winrm_service(self.app)

            # Попереднє завантаження скриптів
            await script_cache.preload_scripts()
            # Більше тут нічого не потрібно, setup_logging вже був викликаний
        except Exception as e:
            logger.error(f"Помилка асинхронної ініціалізації додатка: {str(e)}", exc_info=True)
            raise

    async def shutdown(self):
        """Завершує роботу додатка."""
        logger.info("Завершення роботи...")
        await shutdown_db()

    @asynccontextmanager
    async def lifespan(self):
        """Контекстний менеджер для життєвого циклу додатка."""
        await self.initialize()
        yield
        await self.shutdown()
