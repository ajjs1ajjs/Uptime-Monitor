import hashlib
import secrets
from datetime import datetime, timedelta

import bcrypt

from .database import get_db_connection
from .logger import logger


async def init_auth_tables(db_path):
    async with get_db_connection(db_path) as conn:
        await conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'admin',
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

        async with conn.execute(
            "SELECT id, must_change_password FROM users WHERE username = 'admin'"
        ) as c:
            admin_row = await c.fetchone()

        default_password = "291263"
        password_hash = hash_password(default_password)
        if not admin_row:
            await conn.execute(
                "INSERT INTO users (username, password_hash, role, must_change_password, created_at) VALUES (?, ?, 'admin', 0, ?)",
                ("admin", password_hash, datetime.now().isoformat()),
            )
            logger.info("=" * 50)
            logger.info("DEFAULT ADMIN USER CREATED")
            logger.info("Username: admin")
            logger.info(f"Password: {default_password}")
            logger.info("=" * 50)
            print(f"\n{'='*50}")
            print("DEFAULT ADMIN USER CREATED")
            print("Username: admin")
            print(f"Password: {default_password}")
            print(f"{'='*50}\n")
        elif admin_row["must_change_password"] == 1:
            logger.warning("Admin user has must_change_password=1 — password was NOT reset")

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
    now = datetime.now()
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
    if datetime.now() > expires:
        return None

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


async def change_password(user_id: int, new_password: str, db_path: str) -> bool:
    """Змінює пароль користувача"""
    try:
        async with get_db_connection(db_path) as conn:
            password_hash = hash_password(new_password)
            await conn.execute(
                "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
                (password_hash, user_id),
            )
            await conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error changing password: {e}")
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
    try:
        async with get_db_connection(db_path) as conn:
            password_hash = hash_password(password)
            try:
                await conn.execute(
                    "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                    (username, password_hash, role, datetime.now().isoformat()),
                )
                await conn.commit()
                return True
            except Exception as e:
                logger.error(f"Error creating user db: {e}")
                return False
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return False


async def update_user_role(db_path: str, username: str, new_role: str) -> bool:
    """Update user role"""
    try:
        async with get_db_connection(db_path) as conn:
            await conn.execute("UPDATE users SET role = ? WHERE username = ?", (new_role, username))
            await conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error updating user role: {e}")
        return False


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
        logger.error(f"Error deleting user: {e}")
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
    salt = hashlib.sha256("uptime-monitor-api-key-salt".encode()).digest()
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
            (key_id, user_id, name, key_hash, datetime.now().isoformat()),
        )
        await conn.commit()
    return (key_id, raw_key)


async def validate_api_key(db_path: str, api_key: str) -> dict:
    if not api_key or not api_key.startswith(API_KEY_PREFIX):
        return None

    key_hash = _hash_api_key(api_key)
    async with get_db_connection(db_path) as conn:
        async with conn.execute(
            """SELECT k.key_id, k.user_id, u.username, u.role
               FROM api_keys k JOIN users u ON k.user_id = u.id
               WHERE k.key_hash = ? AND k.is_active = 1""",
            (key_hash,),
        ) as c:
            row = await c.fetchone()

    if not row:
        return None

    async with get_db_connection(db_path) as conn:
        await conn.execute(
            "UPDATE api_keys SET last_used_at = ? WHERE key_id = ?",
            (datetime.now().isoformat(), row["key_id"]),
        )
        await conn.commit()

    return {
        "user_id": row["user_id"],
        "username": row["username"],
        "role": row["role"],
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
