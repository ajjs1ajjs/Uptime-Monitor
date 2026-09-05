# Uptime Monitor (Go) - one-line installer/updater (Windows)
# The SAME command installs on first run and safely UPDATES on subsequent runs:
#   - keeps config, database, users and admin password
#   - replaces only the binary and restarts the service
# Usage (run as Administrator):
#   irm https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.ps1 | iex
# Or download and run:
#   Invoke-WebRequest -Uri "https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.ps1" -OutFile install.ps1
#   .\install.ps1

param(
    [string]$Version = "latest",
    [string]$InstallDir = "$env:LOCALAPPDATA\Uptime-Monitor",
    [string]$ConfigDir = "$env:APPDATA\Uptime-Monitor",
    [string]$DataDir = "$env:LOCALAPPDATA\Uptime-Monitor\data",
    [string]$ServiceName = "UptimeMonitor",
    [string]$AdminPassword = "",
    [switch]$SkipChecksum
)

$ErrorActionPreference = "Stop"
$Repo = "ajjs1ajjs/Uptime-Monitor"
$BinaryName = "uptime-monitor-windows-amd64.exe"

function Get-Checksum {
    param([string]$FilePath, [string]$Algorithm = "SHA256")
    using ($hash = [System.Security.Cryptography.HashAlgorithm]::Create($Algorithm)) {
        $stream = [System.IO.File]::OpenRead($FilePath)
        $bytes = $hash.ComputeHash($stream)
        $stream.Close()
        return [BitConverter]::ToString($bytes).Replace("-", "").ToLowerInvariant()
    }
}

function Get-Architecture {
    $arch = $env:PROCESSOR_ARCHITECTURE
    if ($arch -eq "AMD64") { return "amd64" }
    if ($arch -eq "ARM64") { return "arm64" }
    throw "Unsupported architecture: $arch"
}

$arch = Get-Architecture
$BinaryName = "uptime-monitor-windows-$arch.exe"
$ServiceBinary = "$InstallDir\uptime-monitor.exe"

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "   Uptime Monitor - Встановлення/Оновлення" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

$isUpdate = Test-Path $ServiceBinary
$mode = if ($isUpdate) { "Оновлення (update)" } else { "Встановлення (install)" }
Write-Host "[INFO] Mode: $mode" -ForegroundColor Yellow

if ($Version -eq "latest") {
    $DownloadUrl = "https://github.com/$Repo/releases/latest/download/$BinaryName"
    $VersionUrl = "latest/download/"
} else {
    $DownloadUrl = "https://github.com/$Repo/releases/download/$Version/$BinaryName"
    $VersionUrl = "download/$Version/"
}

Write-Host "[1/5] Downloading Uptime Monitor $Version ($BinaryName)..." -ForegroundColor Green
$TempBinary = "$env:TEMP\$([guid]::NewGuid().ToString()).exe"

try {
    $ProgressPreference = "SilentlyContinue"
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $TempBinary -UserAgent "Wget"
} catch {
    Write-Host "[ERROR] Download failed. Is release $Version published?" -ForegroundColor Red
    throw
}

if (-not $SkipChecksum) {
    Write-Host "[2/5] Verifying checksum..." -ForegroundColor Green
    $ChecksumsUrl = "https://github.com/$Repo/releases/${VersionUrl}checksums.txt"
    $TempSum = "$env:TEMP\sums.txt"

    try {
        Invoke-WebRequest -Uri $ChecksumsUrl -OutFile $TempSum -UserAgent "Wget"
    } catch {
        Write-Host "[ERROR] Could not download checksums.txt" -ForegroundColor Red
        throw
    }

    $sumsContent = Get-Content $TempSum -Raw
    $expectedLine = $sumsContent -split "`n" | Where-Object { $_ -match "$BinaryName`$" }
    if (-not $expectedLine) {
        Write-Host "[ERROR] checksums.txt has no entry for $BinaryName" -ForegroundColor Red
        throw "Checksum entry not found"
    }
    $expected = ($expectedLine -split "\s+")[0]
    $actual = Get-Checksum -FilePath $TempBinary

    if ($expected -ne $actual) {
        Write-Host "[ERROR] Checksum mismatch. Expected $expected, got $actual" -ForegroundColor Red
        throw "Checksum mismatch"
    }
    Write-Host "[OK] Checksum OK" -ForegroundColor Green
    Remove-Item $TempSum -Force -EA SilentlyContinue
}

$newVersion = & $TempBinary --version 2>$null
Write-Host "[OK] Downloaded binary version: $newVersion" -ForegroundColor Green

