#!/bin/bash
#
# Uptime Monitor - Restore System
# Restores from backup archives
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default paths
CONFIG_PATH="/etc/uptime-monitor/config.json"
DEFAULT_BACKUP_PATH="/backup/uptime-monitor"
LOG_FILE="/var/log/uptime-monitor/backup.log"

# Show help
show_help() {
    cat << EOF
Uptime Monitor Restore System

Restores Uptime Monitor from backup archives.

Usage: $(basename "$0") [OPTIONS]

Options:
    --from PATH              Restore from specific backup file
    --auto                   Restore from latest backup (auto-detect)
    --list                   List available backups
    --only COMPONENT         Restore only: database, config, ssl, logs, all (default: all)
    --dry-run                Show what would be restored without restoring
    --force                  Skip confirmation prompts
    --help, -h               Show this help message

Components:
    database    - SQLite database (sites.db)
    config      - Configuration files (config.json, history)
    ssl         - SSL certificates
    logs        - Log files
    all         - Everything (default)

Examples:
    # List available backups
    sudo $(basename "$0") --list

    # Restore from latest backup
    sudo $(basename "$0") --auto

    # Restore from specific backup
    sudo $(basename "$0") --from /backup/uptime-monitor/daily/backup-20260218-020000.tar.gz

    # Restore only database
    sudo $(basename "$0") --auto --only database

    # Dry run (see what would be restored)
    sudo $(basename "$0") --auto --dry-run

    # Force restore without prompts
    sudo $(basename "$0") --auto --force

EOF
}

# Log function
log() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} - $message" | tee -a "$LOG_FILE" 2>/dev/null || echo -e "$message"
}

# Get config value
get_config_value() {
    local keys="$1"
    local default="$2"
    
    if [ -f "$CONFIG_PATH" ]; then
        python3 -c "import json; data=json.load(open('$CONFIG_PATH')); keys='$keys'.split('.'); val=data; 
for k in keys: val=val.get(k, {}) if isinstance(val, dict) else '$default'
print(val if not isinstance(val, dict) else '$default')" 2>/dev/null || echo "$default"
    else
        echo "$default"
    fi
}

