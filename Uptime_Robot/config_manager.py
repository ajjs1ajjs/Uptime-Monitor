import json
import os
import socket
import ssl as ssl_module
import sys
from datetime import datetime

from .crypto_utils import decrypt_config_sensitive, encrypt_config_sensitive, init_crypto
from .logger import logger

# Windows-specific imports (only on Windows)
IS_WINDOWS = sys.platform == "win32"

# Get the application directory (works for both script and compiled EXE)
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.environ.get("CONFIG_PATH")
if not CONFIG_PATH:
    local_path = os.path.join(APP_DIR, "config.json")
    if os.path.exists(local_path):
        CONFIG_PATH = local_path
    else:
        CONFIG_PATH = "/etc/uptime-monitor/config.json"
DB_PATH = ""


def init_paths():
    global CONFIG_PATH, DB_PATH
    if not os.path.exists(CONFIG_PATH) and IS_WINDOWS:
        CONFIG_PATH = os.path.join(
            os.environ.get("USERPROFILE", APP_DIR), "UptimeMonitor", "config.json"
        )
    config = load_config()
    DB_PATH = config.get("data_dir")
    if DB_PATH:
        DB_PATH = os.path.join(DB_PATH, "sites.db")
    else:
        DB_PATH = os.path.join(os.path.dirname(CONFIG_PATH), "sites.db")

    try:
        db_dir = os.path.dirname(DB_PATH)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
    except OSError as e:
        logger.warning("Could not create DB directory: %s", e)


# Default configuration
DEFAULT_CONFIG = {
    "server": {"port": 8080, "host": "auto", "domain": "auto"},
    "cors": {"allow_origins": ["http://localhost:8080"]},
    "ssl": {
        "enabled": False,
        "type": "custom",
        "cert_path": "/etc/uptime-monitor/ssl/cert.pem",
        "key_path": "/etc/uptime-monitor/ssl/key.pem",
        "redirect_http": True,
        "hsts": True,
        "hsts_max_age": 31536000,
    },
    "data_dir": (
        "/var/lib/uptime-monitor"
        if not IS_WINDOWS
        else os.path.join(os.environ.get("USERPROFILE", ""), "UptimeMonitor", "data")
    ),
    "log_dir": (
        "/var/log/uptime-monitor"
        if not IS_WINDOWS
        else os.path.join(os.environ.get("USERPROFILE", ""), "UptimeMonitor", "logs")
    ),
    "check_interval": 60,
    "notifications": {
        "email_enabled": False,
        "email_smtp_server": "",
        "email_smtp_port": 587,
        "email_username": "",
        "email_password": "",
        "email_to": "",
    },
    "alert_policy": {
        "request_timeout_seconds": 30,
        "grace_period_seconds": 0,
        "up_success_threshold": 2,
        "still_down_repeat_seconds": 600,
        "treat_4xx_as_down": True,
        "ssl_notification_days": [30, 14, 7, 5, 3, 1],
        "ssl_notification_cooldown_seconds": 21600,
        "ssl_check_interval_hours": 6,
        "retry_delays": [30, 30],
        "max_retries": 2,
    },
    "backup": {
        "enabled": True,
        "max_backups": 10,
        "backup_dir": (
            "/etc/uptime-monitor/config.backups"
            if not IS_WINDOWS
            else os.path.join(os.environ.get("USERPROFILE", ""), "UptimeMonitor", "config.backups")
        ),
    },
}

DEFAULT_NOTIFY_SETTINGS = {
    "telegram": {
        "enabled": False,
        "channels": [
            {
                "id": "default",
                "name": "Основний",
                "token": "",
                "chat_id": "",
                "message_thread_id": "",
            }
        ],
    },
    "discord": {
        "enabled": False,
        "channels": [{"id": "default", "name": "Основний", "webhook_url": ""}],
    },
    "teams": {
        "enabled": False,
        "channels": [{"id": "default", "name": "Основний", "webhook_url": ""}],
    },
    "email": {
        "enabled": False,
        "smtp_server": "",
        "smtp_port": 587,
        "username": "",
        "password": "",
        "to_email": "",
    },
    "webhook": {
        "enabled": False,
        "channels": [],
    },
}


def get_server_ip():
    """Get the server IP address"""
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip.startswith("127."):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
            except Exception:
                pass
            finally:
                s.close()
        return ip
    except Exception:
        return "0.0.0.0"  # nosec B104


