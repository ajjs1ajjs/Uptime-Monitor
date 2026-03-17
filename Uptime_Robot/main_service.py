import asyncio
import json
import os
import socket
import sqlite3
import sys
import threading
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

# Internal modules
import config_manager
import models
import notifications
import servicemanager
import ui_templates
import uvicorn
import win32event
import win32service
import win32serviceutil
from database import get_db_connection
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from logger import logger
from pydantic import BaseModel

import monitoring

# Configuration
config_manager.init_paths()
CONFIG = config_manager.load_config()
DB_PATH = config_manager.DB_PATH
APP_DIR = config_manager.APP_DIR
DEFAULT_PORT = CONFIG.get("server", {}).get("port", 8080)
DEFAULT_HOST = CONFIG.get("server", {}).get("host", "auto")
CHECK_INTERVAL = CONFIG.get("check_interval", 60)

# Global settings
NOTIFY_SETTINGS = config_manager.DEFAULT_NOTIFY_SETTINGS.copy()


# Get default host if "auto" is set
def get_default_host():
    """Отримує поточну IP адресу сервера"""
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip.startswith("127."):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
            except Exception:
                pass
            finally:
                s.close()
        return ip
    except Exception:
        return "0.0.0.0"


SERVER_HOST = get_default_host() if DEFAULT_HOST == "auto" else DEFAULT_HOST

app = FastAPI(title="Uptime Monitor Service")


# --- Initialization ---
def initialize_app():
    global NOTIFY_SETTINGS
    models.init_database(DB_PATH)
    # Load notify settings from DB
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT config FROM notify_config WHERE id = 1")
        row = c.fetchone()
        if row:
            try:
                NOTIFY_SETTINGS.update(json.loads(row["config"]))
            except:
                pass


initialize_app()


# --- Pydantic Models (Simplified for Service) ---
class SiteCreate(BaseModel):
    name: str
    url: str
    check_interval: int = 60
    is_active: bool = True
    notify_methods: Optional[List[str]] = []


class SiteUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    notify_methods: Optional[List[str]] = None
    is_active: Optional[bool] = None


class NotifySettings(BaseModel):
    telegram: Optional[dict] = None
    teams: Optional[dict] = None
    discord: Optional[dict] = None
    slack: Optional[dict] = None
    email: Optional[dict] = None
    sms: Optional[dict] = None


# --- API Endpoints ---


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM sites")
        total_sites = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM sites WHERE status = 'up'")
        up_sites = c.fetchone()[0]
        down_sites = total_sites - up_sites

    notification_cards = ui_templates.get_notification_cards_html(NOTIFY_SETTINGS)
    notify_config_json = json.dumps(NOTIFY_SETTINGS)

    # Note: Service dashboard uses a single-page approach without login
    return HTMLResponse(
        content=ui_templates.get_dashboard_html(
            total_sites=total_sites,
            up_sites=up_sites,
            down_sites=down_sites,
            notify_config_json=notify_config_json,
            notification_cards=notification_cards,
        )
    )


