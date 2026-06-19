import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt

from .database import get_db_connection
from .logger import logger


def _encrypt_password(plaintext: str) -> str:
    try:
        from .crypto_utils import encrypt_value

        result = encrypt_value(plaintext)
        return result or ""
    except Exception:
        return ""


def _decrypt_password(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        from .crypto_utils import decrypt_value

        result = decrypt_value(ciphertext)
        return result or ""
    except Exception:
        return ""


def _save_credentials_file(password: str):
    try:
        paths = ["/etc/uptime-monitor/credentials.txt"]
        if os.name == "nt":
            app_dir = os.path.dirname(os.path.abspath(__file__))
            paths = [
                os.path.join(app_dir, "credentials.txt"),
                os.path.join(os.environ.get("USERPROFILE", ""), "UptimeMonitor", "credentials.txt"),
            ]

        for path in paths:
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as f:
                    f.write(f"Admin password: {password}\n")
                    f.write("Username: admin\n")
                if os.name != "nt":
                    os.chmod(path, 0o600)
                else:
                    _restrict_windows_acl(path)
            except Exception:
                continue
    except Exception:
        pass


def _restrict_windows_acl(path: str) -> None:
    """Best-effort: lock a plaintext-credentials file down to the current user.

    POSIX uses chmod 0o600; on Windows files inherit the parent directory ACL,
    which may be broader than intended, so strip inheritance and grant only the
    current user. Failures are non-fatal (the file is still written).
    """
    try:
        import getpass
        import subprocess

        user = os.environ.get("USERNAME") or getpass.getuser()
        if not user:
            return
        subprocess.run(
            ["icacls", path, "/inheritance:r", "/grant:r", f"{user}:F"],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except Exception:
        pass


async def init_auth_tables(db_path):
    async with get_db_connection(db_path) as conn:
        await conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'viewer',
            must_change_password BOOLEAN DEFAULT 0,
            created_at TEXT,
            last_login TEXT
        )""")

        await conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id INTEGER,
            created_at TEXT,
            expires_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )""")

        await conn.execute("""CREATE TABLE IF NOT EXISTS api_keys (
            key_id TEXT PRIMARY KEY,
            user_id INTEGER,
            name TEXT NOT NULL,
            key_hash TEXT NOT NULL,
            created_at TEXT,
            last_used_at TEXT,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )""")

        # Migration: force password change for existing users with old (non-bcrypt) passwords
        await conn.execute(
            """UPDATE users SET must_change_password = 1
            WHERE (password_hash NOT LIKE '$%') AND (must_change_password IS NULL OR must_change_password = 0)"""
        )

        # Migration: add password_encrypted column
        try:
            async with conn.execute("PRAGMA table_info(users)") as c:
                cols = {r[1] for r in await c.fetchall()}
            if "password_encrypted" not in cols:
                await conn.execute("ALTER TABLE users ADD COLUMN password_encrypted TEXT")
        except Exception:
            pass

        async with conn.execute(
            "SELECT id, must_change_password, password_encrypted FROM users WHERE username = 'admin'"
        ) as c:
            admin_row = await c.fetchone()

        if not admin_row:
            # Generate random password (or use env var for testing)
            default_password = os.environ.get(
                "UPTIME_MONITOR_ADMIN_PASSWORD"
            ) or secrets.token_urlsafe(12)
            password_hash = hash_password(default_password)

            # Try to encrypt backup
            encrypted = _encrypt_password(default_password)
            await conn.execute(
                "INSERT INTO users (username, password_hash, role, must_change_password, created_at, password_encrypted) VALUES (?, ?, 'admin', 0, ?, ?)",
                ("admin", password_hash, datetime.now(timezone.utc).isoformat(), encrypted),
            )
            _save_credentials_file(default_password)

            # The generated password is shown ONCE on stdout (the operator needs
            # it for first login) and saved to the protected credentials file.
            # It is deliberately NOT written to the application logger, which
            # ends up in journald/Docker logs/log files.
            msg = f"\n{'='*50}\nDEFAULT ADMIN USER CREATED\nUsername: admin\nPassword: {default_password}\n{'='*50}\n"
            logger.info("Default admin user created (password printed once to stdout, not logged)")
            print(msg)
        else:
            # Never re-print the stored password on restart — that would leak it
            # into the journal on every service start. Use the `show-password`
            # CLI command for on-demand recovery instead.
            logger.info("Admin user 'admin' already exists")
            print("\n[OK] Admin user 'admin' already exists\n")

        # Note: legacy admin passwords cannot be recovered into the encrypted
        # backup because only the bcrypt hash is stored. Such accounts will
        # report "no password backup" until the admin changes the password.

        await conn.commit()


