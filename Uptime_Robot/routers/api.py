import asyncio
import json
import sqlite3
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

try:
    from .. import auth_module, models, monitoring
    from ..database import get_db_connection
    from ..dependencies import require_admin, require_viewer_or_higher, get_current_user
    from ..state import DB_PATH
    from .. import state as app_state
except ImportError:
    import auth_module, models, monitoring
    from database import get_db_connection
    from dependencies import require_admin, require_viewer_or_higher, get_current_user
    from state import DB_PATH
    import state as app_state

router = APIRouter(prefix="/api")

class SiteCreate(BaseModel):
    name: str
    url: str
    check_interval: int = 60
    is_active: bool = True
    notify_methods: Optional[List[str]] = []
    monitor_type: str = "http"

class SiteUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    check_interval: Optional[int] = None
    notify_methods: Optional[List[str]] = None
    is_active: Optional[bool] = None

class NotifySettingsModel(BaseModel):
    telegram: Optional[dict] = None
    teams: Optional[dict] = None
    discord: Optional[dict] = None
    slack: Optional[dict] = None
    email: Optional[dict] = None
    sms: Optional[dict] = None

class AppSettingsModel(BaseModel):
    display_address: Optional[str] = ""

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "viewer"

class UserUpdate(BaseModel):
    role: Optional[str] = None
    password: Optional[str] = None

def _normalize_and_validate_url(raw_url: str, monitor_type: str) -> str:
    from urllib.parse import urlparse
    import ipaddress
        
    def _is_valid_host(hostname: Optional[str]) -> bool:
        if not hostname: return False
        host = hostname.strip().lower().rstrip(".")
        if not host: return False
        if host == "localhost": return True
        try:
            ipaddress.ip_address(host)
            return True
        except ValueError:
            pass
        labels = host.split(".")
        if len(labels) < 2: return False
        for label in labels:
            if not label or len(label) > 63: return False
            if label.startswith("-") or label.endswith("-"): return False
            if not all(ch.isalnum() or ch == "-" for ch in label): return False
        return True

    url = (raw_url or "").strip()
    if not url:
        raise HTTPException(400, "URL required")

    m_type = (monitor_type or "http").lower()
    if m_type == "ssl":
        normalized = monitoring.normalize_ssl_url(url)
        if not normalized:
            raise HTTPException(400, "Invalid URL")
        url = normalized

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(400, "URL must start with http:// or https://")
    if not _is_valid_host(parsed.hostname):
        raise HTTPException(400, "Invalid host in URL")
    return url

@router.get("/sites")
async def get_sites(user: dict = Depends(require_viewer_or_higher)):
    if not user:
        raise HTTPException(status_code=401)
    async with get_db_connection() as conn:
        async with conn.execute("SELECT * FROM sites ORDER BY id") as c:
            sites_raw = await c.fetchall()
            sites = [dict(s) for s in sites_raw]
        result = []
        for site in sites:
            async with conn.execute(
                "SELECT * FROM status_history WHERE site_id = ? ORDER BY checked_at DESC LIMIT 1",
                (site["id"],),
            ) as c:
                last_status = await c.fetchone()
            async with conn.execute(
                "SELECT COUNT(*) as total, SUM(CASE WHEN status = 'up' THEN 1 ELSE 0 END) as up_count FROM status_history WHERE site_id = ?",
                (site["id"],),
            ) as c:
                stats = await c.fetchone()
            uptime = (stats["up_count"] / stats["total"] * 100) if stats and stats["total"] > 0 else 0
            result.append(
                {
                    **dict(site),
                    "status": last_status["status"] if last_status else "unknown",
                    "uptime": round(uptime, 2),
                    "notify_methods": json.loads(site["notify_methods"])
                    if site["notify_methods"]
                    else [],
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
            history[sid].append({
                "status": r["status"],
                "checked_at": r["checked_at"]
            })
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
    now = datetime.now()
    return {
        "timestamp": now.timestamp(),
        "iso": now.isoformat(),
        "timezone": now.astimezone().tzname() if now.tzinfo else "local",
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
                "INSERT INTO sites (name, url, check_interval, is_active, notify_methods, monitor_type) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    site.name,
                    url,
                    site.check_interval,
                    site.is_active,
                    json.dumps(site.notify_methods),
                    m_type,
                ),
            )
            await conn.commit()
            # Find last inserted row id
            async with conn.execute("SELECT last_insert_rowid()") as c:
                row = await c.fetchone()
                site_id = row[0]
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Monitor with this URL already exists")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    asyncio.create_task(
        monitoring.check_site_status(site_id, url, site.notify_methods, app_state.NOTIFY_SETTINGS)
    )
    if m_type == "ssl" or url.lower().startswith("https://"):
        asyncio.create_task(
            monitoring.check_site_certificate(site_id, url, site.notify_methods, app_state.NOTIFY_SETTINGS)
        )

    return {"id": site_id, "message": "Site added"}

