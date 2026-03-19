#!/bin/bash
#
# Uptime Monitor - Backup System
# Creates compressed backups of database, config, SSL, and logs
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
DEFAULT_LOCAL_PATH="/backup/uptime-monitor"
LOG_FILE="/var/log/uptime-monitor/backup.log"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Logging function
log() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} - $message" | tee -a "$LOG_FILE"
}

# Show help
show_help() {
    cat << EOF
Uptime Monitor Backup System

Usage: $(basename "$0") [OPTIONS]

Options:
    --dest PATH              Backup destination path (required)
    --type TYPE              Backup type: daily, weekly, monthly, yearly, on-change (default: daily)
    --comment TEXT           Comment/description for backup
    --status                 Show backup status and statistics
    --now                    Create backup immediately with timestamp
    --verify                 Verify backup after creation
    --help, -h               Show this help message

Backup Destinations:
    Local:   /backup/uptime-monitor
    NFS:     /mnt/nfs-backup/uptime-monitor (mount first)
    SMB:     /mnt/smb-backup/uptime-monitor (mount first)

Examples:
    # Daily backup to local disk
    sudo $(basename "$0") --dest /backup/uptime-monitor/ --type daily

    # Backup after configuration change
    sudo $(basename "$0") --dest /backup/uptime-monitor/ --type on-change --comment "After SSL setup"

    # Backup to NFS
    sudo $(basename "$0") --dest /mnt/nfs-backup/uptime-monitor/ --type daily

    # Check status
    sudo $(basename "$0") --status

EOF
}

# Get config value from JSON
get_config_value() {
    local key="$1"
    local default="$2"
    
    if [ -f "$CONFIG_PATH" ]; then
        python3 -c "import json; data=json.load(open('$CONFIG_PATH')); print(data.get('$key', '$default'))" 2>/dev/null || echo "$default"
    else
        echo "$default"
    fi
}

