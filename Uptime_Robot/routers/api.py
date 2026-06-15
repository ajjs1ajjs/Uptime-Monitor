import asyncio
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .. import auth_module, config_manager, models, monitoring
from .. import state as app_state
from ..database import get_db_connection
from ..dependencies import get_current_user, require_admin, require_viewer_or_higher
from ..monitoring import alerting
from ..state import DB_PATH

router = APIRouter(prefix="/api")


class SiteCreate(BaseModel):
    name: str
    url: str
    check_interval: int = 60
    is_active: bool = True
    notify_methods: Optional[list[str]] = []
    monitor_type: str = "http"
    keyword: Optional[str] = None
    tags: Optional[list[str]] = []


class SiteUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    check_interval: Optional[int] = None
    notify_methods: Optional[list[str]] = None
    is_active: Optional[bool] = None
    monitor_type: Optional[str] = None
    keyword: Optional[str] = None
    tags: Optional[list[str]] = None


class NotifySettingsModel(BaseModel):
    telegram: Optional[dict] = None
    teams: Optional[dict] = None
    discord: Optional[dict] = None
    slack: Optional[dict] = None
    email: Optional[dict] = None
    sms: Optional[dict] = None
    webhook: Optional[dict] = None


class AppSettingsModel(BaseModel):
    display_address: Optional[str] = ""
    site_title: Optional[str] = "Uptime Monitor"
    logo_url: Optional[str] = ""
    footer_text: Optional[str] = ""
    primary_color: Optional[str] = "#00ff88"
    brand_accent_color: Optional[str] = "#06b6d4"


class AlertPolicyModel(BaseModel):
    request_timeout_seconds: Optional[int] = None
    grace_period_seconds: Optional[int] = None
    up_success_threshold: Optional[int] = None
    still_down_repeat_seconds: Optional[int] = None
    treat_4xx_as_down: Optional[bool] = None
    ssl_notification_days: Optional[list[int]] = None
    ssl_notification_cooldown_seconds: Optional[int] = None
    ssl_check_interval_hours: Optional[int] = None
    verify_ssl: Optional[bool] = None
    retry_delays: Optional[list[int]] = None
    max_retries: Optional[int] = None
    flapping_threshold: Optional[int] = None
    flapping_window_seconds: Optional[int] = None
    flapping_suppression_seconds: Optional[int] = None


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "viewer"


class UserUpdate(BaseModel):
    role: Optional[str] = None
    password: Optional[str] = None


def _normalize_and_validate_url(raw_url: str, monitor_type: str) -> str:
    import ipaddress
    from urllib.parse import urlparse

    def _is_valid_host(hostname: Optional[str]) -> bool:
        if not hostname:
            return False
        host = hostname.strip().lower().rstrip(".")
        if not host:
            return False
        if host == "localhost":
            return False
        try:
            addr = ipaddress.ip_address(host)
            if addr.is_private or addr.is_loopback or addr.is_link_local:
                return False
            return True
        except ValueError:
            pass
        labels = host.split(".")
        if len(labels) < 2:
            return False
        for label in labels:
            if not label or len(label) > 63:
                return False
            if label.startswith("-") or label.endswith("-"):
                return False
            if not all(ch.isalnum() or ch == "-" for ch in label):
                return False
        return True

    url = (raw_url or "").strip()
    if not url:
        raise HTTPException(400, "URL required")

    m_type = (monitor_type or "http").lower()

    # Pre-processing for HTTP/SSL if missing scheme
    if m_type == "http" and not (url.startswith("http://") or url.startswith("https://")):
        url = "http://" + url

    if m_type == "ssl":
        normalized = monitoring.normalize_ssl_url(url)
        if not normalized:
            raise HTTPException(400, "Invalid URL for SSL check")
        url = normalized

    parsed = urlparse(url)

    # For HTTP/SSL, we require a scheme and netloc
    if m_type in ("http", "ssl"):
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise HTTPException(400, "HTTP/SSL URL must start with http:// or https://")
        if not _is_valid_host(parsed.hostname):
            raise HTTPException(400, "Invalid host in URL")
    else:
        # For PING/PORT, any valid host (with port) is okay
        # urlparse might put the host in path if no scheme
        host = parsed.netloc or parsed.path.split("/")[0]
        if ":" in host:
            host_only = host.split(":")[0]
            if not _is_valid_host(host_only):
                raise HTTPException(400, "Invalid host")
        elif not _is_valid_host(host):
            raise HTTPException(400, "Invalid host/IP")

    return url


