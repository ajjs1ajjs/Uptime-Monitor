"""Модуль для роботи з базою даних"""
import sqlite3
import os
import sys
from contextlib import contextmanager
from typing import Optional


def get_db_path() -> str:
    """Отримує шлях до бази даних з config_manager або з поточної директорії"""
    try:
        import config_manager
        # If init_paths has been called, DB_PATH will be set
        if config_manager.DB_PATH:
            return config_manager.DB_PATH
    except Exception:
        pass
    # Fallback: same directory as this file
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(app_dir, "sites.db")


@contextmanager
def get_db_connection(db_path: Optional[str] = None):
    """Контекстний менеджер для з'єднання з БД"""
    if db_path is None:
        db_path = get_db_path()
        
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db_pool(db_path: Optional[str] = None):
    """Ініціалізує пул з'єднань (заглушка для сумісності)"""
    pass
