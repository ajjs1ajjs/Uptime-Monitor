import json
import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

try:
    from .. import ui_templates
    from ..database import get_db_connection
    from ..dependencies import get_current_user, require_admin
    from ..state import NOTIFY_SETTINGS
except ImportError:
    import ui_templates
    from database import get_db_connection
    from dependencies import get_current_user, require_admin
    from state import NOTIFY_SETTINGS

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, user: dict = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    if user.get("must_change_password"):
        return RedirectResponse(url="/change-password", status_code=302)

    async with get_db_connection() as conn:
        async with conn.execute("SELECT COUNT(*) FROM sites") as c:
            row = await c.fetchone()
            total_sites = row[0]
        async with conn.execute("SELECT COUNT(*) FROM sites WHERE status = 'up'") as c:
            row = await c.fetchone()
            up_sites = row[0]
        async with conn.execute("SELECT COUNT(*) FROM sites WHERE status = 'down'") as c:
            row = await c.fetchone()
            down_sites = row[0]

    notification_cards = ui_templates.get_notification_cards_html(NOTIFY_SETTINGS)
    notify_config_json = json.dumps(NOTIFY_SETTINGS)

    return templates.TemplateResponse(request, "dashboard.html", {
        "request": request,
        "total": total_sites,
        "total_sites": total_sites,
        "up_sites": up_sites,
        "down_sites": down_sites,
        "notification_cards": notification_cards,
        "notify_config_json": notify_config_json
    })

@router.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, user: dict = Depends(require_admin)):
    """User management page (admin only)"""
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse(request, "users.html", {"request": request})

@router.get("/status", response_class=HTMLResponse)
@router.get("/public-status", response_class=HTMLResponse)
async def public_status_page(request: Request):
    """Public status page."""
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT id, name, url, monitor_type, status FROM sites WHERE is_active = 1 ORDER BY id"
        ) as c:
            sites_raw = await c.fetchall()
            sites = [dict(s) for s in sites_raw]

    def status_of(site_row: dict) -> str:
        value = site_row["status"]
        return (value or "unknown").lower()

    up_count = sum(1 for s in sites if status_of(s) == "up")
    down_count = sum(1 for s in sites if status_of(s) == "down")
    total = len(sites)

    def get_sort_order(site_row: dict) -> int:
        status = status_of(site_row)
        if status == "down":
            return 0
        if status == "slow":
            return 1
        if status == "unknown":
            return 2
        if status == "paused":
            return 3
        return 4

    sites.sort(key=get_sort_order)

    # Prep sites for template
    for s in sites:
        status = (s["status"] or "unknown").lower()
        if status == "up":
            s["status_class"] = "up"
            s["status_text"] = "UP"
            s["dot_color"] = "#00ff88"
        elif status in ("paused", "slow"):
            s["status_class"] = "paused"
            s["status_text"] = "PAUSED" if status == "paused" else "SLOW"
            s["dot_color"] = "#f59e0b"
        elif status == "unknown":
            s["status_class"] = "unknown"
            s["status_text"] = "UNKNOWN"
            s["dot_color"] = "#94a3b8"
        else:
            s["status_class"] = "down"
            s["status_text"] = "DOWN"
            s["dot_color"] = "#ff4757"

    overall_status_class = "up" if down_count == 0 else "down"
    overall_status_text = "All systems operational" if down_count == 0 else "Some issues detected"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return templates.TemplateResponse(request, "public_status.html", {
        "request": request,
        "overall_status_class": overall_status_class,
        "overall_status_text": overall_status_text,
        "total": total,
        "up_count": up_count,
        "down_count": down_count,
        "sites": sites,
        "timestamp": timestamp
    })
