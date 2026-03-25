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
# Import models for database init
import models

# Import monitoring
import monitoring
from config_manager import load_config
from database import get_db_connection

# Import monitoring
import monitoring


async def initialize_worker():
    """Initialize database and load notification settings"""
    # Initialize database tables
    await models.init_database(DB_PATH)
    logger.info("Database initialized")

    # Load notification settings from DB
    async with get_db_connection() as conn:
        async with conn.execute("SELECT config FROM notify_config WHERE id = 1") as c:
            row = await c.fetchone()
            if row:
                try:
                    loaded = json.loads(row["config"])
                    NOTIFY_SETTINGS.update(loaded)
                    logger.info(f"Loaded notification settings from DB")
                except Exception as e:
                    logger.error(f"Failed to parse notification settings: {e}")


def run_worker():
    """Entry point for background worker"""
    print("Starting Uptime Monitor Background Worker...")
    print(f"Database: {DB_PATH}")
    print(f"Config: {CONFIG_PATH}")

    # Initialize
    asyncio.run(initialize_worker())

    print(f"Starting monitoring loop (interval: {CHECK_INTERVAL}s)...")
    logger.info("Worker monitoring loop starting...")

    # Run monitoring
    try:
        asyncio.run(monitoring.monitor_loop(NOTIFY_SETTINGS, CHECK_INTERVAL))
    except KeyboardInterrupt:
        print("Worker stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Worker crashed: {e}")
        sys.exit(1)

        sys.exit(1)

if __name__ == "__main__":
    run_worker()
