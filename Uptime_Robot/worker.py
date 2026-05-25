import asyncio
import json
import os
import sys

# Add current folder to path to support imports when run directly or in other environments
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now import local modules (supporting both flat and package/relative environments)
try:
    from . import models, monitoring, config_manager
    from . import state as app_state
    from .database import get_db_connection
    from .logger import logger
except ImportError:
    import models
    import monitoring
    import config_manager
    import state as app_state
    from database import get_db_connection
    from logger import logger

DB_PATH = app_state.DB_PATH
NOTIFY_SETTINGS = app_state.NOTIFY_SETTINGS
CHECK_INTERVAL = app_state.CHECK_INTERVAL
CONFIG_PATH = config_manager.CONFIG_PATH


async def initialize_worker():
    """Initialize database and load notification settings"""
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


def run_worker():
    """Entry point for background worker"""
    logger.info("Starting Uptime Monitor Background Worker...")
    logger.info(f"Database: {DB_PATH}")
    logger.info(f"Config: {CONFIG_PATH}")

    asyncio.run(initialize_worker())

    logger.info(f"Starting monitoring loop (interval: {CHECK_INTERVAL}s)...")

    try:
        asyncio.run(monitoring.monitor_loop(NOTIFY_SETTINGS, CHECK_INTERVAL))
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Worker crashed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_worker()
