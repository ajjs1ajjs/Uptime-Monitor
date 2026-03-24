"""Модуль для моніторингу сайтів"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiohttp

try:
    from .config_manager import load_config
    from .database import get_db_connection
    from .logger import logger
    from .ssl_checker import check_ssl_certificate
except ImportError:
    from config_manager import load_config
    from database import get_db_connection
    from logger import logger
    from ssl_checker import check_ssl_certificate

# Чутливий профіль (конфігуровані значення з fallback)
SENSITIVE_DEFAULTS = {
    "request_timeout_seconds": 60,
    "down_failures_threshold": 1,
    "up_success_threshold": 1,
    "still_down_repeat_seconds": 300,
    "treat_4xx_as_down": True,
    "ssl_notification_days": 14,
    "ssl_notification_cooldown_seconds": 21600,
    "ssl_check_interval_hours": 6,
}


def get_alert_policy() -> Dict[str, Any]:
    """Повертає політику алертів із конфіга (чутливий профіль за замовчуванням)."""
    try:
        config = load_config() or {}
    except Exception:
        config = {}

    policy = (config.get("alert_policy") or {}).copy()

    result = SENSITIVE_DEFAULTS.copy()
    result.update({k: v for k, v in policy.items() if v is not None})

    # Нормалізація типів/меж
    try:
        result["request_timeout_seconds"] = max(1, int(result.get("request_timeout_seconds", 60)))
    except Exception:
        result["request_timeout_seconds"] = 60

    try:
        result["down_failures_threshold"] = max(1, int(result.get("down_failures_threshold", 1)))
    except Exception:
        result["down_failures_threshold"] = 1

    try:
        result["up_success_threshold"] = max(1, int(result.get("up_success_threshold", 1)))
    except Exception:
        result["up_success_threshold"] = 1

    try:
        result["still_down_repeat_seconds"] = max(
            60, int(result.get("still_down_repeat_seconds", 300))
        )
    except Exception:
        result["still_down_repeat_seconds"] = 300

    try:
        result["ssl_notification_days"] = max(1, int(result.get("ssl_notification_days", 14)))
    except Exception:
        result["ssl_notification_days"] = 14

    try:
        result["ssl_notification_cooldown_seconds"] = max(
            300, int(result.get("ssl_notification_cooldown_seconds", 21600))
        )
    except Exception:
        result["ssl_notification_cooldown_seconds"] = 21600

    try:
        result["ssl_check_interval_hours"] = max(1, int(result.get("ssl_check_interval_hours", 6)))
    except Exception:
        result["ssl_check_interval_hours"] = 6

    result["treat_4xx_as_down"] = bool(result.get("treat_4xx_as_down", True))
    return result


def normalize_ssl_url(url: str) -> Optional[str]:
    """Нормалізує URL для перевірки SSL (додає https:// якщо потрібно)"""
    if not url:
        return None
    url = url.strip()
    if not url.lower().startswith(("http://", "https://")):
        return f"https://{url}"
    return url


async def check_site_status(
    site_id: int, url: str, notify_methods: List[str], notify_settings: Dict[str, Any]
):
    """Перевіряє статус сайту та відправляє сповіщення"""
    try:
        from .notifications import send_notification
    except ImportError:
        from notifications import send_notification

    start_time = datetime.now()
    status = "down"
    status_code = None
    response_time = None
    error_message = None

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        policy = get_alert_policy()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=policy["request_timeout_seconds"]),
                headers=headers,
                ssl=False,
                allow_redirects=True,
            ) as response:
                status_code = response.status
                response_time = (datetime.now() - start_time).total_seconds() * 1000

                if policy["treat_4xx_as_down"]:
                    status = "up" if 200 <= status_code < 400 else "down"
                else:
                    status = "up" if status_code < 500 else "down"
    except aiohttp.ClientConnectorError:
        error_message = "Connection failed"
    except asyncio.TimeoutError:
        error_message = "Timeout"
    except Exception as e:
        error_message = str(e)[:100]

    checked_at = datetime.now()
    checked_at_iso = checked_at.isoformat()

    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT name, status, failed_attempts, success_attempts, last_down_alert FROM sites WHERE id = ?",
            (site_id,),
        ) as c:
            row = await c.fetchone()

        site_name = row["name"] if row else url
        prev_status = row["status"] if row else None
        failed_attempts = (
            row["failed_attempts"] if row and row["failed_attempts"] is not None else 0
        )
        success_attempts = (
            row["success_attempts"] if row and row["success_attempts"] is not None else 0
        )
        last_down_alert_str = row["last_down_alert"] if row else None
        last_down_alert = (
            datetime.fromisoformat(last_down_alert_str) if last_down_alert_str else None
        )

        # Only save to history when status CHANGES
        if prev_status != status:
            await conn.execute(
                """INSERT INTO status_history (site_id, status, status_code, response_time, error_message, checked_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    site_id,
                    status,
                    status_code,
                    round(response_time, 2) if response_time else None,
                    error_message,
                    checked_at_iso,
                ),
            )

        notification_status = prev_status

        if status == "down" and notify_methods:
            failed_attempts += 1
            success_attempts = 0

            should_alert = False
            alert_type = ""

            policy = get_alert_policy()
            if notification_status == "up" or notification_status is None:
                if failed_attempts >= policy["down_failures_threshold"]:
                    should_alert = True
                    alert_type = "NEW"
            else:
                if (
                    last_down_alert is None
                    or (checked_at - last_down_alert).total_seconds()
                    >= policy["still_down_repeat_seconds"]
                ):
                    should_alert = True
                    alert_type = "REPEAT"

            if should_alert:
                if alert_type == "NEW":
                    msg = {
                        "alert_type": "down",
                        "site_name": site_name,
                        "url": url,
                        "status_code": status_code or "N/A",
                        "error": error_message or "None",
                        "checked_at": checked_at_iso,
                    }
                else:
                    msg = {
                        "alert_type": "still_down",
                        "site_name": site_name,
                        "url": url,
                        "status_code": status_code or "N/A",
                        "error": error_message or "None",
                        "checked_at": checked_at_iso,
                    }

                await send_notification(msg, notify_methods, notify_settings)
                last_down_alert = checked_at

        if status == "up":
            failed_attempts = 0
            success_attempts += 1

            policy = get_alert_policy()
            if (
                notification_status == "down"
                and notify_methods
                and success_attempts >= policy["up_success_threshold"]
            ):
                msg = {
                    "alert_type": "up",
                    "site_name": site_name,
                    "url": url,
                    "status_code": status_code,
                    "response_time": response_time,
                    "checked_at": checked_at_iso,
                }
                await send_notification(msg, notify_methods, notify_settings)
                last_down_alert = None
        else:
            if status != "down":
                success_attempts = 0

        last_down_str = last_down_alert.isoformat() if last_down_alert else None

        await conn.execute(
            """UPDATE sites SET
               status = ?, status_code = ?, response_time = ?,
               failed_attempts = ?, success_attempts = ?, last_down_alert = ?
               WHERE id = ?""",
            (
                status,
                status_code,
                round(response_time, 2) if response_time else None,
                failed_attempts,
                success_attempts,
                last_down_str,
                site_id,
            ),
        )
        await conn.commit()

    return status, status_code, response_time, error_message


async def check_site_certificate(
    site_id: int, url: str, notify_methods: List[str], notify_settings: Dict[str, Any]
):
    """Перевіряє SSL сертифікат сайту"""
    try:
        from .notifications import send_notification
    except ImportError:
        from notifications import send_notification

    # Тільки для HTTPS
    if not url.lower().startswith("https://"):
        # Спробуємо нормалізувати
        if "." in url and "://" not in url:
            url = "https://" + url
        else:
            return

    cert_info = await check_ssl_certificate(url)
    if not cert_info:
        return

    async with get_db_connection() as conn:
        async with conn.execute("SELECT name FROM sites WHERE id = ?", (site_id,)) as c:
            row = await c.fetchone()
            site_name = row["name"] if row else url

        cursor = await conn.execute(
            """UPDATE ssl_certificates SET
               hostname = ?, issuer = ?, subject = ?, start_date = ?, expire_date = ?,
               days_until_expire = ?, is_valid = ?, last_checked = ?
               WHERE site_id = ?""",
            (
                cert_info["hostname"],
                cert_info["issuer"],
                cert_info["subject"],
                cert_info["start_date"],
                cert_info["expire_date"],
                cert_info["days_until_expire"],
                cert_info["is_valid"],
                cert_info["checked_at"],
                site_id,
            ),
        )

        if cursor.rowcount == 0:
            await conn.execute(
                """INSERT INTO ssl_certificates
                (site_id, hostname, issuer, subject, start_date, expire_date, days_until_expire, is_valid, last_checked)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    site_id,
                    cert_info["hostname"],
                    cert_info["issuer"],
                    cert_info["subject"],
                    cert_info["start_date"],
                    cert_info["expire_date"],
                    cert_info["days_until_expire"],
                    cert_info["is_valid"],
                    cert_info["checked_at"],
                ),
            )
        await conn.commit()

        # Сповіщення про закінчення терміну дії
        policy = get_alert_policy()
        days = cert_info["days_until_expire"]
        if days <= policy["ssl_notification_days"] and notify_methods:
            async with conn.execute(
                "SELECT last_notified FROM ssl_certificates WHERE site_id = ?", (site_id,)
            ) as c:
                row = await c.fetchone()

            should_notify = True
            if row and row["last_notified"]:
                last_notif = datetime.fromisoformat(row["last_notified"])
                if (datetime.now() - last_notif).total_seconds() < policy[
                    "ssl_notification_cooldown_seconds"
                ]:
                    should_notify = False

            if should_notify:
                expire_date = datetime.fromisoformat(cert_info["expire_date"]).strftime(
                    "%Y-%m-%d %H:%M"
                )

                if days <= 0 or days <= 3:
                    urgency = "КРИТИЧНО"
                elif days <= 7:
                    urgency = "ВАЖЛИВО"
                else:
                    urgency = "УВАГА"

                msg = {
                    "alert_type": "ssl",
                    "site_name": site_name,
                    "url": url,
                    "days_left": days,
                    "expire_date": expire_date,
                    "urgency": urgency,
                }
                await send_notification(msg, notify_methods, notify_settings)

                await conn.execute(
                    "UPDATE ssl_certificates SET last_notified = ? WHERE site_id = ?",
                    (datetime.now().isoformat(), site_id),
                )
                await conn.commit()


