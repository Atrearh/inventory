import uuid
import logging
from fastapi import Request, HTTPException, status
from app.utils.security import is_ip_allowed # Імпортуємо нову утиліту

logger = logging.getLogger(__name__)

async def add_correlation_id(request: Request, call_next):
    """Додає унікальний correlation_id для кожного запиту."""
    correlation_id = str(uuid.uuid4())
    # Використовуємо logger, а не створюємо новий адаптер
    request.state.logger = logger
    request.state.correlation_id = correlation_id
    logger.debug(f"Установлено correlation_id {correlation_id} для запиту")
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

    # Використовуємо утиліту для перевірки
    if not is_ip_allowed(client_ip, request.app.state.allowed_ip_networks):
        request_logger.warning(f"Доступ заборонено для IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ заборонено: IP не дозволено"
        )
    return await call_next(request)
