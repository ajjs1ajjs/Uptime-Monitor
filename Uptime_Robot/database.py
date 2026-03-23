"""Модуль для роботи з базою даних (Асинхронний)."""

import os
import sys
import aiosqlite
from contextlib import asynccontextmanager
from typing import Optional


def get_db_path() -> str:
    """Отримує шлях до БД з config_manager або з директорії застосунку."""
    try:
        try:
            from . import config_manager
        except ImportError:
            import config_manager

        if config_manager.DB_PATH:
            return config_manager.DB_PATH
    except Exception:
        pass

    if getattr(sys, "frozen", False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(app_dir, "sites.db")


@asynccontextmanager
async def get_db_connection(db_path: Optional[str] = None):
    """Асинхронний менеджер контексту для БД."""
    if db_path is None:
        db_path = get_db_path()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        yield db


def init_db_pool(db_path: Optional[str] = None):
    """Заглушка для сумісності."""
    return None
