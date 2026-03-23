import asyncio
import socket
import sys
import threading
from datetime import datetime

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

try:
    from . import auth_module, config_manager, models, monitoring
    from .database import get_db_connection
    from .logger import logger
    from .routers import auth, ui, api
    from . import state as app_state
except ImportError:
    import auth_module
    import config_manager
    import models
    import monitoring
    from database import get_db_connection
    from logger import logger
    from routers import auth, ui, api
    import state as app_state

IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    import servicemanager
    import win32con
    import win32event
    import win32service
    import win32serviceutil

# App initialization
config_manager.init_paths()

# Global state and constants from state.py
CONFIG = app_state.CONFIG
DB_PATH = app_state.DB_PATH

# Add cache-busting version for static assets
APP_VERSION = datetime.now().strftime("%Y%m%d%H%M%S")

DEFAULT_HOST = CONFIG.get("server", {}).get("host", "auto")
DEFAULT_PORT = CONFIG.get("server", {}).get("port", 8080)

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

SERVER_HOST = "0.0.0.0" if DEFAULT_HOST == "auto" else DEFAULT_HOST

# FastAPI app
app = FastAPI(title="Uptime Monitor")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "https://localhost:8080"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

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

# --- Initialization ---
async def initialize_app_async():
    # Init DB and run migrations
    await models.init_database(DB_PATH)

    import json
    # Load settings from DB
    async with get_db_connection() as conn:
        async with conn.execute("SELECT config FROM notify_config WHERE id = 1") as c:
            row = await c.fetchone()
            if row:
                try:
                    app_state.NOTIFY_SETTINGS.update(json.loads(row["config"]))
                except:
                    pass

        # App settings
        async with conn.execute("SELECT display_address FROM app_settings WHERE id = 1") as c:
            row = await c.fetchone()
            if row:
                app_state.DISPLAY_ADDRESS = row["display_address"] or ""

    # Init Auth tables
    await auth_module.init_auth_tables(DB_PATH)

def initialize_app():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        loop.create_task(initialize_app_async())
    else:
        asyncio.run(initialize_app_async())

initialize_app()

@app.get("/health")
async def health_check():
    """Health check endpoint for Docker and monitoring"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# --- Include Routers ---
app.include_router(auth.router)
app.include_router(ui.router)
app.include_router(api.router)

# --- Background Task & Service ---
def main():
    """Entry point for package and script запуску."""
    import argparse

    parser = argparse.ArgumentParser(description="Uptime Monitor")
    parser.add_argument("--host", type=str, default=DEFAULT_HOST, help="Host to bind to")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind to")
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
    print(f"Uptime Monitor starting on {host}:{port}...")

    # Background monitoring is now handled independently in worker.py
    print(f"To start background monitoring, run: python -m Uptime_Robot.worker")

    ssl_context = config_manager.setup_ssl(CONFIG)
    uvicorn.run(
        app,
        host=host,
        port=port,
        ssl_keyfile=CONFIG["ssl"].get("key_path") if ssl_context else None,
        ssl_certfile=CONFIG["ssl"].get("cert_path") if ssl_context else None,
        log_level="info",
    )

if __name__ == "__main__":
    main()