def load_config():
    """Load configuration from file or create default"""
    init_crypto()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                config = json.load(f)

            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
                elif isinstance(value, dict):
                    if not isinstance(config[key], dict):
                        config[key] = value
                    else:
                        for sub_key, sub_value in value.items():
                            if sub_key not in config[key]:
                                config[key][sub_key] = sub_value

            config = decrypt_config_sensitive(config)
            return config
        except Exception as e:
            logger.error("Error loading config: %s", e)
            return DEFAULT_CONFIG.copy()
    else:
        config = DEFAULT_CONFIG.copy()
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except OSError as e:
            logger.warning("Could not create default config: %s", e)
        return config


def save_config(config):
    """Save configuration to file"""
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        encrypted = encrypt_config_sensitive(config)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(encrypted, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error("Error saving config: %s", e)
        return False


_SECRET_KEY_HINTS = (
    "password",
    "token",
    "secret",
    "api_key",
    "auth_token",
    "webhook_url",
    "account_sid",
    "private_key",
)


def _redact_secrets(obj):
    """Recursively replace secret-looking values with '***' for safe logging."""
    if isinstance(obj, dict):
        return {
            k: ("***" if any(h in str(k).lower() for h in _SECRET_KEY_HINTS) and v else _redact_secrets(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact_secrets(i) for i in obj]
    return obj


def log_config_change(config, old_config, new_config, user="system"):
    """Log configuration changes (secrets redacted)"""
    try:
        log_dir = config.get("log_dir", "/var/log/uptime-monitor")
        log_file = os.path.join(log_dir, "config-changes.log")
        os.makedirs(log_dir, exist_ok=True)

        change_entry = {
            "timestamp": datetime.now().isoformat(),
            "user": user,
            "action": "config_changed",
            "changes": {
                "old": _redact_secrets(old_config),
                "new": _redact_secrets(new_config),
            },
        }

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(change_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning("Failed to log config change: %s", e)


def backup_config(config):
    """Create backup of current configuration"""
    try:
        backup_dir = config.get("backup", {}).get(
            "backup_dir", "/etc/uptime-monitor/config.backups"
        )
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_file = os.path.join(backup_dir, f"config.{timestamp}.json")

        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

        # Update symlinks atomically
        latest_link = os.path.join(backup_dir, "config.latest.json")
        prev_link = os.path.join(backup_dir, "config.previous.json")

        try:
            os.replace(latest_link, prev_link)
        except OSError:
            pass

        try:
            if hasattr(os, "symlink"):
                os.symlink(backup_file, latest_link)
            else:
                import shutil

                shutil.copy2(backup_file, latest_link)
        except OSError:
            pass

        max_backups = config.get("backup", {}).get("max_backups", 10)
        backups = sorted(
            f
            for f in os.listdir(backup_dir)
            if f.startswith("config.")
            and f.endswith(".json")
            and not f.endswith(".latest.json")
            and not f.endswith(".previous.json")
        )
        if len(backups) > max_backups:
            for old_backup in backups[:-max_backups]:
                try:
                    os.remove(os.path.join(backup_dir, old_backup))
                except OSError:
                    pass

    except Exception as e:
        logger.error("Backup error: %s", e)


def setup_ssl(config):
    """Setup SSL context"""
    if not config.get("ssl", {}).get("enabled", False):
        return None

    try:
        cert_path = config["ssl"].get("cert_path", "")
        key_path = config["ssl"].get("key_path", "")

        if not os.path.exists(cert_path) or not os.path.exists(key_path):
            logger.warning("SSL certificates not found: %s, %s", cert_path, key_path)
            return None

        ssl_context = ssl_module.create_default_context(ssl_module.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(cert_path, key_path)
        return ssl_context
    except Exception as e:
        logger.error("SSL setup error: %s", e)
        return None


async def https_redirect_middleware(request, call_next, config):
    """Middleware for HTTPS redirect and HSTS"""
    ssl_config = config.get("ssl", {})
    if ssl_config.get("enabled") and ssl_config.get("redirect_http"):
        if request.url.scheme == "http":
            url = request.url.replace(scheme="https")
            from fastapi.responses import RedirectResponse

            return RedirectResponse(url, status_code=301)

    response = await call_next(request)

    if ssl_config.get("enabled") and ssl_config.get("hsts"):
        max_age = ssl_config.get("hsts_max_age", 31536000)
        response.headers["Strict-Transport-Security"] = f"max-age={max_age}; includeSubDomains"

    return response
