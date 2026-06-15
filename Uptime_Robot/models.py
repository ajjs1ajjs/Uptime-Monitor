"""Модуль для роботи з базою даних"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

from .database import get_db_connection


async def _create_tables(conn):
    """Створює всі таблиці бази даних."""
    await conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT,
        action TEXT NOT NULL, target_type TEXT, target_id TEXT, details TEXT, created_at TEXT
    )""")
    await conn.execute("""CREATE TABLE IF NOT EXISTS sites (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, url TEXT NOT NULL UNIQUE,
        check_interval INTEGER DEFAULT 60, is_active BOOLEAN DEFAULT 1,
        last_notification TEXT, notify_methods TEXT DEFAULT '[]',
        status TEXT DEFAULT 'unknown', status_code INTEGER, response_time REAL,
        error_message TEXT, monitor_type TEXT DEFAULT 'http',
        failed_attempts INTEGER DEFAULT 0, success_attempts INTEGER DEFAULT 0,
        last_down_alert TEXT, first_failure_at TEXT, keyword TEXT DEFAULT NULL
    )""")
    await conn.execute("""CREATE TABLE IF NOT EXISTS status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, site_id INTEGER, status TEXT,
        status_code INTEGER, response_time REAL, error_message TEXT, checked_at TEXT,
        FOREIGN KEY (site_id) REFERENCES sites(id)
    )""")
    await conn.execute("""CREATE TABLE IF NOT EXISTS notify_config (
        id INTEGER PRIMARY KEY, config TEXT
    )""")
    await conn.execute("""CREATE TABLE IF NOT EXISTS ssl_certificates (
        id INTEGER PRIMARY KEY AUTOINCREMENT, site_id INTEGER UNIQUE, hostname TEXT,
        issuer TEXT, subject TEXT, start_date TEXT, expire_date TEXT,
        days_until_expire INTEGER, is_valid BOOLEAN, last_checked TEXT,
        FOREIGN KEY (site_id) REFERENCES sites(id)
    )""")
    await conn.execute("""CREATE TABLE IF NOT EXISTS app_settings (
        id INTEGER PRIMARY KEY, display_address TEXT,
        site_title TEXT DEFAULT 'Uptime Monitor', logo_url TEXT DEFAULT '',
        footer_text TEXT DEFAULT '', primary_color TEXT DEFAULT '#00ff88',
        brand_accent_color TEXT DEFAULT '#06b6d4'
    )""")
    await conn.execute("""CREATE TABLE IF NOT EXISTS notification_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, site_id INTEGER, site_name TEXT,
        method TEXT, status TEXT, message_preview TEXT, sent_at TEXT
    )""")
    await conn.execute("""CREATE TABLE IF NOT EXISTS backups (
        id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, filepath TEXT,
        size_bytes INTEGER, site_count INTEGER, created_at TEXT
    )""")
    await conn.execute("""CREATE TABLE IF NOT EXISTS rate_limits (
        id INTEGER PRIMARY KEY AUTOINCREMENT, endpoint TEXT NOT NULL, ip TEXT NOT NULL,
        attempt_count INTEGER DEFAULT 1, reset_at REAL NOT NULL, UNIQUE(endpoint, ip)
    )""")
    await conn.execute("""CREATE INDEX IF NOT EXISTS idx_rate_limits_lookup ON rate_limits(endpoint, ip)""")
    await conn.execute("""CREATE TABLE IF NOT EXISTS maintenance_windows (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, site_id INTEGER,
        rule_type TEXT DEFAULT 'one_off', start_time TEXT, end_time TEXT,
        day_of_week INTEGER, start_hour_minute TEXT, duration_minutes INTEGER,
        is_active BOOLEAN DEFAULT 1, FOREIGN KEY(site_id) REFERENCES sites(id)
    )""")