Write-Host "[3/5] Installing binary..." -ForegroundColor Green
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}
if (-not (Test-Path $ConfigDir)) {
    New-Item -ItemType Directory -Path $ConfigDir -Force | Out-Null
}
if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
}

if ($isUpdate) {
    Copy-Item $ServiceBinary "$InstallDir\uptime-monitor.old.exe" -Force -EA SilentlyContinue
}
Copy-Item $TempBinary $ServiceBinary -Force
Remove-Item $TempBinary -Force -EA SilentlyContinue

$configFile = "$ConfigDir\config.json"
if (-not (Test-Path $configFile)) {
    Write-Host "[INFO] Creating default config..." -ForegroundColor Yellow
    @{
        server = @{
            port = 8080
            host = "0.0.0.0"
            trusted_proxies = @()
            allow_localhost = $false
            allow_private_networks = $false
        }
        data_dir = $DataDir
        check_interval = 60
        alert_policy = @{
            request_timeout_seconds = 15
            grace_period_seconds = 0
            up_success_threshold = 3
            still_down_repeat_seconds = 600
            treat_4xx_as_down = $true
            verify_ssl = $true
            ssl_notification_days = @(30, 14, 7, 5, 3, 1)
            ssl_notification_cooldown_seconds = 21600
            ssl_check_interval_hours = 6
            retry_delays = @(10, 10, 10, 10, 10)
            max_retries = 5
        }
        backup = @{
            enabled = $true
            max_backups = 10
            backup_dir = "$DataDir\backups"
        }
    } | ConvertTo-Json -Depth 10 | Set-Content $configFile -Encoding UTF8
}

Write-Host "[4/5] Configuring service..." -ForegroundColor Green
$serviceExists = Get-Service -Name $ServiceName -EA SilentlyContinue

if ($serviceExists) {
    Stop-Service -Name $ServiceName -Force -EA SilentlyContinue
    Write-Host "[INFO] Stopped existing service" -ForegroundColor Yellow
}

$exePath = $ServiceBinary
$ps1Path = "$InstallDir\run.ps1"
$wrapperScript = @"
`$env:DATA_DIR = "$DataDir"
`$env:CONFIG_PATH = "$configFile"
`$env:DB_PATH = "$DataDir\sites.db"
`$env:LOG_DIR = "$InstallDir\logs"
& "$exePath" server --config "$configFile"
"@
$wrapperScript | Set-Content $ps1Path -Encoding UTF8

$serviceDisplayName = "Uptime Monitor"
$description = "Website uptime monitoring service"

if ($serviceExists) {
    Write-Host "[INFO] Updating existing service..." -ForegroundColor Yellow
} else {
    Write-Host "[INFO] Creating Windows service..." -ForegroundColor Yellow
    $scCmd = "sc.exe"
    $createArgs = "create $ServiceName binPath= `"powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"`"$ps1Path`"`"`" DisplayName= `"$serviceDisplayName`" start= auto"
    & $scCmd $createArgs.Split(' ') | Out-Null
    & $scCmd description $ServiceName $description | Out-Null
    & $scCmd failure $ServiceName reset= 86400 actions= restart/60000/restart/60000/restart/60000 | Out-Null
}

Start-Service -Name $ServiceName -EA SilentlyContinue
Write-Host "[OK] Service started" -ForegroundColor Green

Write-Host "[5/5] Health check..." -ForegroundColor Green
$maxWait = 15
for ($i = 0; $i -lt $maxWait; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8080/health" -TimeoutSec 2 -UseBasicParsing -EA SilentlyContinue
        if ($resp.StatusCode -eq 200) {
            Write-Host "[OK] Service is healthy" -ForegroundColor Green
            break
        }
    } catch {}
    if ($i -eq $maxWait - 1) {
        Write-Host "[WARN] Service may not be ready yet" -ForegroundColor Yellow
    }
    Start-Sleep 1
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "   Uptime Monitor $mode complete!" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Binary:   $ServiceBinary"
Write-Host "Config:   $configFile"
Write-Host "Database: $DataDir\sites.db"
Write-Host ""
Write-Host "Dashboard: http://localhost:8080/"
Write-Host ""
Write-Host "Admin login: admin"
if ($AdminPassword) {
    Write-Host "Admin password: $AdminPassword (set as requested)" -ForegroundColor Yellow
} elseif (-not $isUpdate) {
    Write-Host "(Admin password was auto-generated - check Windows Event Log or first login)"
}
Write-Host ""
