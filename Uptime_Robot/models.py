"""Модуль для роботи з базою даних"""

import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from database import get_db_connection


def init_database(db_path: str):
    """Ініціалізує базу даних"""
    with get_db_connection(db_path) as conn:
        c = conn.cursor()

        # Таблиця сайтів
        c.execute("""CREATE TABLE IF NOT EXISTS sites (
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
            monitor_type TEXT DEFAULT 'http'
        )""")

        # Таблиця історії статусів
        c.execute("""CREATE TABLE IF NOT EXISTS status_history (
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
        c.execute("""CREATE TABLE IF NOT EXISTS notify_config (
            id INTEGER PRIMARY KEY,
            config TEXT
        )""")

        # Таблиця SSL сертифікатів
        c.execute("""CREATE TABLE IF NOT EXISTS ssl_certificates (
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
        c.execute("""CREATE TABLE IF NOT EXISTS app_settings (
            id INTEGER PRIMARY KEY,
            display_address TEXT
        )""")

        # Migrations for legacy ssl_certificates schema:
        # - add missing last_notified column
        # - deduplicate legacy rows (older DBs may miss UNIQUE(site_id))
        # - enforce one row per site via unique index
        c.execute("PRAGMA table_info(ssl_certificates)")
        ssl_columns = {row[1] for row in c.fetchall()}
        if "last_notified" not in ssl_columns:
            c.execute("ALTER TABLE ssl_certificates ADD COLUMN last_notified TEXT")

        c.execute("""DELETE FROM ssl_certificates
                     WHERE id NOT IN (
                         SELECT MAX(id) FROM ssl_certificates GROUP BY site_id
                     )""")
        c.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_ssl_certificates_site_id_unique ON ssl_certificates(site_id)"
        )

        # Migration: Add role column to users table if not exists
        c.execute("PRAGMA table_info(users)")
        columns = {row[1] for row in c.fetchall()}
        if "role" not in columns:
            c.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'admin'")
            # Update existing users: is_admin=1 -> admin, is_admin=0 -> viewer
            c.execute("UPDATE users SET role = 'admin' WHERE is_admin = 1")
            c.execute(
                "UPDATE users SET role = 'viewer' WHERE is_admin = 0 OR is_admin IS NULL"
            )

        conn.commit()


def get_all_sites(db_path: str) -> List[Dict[str, Any]]:
    """Отримує всі сайти"""
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM sites ORDER BY id DESC")
        sites = [dict(row) for row in c.fetchall()]
    return sites


def get_active_sites(db_path: str) -> List[Dict[str, Any]]:
    """Отримує активні сайти"""
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM sites WHERE is_active = 1")
        sites = [dict(row) for row in c.fetchall()]
    return sites


def add_site(
    db_path: str,
    name: str,
    url: str,
    check_interval: int = 60,
    notify_methods: Optional[List[str]] = None,
) -> int:
    """Додає новий сайт"""
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """INSERT INTO sites (name, url, check_interval, notify_methods, is_active)
                     VALUES (?, ?, ?, ?, 1)""",
            (name, url, check_interval, json.dumps(notify_methods or [])),
        )
        site_id = c.lastrowid
        conn.commit()
    return site_id


def update_site(db_path: str, site_id: int, **kwargs):
    """Оновлює сайт"""
    allowed_columns = {
        "name",
        "url",
        "check_interval",
        "is_active",
        "notify_methods",
        "last_notification",
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

    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(f"UPDATE sites SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()


def delete_site(db_path: str, site_id: int):
    """Видаляє сайт та його історію"""
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM status_history WHERE site_id = ?", (site_id,))
        c.execute("DELETE FROM ssl_certificates WHERE site_id = ?", (site_id,))
        c.execute("DELETE FROM sites WHERE id = ?", (site_id,))
        conn.commit()


def add_status_history(
    db_path: str,
    site_id: int,
    status: str,
    status_code: Optional[int],
    response_time: Optional[float],
    error_message: Optional[str],
):
    """Додає запис в історію статусів"""
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
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

        # Очищення старих записів (старші за 30 днів)
        c.execute(
            "DELETE FROM status_history WHERE checked_at < datetime('now', '-30 days')"
        )

        conn.commit()


def get_site_stats(db_path: str, site_id: int) -> Dict[str, Any]:
    """Отримує статистику сайту"""
    with get_db_connection(db_path) as conn:
        c = conn.cursor()

        # Останній статус
        c.execute(
            """SELECT * FROM status_history
                     WHERE site_id = ? ORDER BY checked_at DESC LIMIT 1""",
            (site_id,),
        )
        last_check = c.fetchone()

        # Загальна статистика
        c.execute(
            """SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'up' THEN 1 ELSE 0 END) as up_count
                     FROM status_history WHERE site_id = ?""",
            (site_id,),
        )
        stats = c.fetchone()

    return {
        "last_check": dict(last_check) if last_check else None,
        "total_checks": stats["total"] if stats else 0,
        "up_count": stats["up_count"] if stats else 0,
    }


def save_notify_settings(db_path: str, settings: Dict[str, Any]):
    """Зберігає налаштування сповіщень"""
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO notify_config (id, config) VALUES (1, ?)",
            (json.dumps(settings),),
        )
        conn.commit()


def load_notify_settings(db_path: str) -> Dict[str, Any]:
    """Завантажує налаштування сповіщень"""
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute("SELECT config FROM notify_config WHERE id = 1")
        row = c.fetchone()

    if row:
        return json.loads(row["config"])
    return {}


def get_ssl_certificates(db_path: str) -> List[Dict[str, Any]]:
    """Отримує всі SSL сертифікати"""
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute("""SELECT c.*, s.name as site_name, s.url as site_url
                     FROM ssl_certificates c
                     JOIN sites s ON c.site_id = s.id
                     WHERE s.is_active = 1
                     ORDER BY c.days_until_expire ASC""")
        certs = [dict(row) for row in c.fetchall()]
    return certs


def save_ssl_certificate(db_path: str, site_id: int, cert_data: Dict[str, Any]):
    """Зберігає або оновлює SSL сертифікат"""
    with get_db_connection(db_path) as conn:
        c = conn.cursor()

        c.execute("""SELECT id FROM ssl_certificates WHERE site_id = ?""", (site_id,))
        existing = c.fetchone()

        if existing:
            c.execute(
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
            c.execute(
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

        conn.commit()
