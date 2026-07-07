import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..database import get_db_connection
from ..dependencies import get_client_ip, get_current_user, require_admin
from ..logger import logger
from ..state import (
    BRAND_ACCENT_COLOR,
    DB_PATH,
    DISPLAY_ADDRESS,
    FOOTER_TEXT,
    LOGO_URL,
    NOTIFY_SETTINGS,
    PRIMARY_COLOR,
    SITE_TITLE,
)
from ..wss.manager import manager

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


def _monitor_card_html(site: dict) -> str:
    import urllib.parse

    status = (site.get("status") or "unknown").lower()
    if status == "up":
        scolor = "#10b981"
        border = "border-emerald-500"
    elif status == "paused":
        scolor = "#f59e0b"
        border = "border-amber-500"
    elif status == "maintenance":
        scolor = "#a855f7"
        border = "border-purple-500"
    else:
        scolor = "#ef4444"
        border = "border-red-500"

    stext = status.upper()
    mtype = site.get("monitor_type", "http")
    methods = (
        json.loads(site.get("notify_methods", "[]"))
        if isinstance(site.get("notify_methods"), str)
        else (site.get("notify_methods") or [])
    )
    uptime = site.get("uptime", 100)
    if isinstance(uptime, str):
        try:
            uptime = float(uptime)
        except Exception:
            uptime = 100.0

    tags = (
        json.loads(site.get("tags", "[]"))
        if isinstance(site.get("tags"), str)
        else (site.get("tags") or [])
    )
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except Exception:
            tags = []

    keyword = site.get("keyword") or ""

    template = templates.get_template("partials/monitor_card.html")
    return template.render(
        {
            "name": site.get("name", ""),
            "url": site.get("url", ""),
            "escaped_name": json.dumps(site.get("name", "")),
            "escaped_url": json.dumps(site.get("url", "")),
            "escaped_methods": urllib.parse.quote(json.dumps(methods)),
            "escaped_keyword": urllib.parse.quote(keyword),
            "escaped_tags": urllib.parse.quote(json.dumps(tags)),
            "keyword": keyword,
            "tags": tags,
            "scolor": scolor,
            "border": border,
            "stext": stext,
            "mtype": mtype,
            "uptime": uptime,
            "rt": site.get("response_time") or "—",
            "sc": site.get("status_code") or "—",
            "sid": site.get("id", 0),
            "check_interval": site.get("check_interval", 60),
        }
    )


def _hero_stat_html(label: str, value, color: str = "text-accent") -> str:
    return f"""<div class="glass rounded-2xl p-6 text-center">
        <div class="text-4xl md:text-5xl font-bold {color} mb-2">{value}</div>
        <div class="text-slate-400 text-xs md:text-sm uppercase tracking-wider">{label}</div>
    </div>"""


@router.get("/api/htmx/hero-stats", response_class=HTMLResponse)
async def htmx_hero_stats(user: dict = Depends(get_current_user)):
    if not user:
        return HTMLResponse("")
    async with get_db_connection() as conn:
        async with conn.execute("SELECT COUNT(*) FROM sites") as c:
            total = (await c.fetchone())[0]
        async with conn.execute("SELECT COUNT(*) FROM sites WHERE status = 'up'") as c:
            up = (await c.fetchone())[0]
        async with conn.execute("SELECT COUNT(*) FROM sites WHERE status = 'down'") as c:
            down = (await c.fetchone())[0]
        async with conn.execute("SELECT COUNT(*) FROM sites WHERE status = 'slow'") as c:
            slow = (await c.fetchone())[0]
    incidents = down + slow
    return HTMLResponse(
        _hero_stat_html("Monitors", total)
        + _hero_stat_html("Online", up, "text-emerald-400")
        + _hero_stat_html("Offline", down, "text-red-400")
        + _hero_stat_html("Incidents", incidents, "text-amber-400")
    )


