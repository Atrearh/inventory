import structlog
from structlog.stdlib import LoggerFactory
from structlog.processors import TimeStamper, JSONRenderer
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
import logging

def setup_logging(log_level: str = "DEBUG"):
    """Налаштовує логування для додатка з використанням structlog.

    Args:
        log_level (str): Рівень логування (NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL).
                         За замовчуванням: DEBUG.
    """
    valid_log_levels = {'NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
    log_level = log_level.upper()
    if log_level not in valid_log_levels:
        structlog.get_logger().warning(f"Недопустимий рівень логування: {log_level}. Встановлено рівень за замовчуванням: DEBUG")
        log_level = 'DEBUG'

    # Налаштування structlog
    structlog.configure(
        processors=[
            TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.UnicodeDecoder(),
            JSONRenderer(ensure_ascii=False)  # Убрали indent для однострочного JSON
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Створюємо директорію для логів
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Форматтер для однострочного вывода
    log_formatter = logging.Formatter(
        '%(asctime)s,%(msecs)03d %(levelname)s:%(name)s:%(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Налаштування обробника для консолі
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(log_formatter)

    # Налаштування обробника для файлу з ротацією
    file_handler = TimedRotatingFileHandler(
        log_dir / 'app.log',
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, log_level))
    file_handler.setFormatter(log_formatter)

    # Додаємо обробники до стандартного логера, який використовується structlog
    stdlib_logger = logging.getLogger()
    if stdlib_logger.handlers:
        stdlib_logger.handlers.clear()
    stdlib_logger.addHandler(console_handler)
    stdlib_logger.addHandler(file_handler)
    stdlib_logger.setLevel(getattr(logging, log_level))

    structlog.get_logger().debug("Логування налаштовано з рівнем %s", log_level)
    return structlog.get_logger(__name__)