import os
import sys
import threading
from typing import Optional

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    Fernet = None  # type: ignore[assignment]
    InvalidToken = None  # type: ignore[assignment]

from .logger import logger

MASTER_KEY_FILE = "master.key"
ENC_PREFIX = "__ENC__"


class CryptoUnavailableError(RuntimeError):
    """Raised when a secret cannot be encrypted.

    Encryption MUST fail closed: silently writing a secret in plaintext (only a
    log line) is worse than refusing to persist it, because the caller — and the
    operator — would believe the value is encrypted at rest.
    """
_FERNET_INSTANCE = None
_FERNET_LOCK = threading.Lock()
_SENSITIVE_KEYS = {
    "email_password",
    "password",
    "token",
    "auth_token",
    "api_key",
    "secret",
    "private_key",
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
        logger.info("Master key generated: %s", path)
        return key
    except OSError as e:
        logger.warning("Could not save master key to %s: %s", path, e)
        for alt_path in _get_alternative_key_paths():
            try:
                os.makedirs(os.path.dirname(alt_path) or ".", exist_ok=True)
                with open(alt_path, "w") as f:
                    f.write(key)
                os.chmod(alt_path, 0o600)
                logger.info("Master key saved to alternative path: %s", alt_path)
                return key
            except OSError:
                continue
        logger.error("Failed to save master key to any location. Encryption disabled.")
        return ""


def load_master_key() -> Optional[str]:
    if Fernet is None:
        return None

    # First try loading from environment variable
    env_key = os.environ.get("UPTIME_MONITOR_MASTER_KEY")
    if env_key:
        return env_key.strip()

    search_paths = [_get_master_key_path()] + _get_alternative_key_paths()
    for path in search_paths:
        try:
            if os.path.exists(path) and os.path.getsize(path) > 0:
                with open(path) as f:
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

    with _FERNET_LOCK:
        if _FERNET_INSTANCE is not None:
            return _FERNET_INSTANCE

        key = load_master_key()
        if not key:
            key = generate_master_key()
            if not key:
                return None

        try:
            _FERNET_INSTANCE = Fernet(key.encode())
            return _FERNET_INSTANCE
        except Exception as e:
            logger.error("Failed to initialize Fernet: %s", e)
            return None


def is_sensitive_key(key: str) -> bool:
    lower_key = key.lower()
    return any(sk in lower_key for sk in _SENSITIVE_KEYS)


def encrypt_value(plaintext: str) -> str:
    if not plaintext:
        return plaintext
    f = get_fernet()
    if f is None:
        logger.error(
            "encrypt_value: encryption unavailable — refusing to store secret in plaintext. "
            "Ensure the 'cryptography' package is installed and a master key is writable "
            "(set UPTIME_MONITOR_MASTER_KEY or allow %s to be created).",
            _get_master_key_path(),
        )
        raise CryptoUnavailableError("encryption backend unavailable")
    try:
        return f.encrypt(plaintext.encode()).decode()
    except Exception as e:
        logger.error("Encryption failed: %s", e)
        raise CryptoUnavailableError(f"encryption failed: {e}") from e


def decrypt_value(ciphertext: str) -> str:
    if not ciphertext:
        return ciphertext
    f = get_fernet()
    if f is None:
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.warning("Decryption failed: invalid token")
        return ciphertext
    except Exception as e:
        logger.error("Decryption error: %s", e)
        return ciphertext


def encrypt_config_sensitive(config: dict) -> dict:
    config = config.copy()
    notifications = config.get("notifications", {})
    if notifications.get("email_password"):
        pwd = notifications["email_password"]
        if not pwd.startswith(ENC_PREFIX):
            notifications["email_password"] = ENC_PREFIX + encrypt_value(pwd)
    config["notifications"] = notifications
    return config


# Field names (in notify settings / channels) whose string values are secrets.
_NOTIFY_SECRET_FIELDS = {
    "token",
    "auth_token",
    "webhook_url",
    "password",
    "api_key",
    "secret",
    "account_sid",
}


def _enc_field(value):
    if not isinstance(value, str) or not value or value.startswith(ENC_PREFIX):
        return value
    return ENC_PREFIX + encrypt_value(value)


def _dec_field(value):
    if isinstance(value, str) and value.startswith(ENC_PREFIX):
        return decrypt_value(value[len(ENC_PREFIX) :])
    return value


def _transform_secrets(obj, transform):
    """Recursively transform known secret fields in a notify-settings structure."""
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if k in _NOTIFY_SECRET_FIELDS and isinstance(v, str):
                result[k] = transform(v)
            else:
                result[k] = _transform_secrets(v, transform)
        return result
    if isinstance(obj, list):
        return [_transform_secrets(i, transform) for i in obj]
    return obj


def encrypt_notify_secrets(settings: dict) -> dict:
    """Encrypt all sensitive fields (tokens, webhook URLs, passwords) before persisting."""
    return _transform_secrets(settings, _enc_field)


def decrypt_notify_secrets(settings: dict) -> dict:
    """Decrypt sensitive fields after loading. Plaintext (legacy) values pass through unchanged."""
    return _transform_secrets(settings, _dec_field)


def decrypt_config_sensitive(config: dict) -> dict:
    config = config.copy()
    notifications = config.get("notifications", {})
    pwd = notifications.get("email_password", "")
    if pwd.startswith(ENC_PREFIX):
        notifications["email_password"] = decrypt_value(pwd[len(ENC_PREFIX) :])
    config["notifications"] = notifications

    return config


_CRYPTO_STATUS_LOGGED = False


def init_crypto():
    # init_crypto runs on every config reload; only log the status once per
    # process so the monitor loop doesn't spam the journal every cycle.
    global _CRYPTO_STATUS_LOGGED
    if Fernet is None:
        if not _CRYPTO_STATUS_LOGGED:
            logger.warning(
                "cryptography library not available. Sensitive data stored in plaintext."
            )
            _CRYPTO_STATUS_LOGGED = True
        return

    if _CRYPTO_STATUS_LOGGED:
        return
    _CRYPTO_STATUS_LOGGED = True
    if load_master_key():
        logger.info("Master key found, encryption available.")
    else:
        logger.info("No master key found. Run generate_master_key() to enable encryption.")