@router.get("/sites")
async def get_sites(user: dict = Depends(require_viewer_or_higher)):
    if not user:
        raise HTTPException(status_code=401)
    async with get_db_connection() as conn:
        async with conn.execute("SELECT * FROM sites ORDER BY id") as c:
            sites_raw = await c.fetchall()
            sites = [dict(s) for s in sites_raw]

        # Bulk fetch latest statuses
        async with conn.execute(
            "SELECT site_id, status FROM (SELECT site_id, status, ROW_NUMBER() OVER (PARTITION BY site_id ORDER BY checked_at DESC) as rn FROM status_history) WHERE rn = 1"
        ) as c:
            last_status_raw = await c.fetchall()
            last_status_map = {row["site_id"]: row["status"] for row in last_status_raw}

        # Bulk fetch uptime statistics
        async with conn.execute(
            "SELECT site_id, COUNT(*) as total, SUM(CASE WHEN status = 'up' THEN 1 ELSE 0 END) as up_count FROM status_history GROUP BY site_id"
        ) as c:
            stats_raw = await c.fetchall()
            stats_map = {row["site_id"]: (row["total"], row["up_count"]) for row in stats_raw}

        result = []
        for site in sites:
            sid = site["id"]
            last_status = last_status_map.get(sid, "unknown")
            total, up_count = stats_map.get(sid, (0, 0))
            uptime = (
                (up_count / total * 100) if total > 0 else 0
            )
            result.append(
                {
                    **site,
                    "status": last_status,
                    "uptime": round(uptime, 2),
                    "notify_methods": (
                        json.loads(site["notify_methods"]) if site["notify_methods"] else []
                    ),
                    "tags": (
                        json.loads(site.get("tags", "[]"))
                        if site.get("tags") and site.get("tags") != "[]"
                        else []
                    ),
                }
            )
    return result


@router.get("/sites/history-all")
async def get_all_sites_history(user: dict = Depends(require_viewer_or_higher)):
    if not user:
        raise HTTPException(status_code=401)
    async with get_db_connection() as conn:
        async with conn.execute("""
            SELECT site_id, status, checked_at
            FROM status_history
            WHERE checked_at >= datetime('now', '-24 hours')
            ORDER BY checked_at ASC
        """) as c:
            results_raw = await c.fetchall()

        history = {}
        for r in results_raw:
            sid = r["site_id"]
            if sid not in history:
                history[sid] = []
            history[sid].append({"status": r["status"], "checked_at": r["checked_at"]})
    return history


@router.get("/sites/{site_id}/history")
async def get_site_history(
    site_id: int, limit: int = 50, user: dict = Depends(require_viewer_or_higher)
):
    if not user:
        raise HTTPException(status_code=401)
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT status, status_code, checked_at FROM status_history WHERE site_id = ? ORDER BY checked_at DESC LIMIT ?",
            (site_id, limit),
        ) as c:
            history_raw = await c.fetchall()
            history = [dict(h) for h in history_raw]
    return [
        {
            "status": h["status"],
            "status_code": h["status_code"],
            "checked_at": h["checked_at"],
        }
        for h in history
    ]


@router.get("/server-time")
async def get_server_time():
    now = datetime.now(timezone.utc)
    return {
        "timestamp": now.timestamp(),
        "iso": now.isoformat(),
        "timezone": "UTC",
    }


