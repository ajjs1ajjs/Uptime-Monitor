import functools
import json
import os
import secrets
import sqlite3
import sys
from datetime import datetime, timedelta

import bcrypt
from fastapi import Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Ініціалізація Jinja2
if getattr(sys, "frozen", False):
    template_dir = os.path.join(os.path.dirname(sys.executable), "templates")
else:
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

env = Environment(
    loader=FileSystemLoader(template_dir), autoescape=select_autoescape(["html", "xml"])
)


def render_template(template_name: str, **context) -> str:
    """Рендерить Jinja2 шаблон"""
    template = env.get_template(template_name)
    return template.render(**context)


# Ініціалізація таблиці користувачів
def init_auth_tables(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Таблиця користувачів з role замість is_admin
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'admin',
        must_change_password BOOLEAN DEFAULT 0,
        created_at TEXT,
        last_login TEXT
    )""")

    # Таблиця сесій
    c.execute("""CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        user_id INTEGER,
        created_at TEXT,
        expires_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")

    # Створюємо дефолтного адміна якщо немає
    c.execute("SELECT id FROM users WHERE username = 'admin'")
    if not c.fetchone():
        # Пароль: admin (хешується через bcrypt)
        password_hash = hash_password("admin")
        c.execute(
            "INSERT INTO users (username, password_hash, role, must_change_password, created_at) VALUES (?, ?, 'admin', 1, ?)",
            ("admin", password_hash, datetime.now().isoformat()),
        )
        print("Default user created: admin / admin")

    conn.commit()
    conn.close()


def hash_password(password: str) -> str:
    """Хешує пароль використовуючи bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Перевіряє пароль проти хешу"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Невалідний хеш (наприклад, старий SHA256)
        return False


def create_session(user_id: int, db_path: str) -> str:
    """Створює сесію і повертає session_id"""
    session_id = secrets.token_urlsafe(32)
    now = datetime.now()
    expires = now + timedelta(days=7)  # Сесія на 7 днів

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        "INSERT INTO sessions (session_id, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (session_id, user_id, now.isoformat(), expires.isoformat()),
    )

    # Оновлюємо last_login
    c.execute(
        "UPDATE users SET last_login = ? WHERE id = ?", (now.isoformat(), user_id)
    )
    conn.commit()
    conn.close()

    return session_id


def validate_session(session_id: str, db_path: str) -> dict:
    """Перевіряє сесію і повертає дані користувача"""
    if not session_id:
        return None

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Перевіряємо чи сесія існує і не протермінована
    c.execute(
        """
        SELECT s.user_id, u.username, u.role, u.must_change_password, s.expires_at
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.session_id = ?
    """,
        (session_id,),
    )

    row = c.fetchone()
    conn.close()

    if not row:
        return None

    # Перевіряємо термін дії
    expires = datetime.fromisoformat(row["expires_at"])
    if datetime.now() > expires:
        return None

    return {
        "user_id": row["user_id"],
        "username": row["username"],
        "role": row["role"],
        "must_change_password": row["must_change_password"],
    }


def delete_session(session_id: str, db_path: str):
    """Видаляє сесію (logout)"""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()


def change_password(user_id: int, new_password: str, db_path: str) -> bool:
    """Змінює пароль користувача"""
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        password_hash = hash_password(new_password)
        c.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
            (password_hash, user_id),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error changing password: {e}")
        return False


# Role checking functions
def has_role(user: dict, required_role: str) -> bool:
    """Check if user has at least the required role.

    Role hierarchy: admin > viewer
    """
    if not user:
        return False

    role = user.get("role", "viewer")

    # Admin has all permissions
    if role == "admin":
        return True

    # Check exact match for other roles
    return role == required_role


def is_admin(user: dict) -> bool:
    """Check if user is admin"""
    return has_role(user, "admin")


def is_viewer_or_higher(user: dict) -> bool:
    """Check if user is viewer or higher (for read-only access)"""
    if not user:
        return False
    return user.get("role") in ["admin", "viewer"]


def create_user(
    db_path: str, username: str, password: str, role: str = "viewer"
) -> bool:
    """Create a new user with specified role"""
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        password_hash = hash_password(password)
        c.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (username, password_hash, role, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        # Username already exists
        return False
    except Exception as e:
        print(f"Error creating user: {e}")
        return False


def update_user_role(db_path: str, username: str, new_role: str) -> bool:
    """Update user role"""
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("UPDATE users SET role = ? WHERE username = ?", (new_role, username))
        if c.rowcount == 0:
            conn.close()
            return False
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating user role: {e}")
        return False


def delete_user(db_path: str, username: str) -> tuple:
    """Delete a user (cannot delete last admin)

    Returns: (success: bool, error_message: str or None)
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Check if this is the last admin
        c.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        admin_count = c.fetchone()[0]

        c.execute("SELECT role FROM users WHERE username = ?", (username,))
        user_row = c.fetchone()

        if not user_row:
            conn.close()
            return (False, "User not found")

        if user_row["role"] == "admin" and admin_count <= 1:
            conn.close()
            return (False, "Cannot delete the last admin user")

        c.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
        conn.close()
        return (True, None)
    except Exception as e:
        print(f"Error deleting user: {e}")
        return (False, str(e))


