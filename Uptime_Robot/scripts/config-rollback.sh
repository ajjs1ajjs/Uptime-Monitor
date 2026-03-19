#!/bin/bash

# Configuration Rollback Script for Uptime Monitor
# Usage: config-rollback.sh [--list|--to <backup>|--help]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
CONFIG_PATH="/etc/uptime-monitor/config.json"
BACKUP_DIR="/etc/uptime-monitor/config.backups"
SERVICE_NAME="uptime-monitor"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: Please run as root (use sudo)${NC}"
    exit 1
fi

# Get backup directory from config if exists
if [ -f "$CONFIG_PATH" ]; then
    BACKUP_DIR=$(python3 -c "import json; print(json.load(open('$CONFIG_PATH')).get('backup', {}).get('backup_dir', '$BACKUP_DIR'))" 2>/dev/null || echo "$BACKUP_DIR")
fi

# Functions
show_help() {
    echo "Configuration Rollback Tool for Uptime Monitor"
    echo ""
    echo "Usage: sudo $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  --list, -l              List all available backups"
    echo "  --to, -t <backup>       Rollback to specific backup"
    echo "  --previous, -p          Rollback to previous configuration"
    echo "  --latest, -la           Show latest backup info"
    echo "  --diff, -d <backup>     Show differences from backup"
    echo "  --help, -h              Show this help message"
    echo ""
    echo "Examples:"
    echo "  sudo $0 --list                    # List all backups"
    echo "  sudo $0 --to config.20260218-120000.json  # Rollback to specific"
    echo "  sudo $0 --previous                # Quick rollback to previous"
    echo "  sudo $0 --diff config.latest.json # See what changed"
    echo ""
}

list_backups() {
    echo -e "${BLUE}Available Configuration Backups:${NC}"
    echo "=================================="
    
    if [ ! -d "$BACKUP_DIR" ]; then
        echo -e "${RED}Backup directory not found: $BACKUP_DIR${NC}"
        exit 1
    fi
    
    local count=0
    for backup in $(ls -t "$BACKUP_DIR"/config.*.json 2>/dev/null); do
        if [ -f "$backup" ] && [[ ! "$backup" =~ \.latest\.json$ ]] && [[ ! "$backup" =~ \.previous\.json$ ]]; then
            count=$((count + 1))
            local filename=$(basename "$backup")
            local date_str=$(echo "$filename" | grep -oP '\d{8}-\d{6}')
            local formatted_date=$(echo "$date_str" | sed 's/\(....\)\(..\)\(..\)-\(..\)\(..\)\(..\)/\1-\2-\3 \4:\5:\6/')
            echo -e "${GREEN}$count.${NC} $filename (${formatted_date})"
        fi
    done
    
    if [ $count -eq 0 ]; then
        echo -e "${YELLOW}No backups found.${NC}"
    else
        echo ""
        echo -e "${BLUE}Symlinks:${NC}"
        if [ -L "$BACKUP_DIR/config.latest.json" ]; then
            local latest=$(readlink "$BACKUP_DIR/config.latest.json")
            echo -e "  Latest:   ${GREEN}$latest${NC}"
        fi
        if [ -L "$BACKUP_DIR/config.previous.json" ]; then
            local previous=$(readlink "$BACKUP_DIR/config.previous.json")
            echo -e "  Previous: ${GREEN}$previous${NC}"
        fi
    fi
    
    echo ""
}

show_latest() {
    if [ -L "$BACKUP_DIR/config.latest.json" ]; then
        local latest=$(readlink "$BACKUP_DIR/config.latest.json")
        echo -e "${BLUE}Latest backup:${NC} $latest"
        
        if [ -f "$BACKUP_DIR/config.latest.json" ]; then
            echo ""
            echo "Configuration preview:"
            python3 -c "import json; d=json.load(open('$BACKUP_DIR/config.latest.json')); print(json.dumps(d, indent=2))" 2>/dev/null || cat "$BACKUP_DIR/config.latest.json"
        fi
    else
        echo -e "${YELLOW}No latest backup found.${NC}"
    fi
}

show_diff() {
    local backup_file="$1"
    
    if [ ! -f "$BACKUP_DIR/$backup_file" ]; then
        echo -e "${RED}Backup not found: $backup_file${NC}"
        exit 1
    fi
    
    if [ ! -f "$CONFIG_PATH" ]; then
        echo -e "${RED}Current config not found: $CONFIG_PATH${NC}"
        exit 1
    fi
    
    echo -e "${BLUE}Differences from $backup_file:${NC}"
    echo "=================================="
    
    python3 << EOF
import json
import sys

try:
    with open('$BACKUP_DIR/$backup_file', 'r') as f:
        backup = json.load(f)
    with open('$CONFIG_PATH', 'r') as f:
        current = json.load(f)
    
    def show_diff(path, old, new):
        if isinstance(old, dict) and isinstance(new, dict):
            for key in set(old.keys()) | set(new.keys()):
                old_val = old.get(key, 'N/A')
                new_val = new.get(key, 'N/A')
                if old_val != new_val:
                    show_diff(f"{path}.{key}", old_val, new_val)
        elif isinstance(old, list) and isinstance(new, list):
            if old != new:
                print(f"\n{path}:")
                print(f"  Backup:  {old}")
                print(f"  Current: {new}")
        else:
            if old != new:
                print(f"\n{path}:")
                print(f"  Backup:  {old}")
                print(f"  Current: {new}")
    
    show_diff('config', backup, current)
    print("\n")
except Exception as e:
    print(f"Error comparing: {e}")
    sys.exit(1)
EOF
}

