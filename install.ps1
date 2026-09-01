# Uptime Monitor (Go) - one-line installer/updater for Windows 10/11 & Server 2016+
# The SAME script installs on first run and safely UPDATES on subsequent runs:
#   - keeps config, database, users and admin password
#   - replaces only the binary and restarts the service
#
# Usage (PowerShell as Administrator):
#   irm https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.ps1 | iex
# or:
#   .\install.ps1 [-Version v1.2.3] [-SkipChecksum] [-AdminPassword 'YourPass']
#
# Environment variables (same as install.sh): UPTIME_MONITOR_VERSION,
# UPTIME_MONITOR_SKIP_CHECKSUM, UPTIME_MONITOR_ADMIN_PASSWORD,
# UPTIME_MONITOR_WRITE_PASSWORD_FILE.

[CmdletBinding()]
param(
    [string]$Version = $env:UPTIME_MONITOR_VERSION,
    [switch]$SkipChecksum,
    [string]$AdminPassword = $env:UPTIME_MONITOR_ADMIN_PASSWORD
)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Repo        = 'ajjs1ajjs/Uptime-Monitor'
$ServiceName = 'uptime-monitor'
$InstallDir  = "$env:ProgramFiles\uptime-monitor"
$DataDir     = "$env:ProgramData\uptime-monitor"
$ConfigFile  = "$DataDir\config.json"
$Binary      = Join-Path $InstallDir 'uptime-monitor.exe'
$PasswordFile = "$DataDir\admin_password.txt"

if (-not $Version) { $Version = 'latest' }
if ($SkipChecksum -or $env:UPTIME_MONITOR_SKIP_CHECKSUM -eq '1') { $SkipChecksum = $true }

# --- Admin check --------------------------------------------------------------
$identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Please run as Administrator (PowerShell -> Run as Administrator)" -ForegroundColor Red
    exit 1
}

# --- Detect existing installation ---------------------------------------------
$isUpdate = (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) -or (Test-Path $Binary) -or (Test-Path "$DataDir\sites.db") -or (Test-Path "$DataDir\data\sites.db")
$mode = if ($isUpdate) { 'Update' } else { 'Install' }

Write-Host "=============================================="
Write-Host "   Uptime Monitor - $mode"
Write-Host "=============================================="
Write-Host ""

$oldVersion = ""
if (Test-Path $Binary) {
    try { $oldVersion = (& $Binary --version 2>$null) } catch { $oldVersion = "" }
}

# --- Architecture --------------------------------------------------------------
$arch = switch ($env:PROCESSOR_ARCHITECTURE) {
    'AMD64' { 'amd64' }
    'ARM64' { 'arm64' }
    default {
        Write-Host "ERROR: unsupported architecture: $env:PROCESSOR_ARCHITECTURE" -ForegroundColor Red
        exit 1
    }
}
$binaryName = "uptime-monitor-windows-$arch.exe"

if ($Version -eq 'latest') {
    $downloadUrl = "https://github.com/$Repo/releases/latest/download/$binaryName"
    $checksumsUrl = "https://github.com/$Repo/releases/latest/download/checksums.txt"
} else {
    $downloadUrl = "https://github.com/$Repo/releases/download/$Version/$binaryName"
    $checksumsUrl = "https://github.com/$Repo/releases/download/$Version/checksums.txt"
}

function Get-RemoteFile([string]$url, [string]$out) {
    Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing
}

# --- Download -------------------------------------------------------------------
Write-Host "[1/4] Downloading Uptime Monitor $Version ($binaryName)..."
$tmpBin = Join-Path $env:TEMP "$binaryName"
try {
    Get-RemoteFile $downloadUrl $tmpBin
} catch {
    Write-Host "ERROR: download failed. Is release $Version published? ($_)" -ForegroundColor Red
    Remove-Item $tmpBin -ErrorAction SilentlyContinue
    exit 1
}

