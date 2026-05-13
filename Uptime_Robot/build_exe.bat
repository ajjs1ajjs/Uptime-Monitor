@echo off
chcp 65001 >nul
title Uptime Monitor - EXE Builder
echo =========================================
echo    Build UptimeMonitor EXE
echo =========================================
echo.

cd /d "%~dp0"

echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python 3.9 or higher
    pause
    exit /b 1
)

echo.
echo Installing dependencies from requirements.txt...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt
python -m pip install pyinstaller

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install packages!
    pause
    exit /b 1
)

echo.
echo Building EXE with PyInstaller...
if not exist "main.spec" (
    echo Creating PyInstaller spec...
    python -m PyInstaller --name UptimeMonitor ^
        --onefile --console ^
        --add-data "templates;templates" ^
        --add-data "static;static" ^
        --hidden-import uvicorn.logging ^
        --hidden-import uvicorn.loops.auto ^
        --hidden-import uvicorn.protocols.http.auto ^
        --hidden-import aiosqlite ^
        --hidden-import jinja2.ext ^
        --hidden-import cryptography.fernet ^
        --hidden-import bcrypt ^
        --collect-data jinja2 ^
        main.py
) else (
    python -m PyInstaller main.spec --clean
)

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo Copying files to UptimeMonitor_EXE folder...
if not exist "UptimeMonitor_EXE" mkdir "UptimeMonitor_EXE"

copy /Y "dist\UptimeMonitor.exe" "UptimeMonitor_EXE\UptimeMonitor.exe" >nul
copy /Y "icon.ico" "UptimeMonitor_EXE\icon.ico" >nul 2>&1 || echo [SKIP] icon.ico not found

echo 8080 > "UptimeMonitor_EXE\port.txt"

echo.
echo =========================================
echo    Build Complete!
echo =========================================
echo.
echo Files ready in: UptimeMonitor_EXE\
echo.
echo To install as Windows service:
echo   1. cd UptimeMonitor_EXE
echo   2. python main_service.py install
echo   3. net start UptimeMonitor
echo.
echo To run in console:
echo   UptimeMonitor.exe
echo.
echo Access: http://localhost:8080
echo.
pause