@router.put("/sites/{site_id}")
async def update_site(site_id: int, site: SiteUpdate, user: dict = Depends(require_admin)):
    if not user:
        raise HTTPException(status_code=401)
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT name, url, check_interval, is_active, notify_methods, monitor_type FROM sites WHERE id = ?",
            (site_id,),
        ) as c:
            existing = await c.fetchone()
        
        if not existing:
            raise HTTPException(404, "Site not found")

        name = site.name if site.name is not None else existing["name"]
        current_monitor_type = existing["monitor_type"] or "http"
        url = (
            _normalize_and_validate_url(site.url, current_monitor_type)
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

        await conn.execute(
            "UPDATE sites SET name = ?, url = ?, check_interval = ?, is_active = ?, notify_methods = ? WHERE id = ?",
            (name, url, check_interval, is_active, notify_methods, site_id),
        )
        await conn.commit()
    return {"message": "Updated"}

@router.delete("/sites/{site_id}")
async def delete_site(site_id: int, user: dict = Depends(require_admin)):
    if not user:
        raise HTTPException(status_code=401)
    await models.delete_site(DB_PATH, site_id) if asyncio.iscoroutinefunction(models.delete_site) else models.delete_site(DB_PATH, site_id)
    return {"message": "Deleted"}

@router.post("/sites/{site_id}/check")
async def manual_check(site_id: int, user: dict = Depends(require_admin)):
    if not user:
        raise HTTPException(401)
    async with get_db_connection() as conn:
        async with conn.execute("SELECT url, notify_methods FROM sites WHERE id = ?", (site_id,)) as c:
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
    if asyncio.iscoroutinefunction(models.get_ssl_certificates):
        return await models.get_ssl_certificates(DB_PATH)
    else:
        return models.get_ssl_certificates(DB_PATH)

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

        down_times = {}
        for site_id in set(r["site_id"] for r in results):
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
                            from datetime import datetime
                            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
                            duration = end_dt - start_dt
                            hours = duration.total_seconds() // 3600
                            mins = (duration.total_seconds() % 3600) // 60
                            if hours > 0:
                                duration_found = f"{int(hours)}год {int(mins)}хв"
                            else:
                                duration_found = f"{int(mins)}хв"
                        except:
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
    if asyncio.iscoroutinefunction(models.save_notify_settings):
        await models.save_notify_settings(DB_PATH, app_state.NOTIFY_SETTINGS)
    else:    
        models.save_notify_settings(DB_PATH, app_state.NOTIFY_SETTINGS)
    return {"message": "Saved"}

@router.post("/app-settings")
async def save_app(settings: AppSettingsModel, user: dict = Depends(require_admin)):
    if not user:
        raise HTTPException(401)
    app_state.DISPLAY_ADDRESS = settings.display_address
    async with get_db_connection() as conn:
        await conn.execute(
            "INSERT OR REPLACE INTO app_settings (id, display_address) VALUES (1, ?)",
            (app_state.DISPLAY_ADDRESS,),
        )
        await conn.commit()
    return {"message": "Saved"}

@router.get("/app-settings")
async def get_app(user: dict = Depends(require_viewer_or_higher)):
    if not user:
        raise HTTPException(401)
    return {"display_address": app_state.DISPLAY_ADDRESS}

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
    if asyncio.iscoroutinefunction(auth_module.get_all_users):
        users = await auth_module.get_all_users(DB_PATH)
    else:
        users = auth_module.get_all_users(DB_PATH)
    for u in users:
        u.pop("password_hash", None)
    return users

@router.post("/users")
async def create_user_api(user_data: UserCreate, current_user: dict = Depends(require_admin)):
    if user_data.role not in ["admin", "viewer"]:
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin' or 'viewer'")

    success = False
    if asyncio.iscoroutinefunction(auth_module.create_user):
        success = await auth_module.create_user(DB_PATH, user_data.username, user_data.password, user_data.role)
    else:
        success = auth_module.create_user(DB_PATH, user_data.username, user_data.password, user_data.role)
        
    if success:
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
        if asyncio.iscoroutinefunction(auth_module.update_user_role):
            success = await auth_module.update_user_role(DB_PATH, username, user_data.role)
        else:
            success = auth_module.update_user_role(DB_PATH, username, user_data.role)
            
        if not success:
            raise HTTPException(status_code=404, detail="User not found")
        return {"message": f"User '{username}' role updated to '{user_data.role}'"}

    if user_data.password:
        async with get_db_connection() as conn:
            async with conn.execute("SELECT id FROM users WHERE username = ?", (username,)) as c:
                user_row = await c.fetchone()
                
        if not user_row:
            raise HTTPException(status_code=404, detail="User not found")

        if asyncio.iscoroutinefunction(auth_module.change_password):
            await auth_module.change_password(user_row["id"], user_data.password, DB_PATH)
        else:
            auth_module.change_password(user_row["id"], user_data.password, DB_PATH)
        return {"message": f"Password updated for user '{username}'"}

    raise HTTPException(status_code=400, detail="No updates provided")

@router.delete("/users/{username}")
async def delete_user_api(username: str, current_user: dict = Depends(require_admin)):
    if username == current_user["username"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    if asyncio.iscoroutinefunction(auth_module.delete_user):
        success, error_message = await auth_module.delete_user(DB_PATH, username)
    else:
        success, error_message = auth_module.delete_user(DB_PATH, username)

    if success:
        return {"message": f"User '{username}' deleted"}
    else:
        raise HTTPException(status_code=400, detail=error_message)
