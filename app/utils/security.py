import ipaddress
import logging
from typing import List, Union

logger = logging.getLogger(__name__)

def is_ip_allowed(client_ip: str, allowed_ips: List[Union[ipaddress.IPv4Address, ipaddress.IPv4Network]]) -> bool:
    """
    Перевіряє, чи дозволена IP-адреса клієнта.

    Args:
        client_ip: IP-адреса клієнта.
        allowed_ips: Список дозволених IP-адрес та мереж.

    Returns:
        True, якщо IP дозволено, інакше False.
    """
    try:
        client_ip_addr = ipaddress.ip_address(client_ip)
        for ip_or_network in allowed_ips:
            if isinstance(ip_or_network, ipaddress.IPv4Network) and client_ip_addr in ip_or_network:
                return True
            elif client_ip_addr == ip_or_network:
                return True
        return False
    except ValueError:
        logger.warning(f"Невірний формат IP-адреси для перевірки: {client_ip}")
        return False

def setup_cors(app, settings):
    """
    Налаштовує CORS middleware для додатка FastAPI.
    """
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info(f"CORS налаштовано для origins: {settings.cors_allow_origins_list}")
