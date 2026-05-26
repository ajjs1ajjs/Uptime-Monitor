import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

try:
    from .. import ui_templates
    from ..database import get_db_connection
    from ..dependencies import get_current_user, require_admin
    from ..state import NOTIFY_SETTINGS, CONFIG
except ImportError:
    import ui_templates
    from database import get_db_connection
    from dependencies import get_current_user, require_admin
    from state import NOTIFY_SETTINGS, CONFIG

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


def _monitor_card_html(site: dict) -> str:
    import urllib.parse
    status = (site.get("status") or "unknown").lower()
    if status == "up":
        sclass = "up"
        scolor = "#10b981"
        border = "border-emerald-500"
    elif status == "paused":
        sclass = "paused"
        scolor = "#f59e0b"
        border = "border-amber-500"
    elif status == "maintenance":
        sclass = "maintenance"
        scolor = "#a855f7"
        border = "border-purple-500"
    else:
        sclass = "down"
        scolor = "#ef4444"
        border = "border-red-500"
        
    stext = status.upper()
    mtype = site.get("monitor_type", "http")
    methods = json.loads(site.get("notify_methods", "[]")) if isinstance(site.get("notify_methods"), str) else (site.get("notify_methods") or [])
    uptime = site.get("uptime", 100)
    if isinstance(uptime, str):
        try: uptime = float(uptime)
        except: uptime = 100.0
    name = (site.get("name") or "").replace("'", "\\'")
    url = (site.get("url") or "").replace("'", "\\'")
    sid = site.get("id", 0)
    rt = site.get("response_time") or "—"
    sc = site.get("status_code") or "—"

    keyword = site.get("keyword") or ""
    encoded_keyword = urllib.parse.quote(keyword)
    encoded_url = urllib.parse.quote(site.get("url") or "")
    encoded_methods = urllib.parse.quote(json.dumps(methods))
    
    keyword_html = f'<div class="text-[11px] text-indigo-400 mt-1 flex items-center gap-1">🔑 Ключ: <span class="text-slate-300 font-mono">{keyword}</span></div>' if keyword else ""

    return f"""<div class="gradient-card rounded-xl p-5 border-l-4 {border} border border-slate-700/30 card-hover transition">
        <div class="flex justify-between items-start mb-4">
            <div class="min-w-0 flex-1">
                <div class="text-base font-semibold truncate" title="{name}">{site.get("name", "")}</div>
                <div class="text-xs text-slate-400 truncate mt-0.5" title="{url}">{site.get("url", "")}</div>
                {keyword_html}
            </div>
            <span class="px-3 py-1 rounded-full text-[10px] font-bold uppercase bg-accent/10 text-accent">{mtype}</span>
        </div>
        <div class="grid grid-cols-4 gap-2 py-3 border-y border-slate-700/30 text-center text-xs">
            <div><div class="text-sm font-bold" style="color:{scolor}">{stext}</div><div class="text-slate-500 mt-0.5">Status</div></div>
            <div><div class="text-sm font-bold text-slate-200">{rt}ms</div><div class="text-slate-500 mt-0.5">Time</div></div>
            <div><div class="text-sm font-bold text-slate-200">{uptime:.1f}%</div><div class="text-slate-500 mt-0.5">Uptime</div></div>
            <div><div class="text-sm font-bold text-slate-200">{sc}</div><div class="text-slate-500 mt-0.5">HTTP</div></div>
        </div>
        <div class="flex gap-2 mt-4">
            <button onclick="checkSite({sid})" class="flex-1 py-2.5 rounded-lg gradient-accent text-black text-xs font-bold hover:shadow-lg hover:shadow-cyan-500/30 transition">🔄 Check</button>
            <button onclick="openEditModal({sid},'{name}','{encoded_url}','{encoded_methods}',{site.get("check_interval",60)},'{mtype}','{encoded_keyword}')" class="flex-1 py-2.5 rounded-lg bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 transition text-xs font-medium">✏️ Edit</button>
            <button onclick="deleteSite({sid})" class="flex-1 py-2.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition text-xs font-medium">🗑️ Delete</button>
        </div>
    </div>"""


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
        _hero_stat_html("Monitors", total) +
        _hero_stat_html("Online", up, "text-emerald-400") +
        _hero_stat_html("Offline", down, "text-red-400") +
        _hero_stat_html("Incidents", incidents, "text-amber-400")
    )


@router.get("/api/htmx/monitors", response_class=HTMLResponse)
async def htmx_monitors(
    search: Optional[str] = None,
    sort: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    if not user:
        return HTMLResponse("")
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT s.*, (SELECT COUNT(*) FROM status_history sh WHERE sh.site_id = s.id AND sh.checked_at >= datetime('now', '-24 hours')) as checks_24h FROM sites s ORDER BY s.id"
        ) as c:
            sites_raw = await c.fetchall()
            sites = [dict(s) for s in sites_raw]

    for site in sites:
        sid = site["id"]
        async with conn.execute(
            "SELECT status FROM status_history WHERE site_id = ? ORDER BY checked_at DESC LIMIT 1", (sid,)
        ) as c:
            last = await c.fetchone()
        site["status"] = last["status"] if last else "unknown"
        async with conn.execute(
            "SELECT COUNT(*) as total, SUM(CASE WHEN status = 'up' THEN 1 ELSE 0 END) as up_count FROM status_history WHERE site_id = ?", (sid,)
        ) as c:
            st = await c.fetchone()
        site["uptime"] = round((st["up_count"] / st["total"] * 100), 1) if st and st["total"] > 0 else 100.0
        site["notify_methods"] = json.loads(site.get("notify_methods") or "[]")

    if search:
        search_lower = search.lower().strip()
        sites = [
            s for s in sites 
            if search_lower in (s.get("name") or "").lower() or search_lower in (s.get("url") or "").lower()
        ]

    if sort == "name":
        sites.sort(key=lambda s: (s.get("name") or "").lower())
    elif sort == "uptime":
        sites.sort(key=lambda s: s.get("uptime", 100.0), reverse=True)
    elif sort == "response_time":
        sites.sort(key=lambda s: s.get("response_time") if isinstance(s.get("response_time"), (int, float)) else 999999)
    else:
        # Default status sorting: down -> slow -> maintenance -> paused -> unknown -> up
        status_order = {"down": 0, "slow": 1, "maintenance": 2, "paused": 3, "unknown": 4, "up": 5}
        sites.sort(key=lambda s: status_order.get((s.get("status") or "unknown").lower(), 6))

    if not sites:
        return HTMLResponse('<div class="col-span-full text-center py-10 text-slate-500">No monitors found.</div>')

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