@router.get("/api/htmx/monitors", response_class=HTMLResponse)
async def htmx_monitors(
    search: Optional[str] = None,
    sort: Optional[str] = None,
    tag: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    if not user:
        return HTMLResponse("")
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT s.*, (SELECT COUNT(*) FROM status_history sh WHERE sh.site_id = s.id AND sh.checked_at >= datetime('now', '-24 hours')) as checks_24h FROM sites s ORDER BY s.id"
        ) as c:
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

        for site in sites:
            sid = site["id"]
            last = last_status_map.get(sid, "unknown")
            total, up_count = stats_map.get(sid, (0, 0))
            site["status"] = last
            site["uptime"] = round((up_count / total * 100), 1) if total > 0 else 100.0
            site["notify_methods"] = json.loads(site.get("notify_methods") or "[]")
            site["tags"] = (
                json.loads(site.get("tags", "[]"))
                if site.get("tags") and site.get("tags") != "[]"
                else []
            )

    if search:
        search_lower = search.lower().strip()
        sites = [
            s
            for s in sites
            if search_lower in (s.get("name") or "").lower()
            or search_lower in (s.get("url") or "").lower()
        ]

    if tag:
        sites = [s for s in sites if tag in s.get("tags", [])]

    if sort == "name":
        sites.sort(key=lambda s: (s.get("name") or "").lower())
    elif sort == "uptime":
        sites.sort(key=lambda s: s.get("uptime", 100.0), reverse=True)
    elif sort == "response_time":
        sites.sort(
            key=lambda s: (
                s.get("response_time")
                if isinstance(s.get("response_time"), (int, float))
                else 999999
            )
        )
    else:
        status_order = {"down": 0, "slow": 1, "maintenance": 2, "paused": 3, "unknown": 4, "up": 5}
        sites.sort(key=lambda s: status_order.get((s.get("status") or "unknown").lower(), 6))

    if not sites:
        return HTMLResponse(
            '<div class="col-span-full text-center py-10 text-slate-500">No monitors found.</div>'
        )

    html = "".join(_monitor_card_html(s) for s in sites)
    return HTMLResponse(html)


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

    from .. import auth_module
    from ..crypto_utils import redact_notify_secrets

    # Only admins may view/edit notification channels (POST /api/notify-settings
    # is admin-only), so a viewer-role account has no legitimate reason to
    # receive the decrypted bot tokens / SMTP passwords / webhook URLs that
    # would otherwise be embedded verbatim in this page's HTML/JS.
    visible_notify_settings = (
        NOTIFY_SETTINGS if auth_module.is_admin(user) else redact_notify_secrets(NOTIFY_SETTINGS)
    )

    notify_cards_template = templates.get_template("partials/notification_cards.html")
    notification_cards = notify_cards_template.render(
        {"request": request, "notify_settings": visible_notify_settings}
    )
    notify_config_json = json.dumps(visible_notify_settings).replace("</", "<\\/")

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "total": total_sites,
            "total_sites": total_sites,
            "up_sites": up_sites,
            "down_sites": down_sites,
            "notification_cards": notification_cards,
            "notify_config_json": notify_config_json,
            "notify_settings": visible_notify_settings,
        },
    )


@router.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, user: dict = Depends(require_admin)):
    """User management page (admin only)"""
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse(request, "users.html", {"request": request})


