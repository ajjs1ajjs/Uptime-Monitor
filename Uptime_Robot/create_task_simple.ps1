# ============================================================================
# Uptime Monitor - Quick Windows Service Runner
# ============================================================================
# Simplified version: installs as Windows service via main_service.py
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File create_task_simple.ps1
# ============================================================================

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: Not running as Administrator!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Running as Administrator - OK" -ForegroundColor Green

$ProjectPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "Project path: $ProjectPath" -ForegroundColor Cyan

Write-Host ""
Write-Host "Choose installation method:" -ForegroundColor Yellow
Write-Host "  1. Windows Service (recommended) - runs via main_service.py"
Write-Host "  2. Scheduled Task - runs at startup via cmd.exe"
$choice = Read-Host "Enter choice (1 or 2)"

if ($choice -eq "1") {
    # Method 1: Windows Service
    Write-Host ""
    Write-Host "Installing Windows Service..." -ForegroundColor Yellow

    # Ensure dependencies
    python -m pip install -r "$ProjectPath\requirements.txt" -q 2>$null

    # Install service
    python "$ProjectPath\main_service.py" install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Service installation failed!" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }

    # Configure and start
    sc.exe config UptimeMonitor start= auto
    net start UptimeMonitor

    Write-Host ""
    Write-Host "SUCCESS! Uptime Monitor is running as Windows Service." -ForegroundColor Green
    Write-Host "Access: http://localhost:8080" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Management commands:" -ForegroundColor White
    Write-Host "  net start UptimeMonitor"
    Write-Host "  net stop UptimeMonitor"
    Write-Host "  python main_service.py remove"
}

else {
    # Method 2: Scheduled Task
    Write-Host ""
    Write-Host "Creating Scheduled Task..." -ForegroundColor Yellow

    $pythonExe = "python"
    if (-not (Get-Command $pythonExe -ErrorAction SilentlyContinue)) {
        $pythonExe = "py -3"
    }

    $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c cd /d `"$ProjectPath`" && $pythonExe -m Uptime_Robot.main --host 0.0.0.0 --port 8080" -WorkingDirectory $ProjectPath
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

    try {
        Register-ScheduledTask -TaskName 'UptimeMonitor' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force -ErrorAction Stop
        Write-Host "Task created successfully!" -ForegroundColor Green

        Write-Host "Starting task..." -ForegroundColor Yellow
        Start-ScheduledTask -TaskName 'UptimeMonitor' -ErrorAction Stop
        Start-Sleep -Seconds 3

        Write-Host "SUCCESS! Uptime Monitor is running." -ForegroundColor Green
        Write-Host "Access: http://localhost:8080" -ForegroundColor Cyan
    } catch {
        Write-Host "ERROR: $_" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}

Read-Host "Press Enter to exit"
