import json
import os
import socket
import ssl as ssl_module
import sys
from datetime import datetime

# Windows-specific imports (only on Windows)
IS_WINDOWS = sys.platform == "win32"

# Get the application directory (works for both script and compiled EXE)
if getattr(sys, "frozen", False):
    # Running as compiled EXE
    APP_DIR = os.path.dirname(sys.executable)
else:
    # Running as script
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Configuration paths
CONFIG_PATH = os.environ.get("CONFIG_PATH", "/etc/uptime-monitor/config.json")
DB_PATH = ""  # Will be set in init_paths


def init_paths():
    global CONFIG_PATH, DB_PATH
    if not os.path.exists(CONFIG_PATH) and IS_WINDOWS:
        CONFIG_PATH = os.path.join(
            os.environ.get("USERPROFILE", APP_DIR), "UptimeMonitor", "config.json"
        )
    DB_PATH = os.path.join(os.path.dirname(CONFIG_PATH), "sites.db")
    if IS_WINDOWS and not os.path.exists(os.path.dirname(CONFIG_PATH)):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)


# Default configuration
DEFAULT_CONFIG = {
    "server": {"port": 8080, "host": "auto", "domain": "auto"},
    "ssl": {
        "enabled": False,
        "type": "custom",
        "cert_path": "/etc/uptime-monitor/ssl/cert.pem",
        "key_path": "/etc/uptime-monitor/ssl/key.pem",
        "redirect_http": True,
        "hsts": True,
        "hsts_max_age": 31536000,
    },
    "data_dir": "/var/lib/uptime-monitor"
    if not IS_WINDOWS
    else os.path.join(os.environ.get("USERPROFILE", ""), "UptimeMonitor", "data"),
    "log_dir": "/var/log/uptime-monitor"
    if not IS_WINDOWS
    else os.path.join(os.environ.get("USERPROFILE", ""), "UptimeMonitor", "logs"),
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
        "request_timeout_seconds": 60,
        "down_failures_threshold": 1,
        "up_success_threshold": 1,
        "still_down_repeat_seconds": 600,
        "treat_4xx_as_down": True,
        "ssl_notification_days": 7,
        "ssl_notification_cooldown_seconds": 21600,
        "ssl_check_interval_hours": 6,
    },
    "backup": {
        "enabled": True,
        "max_backups": 10,
        "backup_dir": "/etc/uptime-monitor/config.backups"
        if not IS_WINDOWS
        else os.path.join(
            os.environ.get("USERPROFILE", ""), "UptimeMonitor", "config.backups"
        ),
    },
}

DEFAULT_NOTIFY_SETTINGS = {
    "telegram": {
        "enabled": False,
        "channels": [{"id": "default", "name": "Основний", "token": "", "chat_id": ""}],
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
}


def get_server_ip():
    """Get the server IP address"""
    try:
        # Get all network interfaces
        hostname = socket.gethostname()
        # Get IP from hostname
        ip = socket.gethostbyname(hostname)
        # If it's localhost, try to get external IP
        if ip.startswith("127."):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
            except:
                pass
            finally:
                s.close()
        return ip
    except:
        return "0.0.0.0"


def load_config():
    """Load configuration from file or create default"""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
            # Merge with defaults to ensure all keys exist
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
            return config
        except Exception as e:
            print(f"Error loading config: {e}")
            return DEFAULT_CONFIG.copy()
    else:
        config = DEFAULT_CONFIG.copy()
        # Create default config file
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except:
            pass
        return config


def save_config(config):
    """Save configuration to file"""
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False


def log_config_change(config, old_config, new_config, user="system"):
    """Log configuration changes"""
    try:
        log_dir = config.get("log_dir", "/var/log/uptime-monitor")
        log_file = os.path.join(log_dir, "config-changes.log")
        os.makedirs(log_dir, exist_ok=True)

        change_entry = {
            "timestamp": datetime.now().isoformat(),
            "user": user,
            "action": "config_changed",
            "changes": {"old": old_config, "new": new_config},
        }

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(change_entry, ensure_ascii=False) + "\n")
    except:
        pass


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

        # Update symlinks
        latest_link = os.path.join(backup_dir, "config.latest.json")
        prev_link = os.path.join(backup_dir, "config.previous.json")

        if os.path.exists(latest_link):
            if os.path.exists(prev_link):
                try:
                    os.remove(prev_link)
                except:
                    pass
            try:
                os.rename(latest_link, prev_link)
            except:
                pass

        if os.path.exists(latest_link):
            try:
                os.remove(latest_link)
            except:
                pass

        try:
            if hasattr(os, "symlink"):
                os.symlink(backup_file, latest_link)
            else:
                # Fallback for systems without symlink support (Windows without admin)
                import shutil

                shutil.copy2(backup_file, latest_link)
        except:
            pass

        # Clean old backups
        max_backups = config.get("backup", {}).get("max_backups", 10)
        backups = sorted(
            [
                f
                for f in os.listdir(backup_dir)
                if f.startswith("config.")
                and f.endswith(".json")
                and not f.endswith(".latest.json")
                and not f.endswith(".previous.json")
            ]
        )
        if len(backups) > max_backups:
            for old_backup in backups[:-max_backups]:
                try:
                    os.remove(os.path.join(backup_dir, old_backup))
                except:
                    pass

    except Exception as e:
        print(f"Backup error: {e}")


def setup_ssl(config):
    """Setup SSL context"""
    if not config.get("ssl", {}).get("enabled", False):
        return None

    try:
        cert_path = config["ssl"].get("cert_path", "")
        key_path = config["ssl"].get("key_path", "")

        if not os.path.exists(cert_path) or not os.path.exists(key_path):
            print(f"SSL certificates not found: {cert_path}, {key_path}")
            return None

        ssl_context = ssl_module.create_default_context(ssl_module.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(cert_path, key_path)
        return ssl_context
    except Exception as e:
        print(f"SSL setup error: {e}")
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
        response.headers["Strict-Transport-Security"] = (
            f"max-age={max_age}; includeSubDomains"
        )

    return response
