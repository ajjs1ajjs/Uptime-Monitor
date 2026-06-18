"""Модуль для роботи з базою даних (Асинхронний)."""

import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

import aiosqlite

# Legacy global kept only so close_db() (called from lifespan/worker/restore)
# stays valid. The connection-per-context model below no longer relies on it.
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


async def _configure(db: aiosqlite.Connection) -> None:
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA busy_timeout=30000")
    await db.execute("PRAGMA synchronous=NORMAL")


async def get_db() -> aiosqlite.Connection:
    """Deprecated: повертає глобальне з'єднання (створює при першому виклику).

    Збережено для зворотної сумісності. Новий код має використовувати
    ``get_db_connection()``, що відкриває окреме з'єднання на контекст.
    """
    global _db_connection
    if _db_connection is None:
        _db_connection = await aiosqlite.connect(get_db_path(), timeout=30)
        await _configure(_db_connection)
    return _db_connection


@asynccontextmanager
async def get_db_connection(db_path: Optional[str] = None) -> AsyncIterator[aiosqlite.Connection]:
    """Async context manager that yields a dedicated SQLite connection.

    A fresh connection is opened per ``with`` block (and closed on exit) instead
    of sharing one process-wide connection across all concurrent coroutines.
    Under WAL mode this is the safe, standard pattern: readers never block and
    writers serialize via ``busy_timeout``. It also matches what the hot write
    path (``check_site_status``) has always done with an explicit ``db_path``.
    """
    path = db_path or get_db_path()
    async with aiosqlite.connect(path, timeout=30) as db:
        await _configure(db)
        yield db


async def close_db():
    """Закриває застаріле глобальне з'єднання (якщо було створене)."""
    global _db_connection
    if _db_connection is not None:
        await _db_connection.close()
        _db_connection = None
