#!/usr/bin/env python3
"""CLI tool for user and password management"""

import argparse
import os
import secrets
import sqlite3
import sys
from datetime import datetime

import bcrypt


def _init_crypto():
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        from Uptime_Robot.crypto_utils import decrypt_value as _dec
        from Uptime_Robot.crypto_utils import encrypt_value as _enc

        return _enc, _dec
    except Exception:
        return None, None


def _encrypt_password(plaintext: str) -> str:
    enc, _ = _init_crypto()
    if enc and plaintext:
        try:
            return enc(plaintext) or ""
        except Exception:
            pass
    return ""


def _decrypt_password(ciphertext: str) -> str:
    _, dec = _init_crypto()
    if dec and ciphertext:
        try:
            return dec(ciphertext) or ""
        except Exception:
            pass
    return ""


def _save_credentials_file(password: str):
    try:
        paths = []
        if os.name == "nt":
            app_dir = os.path.dirname(os.path.abspath(__file__))
            paths.append(os.path.join(app_dir, "credentials.txt"))
            up = os.environ.get("USERPROFILE", "")
            if up:
                paths.append(os.path.join(up, "UptimeMonitor", "credentials.txt"))
        else:
            paths.append("/etc/uptime-monitor/credentials.txt")

        for path in paths:
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as f:
                    f.write(f"Admin password: {password}\n")
                    f.write("Username: admin\n")
                if os.name != "nt":
                    os.chmod(path, 0o600)
            except Exception:
                continue
    except Exception:
        pass


def get_db_path():
    if getattr(sys, "frozen", False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))

    # Check common locations
    paths = [
        os.path.join(app_dir, "sites.db"),
        "/var/lib/uptime-monitor/sites.db",
        os.path.expanduser("~/UptimeMonitor/data/sites.db"),
    ]

    for p in paths:
        if os.path.exists(p):
            return p

    return paths[0]


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def init_auth(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'admin',
        must_change_password BOOLEAN DEFAULT 0,
        created_at TEXT,
        last_login TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        user_id INTEGER,
        created_at TEXT,
        expires_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")

    # Migration: Add role column if not exists
    c.execute("PRAGMA table_info(users)")
    columns = {row[1] for row in c.fetchall()}
    if "role" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'admin'")
        c.execute("UPDATE users SET role = 'admin' WHERE is_admin = 1")
        c.execute("UPDATE users SET role = 'viewer' WHERE is_admin = 0 OR is_admin IS NULL")
    if "password_encrypted" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN password_encrypted TEXT")

    c.execute("SELECT id, password_encrypted FROM users WHERE username = 'admin'")
    admin_row = c.fetchone()
    if not admin_row:
        default_password = secrets.token_urlsafe(12)
        password_hash = hash_password(default_password)
        encrypted = _encrypt_password(default_password)
        c.execute(
            "INSERT INTO users (username, password_hash, role, must_change_password, created_at, password_encrypted) VALUES (?, ?, 'admin', 0, datetime('now'), ?)",
            ("admin", password_hash, encrypted or None),
        )
        _save_credentials_file(default_password)
        print("\n" + "=" * 50)
        print("DEFAULT ADMIN USER CREATED")
        print("Username: admin")
        print(f"Password: {default_password}")
        print("=" * 50 + "\n")
    else:
        # Do not auto-print the stored password here; use `show-password` to
        # recover it on demand. This keeps passwords out of install/upgrade logs.
        print("\n[OK] User 'admin' already exists")
        print("[HINT] Run 'show-password' to reveal the current admin password\n")

    conn.commit()
    conn.close()


def reset_password(db_path, username, password=None, force_change=True):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    if not password:
        password = secrets.token_urlsafe(12)
        print(f"[INFO] Generated new random password for '{username}'")

    password_hash = hash_password(password)
    encrypted = _encrypt_password(password)
    must_change = 1 if force_change else 0
    c.execute(
        "UPDATE users SET password_hash = ?, password_encrypted = ?, must_change_password = ? WHERE username = ?",
        (password_hash, encrypted or None, must_change, username),
    )

    if c.rowcount == 0:
        print(f"[ERROR] User '{username}' not found")
        conn.close()
        sys.exit(1)

    conn.commit()
    conn.close()
    _save_credentials_file(password)
    print(f"[OK] Password reset for user '{username}' to '{password}'")


def create_user(db_path, username, password, role):
    if role not in ["admin", "viewer"]:
        print(f"[ERROR] Invalid role '{role}'. Must be 'admin' or 'viewer'")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    try:
        password_hash = hash_password(password)
        encrypted = _encrypt_password(password)
        c.execute(
            "INSERT INTO users (username, password_hash, role, created_at, password_encrypted) VALUES (?, ?, ?, ?, ?)",
            (username, password_hash, role, datetime.now().isoformat(), encrypted or None),
        )
        conn.commit()
        print(f"[OK] User '{username}' created with role '{role}'")
    except sqlite3.IntegrityError:
        print(f"[ERROR] User '{username}' already exists")
        conn.close()
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Error creating user: {e}")
        conn.close()
        sys.exit(1)

    conn.close()


def show_password(db_path, username="admin"):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT password_encrypted FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()

    if not row:
        print(f"[ERROR] User '{username}' not found")
        sys.exit(1)

    encrypted = row[0]
    if not encrypted:
        print(f"[ERROR] No password backup found for '{username}'")
        print("[HINT] Use 'reset-password' to set a new password")
        sys.exit(1)

    password = _decrypt_password(encrypted)
    if not password:
        print(f"[ERROR] Cannot decrypt password backup for '{username}'")
        print("[HINT] Use 'reset-password' to set a new password")
        sys.exit(1)

    print(f"\n{'='*50}")
    print(f"Username: {username}")
    print(f"Password: {password}")
    print(f"{'='*50}\n")


def restore_password(db_path, username="admin"):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT password_encrypted FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()

    if not row:
        print(f"[ERROR] User '{username}' not found")
        sys.exit(1)

    encrypted = row[0]
    if not encrypted:
        print(f"[ERROR] No password backup found for '{username}'")
        print("[HINT] Use 'reset-password' to set a new password")
        sys.exit(1)

    password = _decrypt_password(encrypted)
    if not password:
        print(f"[ERROR] Cannot decrypt password backup for '{username}'")
        print("[HINT] Use 'reset-password' to set a new password")
        sys.exit(1)

    password_hash = hash_password(password)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        "UPDATE users SET password_hash = ?, password_encrypted = ?, must_change_password = 0 WHERE username = ?",
        (password_hash, encrypted, username),
    )
    if c.rowcount == 0:
        print(f"[ERROR] User '{username}' not found")
        conn.close()
        sys.exit(1)
    conn.commit()
    conn.close()

    _save_credentials_file(password)
    print(f"\n{'='*50}")
    print(f"[OK] Password restored for '{username}'")
    print(f"Password: {password}")
    print(f"{'='*50}\n")


