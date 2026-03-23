import functools
import json
import os
import secrets
import sys
from datetime import datetime, timedelta
import bcrypt

try:
    from .database import get_db_connection
except ImportError:
    from database import get_db_connection


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

        async with conn.execute("SELECT id FROM users WHERE username = 'admin'") as c:
            admin_exists = await c.fetchone()
            
        if not admin_exists:
            password_hash = hash_password("admin")
            await conn.execute(
                "INSERT INTO users (username, password_hash, role, must_change_password, created_at) VALUES (?, ?, 'admin', 1, ?)",
                ("admin", password_hash, datetime.now().isoformat()),
            )
            print("Default user created: admin / admin")

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
        print(f"Error changing password: {e}")
        return False


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


async def create_user(
    db_path: str, username: str, password: str, role: str = "viewer"
) -> bool:
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
                print(f"Error creating user db: {e}")
                return False
    except Exception as e:
        print(f"Error creating user: {e}")
        return False


async def update_user_role(db_path: str, username: str, new_role: str) -> bool:
    """Update user role"""
    try:
        async with get_db_connection(db_path) as conn:
            await conn.execute("UPDATE users SET role = ? WHERE username = ?", (new_role, username))
            await conn.commit()
            return True
    except Exception as e:
        print(f"Error updating user role: {e}")
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
        print(f"Error deleting user: {e}")
        return (False, str(e))


async def get_all_users(db_path: str) -> list:
    """Get all users"""
    async with get_db_connection(db_path) as conn:
        async with conn.execute(
            "SELECT id, username, role, created_at, last_login FROM users ORDER BY id"
        ) as c:
            rows = await c.fetchall()
            return [dict(row) for row in rows]