@router.post("/sites")
async def add_site(site: SiteCreate, user: dict = Depends(require_admin)):
    if not user:
        raise HTTPException(status_code=401)
    m_type = site.monitor_type.lower()
    url = _normalize_and_validate_url(site.url, m_type)

    try:
        async with get_db_connection() as conn:
            await conn.execute(
                "INSERT INTO sites (name, url, check_interval, is_active, notify_methods, monitor_type, keyword, tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    site.name,
                    url,
                    site.check_interval,
                    site.is_active,
                    json.dumps(site.notify_methods),
                    m_type,
                    site.keyword,
                    json.dumps(site.tags or []),
                ),
            )
            await conn.commit()
            # Find last inserted row id
            async with conn.execute("SELECT last_insert_rowid()") as c:
                row = await c.fetchone()
                site_id = row[0]
    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=400, detail="Monitor with this URL already exists") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    await models.log_audit_event(
        DB_PATH,
        user["user_id"],
        user["username"],
        "site_created",
        "site",
        str(site_id),
        f"name={site.name}, url={url}",
    )

    asyncio.create_task(
        monitoring.check_site_status(site_id, url, site.notify_methods, app_state.NOTIFY_SETTINGS)
    )
    if m_type == "ssl" or url.lower().startswith("https://"):
        asyncio.create_task(
            monitoring.check_site_certificate(
                site_id, url, site.notify_methods, app_state.NOTIFY_SETTINGS
            )
        )

    return {"id": site_id, "message": "Site added"}


@router.put("/sites/{site_id}")
async def update_site(site_id: int, site: SiteUpdate, user: dict = Depends(require_admin)):
    if not user:
        raise HTTPException(status_code=401)
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT name, url, check_interval, is_active, notify_methods, monitor_type, keyword, tags FROM sites WHERE id = ?",
            (site_id,),
        ) as c:
            existing = await c.fetchone()

        if not existing:
            raise HTTPException(404, "Site not found")

        name = site.name if site.name is not None else existing["name"]
        monitor_type = (
            site.monitor_type.lower()
            if site.monitor_type is not None
            else (existing["monitor_type"] or "http")
        )
        url = (
            _normalize_and_validate_url(site.url, monitor_type)
            if site.url is not None
            else existing["url"]
        )
        is_active = site.is_active if site.is_active is not None else existing["is_active"]
        check_interval = (
            site.check_interval if site.check_interval is not None else existing["check_interval"]
        )
        notify_methods = (
            json.dumps(site.notify_methods)
            if site.notify_methods is not None
            else existing["notify_methods"]
        )
        keyword = site.keyword if site.keyword is not None else existing["keyword"]
        tags = json.dumps(site.tags) if site.tags is not None else existing["tags"]

        await conn.execute(
            "UPDATE sites SET name = ?, url = ?, check_interval = ?, is_active = ?, notify_methods = ?, monitor_type = ?, keyword = ?, tags = ? WHERE id = ?",
            (
                name,
                url,
                check_interval,
                is_active,
                notify_methods,
                monitor_type,
                keyword,
                tags,
                site_id,
            ),
        )
        await conn.commit()
    return {"message": "Updated"}


@router.delete("/sites/{site_id}")
async def delete_site(site_id: int, user: dict = Depends(require_admin)):
    if not user:
        raise HTTPException(status_code=401)
    deleted = await models.delete_site(DB_PATH, site_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Site not found")
    await models.log_audit_event(
        DB_PATH,
        user["user_id"],
        user["username"],
        "site_deleted",
        "site",
        str(site_id),
        None,
    )
    return {"message": "Deleted"}


@router.post("/sites/{site_id}/check")
async def manual_check(site_id: int, user: dict = Depends(require_admin)):
    if not user:
        raise HTTPException(401)
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT url, notify_methods FROM sites WHERE id = ?", (site_id,)
        ) as c:
            site = await c.fetchone()
    if not site:
        raise HTTPException(404)
    methods = json.loads(site["notify_methods"]) if site["notify_methods"] else []
    await monitoring.check_site_status(site_id, site["url"], methods, app_state.NOTIFY_SETTINGS)
    return {"message": "Check triggered"}