@app.get("/status", response_class=HTMLResponse)
@app.get("/public-status", response_class=HTMLResponse)
async def public_status_page():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id, name, url, monitor_type, status FROM sites WHERE is_active = 1 ORDER BY id"
        )
        sites = c.fetchall()

    def status_of(site_row: sqlite3.Row) -> str:
        value = site_row["status"]
        return (value or "unknown").lower()

    up_count = sum(1 for s in sites if status_of(s) == "up")
    down_count = sum(1 for s in sites if status_of(s) == "down")
    total = len(sites)

    def get_sort_order(site_row: sqlite3.Row) -> int:
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

    sites = sorted(sites, key=get_sort_order)

    monitors_html = ""
    for site in sites:
        status = status_of(site)
        if status == "up":
            status_class = "up"
            status_text = "UP"
            dot_color = "#00ff88"
        elif status in ("paused", "slow"):
            status_class = "paused"
            status_text = "PAUSED" if status == "paused" else "SLOW"
            dot_color = "#f59e0b"
        elif status == "unknown":
            status_class = "unknown"
            status_text = "UNKNOWN"
            dot_color = "#94a3b8"
        else:
            status_class = "down"
            status_text = "DOWN"
            dot_color = "#ff4757"

        monitors_html += f"""
        <div class="monitor {status_class}">
            <div style="display: flex; align-items: center; gap: 12px;">
                <div style="width: 10px; height: 10px; border-radius: 50%; background: {dot_color}; box-shadow: 0 0 8px {dot_color};"></div>
                <div><div class="monitor-name">{site["name"]}</div>
                <div class="monitor-url">{site["url"]}</div></div>
            </div>
            <span class="status-badge {status_class}">{status_text}</span>
        </div>"""

    overall_status_class = "up" if down_count == 0 else "down"
    overall_status_text = (
        "All systems operational" if down_count == 0 else "Some issues detected"
    )
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return HTMLResponse(
        content=ui_templates.get_public_status_html(
            overall_status_class=overall_status_class,
            overall_status_text=overall_status_text,
            total=total,
            up_count=up_count,
            down_count=down_count,
            monitors_html=monitors_html,
            timestamp=timestamp,
        )
    )


@app.get("/api/sites")
async def get_sites():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM sites ORDER BY id")
        sites = [dict(row) for row in c.fetchall()]

        for site in sites:
            c.execute(
                "SELECT * FROM status_history WHERE site_id = ? ORDER BY checked_at DESC LIMIT 1",
                (site["id"],),
            )
            last = c.fetchone()
            site["status"] = last["status"] if last else "unknown"
            site["notify_methods"] = (
                json.loads(site["notify_methods"]) if site["notify_methods"] else []
            )
    return sites


@app.get("/api/sites/{site_id}/history")
async def get_site_history(site_id: int, limit: int = 50):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT status, status_code, checked_at FROM status_history WHERE site_id = ? ORDER BY checked_at DESC LIMIT ?",
            (site_id, limit),
        )
        history = c.fetchall()
    return [
        {
            "status": h["status"],
            "status_code": h["status_code"],
            "checked_at": h["checked_at"],
        }
        for h in history
    ]


@app.post("/api/sites")
async def add_site(site: SiteCreate):
    with get_db_connection() as conn:
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO sites (name, url, check_interval, is_active, notify_methods) VALUES (?, ?, ?, ?, ?)",
                (
                    site.name,
                    site.url,
                    site.check_interval,
                    site.is_active,
                    json.dumps(site.notify_methods),
                ),
            )
            site_id = c.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(400, "Already exists")

    await monitoring.check_site_status(
        site_id, site.url, site.notify_methods, NOTIFY_SETTINGS
    )
    return {"id": site_id}


@app.put("/api/sites/{site_id}")
async def update_site(site_id: int, site_update: SiteUpdate):
    models.update_site(DB_PATH, site_id, **site_update.dict(exclude_unset=True))
    return {"message": "Updated"}


@app.delete("/api/sites/{site_id}")
async def delete_site(site_id: int):
    models.delete_site(DB_PATH, site_id)
    return {"message": "Deleted"}


@app.post("/api/sites/{site_id}/check")
async def manual_check(site_id: int):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT url, notify_methods FROM sites WHERE id = ?", (site_id,))
        site = c.fetchone()
    if not site:
        raise HTTPException(404)
    methods = json.loads(site["notify_methods"]) if site["notify_methods"] else []
    await monitoring.check_site_status(site_id, site["url"], methods, NOTIFY_SETTINGS)
    return {"message": "Check done"}


@app.post("/api/notify-settings")
async def save_notify(settings: NotifySettings):
    global NOTIFY_SETTINGS
    data = settings.dict(exclude_unset=True)
    for k, v in data.items():
        if v:
            NOTIFY_SETTINGS[k] = v
    models.save_notify_settings(DB_PATH, NOTIFY_SETTINGS)
    return {"message": "Saved"}


@app.get("/api/ssl-certificates")
async def get_ssl_certs():
    return models.get_ssl_certificates(DB_PATH)


