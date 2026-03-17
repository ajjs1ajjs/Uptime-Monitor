import os
import socket
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


def get_default_host() -> str:
    """Отримує поточну IP адресу сервера за замовчуванням"""
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        # Якщо localhost, спробуємо отримати зовнішню IP
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
        return "0.0.0.0"


class Settings(BaseSettings):
    """Клас для зберігання та отримання налаштувань з .env файлу"""

    # Application
    app_name: str = "Uptime Monitor"
    app_version: str = "2.0.0"
    debug: bool = False

    # Server
    port: int = 8080
    host: str = "0.0.0.0"  # Буде замінено на get_default_host() якщо не вказано

    # Database
    db_path: str = "sites.db"

    # Monitoring
    check_interval: int = 60
    notification_cooldown: int = 300

    # Authentication
    default_username: str = "admin"
    default_password: str = "admin"
    session_expiry_days: int = 7

    # Notification Settings
    telegram_enabled: bool = False
    telegram_token: str = ""
    telegram_chat_id: str = ""

    teams_enabled: bool = False
    teams_webhook_url: str = ""

    discord_enabled: bool = False
    discord_webhook_url: str = ""

    slack_enabled: bool = False
    slack_webhook_url: str = ""

    email_enabled: bool = False
    email_smtp_server: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_username: str = ""
    email_password: str = ""
    email_to: str = ""

    sms_enabled: bool = False
    sms_account_sid: str = ""
    sms_auth_token: str = ""
    sms_from_number: str = ""
    sms_to_number: str = ""

    # SSL Certificate Settings
    ssl_check_enabled: bool = True
    ssl_notification_days: int = 7
    ssl_critical_days: int = 3
    ssl_warning_days: int = 7

    # Logging
    log_level: str = "INFO"
    log_file: str = "uptime_monitor.log"
    log_max_bytes: int = 10485760
    log_backup_count: int = 5

    # Security
    secret_key: str = "your-secret-key-here"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Отримує кешовану інстанцію налаштувань"""
    settings = Settings()

    # Якщо host не вказано в .env або це значення за замовчуванням, використовуємо поточну IP
    if settings.host == "0.0.0.0":
        settings.host = get_default_host()

    return settings


def get_env_file_path() -> Optional[str]:
    """Отримує шлях до .env файлу"""
    if getattr(__import__("sys"), "frozen", False):
        app_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))

    env_file = os.path.join(app_dir, ".env")
    return env_file if os.path.exists(env_file) else None


def load_env_file() -> None:
    """Завантажує .env файл якщо існує"""
    env_file = get_env_file_path()
    if env_file:
        Settings.Config.env_file = env_file
        get_settings.cache_clear()
        print(f"Loaded environment from: {env_file}")


def get_database_path() -> str:
    """Отримує шлях до бази даних"""
    if getattr(__import__("sys"), "frozen", False):
        return os.path.join(
            os.path.dirname(os.path.abspath(sys.executable)), "sites.db"
        )
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "sites.db")
