import asyncio
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import auth_module, config_manager, metrics_store, models, monitoring
from . import state as app_state
from .database import close_db, get_db_connection
from .logger import logger
from .routers import api, auth, ui

IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    pass

# App initialization
config_manager.init_paths()

# Global state and constants from state.py
CONFIG = app_state.CONFIG
DB_PATH = app_state.DB_PATH
CHECK_INTERVAL = app_state.CHECK_INTERVAL

# Add cache-busting version for static assets
APP_VERSION = datetime.now().strftime("%Y%m%d%H%M%S")

DEFAULT_HOST = CONFIG.get("server", {}).get("host", "auto")
DEFAULT_PORT = CONFIG.get("server", {}).get("port", 8080)


def get_default_host():
    """Повертає 0.0.0.0 для біндінгу на всі інтерфейси"""
    return "0.0.0.0"  # nosec B104


# --- Initialization ---
async def initialize_app_async():
    # Init DB and run migrations
    try:
        await models.init_database(DB_PATH)
    except Exception as e:
        logger.error("Database initialization failed: %s", e)

    import json

    # Init CSRF table
    try:
        from .csrf import init_csrf_table
        await init_csrf_table()
    except Exception as e:
        logger.error("CSRF init failed: %s", e)

    # Load settings from DB
    try:
        async with get_db_connection() as conn:
            async with conn.execute("SELECT config FROM notify_config WHERE id = 1") as c:
                row = await c.fetchone()
                if row:
                    try:
                        app_state.NOTIFY_SETTINGS.update(json.loads(row["config"]))
                    except json.JSONDecodeError:
                        pass
            async with conn.execute("SELECT * FROM app_settings WHERE id = 1") as c:
                row = await c.fetchone()
                if row:
                    app_state.DISPLAY_ADDRESS = row["display_address"] or ""
                    app_state.SITE_TITLE = row["site_title"] or "Uptime Monitor"
                    app_state.LOGO_URL = row["logo_url"] or ""
                    app_state.FOOTER_TEXT = row["footer_text"] or ""
                    app_state.PRIMARY_COLOR = row["primary_color"] or "#00ff88"
                    app_state.BRAND_ACCENT_COLOR = row["brand_accent_color"] or "#06b6d4"
    except Exception as e:
        logger.error("Settings load failed: %s", e)

    try:
        await auth_module.init_auth_tables(DB_PATH)
    except Exception as e:
        logger.error("Auth tables initialization failed: %s", e)


def initialize_app():
    """Синхронна обгортка для ініціалізації (використовується в Windows-сервісі)"""
    config_manager.init_paths()
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except RuntimeError:
        pass

    try:
        loop = asyncio.get_running_loop()
        asyncio.create_task(initialize_app_async())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(initialize_app_async())


@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize_app_async()
    yield
    await close_db()


# FastAPI app
app = FastAPI(title="Uptime Monitor", lifespan=lifespan)

# Static files (for PWA manifest, service worker, icons)
BASE_DIR = Path(__file__).resolve().parent
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CONFIG.get("cors", {}).get("allow_origins", ["http://localhost:8080"]),
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] =         "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com; img-src 'self' data:; font-src 'self' data:; connect-src 'self' ws: https://cdn.jsdelivr.net;"
    return response


# Access log middleware
@app.middleware("http")
async def access_log(request: Request, call_next):
    import time
    path = request.url.path
    if path.startswith(("/static/", "/health", "/metrics", "/favicon")):
        return await call_next(request)
    start = time.time()
    response = await call_next(request)
    elapsed = int((time.time() - start) * 1000)
    logger.info("%s %s %s %dms", request.method, path, response.status_code, elapsed)
    return response


# Add cache-control middleware to prevent HTML caching
@app.middleware("http")
async def add_cache_control(request: Request, call_next):
    response = await call_next(request)
    if request.url.path in [
        "/",
        "/users",
        "/status",
        "/public-status",
        "/login",
        "/change-password",
        "/forgot-password",
    ]:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# Middleware for HTTPS redirect and HSTS