async def _run_migrations(conn):
    """Виконує міграції для застарілих схем таблиць."""
    async with conn.execute("PRAGMA table_info(ssl_certificates)") as c:
        ssl_columns = {r[1] for r in await c.fetchall()}
    if "last_notified" not in ssl_columns:
        await conn.execute("ALTER TABLE ssl_certificates ADD COLUMN last_notified TEXT")
    if "ssl_notified_thresholds" not in ssl_columns:
        await conn.execute("ALTER TABLE ssl_certificates ADD COLUMN ssl_notified_thresholds TEXT DEFAULT '[]'")
    await conn.execute("""DELETE FROM ssl_certificates WHERE id NOT IN (
        SELECT MAX(id) FROM ssl_certificates GROUP BY site_id
    )""")
    await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_ssl_certificates_site_id_unique ON ssl_certificates(site_id)")

    async with conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'") as c:
        if await c.fetchone():
            async with conn.execute("PRAGMA table_info(users)") as c:
                cols = {r[1] for r in await c.fetchall()}
            if "role" not in cols:
                await conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'admin'")
                await conn.execute("UPDATE users SET role = 'admin' WHERE is_admin = 1")
                await conn.execute("UPDATE users SET role = 'viewer' WHERE is_admin = 0 OR is_admin IS NULL")

    async with conn.execute("PRAGMA table_info(sites)") as c:
        site_cols = {r[1] for r in await c.fetchall()}
    for col in ("failed_attempts", "success_attempts", "last_down_alert", "first_failure_at", "keyword", "tags"):
        if col not in site_cols:
            col_type = "TEXT DEFAULT '[]'" if col == "tags" else "TEXT DEFAULT NULL" if col in ("last_down_alert", "keyword", "first_failure_at") else "INTEGER DEFAULT 0"
            await conn.execute(f"ALTER TABLE sites ADD COLUMN {col} {col_type}")

    async with conn.execute("PRAGMA table_info(app_settings)") as c:
        settings_cols = {r[1] for r in await c.fetchall()}
    for col, col_type in [
        ("site_title", "TEXT DEFAULT 'Uptime Monitor'"), ("logo_url", "TEXT DEFAULT ''"),
        ("footer_text", "TEXT DEFAULT ''"), ("primary_color", "TEXT DEFAULT '#00ff88'"),
        ("brand_accent_color", "TEXT DEFAULT '#06b6d4'"),
    ]:
        if col not in settings_cols:
            await conn.execute(f"ALTER TABLE app_settings ADD COLUMN {col} {col_type}")

    # Sync sites.status from latest status_history for consistency
    await conn.execute("""UPDATE sites SET status = (
        SELECT sh.status FROM status_history sh
        WHERE sh.site_id = sites.id
        ORDER BY sh.checked_at DESC LIMIT 1
    ) WHERE id IN (SELECT DISTINCT site_id FROM status_history)""")


