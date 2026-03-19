#!/bin/bash
#
# Uptime Monitor - Backup Rotation
# Manages backup retention policy
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
Uptime Monitor Backup Rotation

Manages backup retention according to policy:
  - on-change: Keep last 10
  - daily: Keep last 7 days
  - weekly: Keep all (until monthly exists)
  - monthly: Keep all (until yearly exists)
  - yearly: Keep forever

Usage: $(basename "$0") [OPTIONS]

Options:
    --dest PATH              Backup destination path (default: $DEFAULT_BACKUP_PATH)
    --dry-run                Show what would be deleted without deleting
    --keep N                 Keep only N most recent backups (override policy)
    --quiet                  Minimal output
    --help, -h               Show this help message

Examples:
    # Run rotation with default settings
    sudo $(basename "$0")

    # Dry run (see what would be deleted)
    sudo $(basename "$0") --dry-run

    # Keep only last 5 backups
    sudo $(basename "$0") --keep 5

    # Specific destination
    sudo $(basename "$0") --dest /mnt/nfs-backup/uptime-monitor/

EOF
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

# Log function
log() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    if [ "$QUIET" != "true" ]; then
        echo -e "$message"
    fi
    
    echo "${timestamp} - $message" >> "$LOG_FILE" 2>/dev/null || true
}

# Rotate on-change backups
rotate_on_change() {
    local dir="$1"
    local max="$2"
    local dry_run="$3"
    
    if [ ! -d "$dir/on-change" ]; then
        return 0
    fi
    
    local count=$(find "$dir/on-change" -name "backup-*.tar.gz" -type f | wc -l)
    
    if [ "$count" -le "$max" ]; then
        return 0
    fi
    
    local to_delete=$((count - max))
    log "On-change backups: $count found, max $max, deleting $to_delete"
    
    # Get oldest backups
    find "$dir/on-change" -name "backup-*.tar.gz" -type f -printf '%T@ %p\n' | \
        sort -n | \
        head -n "$to_delete" | \
        while read -r line; do
            local file=$(echo "$line" | cut -d' ' -f2-)
            if [ "$dry_run" = "true" ]; then
                log "  ${YELLOW}[DRY-RUN] Would delete: $(basename "$file")${NC}"
            else
                rm -f "$file"
                log "  Deleted: $(basename "$file")"
            fi
        done
}

# Rotate daily backups
rotate_daily() {
    local dir="$1"
    local max="$2"
    local dry_run="$3"
    
    if [ ! -d "$dir/daily" ]; then
        return 0
    fi
    
    local count=$(find "$dir/daily" -name "backup-*.tar.gz" -type f | wc -l)
    
    if [ "$count" -le "$max" ]; then
        return 0
    fi
    
    local to_delete=$((count - max))
    log "Daily backups: $count found, max $max, deleting $to_delete"
    
    find "$dir/daily" -name "backup-*.tar.gz" -type f -printf '%T@ %p\n' | \
        sort -n | \
        head -n "$to_delete" | \
        while read -r line; do
            local file=$(echo "$line" | cut -d' ' -f2-)
            if [ "$dry_run" = "true" ]; then
                log "  ${YELLOW}[DRY-RUN] Would delete: $(basename "$file")${NC}"
            else
                rm -f "$file"
                log "  Deleted: $(basename "$file")"
            fi
        done
}

# Rotate weekly backups
rotate_weekly() {
    local dir="$1"
    local dry_run="$3"
    
    if [ ! -d "$dir/weekly" ]; then
        return 0
    fi
    
    local count=$(find "$dir/weekly" -name "backup-*.tar.gz" -type f | wc -l)
    log "Weekly backups: $count found (keeping all)"
    
    # Keep all weekly backups unless explicitly told to delete
    # They will be deleted only when monthly backups exist
}

# Rotate monthly backups
rotate_monthly() {
    local dir="$1"
    local dry_run="$3"
    
    if [ ! -d "$dir/monthly" ]; then
        return 0
    fi
    
    local count=$(find "$dir/monthly" -name "backup-*.tar.gz" -type f | wc -l)
    log "Monthly backups: $count found (keeping all)"
    
    # Keep all monthly backups
}

