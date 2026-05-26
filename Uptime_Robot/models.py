"""Модуль для роботи з базою даних"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from .database import get_db_connection


async def init_database(db_path: str):
    """Ініціалізує базу даних"""
    async with get_db_connection(db_path) as conn:
        # Таблиця аудиту
        await conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            action TEXT NOT NULL,
            target_type TEXT,
            target_id TEXT,
            details TEXT,
            created_at TEXT
        )""")

        # Таблиця сайтів
        await conn.execute("""CREATE TABLE IF NOT EXISTS sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            check_interval INTEGER DEFAULT 60,
            is_active BOOLEAN DEFAULT 1,
            last_notification TEXT,
            notify_methods TEXT DEFAULT '[]',
            status TEXT DEFAULT 'unknown',
            status_code INTEGER,
            response_time REAL,
            error_message TEXT,
            monitor_type TEXT DEFAULT 'http',
            failed_attempts INTEGER DEFAULT 0,
            success_attempts INTEGER DEFAULT 0,
            last_down_alert TEXT,
            keyword TEXT DEFAULT NULL
        )""")

        # Таблиця історії статусів
        await conn.execute("""CREATE TABLE IF NOT EXISTS status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER,
            status TEXT,
            status_code INTEGER,
            response_time REAL,
            error_message TEXT,
            checked_at TEXT,
            FOREIGN KEY (site_id) REFERENCES sites(id)
        )""")

        # Таблиця налаштувань сповіщень
        await conn.execute("""CREATE TABLE IF NOT EXISTS notify_config (
            id INTEGER PRIMARY KEY,
            config TEXT
        )""")

        # Таблиця SSL сертифікатів
        await conn.execute("""CREATE TABLE IF NOT EXISTS ssl_certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER UNIQUE,
            hostname TEXT,
            issuer TEXT,
            subject TEXT,
            start_date TEXT,
            expire_date TEXT,
            days_until_expire INTEGER,
            is_valid BOOLEAN,
            last_checked TEXT,
            FOREIGN KEY (site_id) REFERENCES sites(id)
        )""")

        # Таблиця налаштувань додатку
        await conn.execute("""CREATE TABLE IF NOT EXISTS app_settings (
            id INTEGER PRIMARY KEY,
            display_address TEXT,
            site_title TEXT DEFAULT 'Uptime Monitor',
            logo_url TEXT DEFAULT '',
            footer_text TEXT DEFAULT '',
            primary_color TEXT DEFAULT '#00ff88',
            brand_accent_color TEXT DEFAULT '#06b6d4'
        )""")

        # Migrations for legacy ssl_certificates
        async with conn.execute("PRAGMA table_info(ssl_certificates)") as c:
            rows = await c.fetchall()
            ssl_columns = {row[1] for row in rows}
        if "last_notified" not in ssl_columns:
            await conn.execute("ALTER TABLE ssl_certificates ADD COLUMN last_notified TEXT")

        await conn.execute("""DELETE FROM ssl_certificates
                     WHERE id NOT IN (
                         SELECT MAX(id) FROM ssl_certificates GROUP BY site_id
                     )""")
        await conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_ssl_certificates_site_id_unique ON ssl_certificates(site_id)"
        )

        # Migrations for legacy users
        async with conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'") as c:
            users_table_exists = await c.fetchone() is not None

        if users_table_exists:
            async with conn.execute("PRAGMA table_info(users)") as c:
                rows = await c.fetchall()
                columns = {row[1] for row in rows}
            if "role" not in columns:
                await conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'admin'")
                await conn.execute("UPDATE users SET role = 'admin' WHERE is_admin = 1")
                await conn.execute("UPDATE users SET role = 'viewer' WHERE is_admin = 0 OR is_admin IS NULL")
                
        # Migrations for legacy sites
        async with conn.execute("PRAGMA table_info(sites)") as c:
            rows = await c.fetchall()
            site_columns = {row[1] for row in rows}
        
        if "failed_attempts" not in site_columns:
            await conn.execute("ALTER TABLE sites ADD COLUMN failed_attempts INTEGER DEFAULT 0")
            await conn.execute("ALTER TABLE sites ADD COLUMN success_attempts INTEGER DEFAULT 0")

        # Migrations for legacy app_settings
        async with conn.execute("PRAGMA table_info(app_settings)") as c:
            rows = await c.fetchall()
            settings_columns = {row[1] for row in rows}
        
        for col, col_type in [("site_title", "TEXT DEFAULT 'Uptime Monitor'"), ("logo_url", "TEXT DEFAULT ''"), ("footer_text", "TEXT DEFAULT ''"), ("primary_color", "TEXT DEFAULT '#00ff88'"), ("brand_accent_color", "TEXT DEFAULT '#06b6d4'")]:
            if col not in settings_columns:
                await conn.execute(f"ALTER TABLE app_settings ADD COLUMN {col} {col_type}")

        if "last_down_alert" not in site_columns:
            await conn.execute("ALTER TABLE sites ADD COLUMN last_down_alert TEXT")

        if "keyword" not in site_columns:
            await conn.execute("ALTER TABLE sites ADD COLUMN keyword TEXT DEFAULT NULL")

        await conn.execute("""CREATE TABLE IF NOT EXISTS notification_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER,
            site_name TEXT,
            method TEXT,
            status TEXT,
            message_preview TEXT,
            sent_at TEXT
        )""")

        await conn.execute("""CREATE TABLE IF NOT EXISTS backups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            filepath TEXT,
            size_bytes INTEGER,
            site_count INTEGER,
            created_at TEXT
        )""")

        # Таблиця періодів обслуговування (Maintenance Windows)
        await conn.execute("""CREATE TABLE IF NOT EXISTS maintenance_windows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            site_id INTEGER,
            rule_type TEXT DEFAULT 'one_off',
            start_time TEXT,
            end_time TEXT,
            day_of_week INTEGER,
            start_hour_minute TEXT,
            duration_minutes INTEGER,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY(site_id) REFERENCES sites(id)
        )""")

        await conn.commit()