# List available backups
list_backups() {
    local backup_dir="${1:-$DEFAULT_BACKUP_PATH}"
    
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}   Available Backups${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    if [ ! -d "$backup_dir" ]; then
        echo -e "${RED}Backup directory not found: $backup_dir${NC}"
        return 1
    fi
    
    local found=0
    
    for type in on-change daily weekly monthly yearly; do
        if [ -d "$backup_dir/$type" ]; then
            local backups=($(find "$backup_dir/$type" -name "backup-*.tar.gz" -type f | sort -r))
            
            if [ ${#backups[@]} -gt 0 ]; then
                found=1
                echo -e "${GREEN}$type:${NC}"
                
                local count=0
                for backup in "${backups[@]}"; do
                    count=$((count + 1))
                    local filename=$(basename "$backup")
                    local size=$(du -h "$backup" | cut -f1)
                    local date=$(echo "$filename" | grep -oP '\d{8}-\d{6}' | sed 's/\(....\)\(..\)\(..\)-\(..\)\(..\)\(..\)/\1-\2-\3 \4:\5:\6/')
                    
                    if [ $count -le 5 ]; then
                        echo -e "  $count. $filename (${size}) - $date"
                    fi
                done
                
                if [ $count -gt 5 ]; then
                    echo -e "  ... and $((count - 5)) more"
                fi
                
                echo ""
            fi
        fi
    done
    
    if [ $found -eq 0 ]; then
        echo -e "${YELLOW}No backups found.${NC}"
        echo ""
        echo "To create a backup, run:"
        echo "  sudo /opt/uptime-monitor/scripts/backup-system.sh --dest $backup_dir"
    fi
}

# Find latest backup
find_latest_backup() {
    local backup_dir="${1:-$DEFAULT_BACKUP_PATH}"
    
    # Search in order: on-change, daily, weekly, monthly, yearly
    for type in on-change daily weekly monthly yearly; do
        if [ -d "$backup_dir/$type" ]; then
            local latest=$(find "$backup_dir/$type" -name "backup-*.tar.gz" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
            if [ -n "$latest" ]; then
                echo "$latest"
                return 0
            fi
        fi
    done
    
    return 1
}

# Extract and restore from backup
restore_backup() {
    local backup_file="$1"
    local component="$2"
    local dry_run="$3"
    local force="$4"
    
    if [ "$EUID" -ne 0 ]; then
        log "${RED}Error: Please run as root (use sudo)${NC}"
        exit 1
    fi
    
    if [ ! -f "$backup_file" ]; then
        log "${RED}Error: Backup file not found: $backup_file${NC}"
        exit 1
    fi
    
    log "${BLUE}Restoring from: $(basename "$backup_file")${NC}"
    
    # Create temporary directory
    local temp_dir="/tmp/uptime-restore-$(date +%s)"
    mkdir -p "$temp_dir"
    
    # Extract backup
    log "Extracting backup..."
    tar -xzf "$backup_file" -C "$temp_dir"
    
    # Find extracted directory
    local extract_dir=$(find "$temp_dir" -maxdepth 1 -type d | tail -1)
    
    if [ ! -d "$extract_dir" ]; then
        log "${RED}Error: Failed to extract backup${NC}"
        rm -rf "$temp_dir"
        exit 1
    fi
    
    # Show backup metadata
    if [ -f "$extract_dir/metadata.json" ]; then
        echo ""
        echo -e "${BLUE}Backup Information:${NC}"
        echo "  File: $(basename "$backup_file")"
        echo "  Created: $(cat "$extract_dir/metadata.json" | python3 -c "import json,sys; print(json.load(sys.stdin).get('timestamp', 'N/A'))")"
        echo "  Host: $(cat "$extract_dir/metadata.json" | python3 -c "import json,sys; print(json.load(sys.stdin).get('hostname', 'N/A'))")"
        echo "  Type: $(cat "$extract_dir/metadata.json" | python3 -c "import json,sys; print(json.load(sys.stdin).get('type', 'N/A'))")"
        if [ -n "$(cat "$extract_dir/metadata.json" | python3 -c "import json,sys; print(json.load(sys.stdin).get('comment', ''))" 2>/dev/null)" ]; then
            echo "  Comment: $(cat "$extract_dir/metadata.json" | python3 -c "import json,sys; print(json.load(sys.stdin).get('comment', ''))")"
        fi
        echo ""
    fi
    
    # Show what will be restored
    echo -e "${BLUE}Components to restore:${NC}"
    
    if [ "$component" = "all" ] || [ "$component" = "database" ]; then
        if [ -f "$extract_dir/database/sites.db" ]; then
            echo "  ✓ Database (sites.db)"
        fi
    fi
    
    if [ "$component" = "all" ] || [ "$component" = "config" ]; then
        if [ -f "$extract_dir/config/config.json" ]; then
            echo "  ✓ Configuration (config.json)"
        fi
    fi
    
    if [ "$component" = "all" ] || [ "$component" = "ssl" ]; then
        if [ -d "$extract_dir/ssl" ]; then
            echo "  ✓ SSL certificates"
        fi
    fi
    
    if [ "$component" = "all" ] || [ "$component" = "logs" ]; then
        if [ -d "$extract_dir/logs" ]; then
            echo "  ✓ Log files"
        fi
    fi
    
    echo ""
    
    # Dry run
    if [ "$dry_run" = "true" ]; then
        log "${YELLOW}[DRY RUN] No changes made.${NC}"
        rm -rf "$temp_dir"
        return 0
    fi
    
    # Confirmation
    if [ "$force" != "true" ]; then
        echo -e "${YELLOW}WARNING: This will overwrite current data!${NC}"
        read -p "Are you sure you want to proceed? (yes/no): " confirm
        
        if [[ ! "$confirm" =~ ^[Yy][Ee][Ss]$ ]]; then
            log "Restore cancelled."
            rm -rf "$temp_dir"
            exit 0
        fi
    fi
    
    # Get current paths from config or defaults
    local data_dir=$(get_config_value 'data_dir' '/var/lib/uptime-monitor')
    local config_dir=$(dirname "$CONFIG_PATH")
    local log_dir=$(get_config_value 'log_dir' '/var/log/uptime-monitor')
    
    # Create pre-restore backup
    log "Creating safety backup of current state..."
    local safety_backup="/tmp/uptime-pre-restore-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$safety_backup"
    
    # Stop service
    log "Stopping uptime-monitor service..."
    systemctl stop uptime-monitor 2>/dev/null || true
    
    # Backup current state
    [ -d "$data_dir" ] && cp -r "$data_dir" "$safety_backup/" 2>/dev/null || true
    [ -f "$CONFIG_PATH" ] && cp "$CONFIG_PATH" "$safety_backup/" 2>/dev/null || true
    [ -d "$config_dir/ssl" ] && cp -r "$config_dir/ssl" "$safety_backup/" 2>/dev/null || true
    
    # Restore components
    if [ "$component" = "all" ] || [ "$component" = "database" ]; then
        if [ -f "$extract_dir/database/sites.db" ]; then
            log "Restoring database..."
            mkdir -p "$data_dir"
            cp "$extract_dir/database/sites.db" "$data_dir/"
            chown -R uptime-monitor:uptime-monitor "$data_dir" 2>/dev/null || true
            chmod 644 "$data_dir/sites.db"
        fi
    fi
    
    if [ "$component" = "all" ] || [ "$component" = "config" ]; then
        if [ -f "$extract_dir/config/config.json" ]; then
            log "Restoring configuration..."
            mkdir -p "$config_dir"
            cp "$extract_dir/config/config.json" "$CONFIG_PATH"
            chmod 600 "$CONFIG_PATH"
            
            # Restore config history
            if [ -d "$extract_dir/config/config.backups" ]; then
                cp -r "$extract_dir/config/config.backups" "$config_dir/" 2>/dev/null || true
            fi
        fi
    fi
    
    if [ "$component" = "all" ] || [ "$component" = "ssl" ]; then
        if [ -d "$extract_dir/ssl" ]; then
            log "Restoring SSL certificates..."
            mkdir -p "$config_dir/ssl"
            cp -r "$extract_dir/ssl/"* "$config_dir/ssl/" 2>/dev/null || true
            chmod 600 "$config_dir/ssl/"*.pem 2>/dev/null || true
        fi
    fi
    
    if [ "$component" = "all" ] || [ "$component" = "logs" ]; then
        if [ -d "$extract_dir/logs" ]; then
            log "Restoring log files..."
            mkdir -p "$log_dir"
            cp -r "$extract_dir/logs/"* "$log_dir/" 2>/dev/null || true
        fi
    fi
    
    # Restore systemd service if present
    if [ "$component" = "all" ] && [ -f "$extract_dir/systemd/uptime-monitor.service" ]; then
        log "Restoring systemd service..."
        cp "$extract_dir/systemd/uptime-monitor.service" "/etc/systemd/system/"
        systemctl daemon-reload
    fi
    
    # Cleanup
    rm -rf "$temp_dir"
    
    # Start service
    log "Starting uptime-monitor service..."
    systemctl start uptime-monitor
    
    sleep 2
    
    # Check status
    if systemctl is-active --quiet uptime-monitor; then
        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}   Restore Completed Successfully!${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        echo -e "Service is ${GREEN}running${NC}."
        echo ""
        echo -e "Safety backup saved to: ${BLUE}$safety_backup${NC}"
        echo ""
        echo "To remove safety backup when confirmed working:"
        echo "  sudo rm -rf $safety_backup"
        echo ""
        
        # Show current URL
        local current_port=$(get_config_value 'server.port' '8080')
        local current_domain=$(get_config_value 'server.domain' 'auto')
        local ssl_enabled=$(get_config_value 'ssl.enabled' 'false')
        
        if [ "$current_domain" = "auto" ]; then
            current_domain=$(hostname -I | awk '{print $1}')
        fi
        
        if [ "$ssl_enabled" = "true" ]; then
            echo -e "Access URL: ${BLUE}https://$current_domain${NC}"
        else
            echo -e "Access URL: ${BLUE}http://$current_domain:$current_port${NC}"
        fi
    else
        echo ""
        echo -e "${RED}========================================${NC}"
        echo -e "${RED}   Restore Completed but Service Failed${NC}"
        echo -e "${RED}========================================${NC}"
        echo ""
        echo -e "The restore completed but the service ${RED}failed to start${NC}."
        echo ""
        echo "Check logs:"
        echo "  sudo journalctl -u uptime-monitor -n 50"
        echo ""
        echo "To restore from safety backup:"
        echo "  sudo cp -r $safety_backup/* /"
        echo "  sudo systemctl restart uptime-monitor"
        echo ""
        exit 1
    fi
}

# Main
main() {
    local backup_file=""
    local auto_restore="false"
    local show_list="false"
    local component="all"
    local dry_run="false"
    local force="false"
    local backup_dir="$DEFAULT_BACKUP_PATH"
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --from)
                backup_file="$2"
                shift 2
                ;;
            --auto)
                auto_restore="true"
                shift
                ;;
            --list)
                show_list="true"
                shift
                ;;
            --only)
                component="$2"
                shift 2
                ;;
            --dry-run)
                dry_run="true"
                shift
                ;;
            --force)
                force="true"
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Show list
    if [ "$show_list" = "true" ]; then
        list_backups "$backup_dir"
        exit 0
    fi
    
    # Auto-find latest backup
    if [ "$auto_restore" = "true" ]; then
        backup_file=$(find_latest_backup "$backup_dir")
        if [ -z "$backup_file" ]; then
            log "${RED}Error: No backups found in $backup_dir${NC}"
            exit 1
        fi
        log "Found latest backup: $(basename "$backup_file")"
    fi
    
    # Check if we have a backup file
    if [ -z "$backup_file" ]; then
        log "${RED}Error: No backup file specified${NC}"
        echo "Use --from to specify a backup file, or --auto to use the latest"
        echo ""
        show_help
        exit 1
    fi
    
    # Validate component
    if [[ ! "$component" =~ ^(all|database|config|ssl|logs)$ ]]; then
        log "${RED}Error: Invalid component: $component${NC}"
        echo "Valid components: all, database, config, ssl, logs"
        exit 1
    fi
    
    # Restore
    restore_backup "$backup_file" "$component" "$dry_run" "$force"
}

main "$@"