@app.post("/api/ssl-certificates/check")
async def manual_ssl_check():
    await monitoring.check_all_certificates(NOTIFY_SETTINGS)
    return {"message": "SSL check triggered"}


@app.get("/api/stats/response-time")
async def get_response_time_stats():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT site_id, s.name as site_name, AVG(sh.response_time) as avg_time, MIN(sh.response_time) as min_time, MAX(sh.response_time) as max_time, COUNT(*) as checks
            FROM status_history sh
            JOIN sites s ON sh.site_id = s.id
            WHERE sh.checked_at >= datetime('now', '-24 hours') AND sh.response_time IS NOT NULL
            GROUP BY site_id
            ORDER BY avg_time ASC
        """)
        results = c.fetchall()
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


@app.get("/api/incidents")
async def get_incidents():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
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
            ORDER BY sh.checked_at DESC
            LIMIT 50
        """)
        results = c.fetchall()

    incidents = []
    for r in results:
        incidents.append(
            {
                "id": r["id"],
                "site_id": r["site_id"],
                "site_name": r["site_name"],
                "site_url": r["site_url"],
                "status": r["status"],
                "status_code": r["status_code"],
                "response_time": r["response_time"],
                "error_message": r["error_message"],
                "checked_at": r["checked_at"],
            }
        )
    return incidents


# --- Windows Service Logic ---


class UptimeMonitorService(win32serviceutil.ServiceFramework):
    _svc_name_ = "UptimeMonitor"
    _svc_display_name_ = "Uptime Monitor Service"
    _svc_description_ = "Website uptime monitoring service with web interface"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = False
        self.server = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self.server is not None:
            self.server.should_exit = True
        win32event.SetEvent(self.stop_event)
        self.running = False

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        self.running = True
        self.main()

    def main(self):
        error_log_path = os.path.join(os.path.dirname(DB_PATH), "service_error.log")
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING, waitHint=30000)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            asyncio.ensure_future(
                monitoring.monitor_loop(NOTIFY_SETTINGS, CHECK_INTERVAL)
            )
            # In Windows Service context stdout/stderr may be None, which breaks
            # uvicorn default logging formatter (isatty check).
            config = uvicorn.Config(
                app,
                host=SERVER_HOST,
                port=DEFAULT_PORT,
                log_level="error",
                log_config=None,
                access_log=False,
            )
            self.server = uvicorn.Server(config)
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            loop.run_until_complete(self.server.serve())
        except Exception:
            err = traceback.format_exc()
            try:
                os.makedirs(os.path.dirname(error_log_path), exist_ok=True)
                with open(error_log_path, "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now().isoformat()}] Service runtime error\n")
                    f.write(err + "\n")
            except Exception:
                pass
            try:
                servicemanager.LogErrorMsg(err)
            except Exception:
                pass
        finally:
            self.server = None
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            except Exception:
                pass
            loop.close()
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)


def install_service():
    try:
        # Use script path so pywin32 registers the correct Python service class.
        script_path = os.path.abspath(__file__)
        win32serviceutil.HandleCommandLine(
            UptimeMonitorService, argv=[script_path, "--startup", "auto", "install"]
        )
        print("Service installed and set to Auto-start.")
    except Exception as e:
        print(f"Installation error: {e}")


def run_console():
    print(f"Uptime Monitor (Console Mode) on port {DEFAULT_PORT}, host {SERVER_HOST}")

    async def run():
        asyncio.create_task(monitoring.monitor_loop(NOTIFY_SETTINGS, CHECK_INTERVAL))
        config = uvicorn.Config(
            app, host=SERVER_HOST, port=DEFAULT_PORT, log_level="info"
        )
        await uvicorn.Server(config).serve()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    if len(sys.argv) == 1:
        run_console()
    else:
        cmd = sys.argv[1].lower()
        if cmd == "console":
            run_console()
        else:
            # Let pywin32 handle install/start/stop/remove/restart with full metadata.
            win32serviceutil.HandleCommandLine(UptimeMonitorService)
