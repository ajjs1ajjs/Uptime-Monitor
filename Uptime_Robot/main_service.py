import asyncio
import os
import sys
import traceback
from datetime import datetime

import uvicorn

try:
    from . import main as app_main
    from . import state as app_state
except ImportError:
    import main as app_main
    import state as app_state


IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil
else:
    servicemanager = None
    win32event = None
    win32service = None
    win32serviceutil = None


app = app_main.app
DB_PATH = app_main.DB_PATH
SERVER_HOST = app_main.SERVER_HOST
DEFAULT_PORT = app_main.DEFAULT_PORT


if IS_WINDOWS:

    class UptimeMonitorService(win32serviceutil.ServiceFramework):
        _svc_name_ = "UptimeMonitor"
        _svc_display_name_ = "Uptime Monitor Service"
        _svc_description_ = "Website uptime monitoring service with web interface"

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.server = None

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            if self.server is not None:
                self.server.should_exit = True
            win32event.SetEvent(self.stop_event)

        def SvcDoRun(self):
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ""),
            )
            self.main()

        def main(self):
            # Use fixed path for error logging to survive environment issues
            app_dir = os.path.dirname(os.path.abspath(__file__))
            error_log_path = os.path.join(app_dir, "service_error.log")
            
            self.ReportServiceStatus(win32service.SERVICE_START_PENDING, waitHint=30000)
            
            try:
                # Initialize app (Sync wrapper handles loop)
                app_main.initialize_app()
                
                # Get the event loop created by initialize_app
                loop = asyncio.get_event_loop()
                
                # Start monitoring in the background
                asyncio.ensure_future(
                    app_main.monitoring.monitor_loop(
                        app_state.NOTIFY_SETTINGS, app_state.CHECK_INTERVAL
                    )
                )
                
                # Configure and start uvicorn
                ssl_context = app_main.config_manager.setup_ssl(app_main.CONFIG)
                config = uvicorn.Config(
                    app,
                    host=app_main.SERVER_HOST,
                    port=app_main.DEFAULT_PORT,
                    ssl_keyfile=app_main.CONFIG["ssl"].get("key_path") if ssl_context else None,
                    ssl_certfile=app_main.CONFIG["ssl"].get("cert_path") if ssl_context else None,
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
                    with open(error_log_path, "a", encoding="utf-8") as f:
                        f.write(f"[{datetime.now().isoformat()}] Service runtime error\n")
                        f.write(err + "\n")
                except: pass
                try: servicemanager.LogErrorMsg(err)
                except: pass
            finally:
                self.ReportServiceStatus(win32service.SERVICE_STOPPED)


def run_console():
    """Run in console mode for testing"""
    print("Starting Uptime Monitor in console mode...")
    app_main.initialize_app()
    app_main.main()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].lower() == "console":
        # Remove 'console' from argv so argparse in main.py doesn't complain
        sys.argv.pop(1)
        run_console()
    elif len(sys.argv) == 1:
        # Default to console if no args
        run_console()
    elif not IS_WINDOWS:
        raise SystemExit("Windows service mode is only supported on Windows.")
    else:
        win32serviceutil.HandleCommandLine(UptimeMonitorService)
