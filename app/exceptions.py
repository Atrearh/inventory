from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from .schemas import ErrorResponse
from .settings import settings
import logging

logger = logging.getLogger(__name__)

async def global_exception_handler(request: Request, exc: Exception):
    """Глобальний обробник винятків для додатка."""
    correlation_id = getattr(request.state, 'correlation_id', "unknown")
    request_logger = request.state.logger if hasattr(request.state, 'logger') else logger
    request_logger.error(f"Необроблений виняток: {exc}", exc_info=True)

    from winrm.exceptions import WinRMTransportError, WinRMError
    from sqlalchemy.exc import SQLAlchemyError

    match exc:
        case HTTPException(status_code=status_code, detail=detail):
            status_code = status_code
            error_message = detail
        case SQLAlchemyError():
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            error_message = "Помилка бази даних"
        case WinRMTransportError() | WinRMError():
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            error_message = "Помилка підключення до WinRM"
        case ValueError():
            status_code = status.HTTP_400_BAD_REQUEST
            error_message = str(exc)
        case _:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            error_message = "Внутрішня помилка сервера"

    response = ErrorResponse(
        error=error_message,
        detail=str(exc) if settings.log_level == "DEBUG" else "",
        correlation_id=correlation_id
    )

    headers = {
        "Access-Control-Allow-Origin": request.headers.get("Origin", "*"),
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "*"
    }

    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(exclude_none=True),
        headers=headers
    )