def hash_password(password: str) -> str:
    """Хешує пароль використовуючи bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Перевіряє пароль проти хешу"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


async def create_session(user_id: int, db_path: str) -> str:
    """Створює сесію і повертає session_id"""
    session_id = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=7)

    async with get_db_connection(db_path) as conn:
        await conn.execute(
            "INSERT INTO sessions (session_id, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (session_id, user_id, now.isoformat(), expires.isoformat()),
        )
        await conn.execute(
            "UPDATE users SET last_login = ? WHERE id = ?", (now.isoformat(), user_id)
        )
        await conn.commit()

    return session_id


async def validate_session(session_id: str, db_path: str) -> dict:
    """Перевіряє сесію і повертає дані користувача"""
    if not session_id:
        return None

    async with get_db_connection(db_path) as conn:
        async with conn.execute(
            """
            SELECT s.user_id, u.username, u.role, u.must_change_password, s.expires_at
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.session_id = ?
            """,
            (session_id,),
        ) as c:
            row = await c.fetchone()

    if not row:
        return None

    expires = datetime.fromisoformat(row["expires_at"])
    now = datetime.now(timezone.utc)
    if now > expires:
        return None

    # Продовжити сесію, якщо залишилось менше 24 годин
    if (expires - now).total_seconds() < 86400:
        async with get_db_connection(db_path) as conn:
            new_expires = now + timedelta(days=7)
            await conn.execute(
                "UPDATE sessions SET expires_at = ? WHERE session_id = ?",
                (new_expires.isoformat(), session_id),
            )
            await conn.commit()

    return {
        "user_id": row["user_id"],
        "username": row["username"],
        "role": row["role"],
        "must_change_password": row["must_change_password"],
    }


async def delete_session(session_id: str, db_path: str):
    """Видаляє сесію (logout)"""
    async with get_db_connection(db_path) as conn:
        await conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        await conn.commit()


async def cleanup_expired_sessions(db_path: str) -> None:
    """Delete sessions whose expires_at is in the past.

    validate_session already rejects expired sessions but never removes them, so
    the table would otherwise grow without bound.
    """
    try:
        now = datetime.now(timezone.utc).isoformat()
        async with get_db_connection(db_path) as conn:
            await conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
            await conn.commit()
    except Exception as e:
        logger.error("Expired session cleanup failed: %s", e)


async def delete_user_sessions(user_id: int, db_path: str) -> None:
    """Delete ALL sessions for a user (used after a password change/reset)."""
    async with get_db_connection(db_path) as conn:
        await conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        await conn.commit()


async def change_password(user_id: int, new_password: str, db_path: str) -> bool:
    """Змінює пароль користувача.

    Invalidates every existing session for the user: a password change/reset
    must evict any other (possibly compromised) live session. The caller that
    represents the acting user should mint a fresh session afterwards.
    """
    try:
        async with get_db_connection(db_path) as conn:
            password_hash = hash_password(new_password)
            encrypted = _encrypt_password(new_password)
            await conn.execute(
                "UPDATE users SET password_hash = ?, password_encrypted = ?, must_change_password = 0 WHERE id = ?",
                (password_hash, encrypted or None, user_id),
            )
            await conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            await conn.commit()
        _save_credentials_file(new_password)
        return True
    except Exception as e:
        logger.error("Error changing password: %s", e)
        return False


def validate_password_strength(password: str) -> tuple:
    """Validate password strength. Returns (is_valid, error_message)."""
    if len(password) < 12:
        return False, "Password must be at least 12 characters long"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"
    return True, ""


# Role checking functions
def has_role(user: dict, required_role: str) -> bool:
    """Check if user has at least the required role."""
    if not user:
        return False

    role = user.get("role", "viewer")

    if role == "admin":
        return True

    return role == required_role


def is_admin(user: dict) -> bool:
    """Check if user is admin"""
    return has_role(user, "admin")


def is_viewer_or_higher(user: dict) -> bool:
    """Check if user is viewer or higher"""
    if not user:
        return False
    return user.get("role") in ["admin", "viewer"]


async def create_user(db_path: str, username: str, password: str, role: str = "viewer") -> bool:
    """Create a new user with specified role"""
    is_valid, err = validate_password_strength(password)
    if not is_valid:
        logger.error("Cannot create user '%s': %s", username, err)
        return False
    try:
        async with get_db_connection(db_path) as conn:
            password_hash = hash_password(password)
            try:
                await conn.execute(
                    "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                    (username, password_hash, role, datetime.now(timezone.utc).isoformat()),
                )
                await conn.commit()
                return True
            except Exception as e:
                logger.error("Error creating user db: %s", e)
                return False
    except Exception as e:
        logger.error("Error creating user: %s", e)
        return False


async def update_user_role(db_path: str, username: str, new_role: str) -> tuple:
    """Update user role. Returns (success, error_message).

    Refuses to demote the last remaining admin — doing so would lock everyone
    out of admin-only functions (there is no self-signup), mirroring the guard
    in ``delete_user``.
    """
    try:
        async with get_db_connection(db_path) as conn:
            async with conn.execute("SELECT role FROM users WHERE username = ?", (username,)) as c:
                user_row = await c.fetchone()
            if not user_row:
                return (False, "User not found")

            if user_row["role"] == "admin" and new_role != "admin":
                async with conn.execute(
                    "SELECT COUNT(*) FROM users WHERE role = 'admin'"
                ) as c:
                    admin_count = (await c.fetchone())[0]
                if admin_count <= 1:
                    return (False, "Cannot demote the last admin user")

            await conn.execute("UPDATE users SET role = ? WHERE username = ?", (new_role, username))
            await conn.commit()
            return (True, None)
    except Exception as e:
        logger.error("Error updating user role: %s", e)
        return (False, str(e))


async def delete_user(db_path: str, username: str) -> tuple:
    """Delete a user (cannot delete last admin)"""
    try:
        async with get_db_connection(db_path) as conn:
            async with conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'") as c:
                row = await c.fetchone()
                admin_count = row[0]

            async with conn.execute("SELECT role FROM users WHERE username = ?", (username,)) as c:
                user_row = await c.fetchone()

            if not user_row:
                return (False, "User not found")

            if user_row["role"] == "admin" and admin_count <= 1:
                return (False, "Cannot delete the last admin user")

            await conn.execute("DELETE FROM users WHERE username = ?", (username,))
            await conn.commit()
            return (True, None)
    except Exception as e:
        logger.error("Error deleting user: %s", e)
        return (False, str(e))


async def get_all_users(db_path: str) -> list:
    """Get all users"""
    async with get_db_connection(db_path) as conn:
        async with conn.execute(
            "SELECT id, username, role, created_at, last_login FROM users ORDER BY id"
        ) as c:
            rows = await c.fetchall()
            return [dict(row) for row in rows]


API_KEY_PREFIX = "um_"


def _hash_api_key(key: str) -> str:
    # A FIXED salt is intentional: the hash must be deterministic so an incoming
    # key can be looked up by hash. This is acceptable because keys are 256 bits
    # of CSPRNG output (generate_api_key), which defeats precomputation/brute
    # force regardless of the salt. The salt must NOT be changed — doing so would
    # invalidate every previously issued API key.
    salt = hashlib.sha256(b"uptime-monitor-api-key-salt").digest()
    return hashlib.pbkdf2_hmac("sha256", key.encode(), salt, 100000).hex()


def generate_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


async def create_api_key(db_path: str, user_id: int, name: str) -> tuple:
    raw_key = generate_api_key()
    key_hash = _hash_api_key(raw_key)
    key_id = secrets.token_urlsafe(16)
    async with get_db_connection(db_path) as conn:
        await conn.execute(
            "INSERT INTO api_keys (key_id, user_id, name, key_hash, created_at, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (key_id, user_id, name, key_hash, datetime.now(timezone.utc).isoformat()),
        )
        await conn.commit()
    return (key_id, raw_key)


async def validate_api_key(db_path: str, api_key: str) -> dict:
    if not api_key or not api_key.startswith(API_KEY_PREFIX):
        return None

    key_hash = _hash_api_key(api_key)
    async with get_db_connection(db_path) as conn:
        async with conn.execute(
            """SELECT k.key_id, k.user_id, k.last_used_at, u.username, u.role, u.must_change_password
               FROM api_keys k JOIN users u ON k.user_id = u.id
               WHERE k.key_hash = ? AND k.is_active = 1""",
            (key_hash,),
        ) as c:
            row = await c.fetchone()

    if not row:
        return None

    # Throttle the last_used_at write: every API request would otherwise open a
    # separate write transaction, serialising with the monitor loop's writers
    # under WAL. A coarse (≥60s) freshness is plenty for an audit timestamp.
    now = datetime.now(timezone.utc)
    last_used = row["last_used_at"]
    should_touch = True
    if last_used:
        try:
            should_touch = (now - datetime.fromisoformat(last_used)).total_seconds() >= 60
        except (ValueError, TypeError):
            should_touch = True
    if should_touch:
        async with get_db_connection(db_path) as conn:
            await conn.execute(
                "UPDATE api_keys SET last_used_at = ? WHERE key_id = ?",
                (now.isoformat(), row["key_id"]),
            )
            await conn.commit()

    return {
        "user_id": row["user_id"],
        "username": row["username"],
        "role": row["role"],
        "must_change_password": row["must_change_password"],
        "auth_method": "api_key",
    }


async def list_api_keys(db_path: str) -> list:
    async with get_db_connection(db_path) as conn:
        async with conn.execute(
            "SELECT key_id, user_id, name, created_at, last_used_at, is_active FROM api_keys ORDER BY created_at DESC"
        ) as c:
            rows = await c.fetchall()
            return [dict(row) for row in rows]


async def revoke_api_key(db_path: str, key_id: str) -> bool:
    async with get_db_connection(db_path) as conn:
        await conn.execute("UPDATE api_keys SET is_active = 0 WHERE key_id = ?", (key_id,))
        await conn.commit()
        return True
