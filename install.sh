#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
GITHUB_REPO="ajjs1ajjs/Uptime-Monitor"
INSTALL_DIR="/opt/uptime-monitor"
CONFIG_DIR="/etc/uptime-monitor"
DATA_DIR="/var/lib/uptime-monitor"
LOG_DIR="/var/log/uptime-monitor"
SERVICE_NAME="uptime-monitor"
APP_USER="uptime-monitor"
APP_VERSION="v1.1.0"

echo -e "${GREEN}"
echo "=========================================="
echo "   Uptime Monitor - Installation Script"
echo "=========================================="
echo -e "${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run as root (use sudo)${NC}"
    exit 1
fi

# Parse arguments
PORT=8080
INSTALL_VERSION="main"

while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            PORT="$2"
            shift 2
            ;;
        --version)
            INSTALL_VERSION="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --port PORT       Set port (default: 8080)"
            echo "  --version VERSION Install specific version (e.g., v1.0.0 or main)"
            echo "  --help            Show this help message"
            exit 0
            ;;
        --local)
            LOCAL_INSTALL=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Determine download URL based on version
if [[ "$INSTALL_VERSION" == "main" ]]; then
    DOWNLOAD_URL="https://github.com/$GITHUB_REPO/archive/refs/heads/main.tar.gz"
    APP_VERSION="latest (main branch)"
elif [[ "$INSTALL_VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    DOWNLOAD_URL="https://github.com/$GITHUB_REPO/archive/refs/tags/$INSTALL_VERSION.tar.gz"
    APP_VERSION="$INSTALL_VERSION"
else
    echo -e "${RED}Error: Invalid version format. Use 'main' or 'v1.0.0' format${NC}"
    exit 1
fi

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_NAME=$NAME
    OS_VERSION=$VERSION_ID
else
    echo -e "${RED}Error: Cannot detect OS${NC}"
    exit 1
fi

echo -e "${YELLOW}Detected OS: $OS_NAME $OS_VERSION${NC}"

# Check Python version
PYTHON_CMD=""
if command -v python3.12 &> /dev/null; then
    PYTHON_CMD="python3.12"
elif command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
elif command -v python3.10 &> /dev/null; then
    PYTHON_CMD="python3.10"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    echo -e "${RED}Error: Python 3.10+ is required${NC}"
    exit 1
fi

PYTHON_VER=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
echo -e "${YELLOW}Using Python: $PYTHON_VER${NC}"

# Install system dependencies
echo -e "${BLUE}Installing system dependencies...${NC}"
case "$OS_NAME" in
    "Ubuntu"|"Debian GNU/Linux")
        apt-get update -qq
        apt-get install -y -qq python3-pip python3-venv python3-full sqlite3 curl > /dev/null
        ;;
    "CentOS Linux"|"Red Hat Enterprise Linux"|"Fedora")
        yum install -y -q python3-pip sqlite curl > /dev/null 2>&1 || \
        dnf install -y -q python3-pip sqlite curl > /dev/null 2>&1
        ;;
    *)
        echo -e "${RED}Unsupported OS: $OS_NAME${NC}"
        echo "Supported: Ubuntu, Debian, CentOS, RHEL, Fedora"
        exit 1
        ;;
esac

# Create user
if ! id "$USER" &>/dev/null; then
    echo -e "${BLUE}Creating user: $USER${NC}"
    useradd -r -s /bin/false -d "$DATA_DIR" "$USER"
fi

# Create directories
echo -e "${BLUE}Creating directories...${NC}"
mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$DATA_DIR" "$LOG_DIR"

# Download or use local files
if [ "$LOCAL_INSTALL" = true ]; then
    echo -e "${YELLOW}Installing from local files...${NC}"
    # Use current directory
    EXTRACT_DIR="$(pwd)"
else
    # Download from source archive
    echo -e "${BLUE}Downloading version $INSTALL_VERSION from GitHub...${NC}"
    TMP_WORKDIR=$(mktemp -d /tmp/uptime-monitor-install.XXXXXX)
    ARCHIVE_PATH="$TMP_WORKDIR/uptime-monitor.tar.gz"
    trap 'rm -rf "$TMP_WORKDIR"' EXIT

    if ! curl -fsSL "$DOWNLOAD_URL" -o "$ARCHIVE_PATH" 2>/dev/null; then
        echo -e "${RED}Error: Failed to download from GitHub${NC}"
        exit 1
    fi

    echo -e "${BLUE}Extracting...${NC}"
    tar -xzf "$ARCHIVE_PATH" -C "$TMP_WORKDIR"

    # Find extracted directory
    EXTRACT_DIR=$(find "$TMP_WORKDIR" -mindepth 1 -maxdepth 1 -type d -name "Uptime-Monitor*" | head -1)
fi

if [ -z "$EXTRACT_DIR" ]; then
    echo -e "${RED}Error: Could not find extracted files${NC}"
    exit 1
fi

echo -e "${BLUE}Found: $EXTRACT_DIR${NC}"