@router.get("/ssl-certificates")
async def get_ssl_certs(user: dict = Depends(require_viewer_or_higher)):
    if not user:
        raise HTTPException(401)
    return await models.get_ssl_certificates(DB_PATH)


@router.post("/ssl-certificates/check")
async def manual_ssl_check(user: dict = Depends(require_admin)):
    if not user:
        raise HTTPException(401)
    await monitoring.check_all_certificates(app_state.NOTIFY_SETTINGS)
    return {"message": "SSL check triggered"}


@router.get("/stats/response-time")
async def get_response_time_stats(user: dict = Depends(require_viewer_or_higher)):
    if not user:
        raise HTTPException(401)
    async with get_db_connection() as conn:
        async with conn.execute("""
            SELECT site_id, s.name as site_name, AVG(sh.response_time) as avg_time, MIN(sh.response_time) as min_time, MAX(sh.response_time) as max_time, COUNT(*) as checks
            FROM status_history sh
            JOIN sites s ON sh.site_id = s.id
            WHERE sh.checked_at >= datetime('now', '-24 hours') AND sh.response_time IS NOT NULL
            GROUP BY site_id
            ORDER BY avg_time ASC
        """) as c:
            results_raw = await c.fetchall()
            results = [dict(r) for r in results_raw]

        return [
            {
                "site_id": r["site_id"],
                "site_name": r["site_name"],
                "avg_time": round(r["avg_time"], 1) if r["avg_time"] else 0,
                "min_time": round(r["min_time"], 1) if r["min_time"] else 0,
                "max_time": round(r["max_time"], 1) if r["max_time"] else 0,
                "checks": r["checks"],
            }
            for r in results
        ]


