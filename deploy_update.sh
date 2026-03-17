#!/bin/bash

# Uptime Monitor - Safe Deployment Update Script
# This script safely updates the production server with backup and rollback support

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/uptime-monitor"
SERVICE_NAME="uptime-monitor"
BACKUP_DIR="/opt/uptime-monitor/backups"
LOG_FILE="/var/log/uptime-monitor/deploy.log"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Uptime Monitor - Deployment Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run with sudo${NC}"
    exit 1
fi

# Create backup directory if not exists
mkdir -p "$BACKUP_DIR"

# Create log directory if not exists
mkdir -p "$(dirname "$LOG_FILE")"

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to create backup
create_backup() {
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="$BACKUP_DIR/ui_templates.py.backup.$timestamp"

    log_message "Creating backup: $backup_file"
    cp "$INSTALL_DIR/ui_templates.py" "$backup_file"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Backup created: $backup_file${NC}"
        log_message "Backup created successfully: $backup_file"
        return 0
    else
        echo -e "${RED}✗ Backup failed!${NC}"
        log_message "Backup failed!"
        return 1
    fi
}

# Function to update code
update_code() {
    log_message "Pulling latest changes from GitHub..."

    cd "$INSTALL_DIR"

    # Check if git repository exists
    if [ ! -d ".git" ]; then
        echo -e "${RED}✗ Not a git repository!${NC}"
        log_message "Error: $INSTALL_DIR is not a git repository"
        return 1
    fi

    # Fix git permissions
    chown -R sa:sa .git/ 2>/dev/null || true

    # Pull latest changes
    git fetch origin
    git reset --hard origin/main

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Code updated successfully${NC}"
        log_message "Code updated successfully"

        # Remove old cached files
        echo -e "${YELLOW}Cleaning old files...${NC}"
        rm -f ui_templates.py
        rm -f page.html
        rm -f Uptime_Robot/page.html
        find . -path ./venv -prune -o -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        find . -path ./venv -prune -o -name "*.pyc" -delete 2>/dev/null || true
        echo -e "${GREEN}✓ Old files cleaned${NC}"
        return 0
    else
        echo -e "${RED}✗ Git pull failed!${NC}"
        log_message "Git pull failed!"
        return 1
    fi
}

# Function to restart service
restart_service() {
    log_message "Restarting service: $SERVICE_NAME"

    systemctl restart "$SERVICE_NAME"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Service restarted${NC}"
        log_message "Service restarted successfully"
        return 0
    else
        echo -e "${RED} Service restart failed!${NC}"
        log_message "Service restart failed!"
        return 1
    fi
}

# Function to check service status
check_service() {
    log_message "Checking service status..."

    systemctl is-active --quiet "$SERVICE_NAME"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Service is running${NC}"
        log_message "Service is running"
        return 0
    else
        echo -e "${RED}✗ Service is NOT running!${NC}"
        log_message "Service is NOT running!"
        return 1
    fi
}

# Function to rollback
rollback() {
    echo -e "${YELLOW}Starting rollback...${NC}"
    log_message "Rollback initiated"

    # Find the latest backup
    local latest_backup=$(ls -t "$BACKUP_DIR"/ui_templates.py.backup.* 2>/dev/null | head -n1)

    if [ -z "$latest_backup" ]; then
        echo -e "${RED}✗ No backup found for rollback!${NC}"
        log_message "Rollback failed: No backup found"
        return 1
    fi

    echo -e "${YELLOW}Rolling back to: $latest_backup${NC}"
    cp "$latest_backup" "$INSTALL_DIR/ui_templates.py"

    if [ $? -eq 0 ]; then
        log_message "Rollback completed: restored from $latest_backup"
        restart_service
        echo -e "${GREEN}✓ Rollback completed successfully${NC}"
        return 0
    else
        echo -e "${RED}✗ Rollback failed!${NC}"
        log_message "Rollback failed!"
        return 1
    fi
}

# Function to show recent logs
show_logs() {
    echo ""
    echo -e "${BLUE}--- Recent Service Logs ---${NC}"
    journalctl -u "$SERVICE_NAME" -n 15 --no-pager
}

# Main deployment function
deploy() {
    echo -e "${YELLOW}Starting deployment...${NC}"
    log_message "Deployment started"

    # Step 1: Create backup
    echo ""
    echo -e "${BLUE}Step 1/4:${NC} Creating backup..."
    create_backup || {
        echo -e "${RED}Deployment aborted: Backup failed${NC}"
        exit 1
    }

    # Step 2: Update code
    echo ""
    echo -e "${BLUE}Step 2/4:${NC} Updating code from GitHub..."
    update_code || {
        echo -e "${RED}Deployment failed: Git pull error${NC}"
        echo -e "${YELLOW}Your code is still safe. Backup exists at: $BACKUP_DIR${NC}"
        exit 1
    }

    # Step 3: Restart service
    echo ""
    echo -e "${BLUE}Step 3/4:${NC} Restarting service..."
    restart_service || {
        echo -e "${RED}Service restart failed!${NC}"
        echo -e "${YELLOW}Consider rollback if needed${NC}"
        exit 1
    }

    # Step 4: Verify service
    echo ""
    echo -e "${BLUE}Step 4/4:${NC} Verifying service...${NC}"
    check_service || {
        echo -e "${RED}Service verification failed!${NC}"
        echo -e "${YELLOW}Use --rollback to revert changes${NC}"
        show_logs
        exit 1
    }

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Deployment completed successfully!${NC}"
    echo -e "${GREEN}========================================${NC}"
    log_message "Deployment completed successfully"

    # Show service status
    echo ""
    systemctl status "$SERVICE_NAME" --no-pager -n 5
}

# Show help
show_help() {
    echo "Usage: $0 [option]"
    echo ""
    echo "Options:"
    echo "  (none)      Run deployment (backup + update + restart)"
    echo "  --status    Check service status"
    echo "  --rollback  Rollback to previous version"
    echo "  --logs      Show recent service logs"
    echo "  --help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  sudo $0              # Deploy update"
    echo "  sudo $0 --status     # Check status"
    echo "  sudo $0 --rollback   # Rollback to backup"
    echo "  sudo $0 --logs       # Show logs"
}

# Parse command line arguments
case "${1:-}" in
    --status)
        check_service
        systemctl status "$SERVICE_NAME" --no-pager
        ;;
    --rollback)
        rollback
        ;;
    --logs)
        show_logs
        ;;
    --help|-h)
        show_help
        ;;
    "")
        deploy
        ;;
    *)
        echo -e "${RED}Unknown option: $1${NC}"
        show_help
        exit 1
        ;;
esac
