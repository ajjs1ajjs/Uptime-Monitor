"""Global application state."""
from __future__ import annotations

from typing import Any

from . import config_manager

config_manager.init_paths()
CONFIG: dict[str, Any] = config_manager.load_config()
DB_PATH: str = config_manager.DB_PATH
APP_DIR: str = config_manager.APP_DIR

NOTIFY_SETTINGS: dict[str, Any] = config_manager.DEFAULT_NOTIFY_SETTINGS.copy()
if "notifications" in CONFIG:
    for k, v in CONFIG["notifications"].items():
        if k in NOTIFY_SETTINGS and isinstance(v, dict):
            NOTIFY_SETTINGS[k].update(v)

DISPLAY_ADDRESS: str = ""
SITE_TITLE: str = "Uptime Monitor"
LOGO_URL: str = ""
FOOTER_TEXT: str = ""
PRIMARY_COLOR: str = "#00ff88"
BRAND_ACCENT_COLOR: str = "#06b6d4"
CHECK_INTERVAL: int = CONFIG.get("check_interval", 60)

_initialized: bool = False


def init_state() -> None:
    """Reinitialize state (used by tests to reset)."""
    global _initialized, CONFIG, DB_PATH, APP_DIR, NOTIFY_SETTINGS, CHECK_INTERVAL
    config_manager.init_paths()
    cfg = config_manager.load_config()
    CONFIG.clear()
    CONFIG.update(cfg)
    DB_PATH = config_manager.DB_PATH
    APP_DIR = config_manager.APP_DIR
    NOTIFY_SETTINGS.clear()
    NOTIFY_SETTINGS.update(config_manager.DEFAULT_NOTIFY_SETTINGS.copy())
    if "notifications" in CONFIG:
        for k, v in CONFIG["notifications"].items():
            if k in NOTIFY_SETTINGS and isinstance(v, dict):
                NOTIFY_SETTINGS[k].update(v)
    CHECK_INTERVAL = int(CONFIG.get("check_interval", 60))
    _initialized = True
