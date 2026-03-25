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
    from . import state as app_state
    from .database import get_db_connection
    from .logger import logger
    from .routers import api, auth, ui
except ImportError:
    import auth_module
    import config_manager
    import models
    import monitoring
    import state as app_state
    from database import get_db_connection
    from logger import logger
    from routers import api, auth, ui

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
    """Повертає 0.0.0.0 для біндінгу на всі інтерфейси"""
    return "0.0.0.0"


SERVER_HOST = "0.0.0.0" if DEFAULT_HOST == "auto" else DEFAULT_HOST

# FastAPI app
app = FastAPI(title="Uptime Monitor")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


from contextlib import asynccontextmanager


# --- Initialization ---
async def initialize_app_async():
    # Init DB and run migrations
    try:
        await models.init_database(DB_PATH)
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    import json

    # Load settings from DB
    try:
        async with get_db_connection() as conn:
            async with conn.execute("SELECT config FROM notify_config WHERE id = 1") as c:
                row = await c.fetchone()
                if row:
                    try:
                        app_state.NOTIFY_SETTINGS.update(json.loads(row["config"]))
                    except:
                        pass
            async with conn.execute("SELECT display_address FROM app_settings WHERE id = 1") as c:
                row = await c.fetchone()
                if row:
                    app_state.DISPLAY_ADDRESS = row["display_address"] or ""
    except Exception as e:
        logger.error(f"Settings load failed: {e}")

    try:
        await auth_module.init_auth_tables(DB_PATH)
    except Exception as e:
        logger.error(f"Auth tables initialization failed: {e}")


def initialize_app():
    """Синхронна обгортка для ініціалізації (використовується в Windows-сервісі)"""
    config_manager.init_paths()
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        # This shouldn't happen in service initialization, but just in case
        asyncio.ensure_future(initialize_app_async())
    else:
        loop.run_until_complete(initialize_app_async())


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await initialize_app_async()
    yield
    # Shutdown (if needed)


# FastAPI app
app = FastAPI(title="Uptime Monitor", lifespan=lifespan)


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker and monitoring"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


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
        logger.error(f"Background monitoring error: {e}")


def main():
    """Entry point for package and script запуску."""
    import argparse

    parser = argparse.ArgumentParser(description="Uptime Monitor")
    parser.add_argument("--host", type=str, default=DEFAULT_HOST, help="Host to bind to")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind to")
    parser.add_argument(
        "--no-monitor",
        action="store_true",
        help="Disable background monitoring (use separate worker service)",
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
    print(f"Uptime Monitor starting on {host}:{port}...")

    # Start background monitoring unless disabled
    if not args.no_monitor:
        logger.info("Background monitoring enabled")
        import threading

        def run_monitor():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_monitor_in_background())

        monitor_thread = threading.Thread(target=run_monitor, daemon=True)
        monitor_thread.start()
    else:
        print("Background monitoring disabled (use worker.py separately)")

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
