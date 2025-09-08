# app/utils/security.py
import ipaddress
import logging
from typing import List, Union
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

def parse_ip_or_network(ip_str: str) -> Union[ipaddress.IPv4Address, ipaddress.IPv4Network, ipaddress.IPv6Address, ipaddress.IPv6Network]:
    """Парсить IP-адресу або мережу."""
    try:
        if '/' in ip_str:
            return ipaddress.ip_network(ip_str, strict=False)
        return ipaddress.ip_address(ip_str)
    except ValueError as e:
        logger.error(f"Невірний формат IP або діапазону: {ip_str}, помилка: {e}")
        raise ValueError(f"Невірний формат IP або діапазону: {ip_str}")

def validate_allowed_ips(ips_str: str) -> str:
    """Валідує список IP-адрес або діапазонів."""
    logger.debug(f"Валідація ALLOWED_IPS: {ips_str}")
    if not ips_str:
        logger.warning("ALLOWED_IPS порожній")
        return ""
    ips = [ip.strip() for ip in ips_str.split(",") if ip.strip()]
    if not ips:
        logger.warning("ALLOWED_IPS містить лише порожні значення")
        return ""
    for ip in ips:
        parse_ip_or_network(ip)  # Викликаємо для валідації
    logger.info(f"ALLOWED_IPS валідовано успішно: {ips}")
    return ips_str

def is_ip_allowed(client_ip: str, allowed_ips: List[Union[ipaddress.IPv4Address, ipaddress.IPv4Network, ipaddress.IPv6Address, ipaddress.IPv6Network]]) -> bool:
    """
    Перевіряє, чи дозволена IP-адреса клієнта.
    """
    try:
        client_ip_addr = ipaddress.ip_address(client_ip)
        for ip_or_network in allowed_ips:
            if isinstance(ip_or_network, (ipaddress.IPv4Network, ipaddress.IPv6Network)) and client_ip_addr in ip_or_network:
                logger.debug(f"IP {client_ip} дозволено в мережі {ip_or_network}")
                return True
            elif client_ip_addr == ip_or_network:
                logger.debug(f"IP {client_ip} дозволено як окрема адреса")
                return True
        logger.warning(f"IP {client_ip} не дозволено")
        return False
    except ValueError:
        logger.warning(f"Невірний формат IP-адреси для перевірки: {client_ip}")
        return False

def setup_cors(app, settings):
    """
    Налаштовує CORS middleware для додатка FastAPI.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info(f"CORS налаштовано для origins: {settings.cors_allow_origins_list}")