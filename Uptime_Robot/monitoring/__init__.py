"""Модуль для моніторингу сайтів"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import aiohttp

from ..database import get_db_connection
from ..logger import logger
from ..metrics_store import increment_metric, update_monitor_heartbeat
from ..notifications import send_notification
from ..ssl_checker import check_ssl_certificate
from .alerting import get_alert_policy
from .maintenance import is_under_maintenance


def normalize_ssl_url(url: str) -> Optional[str]:
    if not url:
        return None
    url = url.strip()
    if not url.lower().startswith(("http://", "https://")):
        return f"https://{url}"
    return url


async def load_notify_settings_from_db() -> dict[str, Any]:
    try:
        async with get_db_connection() as conn:
            async with conn.execute("SELECT config FROM notify_config WHERE id = 1") as c:
                row = await c.fetchone()
                if row:
                    return json.loads(row["config"])
    except Exception as e:
        logger.error(f"Failed to load notify settings from DB: {e}")
    return {}


async def _check_dns(url: str, start_time: datetime) -> tuple:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.hostname or parsed.path.split("/")[0]
    if ":" in host:
        host = host.split(":")[0]

    loop = asyncio.get_event_loop()
    try:
        await loop.getaddrinfo(host, None)
        response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        return "up", 0, response_time, None
    except Exception as e:
        response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        return "down", 1, response_time, f"DNS resolution failed: {e}"


async def _check_ping(url: str, start_time: datetime) -> tuple:
    import sys
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.hostname or parsed.path.split("/")[0]
    if ":" in host:
        host = host.split(":")[0]

    is_win = sys.platform == "win32"
    ping_cmd = ["ping", "-n", "1", host] if is_win else ["ping", "-c", "1", "-W", "5", host]
    proc = await asyncio.create_subprocess_exec(
        *ping_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
    if proc.returncode == 0:
        return "up", 0, response_time, None
    return "down", 1, response_time, "Ping failed"


async def _check_port(url: str, start_time: datetime, timeout: int) -> tuple:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host_port = parsed.netloc or parsed.path.split("/")[0]
    if ":" in host_port:
        host, port_str = host_port.split(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            port = 80
    else:
        host = host_port
        port = 80

    reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass
    response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
    return "up", port, response_time, None


async def _check_http(
    url: str, start_time: datetime, policy: dict, keyword: Optional[str]
) -> tuple:
    import sys
    _os = "Windows NT 10.0; Win64; x64" if sys.platform == "win32" else "X11; Linux x86_64"
    headers = {"User-Agent": f"Mozilla/5.0 ({_os}) AppleWebKit/537.36"}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=policy["request_timeout_seconds"]),
            headers=headers,
            ssl=policy.get("verify_ssl", True),
            allow_redirects=True,
        ) as response:
            status_code = response.status
            response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            if keyword:
                try:
                    body_text = await response.text(errors="ignore")
                except Exception:
                    body_text = ""
                if keyword.startswith("regex:"):
                    import re

                    pattern = keyword[6:]
                    try:
                        if not re.search(pattern, body_text):
                            return "down", status_code, response_time, "Regex pattern not matched"
                    except Exception as e:
                        return "down", status_code, response_time, f"Invalid regex pattern: {e}"
                else:
                    if keyword not in body_text:
                        return "down", status_code, response_time, "Keyword not found"

            if policy["treat_4xx_as_down"]:
                status = "up" if 200 <= status_code < 400 else "down"
            else:
                status = "up" if status_code < 500 else "down"
            return status, status_code, response_time, None


async def _process_alerting(
    status,
    prev_status,
    notify_methods,
    notify_settings,
    site_id,
    site_name,
    url,
    status_code,
    error_message,
    checked_at,
    failed_attempts,
    success_attempts,
    last_down_alert_str,
):
    checked_at_dt = checked_at
    last_down_alert = datetime.fromisoformat(last_down_alert_str) if last_down_alert_str else None
    policy = get_alert_policy()

    if status == "down" and notify_methods:
        failed_attempts += 1
        success_attempts = 0
        should_alert = False
        alert_type = ""

        if prev_status in ("up", None):
            if failed_attempts >= policy["down_failures_threshold"]:
                should_alert = True
                alert_type = "NEW"
        else:
            if (
                last_down_alert is None
                or (checked_at_dt - last_down_alert).total_seconds()
                >= policy["still_down_repeat_seconds"]
            ):
                should_alert = True
                alert_type = "REPEAT"

        if should_alert:
            msg = {
                "alert_type": "down" if alert_type == "NEW" else "still_down",
                "site_name": site_name,
                "url": url,
                "status_code": status_code or "N/A",
                "error": error_message or "None",
                "checked_at": checked_at_dt.isoformat(),
            }
            await send_notification(msg, notify_methods, notify_settings, site_id, site_name)
            last_down_alert = checked_at_dt
            increment_metric("notifications_sent")

    if status == "up":
        failed_attempts = 0
        success_attempts += 1
        if (
            prev_status == "down"
            and notify_methods
            and success_attempts >= policy["up_success_threshold"]
        ):
            msg = {
                "alert_type": "up",
                "site_name": site_name,
                "url": url,
                "status_code": status_code,
                "response_time": None,
                "checked_at": checked_at_dt.isoformat(),
            }
            await send_notification(msg, notify_methods, notify_settings, site_id, site_name)
            last_down_alert = None
    else:
        if status != "down":
            success_attempts = 0

    return failed_attempts, success_attempts, last_down_alert


async def check_site_status(
    site_id: int, url: str, notify_methods: list[str], notify_settings: dict[str, Any]
):
    start_time = datetime.now(timezone.utc)
    status = "down"
    status_code = None
    response_time = None
    error_message = None

    increment_metric("checks_total")
    update_monitor_heartbeat()

    monitor_type, keyword = "http", None
    try:
        async with get_db_connection() as conn:
            async with conn.execute(
                "SELECT monitor_type, keyword FROM sites WHERE id = ?", (site_id,)
            ) as c:
                row = await c.fetchone()
                if row:
                    monitor_type = (row["monitor_type"] or "http").lower()
                    keyword = row["keyword"]
    except Exception as e:
        logger.error(f"Failed to fetch monitor config for site {site_id}: {e}")

    under_maint = False
    try:
        under_maint = await is_under_maintenance(site_id)
    except Exception as e:
        logger.error(f"Failed checking maintenance status for site {site_id}: {e}")

    delays = [30, 30]  # Delays in seconds between retries
    max_attempts = len(delays) + 1

    for attempt in range(max_attempts):
        start_time = datetime.now(timezone.utc)
        try:
            policy = get_alert_policy()
            if under_maint:
                status = "maintenance"
                status_code = None
                response_time = None
                error_message = "Maintenance Window Active"
            elif monitor_type == "ping":
                status, status_code, response_time, error_message = await _check_ping(url, start_time)
            elif monitor_type == "dns":
                status, status_code, response_time, error_message = await _check_dns(url, start_time)
            elif monitor_type in ("port", "tcp"):
                status, status_code, response_time, error_message = await _check_port(
                    url, start_time, policy["request_timeout_seconds"]
                )
            else:
                status, status_code, response_time, error_message = await _check_http(
                    url, start_time, policy, keyword
                )
        except aiohttp.ClientConnectorError:
            status, status_code, response_time, error_message = "down", None, None, "Connection failed"
        except asyncio.TimeoutError:
            status, status_code, response_time, error_message = "down", None, None, "Timeout"
        except Exception as e:
            status, status_code, response_time, error_message = "down", None, None, str(e)[:100]

        if status != "down" or attempt == max_attempts - 1:
            break

        delay = delays[attempt]
        logger.info(
            f"Site {url} (ID: {site_id}) check failed (attempt {attempt+1}/{max_attempts}): {error_message}. Retrying in {delay}s..."
        )
        await asyncio.sleep(delay)

    if status == "down" and not under_maint:
        increment_metric("checks_failed")

    checked_at = datetime.now(timezone.utc)
    checked_at_iso = checked_at.isoformat()

    try:
        from ..wss.manager import manager

        await manager.broadcast(
            {
                "type": "site_status",
                "site_id": site_id,
                "status": status,
                "status_code": status_code,
                "response_time": round(response_time, 2) if response_time else None,
                "error_message": error_message,
                "checked_at": checked_at_iso,
            }
        )
    except Exception:
        pass

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

        failed_attempts, success_attempts, last_down_alert = await _process_alerting(
            status,
            prev_status,
            notify_methods,
            notify_settings,
            site_id,
            site_name,
            url,
            status_code,
            error_message,
            checked_at,
            failed_attempts,
            success_attempts,
            last_down_alert_str,
        )

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
    site_id: int, url: str, notify_methods: list[str], notify_settings: dict[str, Any]
):
    if not url.lower().startswith("https://"):
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
                if (datetime.now(timezone.utc) - last_notif).total_seconds() < policy[
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
                await send_notification(msg, notify_methods, notify_settings, site_id, site_name)

                await conn.execute(
                    "UPDATE ssl_certificates SET last_notified = ? WHERE site_id = ?",
                    (datetime.now(timezone.utc).isoformat(), site_id),
                )
                await conn.commit()


async def check_all_certificates(notify_settings: dict[str, Any]):
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT id, url, notify_methods FROM sites WHERE is_active = 1 AND (url LIKE 'https://%' OR monitor_type = 'ssl')"
        ) as c:
            sites_raw = await c.fetchall()
            sites = [dict(s) for s in sites_raw]

    for site in sites:
        notify_methods = json.loads(site["notify_methods"]) if site["notify_methods"] else []
        try:
            await check_site_certificate(site["id"], site["url"], notify_methods, notify_settings)
        except Exception as e:
            logger.error(f"Error checking SSL certificate for site {site['url']}: {e}")
        await asyncio.sleep(1)


async def monitor_loop(notify_settings: dict[str, Any], default_check_interval: int = 60):
    policy = get_alert_policy()
    ssl_check_interval = policy["ssl_check_interval_hours"] * 3600
    last_cert_check = datetime.now(timezone.utc) - timedelta(hours=25)
    last_notify_settings_reload = datetime.now(timezone.utc)
    notify_settings_reload_interval = 30

    last_check_time = {}
    active_tasks: dict[int, asyncio.Task] = {}

    while True:
        try:
            current_time = datetime.now(timezone.utc)

            # Reap completed tasks
            for site_id in list(active_tasks.keys()):
                if active_tasks[site_id].done():
                    try:
                        active_tasks[site_id].result()
                    except Exception as e:
                        logger.error(f"Background check task for site {site_id} failed: {e}")
                    del active_tasks[site_id]

            if (
                current_time - last_notify_settings_reload
            ).total_seconds() >= notify_settings_reload_interval:
                db_settings = await load_notify_settings_from_db()
                if db_settings:
                    for key, value in db_settings.items():
                        notify_settings[key] = value
                    last_notify_settings_reload = current_time
                    logger.debug("Reloaded notification settings from DB")

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
                    if site["id"] not in active_tasks:
                        task = asyncio.create_task(
                            check_site_status(
                                site["id"], site["url"], notify_methods, notify_settings
                            )
                        )
                        active_tasks[site["id"]] = task
                        last_check_time[site["id"]] = current_time

            if (datetime.now(timezone.utc) - last_cert_check).total_seconds() >= ssl_check_interval:
                logger.info("Checking SSL certificates in background...")
                await check_all_certificates(notify_settings)
                last_cert_check = datetime.now(timezone.utc)

            await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"Error in monitor_loop: {e}")
            await asyncio.sleep(5)
