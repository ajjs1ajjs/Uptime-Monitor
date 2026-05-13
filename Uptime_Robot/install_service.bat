@echo off
title Uptime Monitor - Service Installer
chcp 65001 >nul

echo ========================================
echo   Uptime Monitor - Windows Service
echo ========================================
echo.

net session >nul 2>&1
if not %errorlevel%==0 (
    echo ERROR: Run this script as Administrator!
    echo Right-click -^> "Run as administrator"
    pause
    exit /b 1
)

cd /d "%~dp0"

echo Step 1: Installing Python dependencies...
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo Step 2: Installing pywin32 for service support...
python -m pip install --upgrade --force-reinstall --no-user pywin32 >nul 2>&1
if errorlevel 1 (
    echo WARNING: pywin32 system install failed. Service may not work.
)

echo Step 3: Registering service...
python main_service.py install
if errorlevel 1 (
    echo ERROR: Service installation failed!
    pause
    exit /b 1
)

echo Step 4: Configuring auto-start...
sc config UptimeMonitor start= auto >nul

echo Step 5: Starting service...
net start UptimeMonitor

echo.
echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo Service: UptimeMonitor
echo Access:  http://localhost:8080
echo.
echo Commands:
echo   net start UptimeMonitor    - Start service
echo   net stop UptimeMonitor     - Stop service
echo   python main_service.py remove  - Remove service
echo.
pause
