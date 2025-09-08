# app/logging_config.py
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
    logger = logging.getLogger(__name__)
    logger.debug(f"Виклик setup_logging з log_level={log_level}")
    
    if log_level not in valid_log_levels:
        logger.warning(f"Недопустимий рівень логування: {log_level}. Встановлено рівень за замовчуванням: DEBUG")
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
    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(getattr(logging, log_level))

    logger.debug(f"Логування налаштовано з рівнем {log_level}. Поточний рівень: {logging.getLevelName(root_logger.level)}")
    return root_logger

def update_logging_level(log_level: str):
    """Оновлює рівень логування для всіх обробників."""
    valid_log_levels = {'NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
    log_level = log_level.upper()
    logger = logging.getLogger(__name__)
    logger.debug(f"Виклик update_logging_level з log_level={log_level}")
    
    if log_level not in valid_log_levels:
        logger.warning(f"Недопустимий рівень логування: {log_level}. Залишаємо поточний рівень.")
        return
    
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    for handler in root_logger.handlers: 
        handler.setLevel(getattr(logging, log_level))
    logger.info(f"Рівень логування оновлено: {log_level}. Поточний рівень: {logging.getLevelName(root_logger.level)}")