# Rotate yearly backups
rotate_yearly() {
    local dir="$1"
    local dry_run="$3"
    
    if [ ! -d "$dir/yearly" ]; then
        return 0
    fi
    
    local count=$(find "$dir/yearly" -name "backup-*.tar.gz" -type f | wc -l)
    log "Yearly backups: $count found (keeping forever)"
    
    # Keep all yearly backups forever
}

# Clean empty directories
clean_empty_dirs() {
    local dir="$1"
    local dry_run="$2"
    
    find "$dir" -type d -empty | while read -r empty_dir; do
        if [ "$dry_run" = "true" ]; then
            log "  ${YELLOW}[DRY-RUN] Would remove empty dir: $empty_dir${NC}"
        else
            rmdir "$empty_dir" 2>/dev/null || true
        fi
    done
}

# Main rotation function
run_rotation() {
    local dest="$1"
    local dry_run="$2"
    local keep_override="$3"
    
    if [ "$EUID" -ne 0 ]; then
        log "${RED}Error: Please run as root (use sudo)${NC}"
        exit 1
    fi
    
    if [ ! -d "$dest" ]; then
        log "${YELLOW}Backup directory not found: $dest${NC}"
        exit 0
    fi
    
    if [ "$dry_run" = "true" ]; then
        log "${BLUE}=== DRY RUN MODE (no files will be deleted) ===${NC}"
    fi
    
    log "${BLUE}Starting backup rotation...${NC}"
    log "Destination: $dest"
    
    # Get retention policy from config or use defaults
    local on_change_retention
    local daily_retention
    local weekly_retention
    local monthly_retention
    local yearly_retention
    
    if [ -n "$keep_override" ]; then
        on_change_retention="$keep_override"
        daily_retention="$keep_override"
        weekly_retention="$keep_override"
        monthly_retention="$keep_override"
        yearly_retention="$keep_override"
        log "Using override retention: $keep_override"
    else
        on_change_retention=$(get_config_value 'backup.retention.on_change' '10')
        daily_retention=$(get_config_value 'backup.retention.daily' '7')
        weekly_retention=$(get_config_value 'backup.retention.weekly' 'all')
        monthly_retention=$(get_config_value 'backup.retention.monthly' 'all')
        yearly_retention=$(get_config_value 'backup.retention.yearly' 'all')
        
        log "Retention policy:"
        log "  On-change: $on_change_retention"
        log "  Daily: $daily_retention"
        log "  Weekly: $weekly_retention"
        log "  Monthly: $monthly_retention"
        log "  Yearly: $yearly_retention"
    fi
    
    # Run rotations
    rotate_on_change "$dest" "$on_change_retention" "$dry_run"
    
    if [ "$daily_retention" != "all" ]; then
        rotate_daily "$dest" "$daily_retention" "$dry_run"
    fi
    
    if [ "$weekly_retention" != "all" ]; then
        rotate_weekly "$dest" "$dry_run"
    fi
    
    if [ "$monthly_retention" != "all" ]; then
        rotate_monthly "$dest" "$dry_run"
    fi
    
    if [ "$yearly_retention" != "all" ]; then
        rotate_yearly "$dest" "$dry_run"
    fi
    
    # Clean empty directories
    clean_empty_dirs "$dest" "$dry_run"
    
    if [ "$dry_run" = "true" ]; then
        log "${GREEN}Dry run completed. No files were deleted.${NC}"
    else
        log "${GREEN}Rotation completed.${NC}"
    fi
    
    # Show current stats
    if [ "$QUIET" != "true" ]; then
        echo ""
        echo -e "${BLUE}Current backup counts:${NC}"
        for type in on-change daily weekly monthly yearly; do
            if [ -d "$dest/$type" ]; then
                local count=$(find "$dest/$type" -name "backup-*.tar.gz" -type f | wc -l)
                echo "  $type: $count"
            fi
        done
        
        local total_size=$(du -sh "$dest" 2>/dev/null | cut -f1)
        echo ""
        echo -e "Total size: ${BLUE}$total_size${NC}"
    fi
}

# Main
main() {
    local dest="$DEFAULT_BACKUP_PATH"
    local dry_run="false"
    local keep_override=""
    QUIET="false"
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dest)
                dest="$2"
                shift 2
                ;;
            --dry-run)
                dry_run="true"
                shift
                ;;
            --keep)
                keep_override="$2"
                shift 2
                ;;
            --quiet)
                QUIET="true"
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
    
    run_rotation "$dest" "$dry_run" "$keep_override"
}

main "$@"
