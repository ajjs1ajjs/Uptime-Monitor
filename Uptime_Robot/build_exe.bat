@echo off
chcp 65001 >nul
echo =========================================
echo    Build UptimeMonitor EXE
echo =========================================
echo.

cd /d "%~dp0"

echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python 3.8 or higher
    pause
    exit /b 1
)

echo.
echo Installing required packages...
python -m pip install --upgrade pip
python -m pip install pyinstaller fastapi uvicorn aiohttp pydantic pywin32

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install packages!
    echo Make sure you have internet connection
    pause
    exit /b 1
)

echo.
echo Building EXE with PyInstaller...
python -m PyInstaller main.spec --clean

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo Copying files to UptimeMonitor_EXE folder...
if not exist "UptimeMonitor_EXE" mkdir "UptimeMonitor_EXE"

copy /Y "dist\UptimeMonitor.exe" "UptimeMonitor_EXE\UptimeMonitor.exe"
copy /Y "icon.ico" "UptimeMonitor_EXE\icon.ico"
copy /Y "ssl_checker.py" "UptimeMonitor_EXE\ssl_checker.py"

echo.
echo Creating default port.txt...
echo 8080 > "UptimeMonitor_EXE\port.txt"

echo.
echo =========================================
echo    Build Complete!
echo =========================================
echo.
echo Files ready in: UptimeMonitor_EXE\
echo.
echo To install:
echo   1. Open UptimeMonitor_EXE folder
echo   2. Run install_task.bat as Administrator
echo   3. Open http://localhost:8080
echo.
pause