# --- Checksum (fail-closed: refuse to install an unverified binary) --------------
# Every release since checksums.txt was introduced publishes one; if it can't be
# fetched, doesn't contain this binary, we do NOT fall back to installing
# unverified. UPTIME_MONITOR_SKIP_CHECKSUM=1 / -SkipChecksum is an explicit,
# documented opt-out for air-gapped/legacy scenarios only.
Write-Host "Verifying checksum..."
if ($SkipChecksum) {
    Write-Host "WARNING: checksum verification explicitly skipped. Installing unverified binary." -ForegroundColor Yellow
} else {
    $tmpSum = Join-Path $env:TEMP 'um-checksums.txt'
    try {
        Get-RemoteFile $checksumsUrl $tmpSum
    } catch {
        Write-Host "ERROR: could not download checksums.txt from $checksumsUrl." -ForegroundColor Red
        Write-Host "Refusing to install an unverified binary. Re-run once GitHub is reachable,"
        Write-Host "or set `$env:UPTIME_MONITOR_SKIP_CHECKSUM=1` / pass -SkipChecksum to explicitly bypass verification."
        Remove-Item $tmpBin, $tmpSum -ErrorAction SilentlyContinue
        exit 1
    }
    $expected = (Select-String -Path $tmpSum -Pattern ([regex]::Escape($binaryName)) |
        Select-Object -First 1).Line -split '\s+' | Select-Object -First 1
    if (-not $expected) {
        Write-Host "ERROR: checksums.txt has no entry for $binaryName; refusing to install an unverified binary." -ForegroundColor Red
        Remove-Item $tmpBin, $tmpSum -ErrorAction SilentlyContinue
        exit 1
    }
    $actual = (Get-FileHash -Algorithm SHA256 $tmpBin).Hash.ToLower()
    if ($expected.ToLower() -ne $actual) {
        Write-Host "ERROR: checksum mismatch for ${binaryName}. Expected $expected, got $actual." -ForegroundColor Red
        Remove-Item $tmpBin, $tmpSum -ErrorAction SilentlyContinue
        exit 1
    }
    Write-Host "Checksum OK."
    Remove-Item $tmpSum -ErrorAction SilentlyContinue
}

# --- Stop service before replacing binary ----------------------------------------
$hadService = [bool](Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)
if ($hadService) {
    Write-Host "Stopping service $ServiceName..."
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    # wait up to 15s for the process to release the exe file
    for ($i = 0; $i -lt 15 -and (Get-Process uptime-monitor -ErrorAction SilentlyContinue); $i++) {
        Start-Sleep -Seconds 1
    }
}

# --- Install binary ---------------------------------------------------------------
Write-Host "[2/4] Installing binary..."
New-Item -ItemType Directory -Force -Path $InstallDir, $DataDir, "$DataDir\logs", "$DataDir\data", "$DataDir\backups" | Out-Null
if ($isUpdate -and (Test-Path $Binary)) {
    Copy-Item $Binary "$Binary.old" -Force
}
Move-Item $tmpBin $Binary -Force
# verify the installed file is a runnable executable
& $Binary --version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: installed binary is not runnable. Restoring previous version..." -ForegroundColor Red
    if (Test-Path "$Binary.old") { Move-Item "$Binary.old" $Binary -Force }
    exit 1
}
$newVersion = (& $Binary --version 2>$null)

# --- Config (kept on update, created on first install) ----------------------------
if (-not (Test-Path $ConfigFile)) {
    Write-Host "Creating default config at $ConfigFile ..."
    @{
        server         = @{ port = 8080; host = '0.0.0.0'; trusted_proxies = @(); allow_localhost = $false; allow_private_networks = $false }
        data_dir       = "$DataDir\data"
        log_dir        = "$DataDir\logs"
        check_interval = 60
        alert_policy   = @{
            request_timeout_seconds           = 15
            grace_period_seconds              = 0
            up_success_threshold              = 3
            still_down_repeat_seconds         = 600
            treat_4xx_as_down                 = $true
            verify_ssl                        = $true
            ssl_notification_days             = @(30, 14, 7, 5, 3, 1)
            ssl_notification_cooldown_seconds = 21600
            ssl_check_interval_hours          = 6
            retry_delays                      = @(10, 10, 10, 10, 10)
            max_retries                       = 5
        }
        backup         = @{ enabled = $true; max_backups = 10; backup_dir = "$DataDir\backups" }
    } | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $ConfigFile
}

