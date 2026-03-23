import asyncio
import os
import sys

# Ensure import paths work both when run as a module or as a script
try:
    from . import config_manager, models, monitoring
    from .database import get_db_connection
    from .logger import logger
    from .state import CONFIG, DB_PATH, NOTIFY_SETTINGS, CHECK_INTERVAL
except ImportError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from Uptime_Robot import config_manager, models, monitoring
    from Uptime_Robot.database import get_db_connection
    from Uptime_Robot.logger import logger
    from Uptime_Robot.state import CONFIG, DB_PATH, NOTIFY_SETTINGS, CHECK_INTERVAL

async def initialize_worker():
    """Ініціалізує базу даних і зчитує налаштування для воркера."""
    await models.init_database(DB_PATH)
    import json
    async with get_db_connection() as conn:
        async with conn.execute("SELECT config FROM notify_config WHERE id = 1") as c:
            row = await c.fetchone()
            if row:
                try:
                    NOTIFY_SETTINGS.update(json.loads(row["config"]))
                except:
                    pass

def run_worker():
    """Точка входу для 독립ного воркера (моніторинг-сервісу)."""
    config_manager.init_paths()
    print("Starting standalone background worker for Uptime Monitor...")
    
    # Initialize DB and settings
    asyncio.run(initialize_worker())
    
    # Run the monitor loop
    try:
        asyncio.run(monitoring.monitor_loop(NOTIFY_SETTINGS, CHECK_INTERVAL))
    except KeyboardInterrupt:
        print("Worker stopped manually.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Worker crashed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_worker()
