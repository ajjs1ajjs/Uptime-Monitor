@echo off
echo Installing Uptime Monitor Service...
python main_service.py install
if errorlevel 1 (
    echo ERROR: Service installation failed
    pause
    exit /b 1
)
echo Service installed successfully
sc config UptimeMonitor start= auto
net start UptimeMonitor
echo.
echo Service started on port: 
pause