# --- Service ------------------------------------------------------------------------
Write-Host "[3/4] Configuring Windows service..."
$binArgs = "`"$Binary`" server --config `"$ConfigFile`""
$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $svc) {
    New-Service -Name $ServiceName -BinaryPathName $binArgs `
        -DisplayName 'Uptime Monitor' -Description 'Enterprise uptime & SSL monitoring' `
        -StartupType Automatic | Out-Null
} else {
    # refresh the binary path in case the install dir changed
    sc.exe config $ServiceName binPath= $binArgs | Out-Null
    Set-Service -Name $ServiceName -StartupType Automatic
}
# auto-restart on failure (equivalent of Restart=always in the systemd unit)
sc.exe failure $ServiceName reset= 86400 actions= restart/5000/restart/5000/restart/5000 | Out-Null

# restrict ACLs: SYSTEM and Administrators only on data dir
icacls $DataDir /inheritance:r /grant:r 'SYSTEM:(OI)(CI)F' 'Administrators:(OI)(CI)F' | Out-Null

# --- Admin password (fresh install only, unless AdminPassword/env var provided) -----
# The binary itself never writes admin_password.txt (the password is shown on
# stdout once); remove leftovers from older versions unless opted in below.
if (-not $env:UPTIME_MONITOR_WRITE_PASSWORD_FILE) {
    Remove-Item $PasswordFile -ErrorAction SilentlyContinue
}
$adminSet = $false
if (-not $isUpdate -or $AdminPassword) {
    $env:DB_PATH = "$DataDir\data\sites.db"
    $hasAdmin = (& $Binary has-admin --config $ConfigFile 2>$null) -eq 'yes'
    if (-not $hasAdmin -or $AdminPassword) {
        if (-not $AdminPassword) {
            $chars = (48..57) + (65..90) + (97..122)
            $AdminPassword = -join (1..18 | ForEach-Object { [char](Get-Random -InputObject $chars) })
        }
        $env:UPTIME_MONITOR_ADMIN_PASSWORD = $AdminPassword
        & $Binary reset-admin --config $ConfigFile | Out-Null
        Remove-Item Env:\UPTIME_MONITOR_ADMIN_PASSWORD -ErrorAction SilentlyContinue
        if ($env:UPTIME_MONITOR_WRITE_PASSWORD_FILE) {
            Set-Content -Encoding UTF8 -Path $PasswordFile -Value $AdminPassword
            Write-Host "Пароль збережено: $PasswordFile (видаліть після входу)"
        }
        $adminSet = $true
    }
    Remove-Item Env:\DB_PATH -ErrorAction SilentlyContinue
}

Start-Service -Name $ServiceName

# --- Health check ---------------------------------------------------------------------
Write-Host -NoNewline "Waiting for the service to become healthy..."
$healthy = $false
foreach ($i in 1..15) {
    try {
        Invoke-WebRequest -Uri 'http://localhost:8080/health' -UseBasicParsing -TimeoutSec 2 | Out-Null
        Write-Host " OK"; $healthy = $true; break
    } catch {
        Write-Host -NoNewline "."; Start-Sleep -Seconds 1
    }
}
if (-not $healthy) { Write-Host " FAILED" }

# --- Summary ---------------------------------------------------------------------------
Write-Host "[4/4] Done."
Write-Host ""
if ($isUpdate) {
    Write-Host "Uptime Monitor updated successfully."
    if ($oldVersion) { Write-Host "  Version: $oldVersion -> $newVersion" }
    Write-Host "  Config, database and users were preserved."
    if (Test-Path "$Binary.old") { Write-Host "  Previous binary kept at: $Binary.old" }
} else {
    Write-Host "Uptime Monitor installed successfully."
    Write-Host "  Config:   $ConfigFile"
    Write-Host "  Database: $DataDir\data\sites.db"
}
Write-Host ""
Write-Host "Dashboard: http://localhost:8080/"
Write-Host ""
if ($adminSet) {
    Write-Host "===================================="
    Write-Host "  Логін:    admin"
    Write-Host "  Пароль:   $AdminPassword"
    Write-Host "===================================="
    Write-Host "При вході система попросить змінити пароль."
    Write-Host "Пароль більше не зберігається на диску — запишіть його."
} else {
    Write-Host "Існуючі облікові дані збережено (пароль не змінювався)."
    Write-Host "Якщо треба скинути пароль адміна:"
    Write-Host "  `$env:UPTIME_MONITOR_ADMIN_PASSWORD='YourStrongPass123'; & '$Binary' reset-admin --config '$ConfigFile'"
    Write-Host "  Restart-Service $ServiceName"
}
Write-Host ""
Write-Host "Installed version: $newVersion"