@router.get("/incidents")
async def get_incidents(user: dict = Depends(require_viewer_or_higher)):
    if not user:
        raise HTTPException(401)
    async with get_db_connection() as conn:
        async with conn.execute("""
            SELECT
                sh.id,
                sh.site_id,
                s.name as site_name,
                s.url as site_url,
                sh.status,
                sh.status_code,
                sh.response_time,
                sh.error_message,
                sh.checked_at
            FROM status_history sh
            JOIN sites s ON sh.site_id = s.id
            WHERE sh.status IN ('down', 'slow')
            AND sh.checked_at >= datetime('now', '-7 days')
            ORDER BY sh.site_id, sh.checked_at DESC
            LIMIT 100
        """) as c:
            results_raw = await c.fetchall()
            results = [dict(r) for r in results_raw]

        # Include sites that are currently down/slow but have NO recent status_history
        async with conn.execute("""
            SELECT s.id as site_id, s.name as site_name, s.url as site_url,
                   s.status, s.status_code, NULL as response_time,
                   NULL as error_message, s.first_failure_at as checked_at
            FROM sites s
            WHERE s.status IN ('down', 'slow')
            AND s.id NOT IN (
                SELECT DISTINCT site_id FROM status_history
                WHERE checked_at >= datetime('now', '-7 days')
            )
        """) as c:
            extra_raw = await c.fetchall()

        for row in extra_raw:
            site_id = row["site_id"]
            if not any(r["site_id"] == site_id for r in results):
                results.append({
                    "id": None,
                    "site_id": site_id,
                    "site_name": row["site_name"],
                    "site_url": row["site_url"],
                    "status": row["status"],
                    "status_code": row["status_code"],
                    "response_time": None,
                    "error_message": None,
                    "checked_at": row["checked_at"] or datetime.now(timezone.utc).isoformat(),
                })

        down_times = {}
        for site_id in {r["site_id"] for r in results}:
            async with conn.execute(
                """
                SELECT status, checked_at
                FROM status_history
                WHERE site_id = ?
                AND checked_at >= datetime('now', '-7 days')
                ORDER BY checked_at DESC
            """,
                (site_id,),
            ) as c:
                history_raw = await c.fetchall()
                history = [dict(h) for h in history_raw]

            prev_status = None
            incident_start = None
            for h in history:
                curr_status = h["status"]
                checked = h["checked_at"]

                if curr_status in ("down", "slow"):
                    if prev_status != curr_status:
                        incident_start = checked
                    down_times[f"{site_id}_{curr_status}_{incident_start}"] = {
                        "started_at": incident_start,
                        "ended_at": checked if prev_status == curr_status else None,
                    }
                elif prev_status in ("down", "slow") and incident_start:
                    key = f"{site_id}_{prev_status}_{incident_start}"
                    if key in down_times:
                        down_times[key]["ended_at"] = checked

                prev_status = curr_status

        incidents = []
        seen_incidents = set()
        for r in results:
            inc_key = f"{r['site_id']}_{r['status']}_{r['checked_at']}"
            if inc_key in seen_incidents:
                continue
            seen_incidents.add(inc_key)

            inc = {
                "id": r["id"],
                "site_id": r["site_id"],
                "site_name": r["site_name"],
                "site_url": r["site_url"],
                "status": r["status"],
                "status_code": r["status_code"],
                "response_time": r["response_time"],
                "error_message": r["error_message"],
                "checked_at": r["checked_at"],
                "prev_status": None,
            }

            duration_found = None
            for key, dt in down_times.items():
                if key.startswith(f"{r['site_id']}_{r['status']}_"):
                    if dt["started_at"] == r["checked_at"]:
                        start = dt["started_at"]
                        end = dt["ended_at"] or start
                        try:
                            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
                            duration = end_dt - start_dt
                            hours = duration.total_seconds() // 3600
                            mins = (duration.total_seconds() % 3600) // 60
                            if hours > 0:
                                duration_found = f"{int(hours)}год {int(mins)}хв"
                            else:
                                duration_found = f"{int(mins)}хв"
                        except Exception:
                            duration_found = None
                        break

            inc["duration"] = (
                duration_found if duration_found else ("в процесі" if not down_times else None)
            )
            incidents.append(inc)

        return incidents


@router.post("/notify-settings")
async def save_notify(settings: NotifySettingsModel, user: dict = Depends(require_admin)):
    if not user:
        raise HTTPException(401)
    new_data = settings.dict(exclude_unset=True)
    for k, v in new_data.items():
        if v is not None:
            app_state.NOTIFY_SETTINGS[k] = v
    await models.save_notify_settings(DB_PATH, app_state.NOTIFY_SETTINGS)
    return {"message": "Saved"}


@router.post("/app-settings")
async def save_app(settings: AppSettingsModel, user: dict = Depends(require_admin)):
    if not user:
        raise HTTPException(401)
    app_state.DISPLAY_ADDRESS = settings.display_address or ""
    app_state.SITE_TITLE = settings.site_title or "Uptime Monitor"
    app_state.LOGO_URL = settings.logo_url or ""
    app_state.FOOTER_TEXT = settings.footer_text or ""
    app_state.PRIMARY_COLOR = settings.primary_color or "#00ff88"
    app_state.BRAND_ACCENT_COLOR = settings.brand_accent_color or "#06b6d4"
    async with get_db_connection() as conn:
        await conn.execute(
            """INSERT OR REPLACE INTO app_settings
               (id, display_address, site_title, logo_url, footer_text, primary_color, brand_accent_color)
               VALUES (1, ?, ?, ?, ?, ?, ?)""",
            (
                app_state.DISPLAY_ADDRESS,
                app_state.SITE_TITLE,
                app_state.LOGO_URL,
                app_state.FOOTER_TEXT,
                app_state.PRIMARY_COLOR,
                app_state.BRAND_ACCENT_COLOR,
            ),
        )
        await conn.commit()
    return {"message": "Saved"}


