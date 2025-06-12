# logging_config.py

from logging.handlers import TimedRotatingFileHandler
import logging
import sys
from .settings import settings

def setup_logging():
    """Налаштовує логування для додатка."""
    logger = logging.getLogger()
    if logger.handlers:
        logger.handlers.clear()
    
    # Валідація рівня логування
    valid_log_levels = {'NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
    log_level = settings.log_level.upper()
    if log_level not in valid_log_levels:
        logger.warning(f"Недопустимый уровень логирования: {log_level}. Установлен уровень по умолчанию: DEBUG")
        log_level = 'DEBUG'
    
    logger.setLevel(getattr(logging, log_level))  # Використовуємо getattr для рівня логування
    
    # Обробник для консолі
    console_handler = logging.StreamHandler(sys.stdout)  # Використовуємо sys.stdout
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s,%(msecs)03d %(levelname)s:%(name)s:%(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(console_handler)
    
    # Обробник для файлу з ротацією
    file_handler = TimedRotatingFileHandler(
        'logs/app.log',
        when='midnight',
        interval=1,
        backupCount=7,  # Зберігати логи за 7 днів
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s,%(msecs)03d %(levelname)s:%(name)s:%(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(file_handler)
    
    return logger