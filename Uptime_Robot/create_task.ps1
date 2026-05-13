# ============================================================================
# Uptime Monitor - Windows Scheduled Task Creator
# ============================================================================
# Creates a Windows scheduled task to run Uptime Monitor at startup.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File create_task.ps1
#
# For simple Python runner (no EXE), use:
#   powershell -ExecutionPolicy Bypass -File create_task.ps1 -UsePython
# ============================================================================

param(
    [switch]$UsePython,
    [string]$ProjectPath = "",
    [int]$Port = 8080
)

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: Not running as Administrator! Please run as Administrator." -ForegroundColor Red
    exit 1
}

if (-not $ProjectPath) {
    $ProjectPath = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$TaskName = "UptimeMonitor"

if ($UsePython) {
    # Run as Python module
    $pythonExe = "python"
    if (-not (Get-Command $pythonExe -ErrorAction SilentlyContinue)) {
        $pythonExe = "py -3"
    }
    $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c cd /d `"$ProjectPath`" && $pythonExe -m Uptime_Robot.main --host 0.0.0.0 --port $Port" -WorkingDirectory $ProjectPath
    Write-Host "Mode: Python script (uvicorn)" -ForegroundColor Cyan
} else {
    # Run as compiled EXE
    $exePath = Join-Path $ProjectPath "UptimeMonitor_EXE\UptimeMonitor.exe"
    if (-not (Test-Path $exePath)) {
        Write-Host "WARNING: $exePath not found." -ForegroundColor Yellow
        Write-Host "Falling back to Python mode..." -ForegroundColor Yellow
        $pythonExe = "python"
        $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c cd /d `"$ProjectPath`" && $pythonExe -m Uptime_Robot.main --host 0.0.0.0 --port $Port" -WorkingDirectory $ProjectPath
    } else {
        $action = New-ScheduledTaskAction -Execute $exePath -Argument "--port $Port" -WorkingDirectory (Split-Path $exePath -Parent)
    }
    Write-Host "Mode: Compiled EXE" -ForegroundColor Cyan
}

$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

try {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force -ErrorAction Stop
    Write-Host "Task '$TaskName' created successfully!" -ForegroundColor Green

    Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    Start-Sleep -Seconds 3

    Write-Host "Access: http://localhost:$Port" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Management commands:"
    Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
    Write-Host "  Stop-ScheduledTask -TaskName '$TaskName'"
    Write-Host "  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
} catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
    exit 1
}

Read-Host "Press Enter to exit"
