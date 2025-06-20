import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

def setup_logging(log_level: str = "DEBUG"):
    """Настраивает логирование для приложения.

    Args:
        log_level (str): Уровень логирования (NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL).
                         По умолчанию: DEBUG.
    """
    logger = logging.getLogger()
    if logger.handlers:
        logger.handlers.clear()

    valid_log_levels = {'NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
    log_level = log_level.upper()
    if log_level not in valid_log_levels:
        logger.warning(f"Недопустимый уровень логирования: {log_level}. Установлен уровень по умолчанию: DEBUG")
        log_level = 'DEBUG'

    logger.setLevel(getattr(logging, log_level))

    # Создать директорию для логов
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s,%(msecs)03d %(levelname)s:%(name)s:%(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(console_handler)

    file_handler = TimedRotatingFileHandler(
        log_dir / 'app.log',
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s,%(msecs)03d %(levelname)s:%(name)s:%(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(file_handler)

    logger.debug("Логирование настроено с уровнем %s", log_level)
    return logger