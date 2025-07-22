import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
import sys

def setup_logging(log_level: str = "DEBUG") -> logging.Logger:
    """Налаштовує логування для додатка з використанням стандартного logging.

    Args:
        log_level (str): Рівень логування (NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL).
                        За замовчуванням: DEBUG.

    Returns:
        logging.Logger: Налаштований логер.
    """
    valid_log_levels = {'NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
    log_level = log_level.upper()
    if log_level not in valid_log_levels:
        logging.warning(f"Недопустимий рівень логування: {log_level}. Встановлено рівень за замовчуванням: DEBUG")
        log_level = 'DEBUG'

    # Створюємо директорію для логів
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Форматтер для однострочного виводу
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

    # Налаштування основного логера
    logger = logging.getLogger()
    if logger.handlers:
        logger.handlers.clear()
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.setLevel(getattr(logging, log_level))

    logger.debug("Логування налаштовано з рівнем %s", log_level)
    return logger