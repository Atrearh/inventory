# app/exceptions.py

import logging

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

# 👇 Додайте імпорти для специфічних помилок SQLAlchemy
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from winrm.exceptions import WinRMError, WinRMTransportError

from .config import settings
from .schemas import ErrorResponse

logger = logging.getLogger(__name__)
settings_manager = settings


async def global_exception_handler(request: Request, exc: Exception):
    """Глобальний обробник винятків для додатка."""
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    request_logger = (
        request.state.logger if hasattr(request.state, "logger") else logger
    )
    request_logger.error(f"Необроблений виняток: {exc}", exc_info=True)

    match exc:
        case HTTPException(status_code=status_code, detail=detail):
            error_message = detail

        # 👇 Нова, більш детальна обробка помилок БД
        case IntegrityError():
            status_code = (
                status.HTTP_409_CONFLICT
            )  # 409 Conflict - краще підходить для дублікатів
            error_message = "Запис із такими даними вже існує."

        case OperationalError():
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE  # 503 Service Unavailable
            error_message = "Помилка з'єднання з базою даних. Спробуйте пізніше."

        case SQLAlchemyError():  # Залишаємо як загальний обробник для інших помилок БД
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            error_message = "Сталася помилка бази даних."

        case WinRMTransportError() | WinRMError():
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            error_message = "Помилка підключення до WinRM-хоста."

        case ValueError():
            status_code = status.HTTP_400_BAD_REQUEST
            error_message = str(exc)

        case _:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            error_message = "Внутрішня помилка сервера."

    response = ErrorResponse(
        error=error_message,
        detail=(
            str(exc)
            if settings_manager.log_level == "DEBUG"
            else "Деталі помилки приховані"
        ),
        correlation_id=correlation_id,
    )

    headers = {
        "Access-Control-Allow-Origin": request.headers.get("Origin", "*"),
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "*",
    }

    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(exclude_none=True),
        headers=headers,
    )
