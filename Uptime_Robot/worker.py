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
from .database import get_db_connection
from .logger import logger

DB_PATH = app_state.DB_PATH
NOTIFY_SETTINGS = app_state.NOTIFY_SETTINGS
CHECK_INTERVAL = app_state.CHECK_INTERVAL
CONFIG_PATH = config_manager.CONFIG_PATH


def _handle_signal(signum, frame):
    logger.info(f"Received signal {signum}, shutting down worker...")
    sys.exit(0)


async def initialize_worker():
    await models.init_database(DB_PATH)
    logger.info("Database initialized")

    async with get_db_connection() as conn:
        async with conn.execute("SELECT config FROM notify_config WHERE id = 1") as c:
            row = await c.fetchone()
            if row:
                try:
                    loaded = json.loads(row["config"])
                    NOTIFY_SETTINGS.update(loaded)
                    logger.info("Loaded notification settings from DB")
                except Exception as e:
                    logger.error(f"Failed to parse notification settings: {e}")


async def main_async():
    await initialize_worker()
    logger.info("Starting monitoring loop...")
    await monitoring.monitor_loop(NOTIFY_SETTINGS, CHECK_INTERVAL)


def run_worker():
    logger.info("Starting Uptime Monitor Background Worker...")
    logger.info(f"Database: {DB_PATH}")
    logger.info(f"Config: {CONFIG_PATH}")
    logger.info(f"Check interval: {CHECK_INTERVAL}s")

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
        sys.exit(0)
    except SystemExit:
        logger.info("Worker stopped")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Worker crashed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_worker()