rollback_to() {
    local backup_file="$1"
    local backup_path="$BACKUP_DIR/$backup_file"
    
    if [ ! -f "$backup_path" ]; then
        echo -e "${RED}Error: Backup file not found: $backup_file${NC}"
        exit 1
    fi
    
    echo -e "${YELLOW}WARNING: This will replace your current configuration!${NC}"
    echo -e "Backup file: ${BLUE}$backup_file${NC}"
    echo ""
    
    # Show current and backup config summary
    echo -e "${BLUE}Current configuration port:${NC}"
    python3 -c "import json; d=json.load(open('$CONFIG_PATH')); print('  Port:', d.get('server', {}).get('port', 'N/A')); print('  Domain:', d.get('server', {}).get('domain', 'N/A')); print('  SSL:', 'Enabled' if d.get('ssl', {}).get('enabled') else 'Disabled')" 2>/dev/null || echo "  (Unable to read)"
    
    echo ""
    echo -e "${BLUE}Backup configuration port:${NC}"
    python3 -c "import json; d=json.load(open('$backup_path')); print('  Port:', d.get('server', {}).get('port', 'N/A')); print('  Domain:', d.get('server', {}).get('domain', 'N/A')); print('  SSL:', 'Enabled' if d.get('ssl', {}).get('enabled') else 'Disabled')" 2>/dev/null || echo "  (Unable to read)"
    
    echo ""
    read -p "Are you sure you want to proceed? (yes/no): " confirm
    
    if [[ ! "$confirm" =~ ^[Yy][Ee][Ss]$ ]]; then
        echo -e "${YELLOW}Rollback cancelled.${NC}"
        exit 0
    fi
    
    # Create backup of current config before rollback
    echo -e "${BLUE}Creating backup of current configuration...${NC}"
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local pre_rollback_backup="$BACKUP_DIR/config.pre-rollback.$timestamp.json"
    cp "$CONFIG_PATH" "$pre_rollback_backup"
    
    # Perform rollback
    echo -e "${BLUE}Restoring configuration from backup...${NC}"
    cp "$backup_path" "$CONFIG_PATH"
    chmod 600 "$CONFIG_PATH"
    
    # Restart service
    echo -e "${BLUE}Restarting uptime-monitor service...${NC}"
    systemctl restart "$SERVICE_NAME"
    
    sleep 2
    
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}   Rollback Successful!${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        echo -e "Service is running with restored configuration."
        echo -e "Pre-rollback backup saved as: ${YELLOW}config.pre-rollback.$timestamp.json${NC}"
        echo ""
        echo -e "${BLUE}Current configuration:${NC}"
        python3 -c "import json; d=json.load(open('$CONFIG_PATH')); print('  Port:', d.get('server', {}).get('port', 'N/A')); print('  Domain:', d.get('server', {}).get('domain', 'N/A')); print('  URL:', f\"https://{d.get('server', {}).get('domain', 'localhost')}\" if d.get('ssl', {}).get('enabled') else f\"http://{d.get('server', {}).get('domain', 'localhost')}:{d.get('server', {}).get('port', 8080)}\")" 2>/dev/null
    else
        echo ""
        echo -e "${RED}========================================${NC}"
        echo -e "${RED}   Rollback Completed but Service Failed${NC}"
        echo -e "${RED}========================================${NC}"
        echo ""
        echo -e "${YELLOW}The configuration was restored but the service failed to start.${NC}"
        echo -e "Check logs: ${BLUE}sudo journalctl -u $SERVICE_NAME -n 50${NC}"
        echo ""
        echo -e "To restore previous configuration:"
        echo -e "  ${BLUE}sudo cp $pre_rollback_backup $CONFIG_PATH${NC}"
        echo -e "  ${BLUE}sudo systemctl restart $SERVICE_NAME${NC}"
        exit 1
    fi
}

rollback_previous() {
    if [ ! -L "$BACKUP_DIR/config.previous.json" ]; then
        echo -e "${RED}Error: No previous backup found.${NC}"
        echo -e "${YELLOW}Hint: Use --list to see available backups.${NC}"
        exit 1
    fi
    
    local previous=$(readlink "$BACKUP_DIR/config.previous.json")
    echo -e "${BLUE}Rolling back to previous configuration:${NC}"
    echo "  $previous"
    echo ""
    
    rollback_to "$(basename "$previous")"
}

# Main logic
case "${1:-}" in
    --list|-l)
        list_backups
        ;;
    --to|-t)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: Please specify backup file.${NC}"
            echo "Usage: sudo $0 --to <backup-file>"
            exit 1
        fi
        rollback_to "$2"
        ;;
    --previous|-p)
        rollback_previous
        ;;
    --latest|-la)
        show_latest
        ;;
    --diff|-d)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: Please specify backup file.${NC}"
            echo "Usage: sudo $0 --diff <backup-file>"
            exit 1
        fi
        show_diff "$2"
        ;;
    --help|-h|"")
        show_help
        ;;
    *)
        echo -e "${RED}Unknown option: $1${NC}"
        show_help
        exit 1
        ;;
esac