# Install files from Uptime_Robot subdirectory
echo -e "${BLUE}Installing application...${NC}"
if [ -d "$EXTRACT_DIR/Uptime_Robot" ]; then
    SRC_DIR="$EXTRACT_DIR/Uptime_Robot"
else
    SRC_DIR="$EXTRACT_DIR"
fi

# Copy Python files
for f in main.py worker.py state.py dependencies.py auth_module.py database.py logger.py models.py notifications.py monitoring.py ssl_checker.py config_manager.py ui_templates.py; do
    if [ -f "$SRC_DIR/$f" ]; then
        cp "$SRC_DIR/$f" "$INSTALL_DIR/"
    fi
done

# Copy routers package
if [ -d "$SRC_DIR/routers" ]; then
    cp -r "$SRC_DIR/routers" "$INSTALL_DIR/"
fi

# Copy templates and static
if [ -d "$SRC_DIR/templates" ]; then
    cp -r "$SRC_DIR/templates" "$INSTALL_DIR/"
fi

if [ -d "$SRC_DIR/static" ]; then
    cp -r "$SRC_DIR/static" "$INSTALL_DIR/"
fi

# Copy requirements (prefer Linux-specific file on Linux)
if [ -f "$SRC_DIR/requirements-linux.txt" ]; then
    cp "$SRC_DIR/requirements-linux.txt" "$INSTALL_DIR/requirements.txt"
elif [ -f "$SRC_DIR/requirements.txt" ]; then
    cp "$SRC_DIR/requirements.txt" "$INSTALL_DIR/"
    # Remove Windows-specific packages on Linux
    sed -i '/pywin32/d' "$INSTALL_DIR/requirements.txt"
fi

# Create virtual environment
echo -e "${BLUE}Creating virtual environment...${NC}"
cd "$INSTALL_DIR"
$PYTHON_CMD -m venv venv

# Install Python dependencies in venv
echo -e "${BLUE}Installing Python packages...${NC}"
./venv/bin/pip install --upgrade pip > /dev/null
./venv/bin/pip install -r requirements.txt

# Get server IP for auto-detection
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "0.0.0.0")

# Create configuration
echo -e "${BLUE}Creating configuration...${NC}"
if [ ! -f "$CONFIG_DIR/config.json" ]; then
    cat > "$CONFIG_DIR/config.json" << EOF
{
    "server": {
        "port": $PORT,
        "host": "0.0.0.0",
        "domain": "$SERVER_IP"
    },
    "ssl": {
        "enabled": false,
        "type": "custom",
        "cert_path": "$CONFIG_DIR/ssl/cert.pem",
        "key_path": "$CONFIG_DIR/ssl/key.pem",
        "redirect_http": true,
        "hsts": true,
        "hsts_max_age": 31536000
    },
    "data_dir": "$DATA_DIR",
    "log_dir": "$LOG_DIR",
    "check_interval": 60,
    "notifications": {
        "email_enabled": false,
        "email_smtp_server": "",
        "email_smtp_port": 587,
        "email_username": "",
        "email_password": "",
        "email_to": ""
    },
    "alert_policy": {
        "request_timeout_seconds": 60,
        "down_failures_threshold": 1,
        "up_success_threshold": 1,
        "still_down_repeat_seconds": 600,
        "treat_4xx_as_down": true,
        "ssl_notification_days": 7,
        "ssl_notification_cooldown_seconds": 21600
    },
    "backup": {
        "enabled": true,
        "max_backups": 10,
        "backup_dir": "$CONFIG_DIR/config.backups"
    }
}
EOF
fi

# Create SSL directory
mkdir -p "$CONFIG_DIR/ssl"
mkdir -p "$CONFIG_DIR/config.backups"

# Copy scripts
echo -e "${BLUE}Installing management scripts...${NC}"
if [ -d "$SRC_DIR/scripts" ]; then
    cp -r "$SRC_DIR/scripts" "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/scripts/"*.sh 2>/dev/null || true
    chmod +x "$INSTALL_DIR/scripts/"*.py 2>/dev/null || true
fi

# Create default backup directory
echo -e "${BLUE}Creating backup directories...${NC}"
mkdir -p "/backup/uptime-monitor"
chown -R "$APP_USER:$APP_USER" "/backup/uptime-monitor" 2>/dev/null || true

# Create systemd services
echo -e "${BLUE}Creating systemd services...${NC}"

# 1. Main Web Service
cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=Uptime Monitor Web UI (Version $APP_VERSION)
Documentation=https://github.com/$GITHUB_REPO
After=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="CONFIG_PATH=$CONFIG_DIR/config.json"
Environment="APP_VERSION=$APP_VERSION"
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# 2. Background Worker Service
cat > /etc/systemd/system/$SERVICE_NAME-worker.service << EOF
[Unit]
Description=Uptime Monitor Background Worker
After=network.target $SERVICE_NAME.service
PartOf=$SERVICE_NAME.service

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="CONFIG_PATH=$CONFIG_DIR/config.json"
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/worker.py
Restart=always
RestartSec=10
StandardOutput=append:$LOG_DIR/worker.log
StandardError=append:$LOG_DIR/worker.error.log

NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Set permissions
echo -e "${BLUE}Setting permissions...${NC}"
chown -R "$USER:$USER" "$INSTALL_DIR" "$CONFIG_DIR" "$DATA_DIR" "$LOG_DIR"
chmod 600 "$CONFIG_DIR/config.json"

# Setup firewall
echo -e "${BLUE}Configuring firewall...${NC}"
if command -v ufw &> /dev/null; then
    if ufw status | grep -q "Status: active"; then
        ufw allow $PORT/tcp comment 'Uptime Monitor'
        echo -e "${GREEN}Added UFW rule for port $PORT${NC}"
    fi
elif command -v firewall-cmd &> /dev/null; then
    if firewall-cmd --state 2>/dev/null; then
        firewall-cmd --permanent --add-port=$PORT/tcp
        firewall-cmd --reload
        echo -e "${GREEN}Added firewalld rule for port $PORT${NC}"
    fi
fi

# Start services
echo -e "${BLUE}Starting services...${NC}"
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl enable $SERVICE_NAME-worker
systemctl start $SERVICE_NAME
systemctl start $SERVICE_NAME-worker

# Check status
sleep 3
if systemctl is-active --quiet $SERVICE_NAME; then
    # Get IP
    IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

    echo ""
    echo -e "${GREEN}=========================================="
    echo "   Uptime Monitor - Installation Successful!"
    echo "==========================================${NC}"
    echo ""
    echo -e "  ${GREEN}Version:${NC}     $APP_VERSION"
    echo -e "  ${GREEN}Port:${NC}        $PORT"
    echo -e "  ${GREEN}Host:${NC}        0.0.0.0"
    echo -e "  ${GREEN}Domain:${NC}      $IP (auto-detected)"
    echo -e "  ${GREEN}SSL:${NC}         Disabled (configure manually)"
    echo -e "  ${GREEN}URL:${NC}         http://$IP:$PORT"
    echo ""
    echo -e "  ${YELLOW}Default Credentials:${NC}"
    echo -e "    Username: ${BLUE}admin${NC}"
    echo -e "    Password: ${BLUE}admin${NC}"
    echo ""
    echo -e "  ${YELLOW}Please change the password after first login!${NC}"
    echo ""
    echo "Management Commands:"
    echo "  sudo systemctl status $SERVICE_NAME"
    echo "  sudo systemctl restart $SERVICE_NAME"
    echo "  sudo systemctl stop $SERVICE_NAME"
    echo ""
    echo "Configuration Commands:"
    echo "  sudo nano $CONFIG_DIR/config.json     # Edit configuration"
    echo "  sudo $INSTALL_DIR/scripts/config-rollback.sh --list     # List backups"
    echo "  sudo $INSTALL_DIR/scripts/config-rollback.sh            # Rollback to previous"
    echo ""
    echo "Backup System:"
    echo "  Create backup:  sudo $INSTALL_DIR/scripts/backup-system.sh --dest /backup/uptime-monitor/"
    echo "  Check status:   sudo $INSTALL_DIR/scripts/backup-system.sh --status"
    echo "  Restore:        sudo $INSTALL_DIR/scripts/restore-system.sh --auto"
    echo "  Schedule:       sudo $INSTALL_DIR/scripts/schedule-backup.sh --install --dest /backup/uptime-monitor/"
    echo "  NFS Setup:      sudo $INSTALL_DIR/scripts/mount-backup.sh --type nfs --server <IP> --path /exports/backups --mount-point /mnt/nfs-backup --persist"
    echo "  Samba Setup:    sudo $INSTALL_DIR/scripts/mount-backup.sh --type smb --server <IP> --share backups --mount-point /mnt/smb-backup --persist"
    echo ""
    echo "Enable SSL (when ready):"
    echo "  1. Add your certificates to $CONFIG_DIR/ssl/"
    echo "  2. Edit $CONFIG_DIR/config.json"
    echo "  3. Change ssl.enabled to true"
    echo "  4. Update server.port to 443"
    echo "  5. Update server.domain to your domain"
    echo "  6. Restart: sudo systemctl restart $SERVICE_NAME"
    echo ""
    echo "Configuration File:"
    echo "  Location: $CONFIG_DIR/config.json"
    echo "  Logs:     $LOG_DIR/"
    echo "  SSL:      $CONFIG_DIR/ssl/"
    echo "  Backups:  /backup/uptime-monitor/ (default)"
    echo ""
else
    echo -e "${RED}=========================================="
    echo "   Installation Failed"
    echo "==========================================${NC}"
    echo ""
    echo "Service failed to start. Check logs:"
    echo "  sudo journalctl -u $SERVICE_NAME -n 50"
    echo ""
    exit 1
fi

# Cleanup handled by trap

echo -e "${GREEN}Done!${NC}"