def get_all_users(db_path: str) -> list:
    """Get all users"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT id, username, role, created_at, last_login FROM users ORDER BY id"
    )
    users = [dict(row) for row in c.fetchall()]
    conn.close()
    return users


# Login page HTML
LOGIN_HTML = """<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Uptime Monitor - Login</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f0f23 0%, #1a1a2e 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        .login-container {{
            background: #16213e;
            padding: 40px;
            border-radius: 15px;
            border: 1px solid #2a2a4a;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
            width: 100%;
            max-width: 400px;
        }}
        .logo {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .logo-icon {{
            width: 60px;
            height: 60px;
            background: linear-gradient(135deg, #00d9ff 0%, #00a8cc 100%);
            border-radius: 15px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 30px;
            margin-bottom: 15px;
        }}
        h1 {{
            color: #fff;
            font-size: 24px;
            text-align: center;
        }}
        .form-group {{
            margin-bottom: 20px;
        }}
        label {{
            display: block;
            margin-bottom: 8px;
            color: #a0a0b0;
            font-weight: 500;
        }}
        input[type="text"],
        input[type="password"] {{
            width: 100%;
            padding: 12px;
            border: 1px solid #2a2a4a;
            background: #0f0f23;
            color: #fff;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s;
        }}
        input[type="text"]:focus,
        input[type="password"]:focus {{
            border-color: #00d9ff;
            outline: none;
        }}
        button {{
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #00d9ff 0%, #00a8cc 100%);
            color: #000;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0, 217, 255, 0.4);
        }}
        .error {{
            background: rgba(255, 71, 87, 0.15);
            color: #ff4757;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
            border: 1px solid rgba(255, 71, 87, 0.3);
        }}
        .warning {{
            background: rgba(255, 217, 61, 0.15);
            color: #ffd93d;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 13px;
            border: 1px solid rgba(255, 217, 61, 0.3);
            text-align: center;
        }}
        .info {{
            background: rgba(0, 217, 255, 0.1);
            color: #00d9ff;
            padding: 12px;
            border-radius: 8px;
            margin-top: 20px;
            font-size: 13px;
            text-align: center;
            border: 1px solid rgba(0, 217, 255, 0.3);
        }}
        .forgot-link {{
            display: block;
            text-align: center;
            margin-top: 15px;
            color: #00d9ff;
            text-decoration: none;
            font-size: 14px;
        }}
        .forgot-link:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <div class="logo-icon">⚡</div>
            <h1>Uptime Monitor</h1>
        </div>
        {error_message}
        {warning_message}
        <form method="POST" action="/login">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" required autofocus>
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit">Login</button>
        </form>
        <a href="/forgot-password" class="forgot-link">Забули пароль?</a>
    </div>
</body>
</html>"""

# Forgot password page HTML
FORGOT_PASSWORD_HTML = """<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Uptime Monitor - Скидання пароля</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f0f23 0%, #1a1a2e 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        .container {{
            background: #16213e;
            padding: 40px;
            border-radius: 15px;
            border: 1px solid #2a2a4a;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
            width: 100%;
            max-width: 400px;
        }}
        h1 {{ color: #fff; font-size: 24px; text-align: center; margin-bottom: 10px; }}
        .subtitle {{ color: #a0a0b0; text-align: center; margin-bottom: 30px; font-size: 14px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 8px; color: #a0a0b0; font-weight: 500; }}
        input[type="text"], input[type="password"] {{
            width: 100%;
            padding: 12px;
            border: 1px solid #2a2a4a;
            background: #0f0f23;
            color: #fff;
            border-radius: 8px;
            font-size: 14px;
        }}
        input:focus {{ border-color: #00d9ff; outline: none; }}
        button {{
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #00d9ff 0%, #00a8cc 100%);
            color: #000;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
        }}
        button:hover {{ transform: translateY(-2px); box-shadow: 0 5px 20px rgba(0, 217, 255, 0.4); }}
        .error {{ background: rgba(255, 71, 87, 0.15); color: #ff4757; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; border: 1px solid rgba(255, 71, 87, 0.3); }}
        .success {{ background: rgba(0, 255, 136, 0.15); color: #00ff88; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; border: 1px solid rgba(0, 255, 136, 0.3); text-align: center; }}
        .back-link {{ display: block; text-align: center; margin-top: 15px; color: #00d9ff; text-decoration: none; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Скидання пароля</h1>
        <p class="subtitle">Введіть username для скидання пароля</p>
        {error_message}
        {success_message}
        <form method="POST" action="/forgot-password">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" required autofocus>
            </div>
            <button type="submit">Скинути пароль</button>
        </form>
        <a href="/login" class="back-link">Назад до входу</a>
    </div>
</body>
</html>"""

# Change password page HTML
CHANGE_PASSWORD_HTML = """<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Uptime Monitor - Change Password</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f0f23 0%, #1a1a2e 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        .container {{
            background: #16213e;
            padding: 40px;
            border-radius: 15px;
            border: 1px solid #2a2a4a;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
            width: 100%;
            max-width: 400px;
        }}
        h1 {{
            color: #fff;
            font-size: 24px;
            text-align: center;
            margin-bottom: 10px;
        }}
        .subtitle {{
            color: #a0a0b0;
            text-align: center;
            margin-bottom: 30px;
            font-size: 14px;
        }}
        .warning-box {{
            background: rgba(255, 71, 87, 0.15);
            border: 1px solid rgba(255, 71, 87, 0.3);
            color: #ff4757;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 25px;
            font-size: 14px;
            text-align: center;
        }}
        .form-group {{
            margin-bottom: 20px;
        }}
        label {{
            display: block;
            margin-bottom: 8px;
            color: #a0a0b0;
            font-weight: 500;
        }}
        input[type="password"] {{
            width: 100%;
            padding: 12px;
            border: 1px solid #2a2a4a;
            background: #0f0f23;
            color: #fff;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s;
        }}
        input[type="password"]:focus {{
            border-color: #00d9ff;
            outline: none;
        }}
        button {{
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #00d9ff 0%, #00a8cc 100%);
            color: #000;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0, 217, 255, 0.4);
        }}
        .error {{
            background: rgba(255, 71, 87, 0.15);
            color: #ff4757;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
            border: 1px solid rgba(255, 71, 87, 0.3);
        }}
        .hint {{
            color: #a0a0b0;
            font-size: 12px;
            margin-top: 5px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Change Password</h1>
        <p class="subtitle">You must change the default password</p>

        <div class="warning-box">
            WARNING: For security, change your password!<br>
            Default password is not safe.
        </div>

        {error_message}

        <form method="POST" action="/change-password" onsubmit="return validateForm()">
            <div class="form-group">
                <label for="current_password">Current Password</label>
                <input type="password" id="current_password" name="current_password" required>
            </div>
            <div class="form-group">
                <label for="new_password">New Password</label>
                <input type="password" id="new_password" name="new_password" required minlength="6">
                <p class="hint">Minimum 6 characters</p>
            </div>
            <div class="form-group">
                <label for="confirm_password">Confirm New Password</label>
                <input type="password" id="confirm_password" name="confirm_password" required>
            </div>
            <button type="submit">Change Password</button>
        </form>
    </div>

    <script>
        function validateForm() {{
            const newPass = document.getElementById('new_password').value;
            const confirmPass = document.getElementById('confirm_password').value;

            if (newPass !== confirmPass) {{
                alert('Passwords do not match!');
                return false;
            }}

            if (newPass.length < 6) {{
                alert('Password must be at least 6 characters!');
                return false;
            }}

            return true;
        }}
    </script>
</body>
</html>"""