def update_user_role(db_path, username, role):
    if role not in ["admin", "viewer"]:
        print(f"[ERROR] Invalid role '{role}'. Must be 'admin' or 'viewer'")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("SELECT role FROM users WHERE username = ?", (username,))
    existing = c.fetchone()
    if existing is None:
        print(f"[ERROR] User '{username}' not found")
        conn.close()
        sys.exit(1)

    if existing[0] == "admin" and role != "admin":
        c.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        if c.fetchone()[0] <= 1:
            print("[ERROR] Cannot demote the last admin user")
            conn.close()
            sys.exit(1)

    c.execute("UPDATE users SET role = ? WHERE username = ?", (role, username))

    conn.commit()
    conn.close()
    print(f"[OK] User '{username}' role updated to '{role}'")


def delete_user(db_path, username):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Check if this is the last admin
    c.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
    admin_count = c.fetchone()[0]

    c.execute("SELECT role FROM users WHERE username = ?", (username,))
    user_row = c.fetchone()

    if not user_row:
        print(f"[ERROR] User '{username}' not found")
        conn.close()
        sys.exit(1)

    if user_row[0] == "admin" and admin_count <= 1:
        print("[ERROR] Cannot delete the last admin user")
        conn.close()
        sys.exit(1)

    c.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    print(f"[OK] User '{username}' deleted")


def list_users(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("SELECT id, username, role, must_change_password, last_login FROM users ORDER BY id")
    rows = c.fetchall()

    if not rows:
        print("No users found")
    else:
        print("\nUsers:")
        print(f"{'ID':<5} {'Username':<15} {'Role':<10} {'Must Change':<12} {'Last Login'}")
        print("-" * 70)
        for row in rows:
            print(
                f"{row[0]:<5} {row[1]:<15} {row[2]:<10} {'Yes' if row[3] else 'No':<12} {row[4] or 'Never'}"
            )

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Uptime Monitor CLI")
    parser.add_argument("--db", default=None, help="Path to database")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    subparsers.add_parser("init", help="Initialize database and create default user")

    reset_parser = subparsers.add_parser(
        "reset-password", help="Reset user password (generates random if --password omitted)"
    )
    reset_parser.add_argument("--user", default="admin", help="Username")
    reset_parser.add_argument(
        "--password", default=None, help="New password (omit to generate random)"
    )
    reset_parser.add_argument(
        "--no-force-change",
        action="store_true",
        help="Don't force password change on next login",
    )

    subparsers.add_parser("list-users", help="List all users")

    show_parser = subparsers.add_parser("show-password", help="Show current password")
    show_parser.add_argument("--user", default="admin", help="Username")

    restore_parser = subparsers.add_parser(
        "restore-password", help="Restore password from encrypted backup"
    )
    restore_parser.add_argument("--user", default="admin", help="Username")

    # Create user command
    create_parser = subparsers.add_parser("create-user", help="Create a new user")
    create_parser.add_argument("--username", required=True, help="Username")
    create_parser.add_argument("--password", required=True, help="Password")
    create_parser.add_argument(
        "--role",
        default="viewer",
        choices=["admin", "viewer"],
        help="User role (default: viewer)",
    )

    # Update role command
    role_parser = subparsers.add_parser("set-role", help="Update user role")
    role_parser.add_argument("--username", required=True, help="Username")
    role_parser.add_argument("--role", required=True, choices=["admin", "viewer"], help="New role")

    # Delete user command
    delete_parser = subparsers.add_parser("delete-user", help="Delete a user")
    delete_parser.add_argument("--username", required=True, help="Username")

    args = parser.parse_args()

    db_path = args.db or get_db_path()

    if args.command == "init":
        init_auth(db_path)
    elif args.command == "reset-password":
        reset_password(db_path, args.user, args.password, not args.no_force_change)
    elif args.command == "list-users":
        list_users(db_path)
    elif args.command == "show-password":
        show_password(db_path, args.user)
    elif args.command == "restore-password":
        restore_password(db_path, args.user)
    elif args.command == "create-user":
        create_user(db_path, args.username, args.password, args.role)
    elif args.command == "set-role":
        update_user_role(db_path, args.username, args.role)
    elif args.command == "delete-user":
        delete_user(db_path, args.username)
    else:
        parser.print_help()