# Get nested config value
get_config_nested() {
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

# Show backup status
show_status() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}   Uptime Monitor Backup Status${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    # Check local backup location
    if [ -d "$DEFAULT_LOCAL_PATH" ]; then
        echo -e "${GREEN}Local Backup:${NC} $DEFAULT_LOCAL_PATH"
        echo -e "  Size: $(du -sh "$DEFAULT_LOCAL_PATH" 2>/dev/null | cut -f1)"
        echo -e "  Backups: $(find "$DEFAULT_LOCAL_PATH" -name "*.tar.gz" 2>/dev/null | wc -l)"
        
        # Show latest backup
        local latest=$(find "$DEFAULT_LOCAL_PATH" -name "*.tar.gz" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
        if [ -n "$latest" ]; then
            echo -e "  Latest: $(basename "$latest")"
        fi
    else
        echo -e "${YELLOW}Local Backup:${NC} Not configured"
    fi
    
    echo ""
    
    # Check NFS
    if mount | grep -q "/mnt/nfs-backup"; then
        echo -e "${GREEN}NFS Backup:${NC} Mounted"
        if [ -d "/mnt/nfs-backup/uptime-monitor" ]; then
            echo -e "  Size: $(du -sh "/mnt/nfs-backup/uptime-monitor" 2>/dev/null | cut -f1)"
            echo -e "  Backups: $(find "/mnt/nfs-backup/uptime-monitor" -name "*.tar.gz" 2>/dev/null | wc -l)"
        fi
    else
        echo -e "${YELLOW}NFS Backup:${NC} Not mounted"
    fi
    
    echo ""
    
    # Check Samba
    if mount | grep -q "/mnt/smb-backup"; then
        echo -e "${GREEN}Samba Backup:${NC} Mounted"
        if [ -d "/mnt/smb-backup/uptime-monitor" ]; then
            echo -e "  Size: $(du -sh "/mnt/smb-backup/uptime-monitor" 2>/dev/null | cut -f1)"
            echo -e "  Backups: $(find "/mnt/smb-backup/uptime-monitor" -name "*.tar.gz" 2>/dev/null | wc -l)"
        fi
    else
        echo -e "${YELLOW}Samba Backup:${NC} Not mounted"
    fi
    
    echo ""
    
    # Show retention policy
    echo -e "${BLUE}Retention Policy:${NC}"
    echo -e "  On-change: $(get_config_nested 'backup.retention.on_change' '10') backups"
    echo -e "  Daily: $(get_config_nested 'backup.retention.daily' '7') days"
    echo -e "  Weekly: $(get_config_nested 'backup.retention.weekly' 'all') weeks"
    echo -e "  Monthly: $(get_config_nested 'backup.retention.monthly' 'all') months"
    echo -e "  Yearly: $(get_config_nested 'backup.retention.yearly' 'all') years"
    
    echo ""
    
    # Recent backup log
    echo -e "${BLUE}Recent Backups:${NC}"
    if [ -f "$LOG_FILE" ]; then
        tail -10 "$LOG_FILE" | grep "Backup created" || echo "  No recent backups"
    else
        echo "  No backup log found"
    fi
    
    echo ""
}

# Create backup
create_backup() {
    local dest="$1"
    local backup_type="$2"
    local comment="$3"
    local verify="$4"
    
    # Check if running as root
    if [ "$EUID" -ne 0 ]; then
        log "${RED}Error: Please run as root (use sudo)${NC}"
        exit 1
    fi
    
    # Create destination directory
    mkdir -p "$dest"
    
    # Create subdirectories
    mkdir -p "$dest/$backup_type"
    
    # Generate timestamp
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local backup_name="backup-${timestamp}"
    local temp_dir="/tmp/uptime-backup-${timestamp}"
    local backup_file="$dest/$backup_type/${backup_name}.tar.gz"
    
    log "${BLUE}Starting backup: $backup_type${NC}"
    log "Destination: $backup_file"
    
    # Create temporary directory
    mkdir -p "$temp_dir"
    
    # Get paths from config or use defaults
    local data_dir=$(get_config_nested 'data_dir' '/var/lib/uptime-monitor')
    local log_dir=$(get_config_nested 'log_dir' '/var/log/uptime-monitor')
    local config_dir=$(dirname "$CONFIG_PATH")
    
    # Backup database
    if [ -f "$data_dir/sites.db" ]; then
        log "Backing up database..."
        mkdir -p "$temp_dir/database"
        cp "$data_dir/sites.db" "$temp_dir/database/"
    fi
    
    # Backup configuration
    if [ -f "$CONFIG_PATH" ]; then
        log "Backing up configuration..."
        mkdir -p "$temp_dir/config"
        cp "$CONFIG_PATH" "$temp_dir/config/"
        
        # Backup config history
        if [ -d "$config_dir/config.backups" ]; then
            cp -r "$config_dir/config.backups" "$temp_dir/config/" 2>/dev/null || true
        fi
    fi
    
    # Backup SSL certificates
    if [ -d "$config_dir/ssl" ]; then
        log "Backing up SSL certificates..."
        cp -r "$config_dir/ssl" "$temp_dir/" 2>/dev/null || true
    fi
    
    # Backup recent logs (last 7 days)
    if [ -d "$log_dir" ]; then
        log "Backing up recent logs..."
        mkdir -p "$temp_dir/logs"
        find "$log_dir" -name "*.log" -mtime -7 -exec cp {} "$temp_dir/logs/" \; 2>/dev/null || true
    fi
    
    # Backup systemd service
    if [ -f "/etc/systemd/system/uptime-monitor.service" ]; then
        log "Backing up systemd service..."
        mkdir -p "$temp_dir/systemd"
        cp "/etc/systemd/system/uptime-monitor.service" "$temp_dir/systemd/"
    fi
    
    # Create metadata
    cat > "$temp_dir/metadata.json" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "hostname": "$(hostname)",
    "ip": "$(hostname -I | awk '{print $1}')",
    "type": "$backup_type",
    "version": "$(get_config_nested 'backup.version' '1.0.0')",
    "comment": "$comment",
    "files": {
        "database": $(test -f "$temp_dir/database/sites.db" && echo "true" || echo "false"),
        "config": $(test -f "$temp_dir/config/config.json" && echo "true" || echo "false"),
        "ssl": $(test -d "$temp_dir/ssl" && echo "true" || echo "false"),
        "logs": $(test -d "$temp_dir/logs" && echo "true" || echo "false")
    }
}
EOF
    
    # Create restore script
    cat > "$temp_dir/restore.sh" << 'EOF'
#!/bin/bash
# Uptime Monitor Restore Script
# Auto-generated with backup

set -e

echo "Uptime Monitor Restore"
echo "======================"
echo ""
echo "This will restore Uptime Monitor from this backup."
echo "Current data will be backed up before restore."
echo ""
read -p "Are you sure? (yes/no): " confirm

if [[ ! "$confirm" =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "Restore cancelled."
    exit 0
fi

# Detect paths from system
CONFIG_PATH="/etc/uptime-monitor/config.json"
if [ -f "$CONFIG_PATH" ]; then
    DATA_DIR=$(python3 -c "import json; print(json.load(open('$CONFIG_PATH')).get('data_dir', '/var/lib/uptime-monitor'))" 2>/dev/null || echo "/var/lib/uptime-monitor")
    CONFIG_DIR=$(dirname "$CONFIG_PATH")
else
    DATA_DIR="/var/lib/uptime-monitor"
    CONFIG_DIR="/etc/uptime-monitor"
fi

# Stop service
echo "Stopping uptime-monitor service..."
systemctl stop uptime-monitor || true

# Backup current state before restore
echo "Creating safety backup of current state..."
BACKUP_DIR="/tmp/uptime-pre-restore-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
[ -d "$DATA_DIR" ] && cp -r "$DATA_DIR" "$BACKUP_DIR/" 2>/dev/null || true
[ -f "$CONFIG_PATH" ] && cp "$CONFIG_PATH" "$BACKUP_DIR/" 2>/dev/null || true
echo "Safety backup saved to: $BACKUP_DIR"

# Restore database
echo "Restoring database..."
if [ -d "database" ] && [ -f "database/sites.db" ]; then
    mkdir -p "$DATA_DIR"
    cp "database/sites.db" "$DATA_DIR/"
    chown -R uptime-monitor:uptime-monitor "$DATA_DIR" 2>/dev/null || true
fi

# Restore configuration
echo "Restoring configuration..."
if [ -f "config/config.json" ]; then
    mkdir -p "$CONFIG_DIR"
    cp "config/config.json" "$CONFIG_PATH"
    chmod 600 "$CONFIG_PATH"
fi

# Restore SSL
echo "Restoring SSL certificates..."
if [ -d "ssl" ]; then
    cp -r "ssl" "$CONFIG_DIR/"
    chmod 600 "$CONFIG_DIR/ssl/"*.pem 2>/dev/null || true
fi

# Restore systemd service
echo "Restoring systemd service..."
if [ -f "systemd/uptime-monitor.service" ]; then
    cp "systemd/uptime-monitor.service" "/etc/systemd/system/"
    systemctl daemon-reload
fi

# Start service
echo "Starting service..."
systemctl start uptime-monitor

sleep 2

if systemctl is-active --quiet uptime-monitor; then
    echo ""
    echo "Restore completed successfully!"
    echo "Service is running."
    echo ""
    echo "If something went wrong, restore from safety backup:"
    echo "  $BACKUP_DIR"
else
    echo ""
    echo "Restore completed but service failed to start."
    echo "Check logs: sudo journalctl -u uptime-monitor -n 50"
    echo "Safety backup: $BACKUP_DIR"
fi
EOF
    chmod +x "$temp_dir/restore.sh"
    
    # Create compressed archive
    log "Creating compressed archive..."
    tar -czf "$backup_file" -C "$(dirname "$temp_dir")" "$(basename "$temp_dir")"
    
    # Cleanup temp directory
    rm -rf "$temp_dir"
    
    # Update current symlink
    ln -sf "$backup_file" "$dest/$backup_type/backup-current.tar.gz" 2>/dev/null || true
    
    # Verify if requested
    if [ "$verify" = "true" ]; then
        log "Verifying backup..."
        if tar -tzf "$backup_file" >/dev/null 2>&1; then
            log "${GREEN}Backup verified successfully${NC}"
        else
            log "${RED}Backup verification failed!${NC}"
            rm -f "$backup_file"
            exit 1
        fi
    fi
    
    # Get file size
    local size=$(du -h "$backup_file" | cut -f1)
    
    log "${GREEN}Backup completed: $backup_name.tar.gz ($size)${NC}"
    
    # Run rotation
    log "Running backup rotation..."
    "$(dirname "$0")/backup-rotation.sh" --dest "$dest" --quiet 2>/dev/null || true
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}   Backup Created Successfully!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "Type: ${BLUE}$backup_type${NC}"
    echo -e "File: ${BLUE}$backup_file${NC}"
    echo -e "Size: ${BLUE}$size${NC}"
    if [ -n "$comment" ]; then
        echo -e "Comment: ${BLUE}$comment${NC}"
    fi
    echo ""
    echo -e "To restore: ${YELLOW}sudo $(dirname "$0")/restore-system.sh --from $backup_file${NC}"
    echo ""
}

# Main
main() {
    local dest=""
    local backup_type="daily"
    local comment=""
    local verify="false"
    local show_status="false"
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dest)
                dest="$2"
                shift 2
                ;;
            --type)
                backup_type="$2"
                shift 2
                ;;
            --comment)
                comment="$2"
                shift 2
                ;;
            --verify)
                verify="true"
                shift
                ;;
            --status)
                show_status="true"
                shift
                ;;
            --now)
                backup_type="manual"
                comment="Manual backup"
                dest="${dest:-$DEFAULT_LOCAL_PATH}"
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
    
    # Show status if requested
    if [ "$show_status" = "true" ]; then
        show_status
        exit 0
    fi
    
    # Check destination
    if [ -z "$dest" ]; then
        log "${RED}Error: Backup destination not specified${NC}"
        log "Use --dest to specify backup location"
        echo ""
        show_help
        exit 1
    fi
    
    # Create backup
    create_backup "$dest" "$backup_type" "$comment" "$verify"
}

main "$@"
