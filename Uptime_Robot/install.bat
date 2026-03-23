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

echo Installing Python dependencies...
!PYTHON_CMD! -m pip install -r requirements.txt
if not %errorlevel%==0 (
    echo ERROR: Failed to install dependencies.
    if not "%SILENT%"=="1" pause
    exit /b 1
)

echo Installing pywin32 to system site-packages...
!PYTHON_CMD! -m pip install --upgrade --force-reinstall --no-user pywin32
if not %errorlevel%==0 (
    echo ERROR: Failed to install pywin32 in system site-packages.
    if not "%SILENT%"=="1" pause
    exit /b 1
)

echo Verifying pywin32 service modules...
!PYTHON_CMD! -c "import servicemanager, win32serviceutil; print(servicemanager.__file__)"
if not %errorlevel%==0 (
    echo ERROR: pywin32 modules are not available for service runtime.
    if not "%SILENT%"=="1" pause
    exit /b 1
)

echo Preparing pywin32 runtime files...
!PYTHON_CMD! -c "import os,sys,shutil,glob,site; ver=f'{sys.version_info.major}{sys.version_info.minor}'; candidates=[]; [candidates.extend(glob.glob(os.path.join(p,'pywin32_system32'))) for p in site.getsitepackages()+[site.getusersitepackages()]]; src=next((d for d in candidates if os.path.isdir(d)), None); assert src, 'pywin32_system32 not found'; dst=sys.base_prefix; files=[f'pythoncom{ver}.dll', f'pywintypes{ver}.dll']; [print('exists:', os.path.join(dst,f)) if os.path.exists(os.path.join(dst,f)) else (shutil.copy2(os.path.join(src,f), os.path.join(dst,f)), print('copied:', os.path.join(dst,f))) for f in files if os.path.exists(os.path.join(src,f))]; print('pywin32 runtime check complete:', dst)"
if not %errorlevel%==0 (
    echo ERROR: Failed to prepare pywin32 runtime files.
    if not "%SILENT%"=="1" pause
    exit /b 1
)

echo Saving port to config...
!PYTHON_CMD! -c "import config_manager as c; c.init_paths(); cfg=c.load_config(); cfg.setdefault('server', {})['port']=%PORT%; c.save_config(cfg)"
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
