try:
    from . import config_manager
except ImportError:
    import config_manager

# Initialize paths so DB_PATH is populated correctly before exporting
config_manager.init_paths()

# Avoid circular imports by hosting global dynamic states here
CONFIG = config_manager.load_config()
# Initialize paths so DB_PATH is populated correctly before exporting
config_manager.init_paths()
DB_PATH = config_manager.DB_PATH
APP_DIR = config_manager.APP_DIR

NOTIFY_SETTINGS = config_manager.DEFAULT_NOTIFY_SETTINGS.copy()
# Merge values from CONFIG if available
if "notifications" in CONFIG:
    for k, v in CONFIG["notifications"].items():
        if k in NOTIFY_SETTINGS and isinstance(v, dict):
             NOTIFY_SETTINGS[k].update(v)

DISPLAY_ADDRESS = ""
CHECK_INTERVAL = CONFIG.get("check_interval", 60)
