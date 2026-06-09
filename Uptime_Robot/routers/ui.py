import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..database import get_db_connection
from ..dependencies import get_current_user, require_admin
from ..state import (
    BRAND_ACCENT_COLOR,
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
            "escaped_name": (site.get("name") or "").replace("'", "\\'"),
            "escaped_url": (site.get("url") or "").replace("'", "\\'"),
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
            site["uptime"] = (
                round((up_count / total * 100), 1) if total > 0 else 100.0
            )
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

    notify_cards_template = templates.get_template("partials/notification_cards.html")
    notification_cards = notify_cards_template.render(
        {"request": request, "notify_settings": NOTIFY_SETTINGS}
    )
    notify_config_json = json.dumps(NOTIFY_SETTINGS)

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
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT id, name, url, monitor_type, status, response_time FROM sites WHERE is_active = 1 ORDER BY id"
        ) as c:
            sites_raw = await c.fetchall()
            sites = [dict(s) for s in sites_raw]

        cutoff_30d = (datetime.now() - timedelta(days=30)).isoformat()

        incidents_raw = []
        for s in sites:
            sid = s["id"]
            async with conn.execute(
                "SELECT COUNT(*) as total, SUM(CASE WHEN status = 'up' THEN 1 ELSE 0 END) as up_count "
                "FROM status_history WHERE site_id = ? AND checked_at >= ?",
                (sid, cutoff_30d),
            ) as c:
                row = await c.fetchone()
                total_checks = row[0] or 0
                up_checks = row[1] or 0
                s["uptime_pct"] = round(
                    (up_checks / total_checks * 100) if total_checks > 0 else 100.0, 2
                )

            async with conn.execute(
                "SELECT status, response_time, checked_at FROM status_history "
                "WHERE site_id = ? AND checked_at >= ? ORDER BY checked_at DESC LIMIT 1",
                (sid, cutoff_30d),
            ) as c:
                last = await c.fetchone()
                s["latest_response_time"] = (
                    round(last[1], 2) if last and last[1] is not None else None
                )

            async with conn.execute(
                "SELECT checked_at FROM status_history "
                "WHERE site_id = ? AND status = 'down' AND checked_at >= ? "
                "ORDER BY checked_at DESC LIMIT 5",
                (sid, cutoff_30d),
            ) as c:
                down_events = await c.fetchall()
                for de in down_events:
                    incidents_raw.append(
                        {
                            "site_name": s["name"],
                            "time": de[0][:19].replace("T", " "),
                        }
                    )

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
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
    from ..auth_module import validate_session
    from ..state import DB_PATH

    cookies = ws.headers.get("cookie", "")
    session_id = None
    for c in cookies.split(";"):
        c = c.strip()
        if c.startswith("session_id="):
            session_id = c[len("session_id="):]
            break

    if not session_id:
        await ws.close(code=4001, reason="Authentication required")
        return
    session = await validate_session(session_id, DB_PATH)
    if not session:
        await ws.close(code=4001, reason="Invalid session")
        return
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await manager.disconnect(ws)
