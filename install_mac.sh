#!/bin/bash
# Uptime Monitor (Go) - one-line installer/updater (macOS)
# The SAME command installs on first run and safely UPDATES on subsequent runs:
#   - keeps config, database, users and admin password
#   - replaces only the binary and restarts the service
# Usage: curl -sSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash

set -e

INSTALL_DIR="/opt/homebrew/opt/uptime-monitor"
CONFIG_DIR="/etc/uptime-monitor"
DATA_DIR="/var/lib/uptime-monitor"
LOG_DIR="/var/log/uptime-monitor"
SERVICE_NAME="com.uptime-monitor.plist"
UM_VERSION="${UPTIME_MONITOR_VERSION:-latest}"
REPO="ajjs1ajjs/Uptime-Monitor"
CONFIG_FILE="$CONFIG_DIR/config.json"

if [ "$(uname)" != "Darwin" ]; then
    echo "ERROR: This installer is for macOS only. Detected: $(uname)"
    exit 1
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "Please run as root (sudo ./install.sh)"
    exit 1
fi

echo "=============================================="
echo "   Uptime Monitor - Встановлення/Оновлення"
echo "=============================================="
echo ""

OLD_VERSION=""
if [ -x "$INSTALL_DIR/uptime-monitor" ] && [ ! -d "$INSTALL_DIR/uptime-monitor" ]; then
    OLD_VERSION="$("$INSTALL_DIR/uptime-monitor" --version 2>/dev/null || true)"
fi

IS_UPDATE=0
if [ -f "/Library/LaunchDaemons/$SERVICE_NAME" ] || [ -x "$INSTALL_DIR/uptime-monitor" ] || [ -f "$DATA_DIR/sites.db" ]; then
    IS_UPDATE=1
fi
if [ "$IS_UPDATE" = "1" ]; then MODE="Оновлення (update)"; else MODE="Встановлення (install)"; fi
echo "[INFO] Mode: $MODE"

case "$(uname -m)" in
    x86_64|amd64)  ARCH="amd64" ;;
    aarch64|arm64) ARCH="arm64" ;;
    *)
        echo "ERROR: unsupported architecture: $(uname -m)"
        exit 1
        ;;
esac
BINARY_NAME="uptime-monitor-darwin-${ARCH}"

if [ "$UM_VERSION" = "latest" ]; then
    DOWNLOAD_URL="https://github.com/${REPO}/releases/latest/download/${BINARY_NAME}"
    VERSION_URL="latest/download/"
else
    DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${UM_VERSION}/${BINARY_NAME}"
    VERSION_URL="download/${UM_VERSION}/"
fi

echo "[1/5] Downloading Uptime Monitor ${UM_VERSION} (${BINARY_NAME})..."
TMP_BIN="$(mktemp)"
if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$DOWNLOAD_URL" -o "$TMP_BIN" || { echo "ERROR: download failed. Is release ${UM_VERSION} published?"; rm -f "$TMP_BIN"; exit 1; }
elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$TMP_BIN" "$DOWNLOAD_URL" || { echo "ERROR: download failed. Is release ${UM_VERSION} published?"; rm -f "$TMP_BIN"; exit 1; }
else
    echo "ERROR: neither curl nor wget is installed."
    rm -f "$TMP_BIN"
    exit 1
fi

echo "[2/5] Verifying checksum..."
if [ "$UPTIME_MONITOR_SKIP_CHECKSUM" = "1" ]; then
    echo "WARNING: checksum verification explicitly skipped."
else
    CHECKSUMS_URL="https://github.com/${REPO}/releases/${VERSION_URL}checksums.txt"
    TMP_SUM="$(mktemp)"
    DL_OK=0
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$CHECKSUMS_URL" -o "$TMP_SUM" && DL_OK=1
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O "$TMP_SUM" "$CHECKSUMS_URL" && DL_OK=1
    fi
    if [ "$DL_OK" != "1" ] || [ ! -s "$TMP_SUM" ]; then
        echo "ERROR: could not download checksums.txt"
        rm -f "$TMP_BIN" "$TMP_SUM"
        exit 1
    fi
    EXPECTED="$(grep "${BINARY_NAME}$" "$TMP_SUM" | awk '{print $1}')"
    if [ -z "$EXPECTED" ]; then
        echo "ERROR: checksums.txt has no entry for ${BINARY_NAME}"
        rm -f "$TMP_BIN" "$TMP_SUM"
        exit 1
    fi
    if command -v shasum >/dev/null 2>&1; then
        ACTUAL="$(shasum -a 256 "$TMP_BIN" | awk '{print $1}')"
    elif command -v sha256sum >/dev/null 2>&1; then
        ACTUAL="$(sha256sum "$TMP_BIN" | awk '{print $1}')"
    else
        echo "ERROR: neither shasum nor sha256sum is installed"
        rm -f "$TMP_BIN" "$TMP_SUM"
        exit 1
    fi
    if [ "$EXPECTED" != "$ACTUAL" ]; then
        echo "ERROR: checksum mismatch. Expected ${EXPECTED}, got ${ACTUAL}."
        rm -f "$TMP_BIN" "$TMP_SUM"
        exit 1
    fi
    echo "[OK] Checksum OK"
    rm -f "$TMP_SUM"
