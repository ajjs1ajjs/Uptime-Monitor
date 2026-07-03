"""Standalone background worker process for monitoring.
Run separately from the web server for better isolation.
Usage: python -m Uptime_Robot.worker
"""

import asyncio
import json
import signal
import sys

from . import config_manager, models, monitoring
from . import state as app_state
from .database import close_db, get_db_connection
from .logger import logger

DB_PATH = app_state.DB_PATH
NOTIFY_SETTINGS = app_state.NOTIFY_SETTINGS
CHECK_INTERVAL = app_state.CHECK_INTERVAL
CONFIG_PATH = config_manager.CONFIG_PATH

_worker_loop: asyncio.AbstractEventLoop | None = None
_main_task: "asyncio.Task | None" = None


def _handle_signal(signum, frame):
    logger.info("Received signal %s, shutting down worker...", signum)
    loop = _worker_loop
    task = _main_task
    # Just cancel the main task. Its finally-block performs the cleanup and the
    # coroutine then completes, so run_until_complete returns cleanly. (Calling
    # loop.stop() here would race the still-running cleanup and could leave the
    # DB/session unclosed.)
    if loop and loop.is_running() and task is not None and not task.done():
        loop.call_soon_threadsafe(task.cancel)
    else:
        sys.exit(0)


async def initialize_worker():
    await models.init_database(DB_PATH)
    logger.info("Database initialized")

    from .crypto_utils import decrypt_notify_secrets

    async with get_db_connection() as conn:
        async with conn.execute("SELECT config FROM notify_config WHERE id = 1") as c:
            row = await c.fetchone()
            if row:
                try:
                    loaded = decrypt_notify_secrets(json.loads(row["config"]))
                    NOTIFY_SETTINGS.update(loaded)
                    logger.info("Loaded notification settings from DB")
                except Exception as e:
                    logger.error("Failed to parse notification settings: %s", e)


async def main_async():
    global _main_task
    _main_task = asyncio.current_task()
    await initialize_worker()
    logger.info("Starting monitoring loop...")
    from .telegram_bot import poll_telegram_updates

    poller_task = asyncio.create_task(poll_telegram_updates(lambda: NOTIFY_SETTINGS))
    try:
        await monitoring.monitor_loop(NOTIFY_SETTINGS, CHECK_INTERVAL)
    except asyncio.CancelledError:
        logger.info("Worker shutdown requested, stopping monitoring loop...")
    finally:
        poller_task.cancel()
        try:
            await poller_task
        except (asyncio.CancelledError, Exception):
            pass
        # Cancel any in-flight site-check tasks, then release shared resources.
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for t in pending:
            t.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        from .http_client import close_sessions

        await close_sessions()
        await close_db()


def run_worker():
    global _worker_loop
    logger.info("Starting Uptime Monitor Background Worker...")
    logger.info("Database: %s", DB_PATH)
    logger.info("Config: %s", CONFIG_PATH)
    logger.info("Check interval: %ss", CHECK_INTERVAL)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)
        _worker_loop.run_until_complete(main_async())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except SystemExit:
        logger.info("Worker stopped")
    except Exception as e:
        logger.error("Worker crashed: %s", e)
        sys.exit(1)
    finally:
        try:
            _worker_loop.run_until_complete(close_db())
        except Exception:
            pass
        _worker_loop.close()


if __name__ == "__main__":
    run_worker()