async def get_all_sites(db_path: str) -> List[Dict[str, Any]]:
    """Отримує всі сайти"""
    async with get_db_connection(db_path) as conn:
        async with conn.execute("SELECT * FROM sites ORDER BY id DESC") as c:
            rows = await c.fetchall()
            return [dict(row) for row in rows]


async def get_active_sites(db_path: str) -> List[Dict[str, Any]]:
    """Отримує активні сайти"""
    async with get_db_connection(db_path) as conn:
        async with conn.execute("SELECT * FROM sites WHERE is_active = 1") as c:
            rows = await c.fetchall()
            return [dict(row) for row in rows]


async def add_site(
    db_path: str,
    name: str,
    url: str,
    check_interval: int = 60,
    notify_methods: Optional[List[str]] = None,
    monitor_type: str = "http",
    keyword: Optional[str] = None,
) -> int:
    """Додає новий сайт"""
    async with get_db_connection(db_path) as conn:
        async with conn.execute(
            """INSERT INTO sites (name, url, check_interval, notify_methods, monitor_type, keyword, is_active)
                     VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (name, url, check_interval, json.dumps(notify_methods or []), monitor_type, keyword),
        ) as c:
            site_id = c.lastrowid
        await conn.commit()
    return site_id


async def update_site(db_path: str, site_id: int, **kwargs):
    """Оновлює сайт"""
    allowed_columns = {
        "name",
        "url",
        "check_interval",
        "is_active",
        "notify_methods",
        "last_notification",
        "failed_attempts",
        "success_attempts",
        "status",
        "status_code",
        "response_time",
        "monitor_type",
        "keyword"
    }

    updates = []
    params = []
    for key, value in kwargs.items():
        if key in allowed_columns:
            if key == "notify_methods" and isinstance(value, list):
                value = json.dumps(value)
            updates.append(f"{key} = ?")
            params.append(value)

    if not updates:
        return

    params.append(site_id)

    async with get_db_connection(db_path) as conn:
        await conn.execute(f"UPDATE sites SET {', '.join(updates)} WHERE id = ?", params)
        await conn.commit()


async def delete_site(db_path: str, site_id: int):
    """Видаляє сайт та його історію"""
    async with get_db_connection(db_path) as conn:
        await conn.execute("DELETE FROM status_history WHERE site_id = ?", (site_id,))
        await conn.execute("DELETE FROM ssl_certificates WHERE site_id = ?", (site_id,))
        await conn.execute("DELETE FROM sites WHERE id = ?", (site_id,))
        await conn.commit()


async def add_status_history(
    db_path: str,
    site_id: int,
    status: str,
    status_code: Optional[int],
    response_time: Optional[float],
    error_message: Optional[str],
):
    """Додає запис в історію статусів"""
    async with get_db_connection(db_path) as conn:
        await conn.execute(
            """INSERT INTO status_history
                     (site_id, status, status_code, response_time, error_message, checked_at)
                     VALUES (?, ?, ?, ?, ?, ?)""",
            (
                site_id,
                status,
                status_code,
                response_time,
                error_message,
                datetime.now().isoformat(),
            ),
        )

        await conn.execute("DELETE FROM status_history WHERE checked_at < datetime('now', '-30 days')")
        await conn.commit()


async def get_site_stats(db_path: str, site_id: int) -> Dict[str, Any]:
    """Отримує статистику сайту"""
    async with get_db_connection(db_path) as conn:
        async with conn.execute(
            """SELECT * FROM status_history
                     WHERE site_id = ? ORDER BY checked_at DESC LIMIT 1""",
            (site_id,)
        ) as c:
            last_check = await c.fetchone()

        async with conn.execute(
            """SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'up' THEN 1 ELSE 0 END) as up_count
                     FROM status_history WHERE site_id = ?""",
            (site_id,)
        ) as c:
            stats = await c.fetchone()

    return {
        "last_check": dict(last_check) if last_check else None,
        "total_checks": stats["total"] if stats else 0,
        "up_count": stats["up_count"] if stats else 0,
    }


async def save_notify_settings(db_path: str, settings: Dict[str, Any]):
    """Зберігає налаштування сповіщень"""
    async with get_db_connection(db_path) as conn:
        await conn.execute(
            "INSERT OR REPLACE INTO notify_config (id, config) VALUES (1, ?)",
            (json.dumps(settings),),
        )
        await conn.commit()


async def load_notify_settings(db_path: str) -> Dict[str, Any]:
    """Завантажує налаштування сповіщень"""
    async with get_db_connection(db_path) as conn:
        async with conn.execute("SELECT config FROM notify_config WHERE id = 1") as c:
            row = await c.fetchone()

    if row:
        return json.loads(row["config"])
    return {}


async def get_ssl_certificates(db_path: str) -> List[Dict[str, Any]]:
    """Отримує всі SSL сертифікати"""
    async with get_db_connection(db_path) as conn:
        async with conn.execute("""SELECT c.*, s.name as site_name, s.url as site_url
                     FROM ssl_certificates c
                     JOIN sites s ON c.site_id = s.id
                     WHERE s.is_active = 1
                     ORDER BY c.days_until_expire ASC""") as c:
            rows = await c.fetchall()
            return [dict(row) for row in rows]


async def save_ssl_certificate(db_path: str, site_id: int, cert_data: Dict[str, Any]):
    """Зберігає або оновлює SSL сертифікат"""
    async with get_db_connection(db_path) as conn:
        async with conn.execute("""SELECT id FROM ssl_certificates WHERE site_id = ?""", (site_id,)) as c:
            existing = await c.fetchone()

        if existing:
            await conn.execute(
                """UPDATE ssl_certificates SET
                            hostname = ?, issuer = ?, subject = ?,
                            start_date = ?, expire_date = ?, days_until_expire = ?,
                            is_valid = ?, last_checked = ?
                         WHERE site_id = ?""",
                (
                    cert_data["hostname"],
                    cert_data["issuer"],
                    cert_data["subject"],
                    cert_data["start_date"],
                    cert_data["expire_date"],
                    cert_data["days_until_expire"],
                    cert_data["is_valid"],
                    datetime.now().isoformat(),
                    site_id,
                ),
            )
        else:
            await conn.execute(
                """INSERT INTO ssl_certificates
                            (site_id, hostname, issuer, subject, start_date, expire_date,
                             days_until_expire, is_valid, last_checked)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    site_id,
                    cert_data["hostname"],
                    cert_data["issuer"],
                    cert_data["subject"],
                    cert_data["start_date"],
                    cert_data["expire_date"],
                    cert_data["days_until_expire"],
                    cert_data["is_valid"],
                    datetime.now().isoformat(),
                ),
            )

        await conn.commit()


