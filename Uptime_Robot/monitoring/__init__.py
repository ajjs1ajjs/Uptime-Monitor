"""Модуль для моніторингу сайтів"""

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import aiohttp

from ..database import get_db_connection
from ..http_client import get_session
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


def _host_resolves_to_blocked(host: str) -> bool:
    """True if ``host`` (literal IP or DNS name) maps to an internal address.

    URLs are validated against the same loopback/link-local/reserved set at
    creation time, but DNS is resolved again here at check time — a hostname
    can be re-pointed at an internal address after creation (DNS rebinding). This
    re-checks at the moment of use so PING/PORT/DNS probes cannot be turned into
    an SSRF scan of dangerous targets. Resolution failures are NOT treated as
    blocked (let the probe surface them as a normal "down").

    NOTE: private RFC 1918 ranges (10/8, 172.16/12, 192.168/16) are intentionally
    allowed — this is an internal corporate monitor whose primary job is to watch
    services on the private network. Only loopback, link-local (incl. the
    169.254.169.254 cloud-metadata IP), reserved, multicast and unspecified
    addresses remain blocked.
    """
    import ipaddress
    import socket

    def _blocked(addr) -> bool:
        return (
            addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
            or addr.is_unspecified
        )

    host = (host or "").strip().rstrip(".")
    if not host:
        return False
    try:
        return _blocked(ipaddress.ip_address(host))
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except (OSError, UnicodeError):
        return False
    for *_, sockaddr in infos:
        try:
            if _blocked(ipaddress.ip_address(sockaddr[0])):
                return True
        except ValueError:
            continue
    return False


async def load_notify_settings_from_db() -> dict[str, Any]:
    try:
        async with get_db_connection() as conn:
            async with conn.execute("SELECT config FROM notify_config WHERE id = 1") as c:
                row = await c.fetchone()
                if row:
                    return json.loads(row["config"])
    except Exception as e:
        logger.error("Failed to load notify settings from DB: %s", e)
    return {}


async def _check_dns(url: str, start_time: datetime) -> tuple:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.hostname or parsed.path.split("/")[0]
    if ":" in host:
        host = host.split(":")[0]

    if _host_resolves_to_blocked(host):
        response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        return "down", 1, response_time, "Blocked internal address"

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

    if _host_resolves_to_blocked(host):
        response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        return "down", 1, response_time, "Blocked internal address"

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

    if _host_resolves_to_blocked(host):
        response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        return "down", port, response_time, "Blocked internal address"

    reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
    try:
        response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        return "up", port, response_time, None
    finally:
        # Always release the socket, even if the lines above start raising in
        # future edits — the connection must never leak.
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


_REDIRECT_CODES = (301, 302, 303, 307, 308)
_MAX_REDIRECTS = 5
_REGEX_TIMEOUT_SECONDS = 2


