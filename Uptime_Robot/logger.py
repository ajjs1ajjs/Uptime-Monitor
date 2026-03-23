import logging
import sys
from logging.handlers import RotatingFileHandler
import os


def setup_logger(name: str = "uptime_monitor", log_file: str = None) -> logging.Logger:
    """Налаштовує логер з ротацією файлів"""
    
    if log_file is None:
        log_file = os.environ.get("UPTIME_MONITOR_LOG", "uptime_monitor.log")
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Уникаємо дублювання обробників
    if logger.handlers:
        return logger
    
    # Формат логів
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Файл з ротацією (10 МБ, 5 резервних копій)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # Консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


# Глобальний логер
logger = setup_logger()