async def check_all_certificates(notify_settings: Dict[str, Any]):
    """Перевіряє всі SSL сертифікати"""
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT id, url, notify_methods FROM sites WHERE is_active = 1 AND (url LIKE 'https://%' OR monitor_type = 'ssl')"
        ) as c:
            sites_raw = await c.fetchall()
            sites = [dict(s) for s in sites_raw]

    for site in sites:
        notify_methods = json.loads(site["notify_methods"]) if site["notify_methods"] else []
        await check_site_certificate(site["id"], site["url"], notify_methods, notify_settings)
        await asyncio.sleep(1)


async def monitor_loop(notify_settings: Dict[str, Any], default_check_interval: int = 60):
    """Основний цикл моніторингу з підтримкою індивідуальних інтервалів і Stateless Storage в БД"""
    policy = get_alert_policy()
    ssl_check_interval = policy["ssl_check_interval_hours"] * 3600  # конвертація в секунди
    last_cert_check = datetime.now() - timedelta(hours=25)

    # Track last check time for each site locally in memory (just for pacing)
    # The actual failure/success state is now entirely in the DB.
    last_check_time = {}  # site_id -> datetime

    while True:
        try:
            current_time = datetime.now()

            async with get_db_connection() as conn:
                async with conn.execute(
                    "SELECT id, url, notify_methods, check_interval FROM sites WHERE is_active = 1"
                ) as c:
                    sites_raw = await c.fetchall()
                    sites = [dict(s) for s in sites_raw]

            for site in sites:
                notify_methods = (
                    json.loads(site["notify_methods"]) if site["notify_methods"] else []
                )
                site_interval = (
                    site["check_interval"] if site["check_interval"] else default_check_interval
                )

                last_check = last_check_time.get(site["id"])
                if (
                    last_check is None
                    or (current_time - last_check).total_seconds() >= site_interval
                ):
                    await check_site_status(
                        site["id"], site["url"], notify_methods, notify_settings
                    )
                    last_check_time[site["id"]] = current_time

            # Перевірка SSL сертифікатів
            if (datetime.now() - last_cert_check).total_seconds() >= ssl_check_interval:
                logger.info("Checking SSL certificates in background...")
                await check_all_certificates(notify_settings)
                last_cert_check = datetime.now()

            await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"Error in monitor_loop: {e}")
            await asyncio.sleep(5)