@router.get("/status", response_class=HTMLResponse)
@router.get("/public-status", response_class=HTMLResponse)
async def public_status_page(request: Request):
    """Public status page with uptime %, response time, and incident history."""
    # Rate limit: 30 req/min per IP
    from ..models import check_db_rate_limit

    client_ip = get_client_ip(request)
    if not await check_db_rate_limit("public_status", client_ip, 30, 60, DB_PATH):
        return HTMLResponse("Too Many Requests", status_code=429)
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT id, name, url, monitor_type, status, response_time FROM sites WHERE is_active = 1 ORDER BY id"
        ) as c:
            sites_raw = await c.fetchall()
            sites = [dict(s) for s in sites_raw]

        cutoff_30d = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

        # Bulk uptime stats for all sites in one query (was N queries).
        async with conn.execute(
            "SELECT site_id, COUNT(*) as total, "
            "SUM(CASE WHEN status = 'up' THEN 1 ELSE 0 END) as up_count "
            "FROM status_history WHERE checked_at >= ? GROUP BY site_id",
            (cutoff_30d,),
        ) as c:
            uptime_map = {
                r["site_id"]: (r["total"] or 0, r["up_count"] or 0) for r in await c.fetchall()
            }

        # Bulk latest response time per site via a window function (was N queries).
        async with conn.execute(
            "SELECT site_id, response_time FROM ("
            "  SELECT site_id, response_time, "
            "         ROW_NUMBER() OVER (PARTITION BY site_id ORDER BY checked_at DESC) AS rn "
            "  FROM status_history WHERE checked_at >= ?"
            ") WHERE rn = 1",
            (cutoff_30d,),
        ) as c:
            latest_rt_map = {r["site_id"]: r["response_time"] for r in await c.fetchall()}

        # Bulk recent down events for all sites (was N queries); keep 5 per site.
        async with conn.execute(
            "SELECT site_id, checked_at FROM status_history "
            "WHERE status = 'down' AND checked_at >= ? ORDER BY checked_at DESC",
            (cutoff_30d,),
        ) as c:
            down_rows = await c.fetchall()

        site_name_by_id = {s["id"]: s["name"] for s in sites}
        down_count_per_site: dict = {}
        incidents_raw = []
        for dr in down_rows:
            sid = dr["site_id"]
            if down_count_per_site.get(sid, 0) >= 5:
                continue
            down_count_per_site[sid] = down_count_per_site.get(sid, 0) + 1
            incidents_raw.append(
                {
                    "site_name": site_name_by_id.get(sid, ""),
                    "time": dr["checked_at"][:19].replace("T", " "),
                }
            )

        for s in sites:
            total_checks, up_checks = uptime_map.get(s["id"], (0, 0))
            s["uptime_pct"] = round(
                (up_checks / total_checks * 100) if total_checks > 0 else 100.0, 2
            )
            rt = latest_rt_map.get(s["id"])
            s["latest_response_time"] = round(rt, 2) if rt is not None else None

        thirty_day_uptime = 100.0
        if sites:
            total_up = sum(s["uptime_pct"] for s in sites)
            thirty_day_uptime = round(total_up / len(sites), 2)

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

    for s in sites:
        status = (s["status"] or "unknown").lower()
        if status == "up":
            s["status_class"] = "up"
            s["status_text"] = "UP"
            s["dot_color"] = "#00ff88"
        elif status == "maintenance":
            s["status_class"] = "maintenance"
            s["status_text"] = "MAINTENANCE"
            s["dot_color"] = "#a855f7"
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
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    return templates.TemplateResponse(
        request,
        "public_status.html",
        {
            "request": request,
            "overall_status_class": overall_status_class,
            "overall_status_text": overall_status_text,
            "total": total,
            "up_count": up_count,
            "down_count": down_count,
            "sites": sites,
            "timestamp": timestamp,
            "site_title": SITE_TITLE,
            "logo_url": LOGO_URL,
            "footer_text": FOOTER_TEXT,
            "primary_color": PRIMARY_COLOR,
            "brand_accent_color": BRAND_ACCENT_COLOR,
            "display_address": DISPLAY_ADDRESS,
            "thirty_day_uptime": thirty_day_uptime,
            "incidents": sorted(incidents_raw, key=lambda x: x["time"], reverse=True)[:10],
        },
    )


@router.websocket("/ws")
async def dashboard_websocket(ws: WebSocket):
    """WebSocket endpoint for real-time dashboard updates."""
    from http.cookies import SimpleCookie

    from ..auth_module import validate_session
    from ..state import DB_PATH

    cookies = SimpleCookie(ws.headers.get("cookie", ""))
    session_id = cookies.get("session_id")
    if not session_id:
        await ws.close(code=4001, reason="Authentication required")
        return
    session_id = session_id.value
    session = await validate_session(session_id, DB_PATH)
    if not session:
        await ws.close(code=4001, reason="Invalid session")
        return
    await manager.connect(ws)
    try:
        while True:
            data = await asyncio.wait_for(ws.receive_text(), timeout=120)
            if data == "ping":
                await ws.send_text("pong")
    except asyncio.TimeoutError:
        logger.debug("WS idle timeout — closing")
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await manager.disconnect(ws)
