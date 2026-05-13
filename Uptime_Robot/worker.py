import asyncio
import json
import os
import sys

# Get paths
CONFIG_PATH = os.environ.get("CONFIG_PATH", "/etc/uptime-monitor/config.json")

# Load config to get DB path
with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

DB_PATH = config.get("data_dir", "/var/lib/uptime-monitor")
DB_PATH = os.path.join(DB_PATH, "sites.db")

# Add installation directory to path
INSTALL_DIR = "/opt/uptime-monitor"
sys.path.insert(0, INSTALL_DIR)

# Now import local modules
import models
import monitoring
import state as app_state
from config_manager import load_config
from database import get_db_connection
from logger import logger

NOTIFY_SETTINGS = app_state.NOTIFY_SETTINGS
CHECK_INTERVAL = app_state.CHECK_INTERVAL


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
