import uuid
import logging
from fastapi import Request, HTTPException, status
import ipaddress

logger = logging.getLogger(__name__)

async def add_correlation_id(request: Request, call_next):
    """Добавляет уникальный correlation_id для каждого запроса."""
    correlation_id = str(uuid.uuid4())
    request_logger = logging.LoggerAdapter(logger, {"correlation_id": correlation_id})
    request.state.logger = request_logger
    request.state.correlation_id = correlation_id
    logger.debug(f"Установлен correlation_id: {correlation_id} и logger для запроса")
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response

async def log_requests(request: Request, call_next):
    """Логирует входящие запросы и ответы."""
    request_logger = getattr(request.state, 'logger', logger)
    request_logger.info(f"Запрос: {request.method} {request.url}, headers: {request.headers}")
    response = await call_next(request)
    request_logger.info(f"Ответ: {response.status_code}")
    return response

async def check_ip_allowed(request: Request, call_next):
    """Проверяет, разрешен ли IP-адрес клиента."""
    client_ip = request.client.host
    request_logger = getattr(request.state, 'logger', logger)
    request_logger.debug(f"Проверка IP: {client_ip}")
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
        request_logger.error(f"Неверный формат IP клиента {client_ip}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный IP-адрес клиента")
    
    if not allowed:
        request_logger.warning(f"Доступ запрещен для IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещен: IP не разрешен"
        )
    return await call_next(request)