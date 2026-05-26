from . import config_manager

# Avoid circular imports by hosting global dynamic states here
config_manager.init_paths()
CONFIG = config_manager.load_config()
DB_PATH = config_manager.DB_PATH
APP_DIR = config_manager.APP_DIR

NOTIFY_SETTINGS = config_manager.DEFAULT_NOTIFY_SETTINGS.copy()
# Merge values from CONFIG if available
if "notifications" in CONFIG:
    for k, v in CONFIG["notifications"].items():
        if k in NOTIFY_SETTINGS and isinstance(v, dict):
             NOTIFY_SETTINGS[k].update(v)

DISPLAY_ADDRESS = ""
SITE_TITLE = "Uptime Monitor"
LOGO_URL = ""
FOOTER_TEXT = ""
PRIMARY_COLOR = "#00ff88"
BRAND_ACCENT_COLOR = "#06b6d4"
CHECK_INTERVAL = CONFIG.get("check_interval", 60)
