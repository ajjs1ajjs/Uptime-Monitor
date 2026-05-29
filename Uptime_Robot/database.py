"""Модуль для роботи з базою даних (Асинхронний)."""

import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

import aiosqlite

_db_connection: Optional[aiosqlite.Connection] = None


def get_db_path() -> str:
    """Отримує шлях до БД з config_manager або з директорії застосунку."""
    try:
        from . import config_manager

        if config_manager.DB_PATH:
            return config_manager.DB_PATH
    except Exception:
        pass

    if getattr(sys, "frozen", False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(app_dir, "sites.db")


async def get_db() -> aiosqlite.Connection:
    """Повертає глобальне з'єднання (створює при першому виклику)."""
    global _db_connection
    if _db_connection is None:
        db_path = get_db_path()
        _db_connection = await aiosqlite.connect(db_path)
        _db_connection.row_factory = aiosqlite.Row
    return _db_connection


@asynccontextmanager
async def get_db_connection(db_path: Optional[str] = None) -> AsyncIterator[aiosqlite.Connection]:
    """Асинхронний менеджер контексту для БД (single connection)."""
    if db_path is not None:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            yield db
    else:
        conn = await get_db()
        yield conn


async def close_db():
    """Закриває глобальне з'єднання."""
    global _db_connection
    if _db_connection is not None:
        await _db_connection.close()
        _db_connection = None
