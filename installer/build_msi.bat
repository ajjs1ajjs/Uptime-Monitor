@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo =========================================
echo    Build Uptime Monitor MSI Installer
echo =========================================
echo.

cd /d "%~dp0"

REM Додаємо WiX Toolset до PATH
set "WIX_PATH=C:\Program Files (x86)\WiX Toolset v3.14\bin"
set "PATH=%WIX_PATH%;%PATH%"

REM Перевірка WiX Toolset
echo Checking WiX Toolset installation...
where heat.exe >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: WiX Toolset not found!
    echo Please run: choco install wixtoolset
    echo.
    pause
    exit /b 1
)

echo WiX Toolset found!
echo.

REM Перевірка вихідних файлів
echo Checking source files...
if not exist "..\Uptime_Robot\main.py" (
    echo ERROR: main.py not found!
    pause
    exit /b 1
)

echo Source files OK!
echo.

REM Отримання версії
set VERSION=2.0.0
echo Version: %VERSION%
echo.

echo =========================================
echo    Compiling WiX files
echo =========================================
echo.

REM Компіляція
echo Compiling product.wxs...
candle.exe -out "product.wixobj" "product.wxs" -ext WixUIExtension

if errorlevel 1 (
    echo.
    echo ERROR: Compilation failed!
    pause
    exit /b 1
)

echo Compilation successful!
echo.

REM Лінкування
echo Linking to create MSI...
light.exe -out "UptimeMonitor-%VERSION%.msi" "product.wixobj" -ext WixUIExtension

if errorlevel 1 (
    echo.
    echo ERROR: Linking failed!
    pause
    exit /b 1
)

echo.
echo =========================================
echo    Build Complete!
echo =========================================
echo.
echo MSI Installer created: UptimeMonitor-%VERSION%.msi
echo.
for %%A in ("UptimeMonitor-%VERSION%.msi") do echo File size: %%~zA bytes
echo.
echo To install:
echo   msiexec /i UptimeMonitor-%VERSION%.msi
echo.
echo To uninstall:
echo   msiexec /x UptimeMonitor-%VERSION%.msi
echo.

REM Очищення
del product.wixobj 2>nul

pause
