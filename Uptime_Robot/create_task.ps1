# Create UptimeMonitor Scheduled Task
$installPath = "D:\Project\Uptime_Robot\UptimeMonitor_EXE"
$vbsPath = "$installPath\UptimeMonitor.vbs"

$action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument "`"$vbsPath`"" -WorkingDirectory $installPath
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName 'UptimeMonitor' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force

Write-Host "Task created successfully!" -ForegroundColor Green
Write-Host "Starting task..."
Start-ScheduledTask -TaskName 'UptimeMonitor'
Start-Sleep -Seconds 3

$process = Get-Process | Where-Object {$_.ProcessName -like "*UptimeMonitor*"}
if ($process) {
    Write-Host "Process is running!" -ForegroundColor Green
    Write-Host "Access: http://localhost:8080"
} else {
    Write-Host "Process not found. Check logs." -ForegroundColor Red
}

Read-Host "Press Enter to exit"