async def _seed_sites(conn):
    """Заповнює таблицю сайтів початковими даними, якщо вона порожня."""
    import sys, urllib.parse, re
    async with conn.execute("SELECT COUNT(*) FROM sites") as c:
        row = await c.fetchone()
        if row[0] > 0:
            return
    is_testing = "pytest" in sys.modules or os.environ.get("TESTING")
    force_seed = os.environ.get("FORCE_DB_SEED") == "True"
    if is_testing and not force_seed:
        return

    default_sites = []
    try:
        app_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(app_dir, "default_sites.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    default_sites.extend(data)
    except Exception as e:
        from .logger import logger
        logger.error("Failed to load default_sites.json: %s", e)

    for env_name in ("UPTIME_MONITOR_URL", "UPTIME_MONITOR_URLS"):
        val = os.environ.get(env_name, "").strip()
        if not val:
            continue
        if val.startswith("["):
            try:
                for item in json.loads(val):
                    if isinstance(item, dict) and "url" in item:
                        default_sites.append(item)
                    elif isinstance(item, str):
                        default_sites.append({"name": urllib.parse.urlparse(item).netloc or item, "url": item})
            except Exception as e:
                from .logger import logger
                logger.error("Failed to parse %s: %s", env_name, e)
        else:
            for u in re.split(r'[,\n;]+', val):
                u = u.strip()
                if u:
                    default_sites.append({"name": urllib.parse.urlparse(u).netloc or u, "url": u})

    seen = set()
    has_tg = bool(os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN"))
    for ds in default_sites:
        url = ds.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        methods = list(ds.get("notify_methods", []))
        if has_tg and "telegram" not in methods:
            methods.append("telegram")
        try:
            await conn.execute(
                """INSERT OR IGNORE INTO sites (name, url, check_interval, notify_methods, monitor_type, keyword, tags, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
                (ds.get("name") or urllib.parse.urlparse(url).netloc or url,
                 url, ds.get("check_interval", 60), json.dumps(methods),
                 ds.get("monitor_type", "http"), ds.get("keyword"), json.dumps(ds.get("tags", []))),
            )
        except Exception as e:
            from .logger import logger
            logger.error("Failed to seed %s: %s", url, e)


async def _seed_notify_config(conn):
    """Заповнює notify_config, якщо порожня."""
    import sys
    is_testing = "pytest" in sys.modules or os.environ.get("TESTING")
    force_seed = os.environ.get("FORCE_DB_SEED") == "True"
    if is_testing and not force_seed:
        return
    async with conn.execute("SELECT COUNT(*) FROM notify_config") as c:
        row = await c.fetchone()
        if row[0] > 0:
            return
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
    tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if tg_token and tg_chat_id:
        settings = {
            "telegram": {"enabled": True, "channels": [{"id": "default", "name": "Основний", "token": tg_token, "chat_id": tg_chat_id}]},
            "discord": {"enabled": False, "channels": [{"id": "default", "name": "Основний", "webhook_url": ""}]},
            "teams": {"enabled": False, "channels": [{"id": "default", "name": "Основний", "webhook_url": ""}]},
            "email": {"enabled": False, "smtp_server": "", "smtp_port": 587, "username": "", "password": "", "to_email": ""},
            "webhook": {"enabled": False, "channels": []},
        }
        await conn.execute("INSERT OR REPLACE INTO notify_config (id, config) VALUES (1, ?)", (json.dumps(settings),))
    elif not is_testing:
        await conn.execute("INSERT OR IGNORE INTO notify_config (id, config) VALUES (1, '{}')")


async def _cleanup_old_data(conn):
    """Retention: видаляє застарілі записи з таблиць."""
    from .logger import logger

    # status_history — старше 30 днів
    async with conn.execute("DELETE FROM status_history WHERE checked_at < datetime('now', '-30 days')") as c:
        deleted = c.rowcount
        if deleted:
            logger.info("Cleaned %d old status_history rows", deleted)

    # notification_history — старше 90 днів
    async with conn.execute("DELETE FROM notification_history WHERE sent_at < datetime('now', '-90 days')") as c:
        deleted = c.rowcount
        if deleted:
            logger.info("Cleaned %d old notification_history rows", deleted)

    # rate_limits — старше 7 днів
    async with conn.execute("DELETE FROM rate_limits WHERE attempted_at < datetime('now', '-7 days')") as c:
        deleted = c.rowcount
        if deleted:
            logger.info("Cleaned %d old rate_limit rows", deleted)

    # csrf_tokens — старше 24 годин
    async with conn.execute("DELETE FROM csrf_tokens WHERE created_at < datetime('now', '-1 day')") as c:
        deleted = c.rowcount
        if deleted:
            logger.info("Cleaned %d old csrf_token rows", deleted)

    # sessions — прострочені
    async with conn.execute("DELETE FROM sessions WHERE expires_at < datetime('now')") as c:
        deleted = c.rowcount
        if deleted:
            logger.info("Cleaned %d expired sessions", deleted)


async def init_database(db_path: str):
    """Ініціалізує базу даних: таблиці, міграції, початкові дані."""
    async with get_db_connection(db_path) as conn:
        await _create_tables(conn)
        await _run_migrations(conn)
        await _seed_sites(conn)
        await _seed_notify_config(conn)
        await _cleanup_old_data(conn)
        await conn.commit()


async def get_all_sites(db_path: str) -> list[dict[str, Any]]:
    """Отримує всі сайти"""
    async with get_db_connection(db_path) as conn:
        async with conn.execute("SELECT * FROM sites ORDER BY id DESC") as c:
            rows = await c.fetchall()
            return [dict(row) for row in rows]


async def get_active_sites(db_path: str) -> list[dict[str, Any]]:
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
    notify_methods: Optional[list[str]] = None,
    monitor_type: str = "http",
    keyword: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> int:
    """Додає новий сайт"""
    async with get_db_connection(db_path) as conn:
        async with conn.execute(
            """INSERT INTO sites (name, url, check_interval, notify_methods, monitor_type, keyword, tags, is_active)
                     VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
            (
                name,
                url,
                check_interval,
                json.dumps(notify_methods or []),
                monitor_type,
                keyword,
                json.dumps(tags or []),
            ),
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
        "keyword",
        "tags",
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
        await conn.execute(
            f"UPDATE sites SET {', '.join(updates)} WHERE id = ?", params
        )  # nosec B608
        await conn.commit()


async def delete_site(db_path: str, site_id: int) -> bool:
    """Видаляє сайт та його історію. Повертає True, якщо сайт було видалено."""
    async with get_db_connection(db_path) as conn:
        await conn.execute("DELETE FROM status_history WHERE site_id = ?", (site_id,))
        await conn.execute("DELETE FROM ssl_certificates WHERE site_id = ?", (site_id,))
        cursor = await conn.execute("DELETE FROM sites WHERE id = ?", (site_id,))
        await conn.commit()
        return cursor.rowcount > 0


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
                datetime.now(timezone.utc).isoformat(),
            ),
        )

        await conn.commit()


async def cleanup_old_history():
    """Видаляє записи старші 30 днів. Викликається з monitor_loop раз на годину."""
    try:
        async with get_db_connection() as conn:
            await conn.execute(
                "DELETE FROM status_history WHERE checked_at < datetime('now', '-30 days')"
            )
            await conn.commit()
    except Exception:
        pass


async def get_site_stats(db_path: str, site_id: int) -> dict[str, Any]:
    """Отримує статистику сайту"""
    async with get_db_connection(db_path) as conn:
        async with conn.execute(
            """SELECT * FROM status_history
                     WHERE site_id = ? ORDER BY checked_at DESC LIMIT 1""",
            (site_id,),
        ) as c:
            last_check = await c.fetchone()

        async with conn.execute(
            """SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'up' THEN 1 ELSE 0 END) as up_count
                     FROM status_history WHERE site_id = ?""",
            (site_id,),
        ) as c:
            stats = await c.fetchone()

    return {
        "last_check": dict(last_check) if last_check else None,
        "total_checks": stats["total"] if stats else 0,
        "up_count": stats["up_count"] if stats else 0,
    }


async def save_notify_settings(db_path: str, settings: dict[str, Any]):
    """Зберігає налаштування сповіщень"""
    async with get_db_connection(db_path) as conn:
        await conn.execute(
            "INSERT OR REPLACE INTO notify_config (id, config) VALUES (1, ?)",
            (json.dumps(settings),),
        )
        await conn.commit()


async def load_notify_settings(db_path: str) -> dict[str, Any]:
    """Завантажує налаштування сповіщень"""
    async with get_db_connection(db_path) as conn:
        async with conn.execute("SELECT config FROM notify_config WHERE id = 1") as c:
            row = await c.fetchone()

    if row:
        return json.loads(row["config"])
    return {}


async def get_ssl_certificates(db_path: str) -> list[dict[str, Any]]:
    """Отримує всі SSL сертифікати"""
    async with get_db_connection(db_path) as conn:
        async with conn.execute("""SELECT c.*, s.name as site_name, s.url as site_url
                     FROM ssl_certificates c
                     JOIN sites s ON c.site_id = s.id
                     WHERE s.is_active = 1
                     ORDER BY c.days_until_expire ASC""") as c:
            rows = await c.fetchall()
            return [dict(row) for row in rows]


async def save_ssl_certificate(db_path: str, site_id: int, cert_data: dict[str, Any]):
    """Зберігає або оновлює SSL сертифікат"""
    async with get_db_connection(db_path) as conn:
        async with conn.execute(
            """SELECT id FROM ssl_certificates WHERE site_id = ?""", (site_id,)
        ) as c:
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
                    datetime.now(timezone.utc).isoformat(),
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
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        await conn.commit()


async def get_maintenance_windows(db_path: str) -> list[dict[str, Any]]:
    """Отримує всі періоди обслуговування"""
    async with get_db_connection(db_path) as conn:
        async with conn.execute("""SELECT mw.*, s.name as site_name
               FROM maintenance_windows mw
               LEFT JOIN sites s ON mw.site_id = s.id
               ORDER BY mw.id DESC""") as c:
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
            (
                name,
                site_id,
                rule_type,
                start_time,
                end_time,
                day_of_week,
                start_hour_minute,
                duration_minutes,
            ),
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
        await conn.execute(
            "UPDATE maintenance_windows SET is_active = ? WHERE id = ?",
            (1 if is_active else 0, window_id),
        )
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
            (
                user_id,
                username,
                action,
                target_type,
                target_id,
                details,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await conn.commit()


async def get_audit_log(db_path: str, limit: int = 200) -> list:
    """Get recent audit log entries."""
    async with get_db_connection(db_path) as conn:
        async with conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)) as c:
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
            (
                site_id,
                site_name,
                method,
                status,
                (message_preview or "")[:200],
                datetime.now(timezone.utc).isoformat(),
            ),
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
            (
                os.path.basename(backup_path),
                backup_path,
                os.path.getsize(backup_path),
                site_count,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await conn.commit()
    return {
        "filename": os.path.basename(backup_path),
        "path": backup_path,
        "site_count": site_count,
    }


async def get_backups(db_path: str) -> list:
    """List all backups."""
    async with get_db_connection(db_path) as conn:
        async with conn.execute("SELECT * FROM backups ORDER BY id DESC LIMIT 20") as c:
            rows = await c.fetchall()
            return [dict(row) for row in rows]


async def check_db_rate_limit(
    endpoint: str, ip: str, max_attempts: int = 5, window_seconds: int = 900
) -> bool:
    """Returns True if within limit, False if rate limited."""
    import time

    now = time.time()
    # Clean expired entries first
    async with get_db_connection() as conn:
        await conn.execute("DELETE FROM rate_limits WHERE reset_at < ?", (now,))

        # Atomic upsert: create if not exists, increment if exists and within window
        await conn.execute(
            """INSERT INTO rate_limits (endpoint, ip, attempt_count, reset_at)
               VALUES (?, ?, 1, ?)
               ON CONFLICT(endpoint, ip) DO UPDATE SET
                 attempt_count = CASE WHEN excluded.reset_at > ? THEN attempt_count + 1 ELSE 1 END,
                 reset_at = CASE WHEN excluded.reset_at > ? THEN reset_at ELSE excluded.reset_at END""",
            (endpoint, ip, now + window_seconds, now, now),
        )

        async with conn.execute(
            "SELECT attempt_count FROM rate_limits WHERE endpoint = ? AND ip = ?",
            (endpoint, ip),
        ) as c:
            row = await c.fetchone()
            limited = row and row["attempt_count"] > max_attempts

        await conn.commit()
    return not limited
