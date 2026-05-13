import os
import sys
from typing import Optional

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    Fernet = None
    InvalidToken = None

try:
    from .logger import logger
except ImportError:
    from logger import logger

MASTER_KEY_FILE = "master.key"
_FERNET_INSTANCE = None
_SENSITIVE_KEYS = {
    "email_password", "password", "token", "auth_token",
    "api_key", "secret", "private_key",
}


def _get_master_key_path() -> str:
    app_dir = os.path.dirname(os.path.abspath(__file__))
    if getattr(sys, "frozen", False):
        app_dir = os.path.dirname(sys.executable)
    return os.path.join(app_dir, MASTER_KEY_FILE)


def _get_alternative_key_paths() -> list:
    paths = []
    etc_path = "/etc/uptime-monitor/master.key"
    if sys.platform != "win32":
        paths.append(etc_path)
    user_home = os.environ.get("HOME") or os.environ.get("USERPROFILE", "")
    if user_home:
        paths.append(os.path.join(user_home, ".uptime-monitor-master.key"))
    return paths


def generate_master_key(base_path: Optional[str] = None) -> str:
    if Fernet is None:
        logger.warning("cryptography not installed. Skipping master key generation.")
        return ""

    key = Fernet.generate_key().decode()
    path = base_path or _get_master_key_path()

    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(key)
        os.chmod(path, 0o600)
        logger.info(f"Master key generated: {path}")
        return key
    except OSError as e:
        logger.warning(f"Could not save master key to {path}: {e}")
        for alt_path in _get_alternative_key_paths():
            try:
                os.makedirs(os.path.dirname(alt_path) or ".", exist_ok=True)
                with open(alt_path, "w") as f:
                    f.write(key)
                os.chmod(alt_path, 0o600)
                logger.info(f"Master key saved to alternative path: {alt_path}")
                return key
            except OSError:
                continue
        logger.error("Failed to save master key to any location. Encryption disabled.")
        return ""


def load_master_key() -> Optional[str]:
    if Fernet is None:
        return None

    search_paths = [_get_master_key_path()] + _get_alternative_key_paths()
    for path in search_paths:
        try:
            if os.path.exists(path) and os.path.getsize(path) > 0:
                with open(path, "r") as f:
                    return f.read().strip()
        except OSError:
            continue
    return None


def get_fernet() -> Optional[object]:
    global _FERNET_INSTANCE
    if _FERNET_INSTANCE is not None:
        return _FERNET_INSTANCE

    if Fernet is None:
        return None

    key = load_master_key()
    if not key:
        key = generate_master_key()
        if not key:
            return None

    try:
        _FERNET_INSTANCE = Fernet(key.encode())
        return _FERNET_INSTANCE
    except Exception as e:
        logger.error(f"Failed to initialize Fernet: {e}")
        return None


def is_sensitive_key(key: str) -> bool:
    lower_key = key.lower()
    return any(sk in lower_key for sk in _SENSITIVE_KEYS)


def encrypt_value(plaintext: str) -> str:
    if not plaintext:
        return plaintext
    f = get_fernet()
    if f is None:
        return plaintext
    try:
        return f.encrypt(plaintext.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        return plaintext


def decrypt_value(ciphertext: str) -> str:
    if not ciphertext:
        return ciphertext
    f = get_fernet()
    if f is None:
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except (InvalidToken, Exception):
        return ciphertext


def encrypt_config_sensitive(config: dict) -> dict:
    config = config.copy()
    notifications = config.get("notifications", {})
    if notifications.get("email_password"):
        notifications["email_password"] = (
            "__ENC__" + encrypt_value(notifications["email_password"])
        )
    config["notifications"] = notifications

    notify_settings_keys = ["telegram", "discord", "teams", "slack", "sms"]
    for service_key in notify_settings_keys:
        service = config.get(service_key, {})
        if isinstance(service, dict):
            for k, v in service.items():
                if is_sensitive_key(k) and v and not str(v).startswith("__ENC__"):
                    service[k] = "__ENC__" + encrypt_value(str(v))
        channels = service.get("channels", []) if isinstance(service, dict) else []
        for channel in channels:
            for k, v in channel.items():
                if is_sensitive_key(k) and v and not str(v).startswith("__ENC__"):
                    channel[k] = "__ENC__" + encrypt_value(str(v))

    return config


def decrypt_config_sensitive(config: dict) -> dict:
    config = config.copy()
    notifications = config.get("notifications", {})
    pwd = notifications.get("email_password", "")
    if pwd.startswith("__ENC__"):
        notifications["email_password"] = decrypt_value(pwd[7:])
    config["notifications"] = notifications

    notify_settings_keys = ["telegram", "discord", "teams", "slack", "sms"]
    for service_key in notify_settings_keys:
        service = config.get(service_key, {})
        if isinstance(service, dict):
            for k, v in service.items():
                if isinstance(v, str) and v.startswith("__ENC__"):
                    service[k] = decrypt_value(v[7:])
        channels = service.get("channels", []) if isinstance(service, dict) else []
        for channel in channels:
            for k, v in channel.items():
                if isinstance(v, str) and v.startswith("__ENC__"):
                    channel[k] = decrypt_value(v[7:])

    return config


def init_crypto():
    if Fernet is None:
        logger.warning("cryptography library not available. Sensitive data stored in plaintext.")
        return

    key = load_master_key()
    if key:
        logger.info("Master key found, encryption available.")
    else:
        logger.info("No master key found. Run generate_master_key() to enable encryption.")
