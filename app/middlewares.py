import uuid
import logging
from fastapi import Request, HTTPException, status
import ipaddress

logger = logging.getLogger(__name__)

async def add_correlation_id(request: Request, call_next):
    """Додає унікальний correlation_id для кожного запиту."""
    correlation_id = str(uuid.uuid4())
    request_logger = logger
    request.state.logger = request_logger
    request.state.correlation_id = correlation_id
    request_logger.debug(f"Установлено correlation_id {correlation_id} для запиту")
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response

async def log_requests(request: Request, call_next):
    """Логування вхідних запитів і відповідей."""
    request_logger = getattr(request.state, 'logger', logger)
    request_logger.info(f"Запит: {request.method} {request.url}, headers: {dict(request.headers)}")
    response = await call_next(request)
    request_logger.info(f"Відповідь: {response.status_code}")
    return response

async def check_ip_allowed(request: Request, call_next):
    """Перевіряє, чи дозволено IP-адресу клієнта."""
    client_ip = request.client.host
    request_logger = getattr(request.state, 'logger', logger)
    request_logger.debug(f"Перевірка IP: {client_ip}")
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
        request_logger.error(f"Невірний формат IP клієнта {client_ip}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Невірний IP-адрес клієнта")

    if not allowed:
        request_logger.warning(f"Доступ заборонено для IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ заборонено: IP не дозволено"
        )
    return await call_next(request)