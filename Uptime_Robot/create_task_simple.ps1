# Simple test - check admin rights and create task
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: Not running as Administrator!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Running as Administrator - OK" -ForegroundColor Green

$installPath = "D:\Project\Uptime_Robot\UptimeMonitor_EXE"
$vbsPath = "$installPath\UptimeMonitor.vbs"

Write-Host "Install path: $installPath"
Write-Host "VBS path: $vbsPath"

if (-not (Test-Path $vbsPath)) {
    Write-Host "ERROR: VBS file not found!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Creating scheduled task..." -ForegroundColor Yellow

try {
    $action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument "`"$vbsPath`"" -WorkingDirectory $installPath
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    
    Register-ScheduledTask -TaskName 'UptimeMonitor' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force -ErrorAction Stop
    
    Write-Host "Task created successfully!" -ForegroundColor Green
    
    Write-Host "Starting task..." -ForegroundColor Yellow
    Start-ScheduledTask -TaskName 'UptimeMonitor' -ErrorAction Stop
    
    Start-Sleep -Seconds 3
    
    $process = Get-Process | Where-Object {$_.ProcessName -like "*UptimeMonitor*"}
    if ($process) {
        Write-Host "SUCCESS! Process is running!" -ForegroundColor Green
        Write-Host "Access: http://localhost:8080" -ForegroundColor Cyan
    } else {
        Write-Host "WARNING: Process not found. Check logs." -ForegroundColor Yellow
    }
} catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
}

Read-Host "Press Enter to exit"