async def get_maintenance_windows(db_path: str) -> List[Dict[str, Any]]:
    """Отримує всі періоди обслуговування"""
    async with get_db_connection(db_path) as conn:
        async with conn.execute(
            """SELECT mw.*, s.name as site_name 
               FROM maintenance_windows mw 
               LEFT JOIN sites s ON mw.site_id = s.id 
               ORDER BY mw.id DESC"""
        ) as c:
            rows = await c.fetchall()
            return [dict(row) for row in rows]


async def add_maintenance_window(
    db_path: str,
    name: str,
    site_id: Optional[int],
    rule_type: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    day_of_week: Optional[int] = None,
    start_hour_minute: Optional[str] = None,
    duration_minutes: Optional[int] = None,
) -> int:
    """Додає новий період обслуговування"""
    async with get_db_connection(db_path) as conn:
        async with conn.execute(
            """INSERT INTO maintenance_windows 
               (name, site_id, rule_type, start_time, end_time, day_of_week, start_hour_minute, duration_minutes, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (name, site_id, rule_type, start_time, end_time, day_of_week, start_hour_minute, duration_minutes),
        ) as c:
            window_id = c.lastrowid
        await conn.commit()
    return window_id


async def delete_maintenance_window(db_path: str, window_id: int):
    """Видаляє період обслуговування за ID"""
    async with get_db_connection(db_path) as conn:
        await conn.execute("DELETE FROM maintenance_windows WHERE id = ?", (window_id,))
        await conn.commit()


async def toggle_maintenance_window(db_path: str, window_id: int, is_active: bool):
    """Вмикає або вимикає період обслуговування"""
    async with get_db_connection(db_path) as conn:
        await conn.execute("UPDATE maintenance_windows SET is_active = ? WHERE id = ?", (1 if is_active else 0, window_id))
        await conn.commit()


async def log_audit_event(
    db_path: str,
    user_id: int,
    username: str,
    action: str,
    target_type: str = None,
    target_id: str = None,
    details: str = None,
):
    """Log an audit event."""
    async with get_db_connection(db_path) as conn:
        await conn.execute(
            """INSERT INTO audit_log (user_id, username, action, target_type, target_id, details, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, username, action, target_type, target_id, details, datetime.now().isoformat()),
        )
        await conn.commit()