@app.middleware("http")
async def https_redirect_middleware(request: Request, call_next):
    return await config_manager.https_redirect_middleware(request, call_next, CONFIG)


# Error handlers for 404 and 500
HTML_404 = """<!DOCTYPE html><html lang="uk"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>404 — Сторінку не знайдено</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-gray-900 text-white flex items-center justify-center h-screen"><div class="text-center"><h1 class="text-9xl font-bold text-cyan-400">404</h1><p class="text-2xl mt-4">Сторінку не знайдено</p><p class="text-gray-400 mt-2">Page not found</p><a href="/" class="inline-block mt-6 px-6 py-3 bg-cyan-500 rounded-lg hover:bg-cyan-600 transition">На головну</a></div></body></html>"""

HTML_500 = """<!DOCTYPE html><html lang="uk"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>500 — Помилка сервера</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-gray-900 text-white flex items-center justify-center h-screen"><div class="text-center"><h1 class="text-9xl font-bold text-red-400">500</h1><p class="text-2xl mt-4">Внутрішня помилка сервера</p><p class="text-gray-400 mt-2">Internal server error</p><a href="/" class="inline-block mt-6 px-6 py-3 bg-cyan-500 rounded-lg hover:bg-cyan-600 transition">На головну</a></div></body></html>"""


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    from fastapi.responses import HTMLResponse
    return HTMLResponse(HTML_404, status_code=404)


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    from fastapi.responses import HTMLResponse
    return HTMLResponse(HTML_500, status_code=500)


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker and monitoring."""

    db_ok = False
    try:
        async with get_db_connection() as conn:
            await conn.execute("SELECT 1")
            db_ok = True
    except Exception:
        pass

    monitor_ok = True
    heartbeat = metrics_store.get_heartbeat_age()
    if heartbeat > 0:
        monitor_ok = heartbeat < 120

    overall = "healthy" if db_ok and monitor_ok else "degraded"
    return {
        "status": overall,
        "timestamp": datetime.now().isoformat(),
        "checks": {
            "database": "ok" if db_ok else "error",
            "monitor_thread": "ok" if monitor_ok else "stale",
        },
        "version": "2.1.0",
    }


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint (no external dependencies)."""
    from .database import get_db_connection

    store = metrics_store.get_metrics()
    metrics = []
    metrics.append("# HELP uptime_monitor_sites_total Total number of monitored sites")
    metrics.append("# TYPE uptime_monitor_sites_total gauge")
    metrics.append("# HELP uptime_monitor_sites_up Number of sites currently up")
    metrics.append("# TYPE uptime_monitor_sites_up gauge")
    metrics.append("# HELP uptime_monitor_sites_down Number of sites currently down")
    metrics.append("# TYPE uptime_monitor_sites_down gauge")
    metrics.append("# HELP uptime_monitor_sites_maintenance Number of sites in maintenance")
    metrics.append("# TYPE uptime_monitor_sites_maintenance gauge")
    metrics.append("# HELP uptime_monitor_sites_paused Number of paused sites")
    metrics.append("# TYPE uptime_monitor_sites_paused gauge")
    metrics.append("# HELP uptime_monitor_checks_total Total checks performed")
    metrics.append("# TYPE uptime_monitor_checks_total counter")
    metrics.append("# HELP uptime_monitor_checks_failed_total Failed checks")
    metrics.append("# TYPE uptime_monitor_checks_failed_total counter")
    metrics.append("# HELP uptime_monitor_notifications_sent_total Notifications sent")
    metrics.append("# TYPE uptime_monitor_notifications_sent_total counter")
    metrics.append("# HELP uptime_monitor_notifications_failed_total Failed notifications")
    metrics.append("# TYPE uptime_monitor_notifications_failed_total counter")
    metrics.append(
        "# HELP uptime_monitor_monitor_heartbeat_seconds Time since last monitor heartbeat"
    )
    metrics.append("# TYPE uptime_monitor_monitor_heartbeat_seconds gauge")
    metrics.append("# HELP uptime_monitor_info Static info about this instance")
    metrics.append("# TYPE uptime_monitor_info gauge")

    try:
        async with get_db_connection() as conn:
            async with conn.execute("SELECT COUNT(*) FROM sites") as c:
                row = await c.fetchone()
                total = row[0] or 0
            async with conn.execute("SELECT COUNT(*) FROM sites WHERE status = 'up'") as c:
                row = await c.fetchone()
                up = row[0] or 0
            async with conn.execute("SELECT COUNT(*) FROM sites WHERE status = 'down'") as c:
                row = await c.fetchone()
                down = row[0] or 0
            async with conn.execute("SELECT COUNT(*) FROM sites WHERE status = 'maintenance'") as c:
                row = await c.fetchone()
                maint = row[0] or 0
            async with conn.execute("SELECT COUNT(*) FROM sites WHERE status = 'paused'") as c:
                row = await c.fetchone()
                paused = row[0] or 0
    except Exception:
        total = up = down = maint = paused = 0

    metrics.append(f"uptime_monitor_sites_total {total}")
    metrics.append(f"uptime_monitor_sites_up {up}")
    metrics.append(f"uptime_monitor_sites_down {down}")
    metrics.append(f"uptime_monitor_sites_maintenance {maint}")
    metrics.append(f"uptime_monitor_sites_paused {paused}")
    metrics.append(f"uptime_monitor_checks_total {store['checks_total']}")
    metrics.append(f"uptime_monitor_checks_failed_total {store['checks_failed']}")
    metrics.append(f"uptime_monitor_notifications_sent_total {store['notifications_sent']}")
    metrics.append(f"uptime_monitor_notifications_failed_total {store['notifications_failed']}")
    metrics.append(
        f"uptime_monitor_monitor_heartbeat_seconds {metrics_store.get_heartbeat_age():.1f}"
    )
    metrics.append(f'uptime_monitor_info{{version="2.1.0",python="{sys.version}"}} 1')

    return Response(
        content="\n".join(metrics) + "\n",
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache"},
    )