@router.get("/app-settings")
async def get_app(user: dict = Depends(require_viewer_or_higher)):
    if not user:
        raise HTTPException(401)
    return {
        "display_address": app_state.DISPLAY_ADDRESS,
        "site_title": app_state.SITE_TITLE,
        "logo_url": app_state.LOGO_URL,
        "footer_text": app_state.FOOTER_TEXT,
        "primary_color": app_state.PRIMARY_COLOR,
        "brand_accent_color": app_state.BRAND_ACCENT_COLOR,
    }


@router.get("/alert-policy")
async def get_alert_policy_api(user: dict = Depends(require_viewer_or_higher)):
    if not user:
        raise HTTPException(401)
    return alerting.get_alert_policy()


@router.post("/alert-policy")
async def save_alert_policy_api(settings: AlertPolicyModel, user: dict = Depends(require_admin)):
    if not user:
        raise HTTPException(401)
    cfg = config_manager.load_config() or {}
    existing = cfg.get("alert_policy") or {}
    new_data = settings.dict(exclude_unset=True, exclude_none=True)
    existing.update(new_data)
    cfg["alert_policy"] = existing
    config_manager.save_config(cfg)
    alerting._cache = None
    alerting._cache_time = 0
    return {"message": "Saved"}


@router.get("/user")
async def get_user_info(user: dict = Depends(get_current_user)):
    if not user:
        raise HTTPException(401)
    return {
        "username": user["username"],
        "role": user.get("role", "viewer"),
        "is_admin": auth_module.is_admin(user),
    }


@router.get("/users")
async def get_users(user: dict = Depends(require_admin)):
    users = await auth_module.get_all_users(DB_PATH)
    for u in users:
        u.pop("password_hash", None)
    return users


@router.post("/users")
async def create_user_api(user_data: UserCreate, current_user: dict = Depends(require_admin)):
    if user_data.role not in ["admin", "viewer"]:
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin' or 'viewer'")

    success = await auth_module.create_user(
        DB_PATH, user_data.username, user_data.password, user_data.role
    )

    if success:
        await models.log_audit_event(
            DB_PATH,
            current_user["user_id"],
            current_user["username"],
            "user_created",
            "user",
            user_data.username,
            f"role={user_data.role}",
        )
        return {"message": f"User '{user_data.username}' created with role '{user_data.role}'"}
    else:
        raise HTTPException(status_code=400, detail="User already exists or error creating user")


