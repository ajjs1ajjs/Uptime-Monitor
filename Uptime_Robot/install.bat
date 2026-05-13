@echo off
setlocal enabledelayedexpansion
set SILENT=0
if "%~1"=="/y" set SILENT=1

echo ========================================
echo   Uptime Monitor - Installation
echo ========================================
echo.

net session >nul 2>&1
if not %errorlevel%==0 (
    echo ERROR: Run this script as Administrator.
    if not "%SILENT%"=="1" pause
    exit /b 1
)

set PYTHON_CMD=python
!PYTHON_CMD! --version >nul 2>&1
if not %errorlevel%==0 (
    set PYTHON_CMD=py -3
    !PYTHON_CMD! --version >nul 2>&1
    if not !errorlevel!==0 (
        set PYTHON_CMD=py
        !PYTHON_CMD! --version >nul 2>&1
        if not !errorlevel!==0 (
            echo ERROR: Python not found. 
            set /p USER_PYTHON="Please enter the full path to python.exe (e.g. C:\Python39\python.exe): "
            if "!USER_PYTHON!"=="" (
                echo ERROR: No Python path provided.
                if not "%SILENT%"=="1" pause
                exit /b 1
            )
            set PYTHON_CMD="!USER_PYTHON!"
            !PYTHON_CMD! --version >nul 2>&1
            if not !errorlevel!==0 (
                echo ERROR: The provided path is not a valid Python executable.
                if not "%SILENT%"=="1" pause
                exit /b 1
            )
        )
    )
)

if "%SILENT%"=="1" (
    set PORT=8080
) else (
    set /p PORT="Enter port (default 8080): "
)
if "!PORT!"=="" set PORT=8080

echo.
echo Installing Uptime Monitor on port %PORT%...
echo.

cd /d "%~dp0"

echo Ensuring pip is installed...
!PYTHON_CMD! -m ensurepip --default-pip >nul 2>&1

echo Installing Python dependencies (includes: fastapi, aiohttp, bcrypt, cryptography, jinja2, aiosqlite, pywin32)...
!PYTHON_CMD! -m pip install -r requirements.txt
if not %errorlevel%==0 (
    echo ERROR: Failed to install dependencies.
    if not "%SILENT%"=="1" pause
    exit /b 1
)

echo Installing pywin32 to system site-packages (required for Windows service)...
!PYTHON_CMD! -m pip install --upgrade --force-reinstall --no-user pywin32 2>nul
if not %errorlevel%==0 (
    echo WARNING: pywin32 system install failed. Service may not start automatically.
)

echo Verifying pywin32 service modules...
!PYTHON_CMD! -c "import servicemanager, win32serviceutil; print('pywin32 OK:', servicemanager.__file__)"
if not %errorlevel%==0 (
    echo WARNING: pywin32 modules not found. Please reinstall: python -m pip install --force-reinstall pywin32
)

echo Preparing pywin32 runtime files (DLLs)...
!PYTHON_CMD! -c "
import os, sys, shutil, glob, site
ver = f'{sys.version_info.major}{sys.version_info.minor}'
src = None
for p in site.getsitepackages() + [site.getusersitepackages()]:
    d = os.path.join(p, 'pywin32_system32')
    if os.path.isdir(d): src = d; break
if src:
    for f in [f'pythoncom{ver}.dll', f'pywintypes{ver}.dll']:
        sf = os.path.join(src, f)
        if os.path.exists(sf):
            df = os.path.join(sys.base_prefix, f)
            if not os.path.exists(df): shutil.copy2(sf, df); print('copied:', f)
            else: print('exists:', f)
    print('pywin32 DLLs OK')
else:
    print('pywin32_system32 dir not found — service may still work via PATH')
" 2>nul

echo Initializing crypto...
!PYTHON_CMD! -c "from crypto_utils import generate_master_key; k=generate_master_key(); print('Master key:', 'generated' if k else 'skipped')" 2>nul || echo [SKIP] crypto_utils not available

echo Saving port to config...
!PYTHON_CMD! -c "import config_manager as c; cfg=c.load_config(); cfg.setdefault('server', {})['port']=%PORT%; c.save_config(cfg)"
if not %errorlevel%==0 (
    echo ERROR: Failed to update config.
    if not "%SILENT%"=="1" pause
    exit /b 1
)

echo Installing Windows service...
!PYTHON_CMD! main_service.py install
if not %errorlevel%==0 (
    echo ERROR: Service installation failed.
    if not "%SILENT%"=="1" pause
    exit /b 1
)

sc config UptimeMonitor start= auto
net start UptimeMonitor

echo.
echo ========================================
echo   Installation complete!
echo ========================================
echo.
echo Service: UptimeMonitor
echo Port: %PORT%
echo.
echo To manage service:
echo   net stop UptimeMonitor
echo   net start UptimeMonitor
echo   sc delete UptimeMonitor
echo.
echo To access: http://localhost:%PORT%
echo.

if not "%SILENT%"=="1" pause
