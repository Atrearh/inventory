import asyncio
import functools
import logging
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)


def log_function_call(func: Callable) -> Callable:
    """
    Декоратор для логування викликів функцій, їхніх аргументів,
    результатів та часу виконання. Підтримує синхронні та асинхронні функції.
    """

    def _format_args(args: Any, kwargs: Any) -> dict:
        """Форматує аргументи для логування, обмежуючи їх розмір."""
        try:
            # Обмежуємо розмір аргументів для логування
            args_str = str(args)[:1000]
            kwargs_str = str(kwargs)[:1000]
            return {"func_args": args_str, "func_kwargs": kwargs_str}
        except Exception as e:
            logger.warning(f"Помилка форматування аргументів: {e}")
            return {"func_args": "<unformattable>", "func_kwargs": "<unformattable>"}

    @functools.wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.perf_counter()
        func_name = func.__name__
        extra = {"func_name": func_name, **_format_args(args, kwargs)}
        logger.debug(f"Виклик асинхронної функції: {func_name}", extra=extra)
        try:
            result = await func(*args, **kwargs)
            end_time = time.perf_counter()
            logger.debug(
                f"Функція {func_name} завершилася успішно за {end_time - start_time:.4f}с",
                extra={**extra, "execution_time": end_time - start_time},
            )
            return result
        except Exception as e:
            end_time = time.perf_counter()
            logger.error(
                f"Помилка у функції {func_name} після {end_time - start_time:.4f}с: {e}",
                exc_info=True,
                extra={**extra, "execution_time": end_time - start_time},
            )
            raise

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.perf_counter()
        func_name = func.__name__
        extra = {"func_name": func_name, **_format_args(args, kwargs)}
        logger.debug(f"Виклик синхронної функції: {func_name}", extra=extra)
        try:
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            logger.debug(
                f"Функція {func_name} завершилася успішно за {end_time - start_time:.4f}с",
                extra={**extra, "execution_time": end_time - start_time},
            )
            return result
        except Exception as e:
            end_time = time.perf_counter()
            logger.error(
                f"Помилка у функції {func_name} після {end_time - start_time:.4f}с: {e}",
                exc_info=True,
                extra={**extra, "execution_time": end_time - start_time},
            )
            raise

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