async def _match_keyword(keyword: str, body_text: str) -> Optional[str]:
    """Apply a keyword/regex content check. Returns an error string or None.

    Regex matching runs in a worker thread with a timeout so a catastrophic
    backtracking pattern (ReDoS) against an attacker-influenced body cannot
    block the monitoring event loop.
    """
    if keyword.startswith("regex:"):
        import re

        pattern = keyword[6:]
        try:
            compiled = re.compile(pattern)
        except re.error as e:
            return f"Invalid regex pattern: {e}"
        try:
            matched = await asyncio.wait_for(
                asyncio.to_thread(compiled.search, body_text), timeout=_REGEX_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            return "Regex evaluation timed out"
        if not matched:
            return "Regex pattern not matched"
    elif keyword not in body_text:
        return "Keyword not found"
    return None


async def _check_http(
    url: str, start_time: datetime, policy: dict, keyword: Optional[str]
) -> tuple:
    import sys
    from urllib.parse import urljoin, urlparse

    _os = "Windows NT 10.0; Win64; x64" if sys.platform == "win32" else "X11; Linux x86_64"
    headers = {"User-Agent": f"Mozilla/5.0 ({_os}) AppleWebKit/537.36"}
    # Reuse the shared pooled session (keep-alive / connection reuse) instead of
    # building and tearing down a ClientSession on every single check.
    session = await get_session()
    timeout = aiohttp.ClientTimeout(total=policy["request_timeout_seconds"])
    verify_ssl = policy.get("verify_ssl", True)

    # Follow redirects MANUALLY so every hop's host is re-validated against the
    # blocked-IP set. With allow_redirects=True aiohttp would transparently
    # follow a 30x Location into 127.0.0.1 / 169.254.169.254 / RFC1918, and the
    # creation-time SSRF check (which only saw the original host) would be
    # bypassed. Re-resolving each hop also defeats DNS rebinding on the target.
    current_url = url
    for _hop in range(_MAX_REDIRECTS + 1):
        if _host_resolves_to_blocked(urlparse(current_url).hostname or ""):
            response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            return "down", None, response_time, "Blocked internal address"

        async with session.get(
            current_url,
            timeout=timeout,
            headers=headers,
            ssl=verify_ssl,
            allow_redirects=False,
        ) as response:
            status_code = response.status

            location = response.headers.get("Location") if status_code in _REDIRECT_CODES else None
            if location:
                current_url = urljoin(current_url, location)
                continue

            response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            if keyword:
                try:
                    body_text = await response.text(errors="ignore")
                except Exception:
                    body_text = ""
                err = await _match_keyword(keyword, body_text)
                if err:
                    return "down", status_code, response_time, err

            if policy["treat_4xx_as_down"]:
                status = "up" if 200 <= status_code < 400 else "down"
            else:
                status = "up" if status_code < 500 else "down"
            return status, status_code, response_time, None

    response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
    return "down", None, response_time, "Too many redirects"


_flap_state: dict[int, dict] = {}
_LAST_FLAP_CLEANUP = time.time()


def _cleanup_flap_state():
    global _LAST_FLAP_CLEANUP
    now = time.time()
    if now - _LAST_FLAP_CLEANUP < 3600:
        return
    _LAST_FLAP_CLEANUP = now
    cutoff = now - 3600
    for sid in list(_flap_state.keys()):
        if _flap_state[sid]["last_time"] < cutoff:
            del _flap_state[sid]


def _check_flapping(site_id: int, prev_status: str, status: str, policy: dict) -> bool:
    _cleanup_flap_state()
    now = time.time()
    state = _flap_state.get(site_id)
    if state is None:
        state = {"count": 0, "last_time": now, "suppressed_until": 0}
        _flap_state[site_id] = state

    if state["suppressed_until"] > now:
        if (now - state["last_time"]) >= policy["flapping_suppression_seconds"]:
            state["count"] = 0
            state["suppressed_until"] = 0
        else:
            return True

    if prev_status in ("up", "down") and status in ("up", "down") and prev_status != status:
        if (now - state["last_time"]) <= policy["flapping_window_seconds"]:
            state["count"] += 1
        else:
            state["count"] = 1
        state["last_time"] = now

        if state["count"] >= policy["flapping_threshold"]:
            state["suppressed_until"] = now + policy["flapping_suppression_seconds"]
            logger.warning(
                "Site %d flapping detected — alerts suppressed for %ss",
                site_id,
                policy["flapping_suppression_seconds"],
            )
            return True

    return False


def _process_alerting(
    status,
    prev_status,
    notify_methods,
    site_name,
    url,
    status_code,
    error_message,
    checked_at,
    failed_attempts,
    success_attempts,
    last_down_alert_str,
    first_failure_at_str,
    skip_alert,
):
    """Pure decision step: compute the new counters/alert-state and the list of
    alert messages to dispatch.

    It performs NO network or DB I/O so it can run inside the single write
    transaction in check_site_status. The caller sends `alerts` AFTER the commit.
    Returns (failed_attempts, success_attempts, last_down_alert, first_failure_at, alerts).
    """
    checked_at_dt = checked_at
    last_down_alert = datetime.fromisoformat(last_down_alert_str) if last_down_alert_str else None
    first_failure_at = (
        datetime.fromisoformat(first_failure_at_str) if first_failure_at_str else None
    )
    policy = get_alert_policy()
    alerts: list[dict] = []

    if status == "down":
        # Consecutive-failure bookkeeping must run for EVERY down result, not
        # only when notify_methods is set — otherwise sites without alert
        # channels report a stuck failed_attempts counter.
        failed_attempts += 1
        success_attempts = 0
        should_alert = False
        alert_type = ""
        grace = policy.get("grace_period_seconds", 0)

        if prev_status in ("up", None):
            first_failure_at = checked_at_dt
            if grace <= 0:
                should_alert = True
                alert_type = "NEW"
        else:
            if last_down_alert is None:
                elapsed = (
                    (checked_at_dt - first_failure_at).total_seconds() if first_failure_at else 0
                )
                if elapsed >= grace:
                    should_alert = True
                    alert_type = "NEW"
            else:
                if (checked_at_dt - last_down_alert).total_seconds() >= policy[
                    "still_down_repeat_seconds"
                ]:
                    should_alert = True
                    alert_type = "REPEAT"

        if should_alert and notify_methods and not skip_alert:
            alerts.append(
                {
                    "alert_type": "down" if alert_type == "NEW" else "still_down",
                    "site_name": site_name,
                    "url": url,
                    "status_code": status_code or "N/A",
                    "error": error_message or "None",
                    "checked_at": checked_at_dt.isoformat(),
                }
            )
            last_down_alert = checked_at_dt
    elif status == "up":
        failed_attempts = 0
        first_failure_at = None
        success_attempts += 1
        if (
            prev_status == "down"
            and notify_methods
            and success_attempts >= policy["up_success_threshold"]
            and not skip_alert
        ):
            alerts.append(
                {
                    "alert_type": "up",
                    "site_name": site_name,
                    "url": url,
                    "status_code": status_code,
                    "response_time": None,
                    "checked_at": checked_at_dt.isoformat(),
                }
            )
            last_down_alert = None
    else:
        success_attempts = 0

    return failed_attempts, success_attempts, last_down_alert, first_failure_at, alerts


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
        logger.error("Failed to fetch monitor config for site %d: %s", site_id, e)

    under_maint = False
    try:
        under_maint = await is_under_maintenance(site_id)
    except Exception as e:
        logger.error("Failed checking maintenance status for site %d: %s", site_id, e)

    policy = get_alert_policy()
    delays = policy["retry_delays"]
    max_retries = policy["max_retries"]
    max_attempts = max_retries + 1

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
                status, status_code, response_time, error_message = await _check_ping(
                    url, start_time
                )
            elif monitor_type == "dns":
                status, status_code, response_time, error_message = await _check_dns(
                    url, start_time
                )
            elif monitor_type in ("port", "tcp"):
                status, status_code, response_time, error_message = await _check_port(
                    url, start_time, policy["request_timeout_seconds"]
                )
            else:
                status, status_code, response_time, error_message = await _check_http(
                    url, start_time, policy, keyword
                )
        except aiohttp.ClientConnectorError:
            status, status_code, response_time, error_message = (
                "down",
                None,
                None,
                "Connection failed",
            )
        except asyncio.TimeoutError:
            status, status_code, response_time, error_message = "down", None, None, "Timeout"
        except Exception as e:
            status, status_code, response_time, error_message = "down", None, None, str(e)[:100]

        if status != "down" or attempt == max_attempts - 1:
            break

        # retry_delays may be shorter than the number of retries; reuse the last
        # configured delay instead of raising IndexError (which would abort the
        # whole check and silently stop monitoring the site).
        delay = delays[attempt] if attempt < len(delays) else delays[-1]
        logger.info(
            "Site %s (ID: %d) check failed (attempt %d/%d): %s. Retrying in %ds...",
            url,
            site_id,
            attempt + 1,
            max_attempts,
            error_message,
            delay,
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

    from ..state import DB_PATH

    rt_rounded = round(response_time, 2) if response_time else None

    # Single transaction: read prior state, decide alerting (pure CPU, no I/O),
    # then persist status + history + counters + alert-state atomically. The
    # alert decision is computed BEFORE the write so a crash can never leave a
    # status_history row whose counters were never persisted, and concurrent
    # checks of the same site cannot interleave a read-modify-write. Notification
    # network I/O happens AFTER commit, holding no DB lock.
    site_name = url
    alerts: list[dict] = []
    async with get_db_connection(DB_PATH) as conn:
        try:
            # IMMEDIATE acquires the write lock up front so busy_timeout applies;
            # a plain BEGIN takes a read snapshot first and a later write can fail
            # instantly with a stale-snapshot "database is locked" under WAL.
            await conn.execute("BEGIN IMMEDIATE")
            async with conn.execute(
                "SELECT name, status, failed_attempts, success_attempts, last_down_alert, first_failure_at FROM sites WHERE id = ?",
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
            first_failure_at_str = row["first_failure_at"] if row else None

            skip_alert = _check_flapping(site_id, prev_status, status, policy)
            (
                failed_attempts,
                success_attempts,
                last_down_alert,
                first_failure_at,
                alerts,
            ) = _process_alerting(
                status,
                prev_status,
                notify_methods,
                site_name,
                url,
                status_code,
                error_message,
                checked_at,
                failed_attempts,
                success_attempts,
                last_down_alert_str,
                first_failure_at_str,
                skip_alert,
            )

            # Record EVERY check (not only transitions) so uptime % = up/total is
            # a true ratio of checks. The 30-day retention bounds table growth.
            await conn.execute(
                """INSERT INTO status_history (site_id, status, status_code, response_time, error_message, checked_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (site_id, status, status_code, rt_rounded, error_message, checked_at_iso),
            )

            await conn.execute(
                """UPDATE sites SET
                   status = ?, status_code = ?, response_time = ?,
                   failed_attempts = ?, success_attempts = ?, last_down_alert = ?,
                   first_failure_at = ?
                   WHERE id = ?""",
                (
                    status,
                    status_code,
                    rt_rounded,
                    failed_attempts,
                    success_attempts,
                    last_down_alert.isoformat() if last_down_alert else None,
                    first_failure_at.isoformat() if first_failure_at else None,
                    site_id,
                ),
            )
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise

    # Notifications (network I/O) — after commit, no DB lock held.
    for msg in alerts:
        await send_notification(msg, notify_methods, notify_settings, site_id, site_name)

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

        await conn.execute(
            """INSERT INTO ssl_certificates
            (site_id, hostname, issuer, subject, start_date, expire_date, days_until_expire, is_valid, last_checked)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(site_id) DO UPDATE SET
            hostname=excluded.hostname, issuer=excluded.issuer, subject=excluded.subject,
            start_date=excluded.start_date, expire_date=excluded.expire_date,
            days_until_expire=excluded.days_until_expire, is_valid=excluded.is_valid,
            last_checked=excluded.last_checked""",
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

        async with conn.execute(
            "SELECT last_notified, ssl_notified_thresholds FROM ssl_certificates WHERE site_id = ?",
            (site_id,),
        ) as c:
            row = await c.fetchone()

        notified = set()
        if row and row["ssl_notified_thresholds"]:
            try:
                notified = set(json.loads(row["ssl_notified_thresholds"]))
            except Exception:
                notified = set()

        last_notif_dt = None
        if row and row["last_notified"]:
            try:
                last_notif_dt = datetime.fromisoformat(row["last_notified"])
            except Exception:
                last_notif_dt = None

        cooldown = policy["ssl_notification_cooldown_seconds"]
        thresholds = policy["ssl_notification_days"]
        thresholds_to_notify = [t for t in thresholds if days <= t and t not in notified]

        if thresholds_to_notify and notify_methods:
            if (
                last_notif_dt
                and (datetime.now(timezone.utc) - last_notif_dt).total_seconds() < cooldown
            ):
                thresholds_to_notify = []

        for threshold in thresholds_to_notify:
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
                "threshold_days": threshold,
            }
            await send_notification(msg, notify_methods, notify_settings, site_id, site_name)
            notified.add(threshold)

        if thresholds_to_notify:
            await conn.execute(
                "UPDATE ssl_certificates SET last_notified = ?, ssl_notified_thresholds = ? WHERE site_id = ?",
                (
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(list(notified)),
                    site_id,
                ),
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
            logger.error("Error checking SSL certificate for site %s: %s", site["url"], e)
        await asyncio.sleep(1)


async def monitor_loop(notify_settings: dict[str, Any], default_check_interval: int = 60):
    policy = get_alert_policy()
    ssl_check_interval = policy["ssl_check_interval_hours"] * 3600
    last_cert_check = datetime.now(timezone.utc) - timedelta(hours=25)
    last_notify_settings_reload = datetime.now(timezone.utc)
    notify_settings_reload_interval = 30
    # Purge expired sessions / stale CSRF tokens periodically so those tables do
    # not grow without bound. Run shortly after startup, then hourly.
    last_auth_cleanup = datetime.now(timezone.utc) - timedelta(hours=2)
    auth_cleanup_interval = 3600

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
                        logger.error("Background check task for site %d failed: %s", site_id, e)
                    del active_tasks[site_id]

            if (
                current_time - last_notify_settings_reload
            ).total_seconds() >= notify_settings_reload_interval:
                db_settings = await load_notify_settings_from_db()
                if db_settings:
                    for key, value in db_settings.items():
                        notify_settings[key] = value
                    logger.debug("Reloaded notification settings from DB")
                # Advance the marker regardless of result, otherwise an empty
                # config makes us re-query the DB on every 5s loop iteration.
                last_notify_settings_reload = current_time

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

            if (
                datetime.now(timezone.utc) - last_auth_cleanup
            ).total_seconds() >= auth_cleanup_interval:
                from ..auth_module import cleanup_expired_sessions
                from ..csrf import cleanup_expired_csrf_tokens
                from ..state import DB_PATH

                await cleanup_expired_sessions(DB_PATH)
                await cleanup_expired_csrf_tokens()
                last_auth_cleanup = datetime.now(timezone.utc)

            await asyncio.sleep(5)

        except asyncio.CancelledError:
            logger.info("Monitor loop cancelled, shutting down...")
            raise
        except Exception as e:
            logger.error("Error in monitor_loop: %s", e)
            await asyncio.sleep(5)