async def get_audit_log(db_path: str, limit: int = 200) -> list:
    """Get recent audit log entries."""
    async with get_db_connection(db_path) as conn:
        async with conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ) as c:
            rows = await c.fetchall()
            return [dict(row) for row in rows]


async def log_notification(
    db_path: str,
    site_id: int,
    site_name: str,
    method: str,
    status: str,
    message_preview: str = "",
):
    """Log a sent notification."""
    async with get_db_connection(db_path) as conn:
        await conn.execute(
            """INSERT INTO notification_history (site_id, site_name, method, status, message_preview, sent_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (site_id, site_name, method, status, (message_preview or "")[:200], datetime.now().isoformat()),
        )
        await conn.commit()


async def get_notification_history(db_path: str, limit: int = 100) -> list:
    """Get recent notification history."""
    async with get_db_connection(db_path) as conn:
        async with conn.execute(
            "SELECT * FROM notification_history ORDER BY id DESC LIMIT ?", (limit,)
        ) as c:
            rows = await c.fetchall()
            return [dict(row) for row in rows]


async def create_backup(db_path: str, backup_path: str) -> dict:
    """Create a backup of the database."""
    import shutil
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
    shutil.copy2(db_path, backup_path)
    async with get_db_connection(db_path) as conn:
        async with conn.execute("SELECT COUNT(*) FROM sites") as c:
            row = await c.fetchone()
            site_count = row[0] if row else 0
        await conn.execute(
            """INSERT INTO backups (filename, filepath, size_bytes, site_count, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (os.path.basename(backup_path), backup_path, os.path.getsize(backup_path), site_count, datetime.now().isoformat()),
        )
        await conn.commit()
    return {"filename": os.path.basename(backup_path), "path": backup_path, "site_count": site_count}


async def get_backups(db_path: str) -> list:
    """List all backups."""
    async with get_db_connection(db_path) as conn:
        async with conn.execute(
            "SELECT * FROM backups ORDER BY id DESC LIMIT 20"
        ) as c:
            rows = await c.fetchall()
            return [dict(row) for row in rows]