@router.put("/users/{username}")
async def update_user_api(
    username: str, user_data: UserUpdate, current_user: dict = Depends(require_admin)
):
    if user_data.role and user_data.role not in ["admin", "viewer"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    if user_data.role:
        success = await auth_module.update_user_role(DB_PATH, username, user_data.role)

        if not success:
            raise HTTPException(status_code=404, detail="User not found")
        await models.log_audit_event(
            DB_PATH,
            current_user["user_id"],
            current_user["username"],
            "user_role_updated",
            "user",
            username,
            f"new_role={user_data.role}",
        )
        return {"message": f"User '{username}' role updated to '{user_data.role}'"}

    if user_data.password:
        async with get_db_connection() as conn:
            async with conn.execute("SELECT id FROM users WHERE username = ?", (username,)) as c:
                user_row = await c.fetchone()

        if not user_row:
            raise HTTPException(status_code=404, detail="User not found")

        await auth_module.change_password(user_row["id"], user_data.password, DB_PATH)
        await models.log_audit_event(
            DB_PATH,
            current_user["user_id"],
            current_user["username"],
            "user_password_reset",
            "user",
            username,
            None,
        )
        return {"message": f"Password updated for user '{username}'"}

    raise HTTPException(status_code=400, detail="No updates provided")


@router.delete("/users/{username}")
async def delete_user_api(username: str, current_user: dict = Depends(require_admin)):
    if username == current_user["username"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    success, error_message = await auth_module.delete_user(DB_PATH, username)

    if success:
        await models.log_audit_event(
            DB_PATH,
            current_user["user_id"],
            current_user["username"],
            "user_deleted",
            "user",
            username,
            None,
        )
        return {"message": f"User '{username}' deleted"}
    else:
        raise HTTPException(status_code=400, detail=error_message)


class MaintenanceWindowCreate(BaseModel):
    name: str
    site_id: Optional[int] = None
    rule_type: str = "one_off"
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    day_of_week: Optional[int] = None
    start_hour_minute: Optional[str] = None
    duration_minutes: Optional[int] = None


class MaintenanceWindowToggle(BaseModel):
    is_active: bool


@router.get("/maintenance-windows")
async def get_maint_windows(user: dict = Depends(require_viewer_or_higher)):
    return await models.get_maintenance_windows(DB_PATH)


@router.post("/maintenance-windows")
async def create_maint_window(window: MaintenanceWindowCreate, user: dict = Depends(require_admin)):
    window_id = await models.add_maintenance_window(
        DB_PATH,
        name=window.name,
        site_id=window.site_id,
        rule_type=window.rule_type,
        start_time=window.start_time,
        end_time=window.end_time,
        day_of_week=window.day_of_week,
        start_hour_minute=window.start_hour_minute,
        duration_minutes=window.duration_minutes,
    )
    return {"id": window_id, "message": "Maintenance window added"}


@router.delete("/maintenance-windows/{window_id}")
async def delete_maint_window(window_id: int, user: dict = Depends(require_admin)):
    await models.delete_maintenance_window(DB_PATH, window_id)
    return {"message": "Maintenance window deleted"}


@router.put("/maintenance-windows/{window_id}/toggle")
async def toggle_maint_window(
    window_id: int, toggle: MaintenanceWindowToggle, user: dict = Depends(require_admin)
):
    await models.toggle_maintenance_window(DB_PATH, window_id, toggle.is_active)
    return {"message": "Toggled"}


@router.get("/reports/sla")
async def get_sla_report(days: int = 7, user: dict = Depends(require_viewer_or_higher)):
    async with get_db_connection() as conn:
        async with conn.execute("SELECT id, name, url FROM sites") as c:
            sites_raw = await c.fetchall()
            sites = [dict(s) for s in sites_raw]

        report = []
        for s in sites:
            sid = s["id"]
            async with conn.execute(
                """SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'up' THEN 1 ELSE 0 END) as up_count,
                    AVG(response_time) as avg_rt
                  FROM status_history
                  WHERE site_id = ? AND checked_at >= datetime('now', ?)""",
                (sid, f"-{days} days"),
            ) as c:
                stats = await c.fetchone()

            async with conn.execute(
                """SELECT COUNT(*) FROM status_history
                   WHERE site_id = ? AND status IN ('down', 'slow') AND checked_at >= datetime('now', ?)""",
                (sid, f"-{days} days"),
            ) as c:
                incidents = (await c.fetchone())[0]

            total = stats["total"] or 0
            up_count = stats["up_count"] or 0
            uptime = (up_count / total * 100) if total > 0 else 100.0
            avg_rt = stats["avg_rt"] or 0

            report.append(
                {
                    "id": sid,
                    "name": s["name"],
                    "url": s["url"],
                    "uptime": round(uptime, 2),
                    "avg_response_time": round(avg_rt, 1),
                    "total_checks": total,
                    "incidents": incidents,
                }
            )
        return report


@router.get("/reports/sla/export")
async def export_sla_report(days: int = 7, user: dict = Depends(require_viewer_or_higher)):
    import csv
    import io

    from fastapi.responses import StreamingResponse

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["ID", "Name", "URL", "Uptime %", "Avg Response Time (ms)", "Total Checks", "Incidents"]
    )

    report = await get_sla_report(days, user)
    for item in report:
        writer.writerow(
            [
                item["id"],
                item["name"],
                item["url"],
                f"{item['uptime']}%",
                item["avg_response_time"],
                item["total_checks"],
                item["incidents"],
            ]
        )

    output.seek(0)

    response = StreamingResponse(io.StringIO(output.getvalue()), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=sla_report_{days}days.csv"
    return response


@router.get("/reports/sla/pdf")
async def export_sla_pdf(days: int = 30, user: dict = Depends(require_viewer_or_higher)):
    from ..reporting import render_sla_pdf

    pdf_bytes = await render_sla_pdf(days)
    if not pdf_bytes:
        raise HTTPException(status_code=500, detail="PDF generation failed (weasyprint not available)")

    from fastapi.responses import Response

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=sla_report_{days}days.pdf"},
    )


@router.post("/api-keys", dependencies=[Depends(require_admin)])
async def create_api_key_endpoint(name: str, user: dict = Depends(get_current_user)):
    """Create a new API key (admin only). Returns the key once."""
    key_id, raw_key = await auth_module.create_api_key(DB_PATH, user["user_id"], name)
    return {"key_id": key_id, "api_key": raw_key, "name": name}


@router.get("/api-keys", dependencies=[Depends(require_admin)])
async def list_api_keys_endpoint():
    """List all API keys (key_id only, not the actual key)."""
    keys = await auth_module.list_api_keys(DB_PATH)
    return keys


@router.delete("/api-keys/{key_id}", dependencies=[Depends(require_admin)])
async def revoke_api_key_endpoint(key_id: str):
    """Revoke an API key (admin only)."""
    await auth_module.revoke_api_key(DB_PATH, key_id)
    return {"status": "revoked"}


@router.get("/audit-log", dependencies=[Depends(require_admin)])
async def get_audit_log_endpoint(limit: int = 200):
    """Get recent audit log entries (admin only)."""
    entries = await models.get_audit_log(DB_PATH, limit)
    return entries


@router.get("/notification-history", dependencies=[Depends(require_admin)])
async def get_notification_history_endpoint(limit: int = 100):
    """Get notification history (admin only)."""
    entries = await models.get_notification_history(DB_PATH, limit)
    return entries


@router.post("/backup", dependencies=[Depends(require_admin)])
async def create_backup_endpoint():
    """Create a DB backup (admin only)."""
    from datetime import datetime

    backup_dir = os.path.join(os.path.dirname(DB_PATH), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    backup_path = os.path.join(backup_dir, filename)
    result = await models.create_backup(DB_PATH, backup_path)
    return result


@router.get("/backups", dependencies=[Depends(require_admin)])
async def list_backups_endpoint():
    """List all backups (admin only)."""
    result = await models.get_backups(DB_PATH)
    return result


@router.post("/backup/restore/{backup_id}", dependencies=[Depends(require_admin)])
async def restore_backup_endpoint(backup_id: int, confirm: bool = Query(False)):
    """Restore a backup by ID (admin only). Requires confirm=true."""
    if not confirm:
        raise HTTPException(status_code=400, detail="Confirmation required: add ?confirm=true")
    backups = await models.get_backups(DB_PATH)
    target = None
    for b in backups:
        if b["id"] == backup_id:
            target = b
            break
    if not target:
        raise HTTPException(status_code=404, detail="Backup not found")
    import shutil

    shutil.copy2(target["filepath"], DB_PATH)
    await models.log_audit_event(
        DB_PATH,
        0,
        "system",
        "backup_restored",
        "backup",
        str(backup_id),
        f"restored {target['filename']}",
    )
    return {"status": "restored", "backup": target["filename"]}


@router.get("/tags")
async def get_all_tags(user: dict = Depends(require_viewer_or_higher)):
    """Get all unique tags across all sites."""
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT tags FROM sites WHERE tags IS NOT NULL AND tags != '[]'"
        ) as c:
            rows = await c.fetchall()
    all_tags = set()
    for row in rows:
        try:
            tag_list = json.loads(row["tags"])
            all_tags.update(tag_list)
        except (json.JSONDecodeError, TypeError):
            pass
    return sorted(all_tags)