fi

chmod +x "$TMP_BIN"
NEW_VERSION="$("$TMP_BIN" --version 2>/dev/null || echo "?")"

echo "[3/5] Installing binary..."
mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$DATA_DIR" "$LOG_DIR"
if [ -d "$INSTALL_DIR/uptime-monitor" ]; then rm -rf "$INSTALL_DIR/uptime-monitor"; fi
if [ "$IS_UPDATE" = "1" ] && [ -f "$INSTALL_DIR/uptime-monitor" ]; then
    cp -f "$INSTALL_DIR/uptime-monitor" "$INSTALL_DIR/uptime-monitor.old" 2>/dev/null || true
fi
install -m 0755 "$TMP_BIN" "$INSTALL_DIR/uptime-monitor"
rm -f "$TMP_BIN"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "[INFO] Creating default config..."
    cat > "$CONFIG_FILE" <<EOF
{
  "server": {
    "port": 8080,
    "host": "0.0.0.0",
    "trusted_proxies": [],
    "allow_localhost": false,
    "allow_private_networks": false
  },
  "data_dir": "$DATA_DIR",
  "log_dir": "$LOG_DIR",
  "check_interval": 60,
  "alert_policy": {
    "request_timeout_seconds": 15,
    "grace_period_seconds": 0,
    "up_success_threshold": 3,
    "still_down_repeat_seconds": 600,
    "treat_4xx_as_down": true,
    "verify_ssl": true,
    "ssl_notification_days": [30, 14, 7, 5, 3, 1],
    "ssl_notification_cooldown_seconds": 21600,
    "ssl_check_interval_hours": 6,
    "retry_delays": [10, 10, 10, 10, 10],
    "max_retries": 5
  },
  "backup": {
    "enabled": true,
    "max_backups": 10,
    "backup_dir": "$DATA_DIR/backups"
  }
}
EOF
fi

echo "[4/5] Configuring launchd service..."
if [ -f "/Library/LaunchDaemons/$SERVICE_NAME" ]; then
    launchctl unload "/Library/LaunchDaemons/$SERVICE_NAME" 2>/dev/null || true
fi

cat > "/Library/LaunchDaemons/$SERVICE_NAME" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.uptime-monitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>$INSTALL_DIR/uptime-monitor</string>
        <string>server</string>
        <string>--config</string>
        <string>$CONFIG_FILE</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>DATA_DIR</key>
        <string>$DATA_DIR</string>
        <key>DB_PATH</key>
        <string>$DATA_DIR/sites.db</string>
        <key>LOG_DIR</key>
        <string>$LOG_DIR</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/stderr.log</string>
    <key>HardResourceLimits</key>
    <dict>
        <key>NumberOfFiles</key>
        <integer>1024</integer>
    </dict>
</dict>
</plist>
EOF

chown -R root:wheel "/Library/LaunchDaemons/$SERVICE_NAME"
chmod 644 "/Library/LaunchDaemons/$SERVICE_NAME"
launchctl load "/Library/LaunchDaemons/$SERVICE_NAME"

echo "[5/5] Health check..."
for i in $(seq 1 15); do
    if curl -fsS "http://localhost:8080/health" >/dev/null 2>&1; then
        echo "[OK] Service is healthy"
        break
    fi
    if [ "$i" = "15" ]; then
        echo "[WARN] Service may not be ready yet"
    else
        sleep 1
    fi
done

echo ""
echo "=============================================="
echo "   Uptime Monitor $MODE complete!"
echo "=============================================="
echo ""
echo "Binary:   $INSTALL_DIR/uptime-monitor"
echo "Config:   $CONFIG_FILE"
echo "Database: $DATA_DIR/sites.db"
echo ""
echo "Dashboard: http://localhost:8080/"
echo ""
echo "Admin login: admin"
echo "(Admin password was auto-generated on first run)"
echo ""