# --- Include Routers ---
app.include_router(auth.router)
app.include_router(ui.router)
app.include_router(api.router)


# --- Background Task & Service ---
async def run_monitor_in_background():
    """Запускає моніторинг у фоновому режимі разом із веб-сервером"""
    try:
        logger.info("Starting background monitoring loop...")
        await monitoring.monitor_loop(app_state.NOTIFY_SETTINGS, CHECK_INTERVAL)
    except Exception as e:
        logger.error("Background monitoring error: %s", e)


def main():
    """Entry point for package and script запуску."""
    import argparse

    parser = argparse.ArgumentParser(description="Uptime Monitor")
    parser.add_argument("--host", type=str, default=DEFAULT_HOST, help="Host to bind to")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind to")
    parser.add_argument(
        "--no-monitor",
        action="store_true",
        default=True,
        help="Disable background monitoring (use separate worker service)",
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        dest="enable_monitor",
        help="Enable embedded background monitoring (not recommended when worker service is used)",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["install", "remove", "start", "stop", "restart"],
        help="Service command",
    )
    args, _ = parser.parse_known_args()

    if args.command:
        if IS_WINDOWS:
            print(f"Executing service command: {args.command}")
            return
        print("Service commands are only supported on Windows.")
        return

    host = get_default_host() if args.host == "auto" else args.host
    port = args.port
    logger.info("Uptime Monitor starting on %s:%s...", host, port)

    # Start background monitoring only if explicitly enabled with --monitor
    if args.enable_monitor:
        logger.warning("Embedded monitoring enabled via --monitor (consider using worker service instead)")
        import threading

        def run_monitor():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_monitor_in_background())

        monitor_thread = threading.Thread(target=run_monitor, daemon=True)
        monitor_thread.start()

    ssl_context = config_manager.setup_ssl(CONFIG)
    ssl_cfg = CONFIG.get("ssl", {})
    uvicorn.run(
        app,
        host=host,
        port=port,
        ssl_keyfile=ssl_cfg.get("key_path") if ssl_context else None,
        ssl_certfile=ssl_cfg.get("cert_path") if ssl_context else None,
        log_level="info",
    )


if __name__ == "__main__":
    main()
