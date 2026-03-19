#!/bin/bash
#
# Uptime Monitor - Schedule Backup
# Sets up automatic backup schedules via cron
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_DEST="/backup/uptime-monitor"
CRON_FILE="/etc/cron.d/uptime-monitor-backup"

# Show help
show_help() {
    cat << EOF
Uptime Monitor Backup Scheduler

Sets up automatic backup schedules using cron.

Usage: $(basename "$0") [OPTIONS]

Options:
    --install                Install cron jobs
    --remove                 Remove all cron jobs
    --status                 Show current schedule status
    --daily "CRON"           Daily backup schedule (default: "0 2 * * *")
    --weekly "CRON"          Weekly backup schedule (default: "0 3 * * 0")
    --monthly "CRON"         Monthly backup schedule (default: "0 4 1 * *")
    --dest PATH              Backup destination (default: $DEFAULT_DEST)
    --enable-nfs             Enable NFS backup (mount must be configured)
    --enable-smb             Enable Samba backup (mount must be configured)
    --test                   Test run backups now
    --help, -h               Show this help message

Cron Format:
    "minute hour day month weekday"
    Examples:
        "0 2 * * *"     - Daily at 2:00 AM
        "0 3 * * 0"     - Weekly on Sunday at 3:00 AM
        "0 4 1 * *"     - Monthly on 1st at 4:00 AM
        "*/30 * * * *"  - Every 30 minutes

Examples:
    # Install with defaults (daily at 2 AM)
    sudo $(basename "$0") --install

    # Install with custom schedule
    sudo $(basename "$0") --install --daily "0 3 * * *" --weekly "0 4 * * 0"

    # Install with NFS
    sudo $(basename "$0") --install --dest /mnt/nfs-backup/uptime-monitor/ --enable-nfs

    # Remove all schedules
    sudo $(basename "$0") --remove

    # Check status
    sudo $(basename "$0") --status

    # Test backups
    sudo $(basename "$0") --test

EOF
}

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}Error: Please run as root (use sudo)${NC}"
        exit 1
    fi
}

# Show current status
show_status() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}   Backup Schedule Status${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    if [ -f "$CRON_FILE" ]; then
        echo -e "${GREEN}Cron jobs installed:${NC}"
        echo ""
        cat "$CRON_FILE" | grep -v "^#" | grep -v "^$" | while read line; do
            if [ -n "$line" ]; then
                echo "  $line"
            fi
        done
        echo ""
        
        echo -e "${BLUE}Next scheduled runs:${NC}"
        echo "  Daily:   $(cat "$CRON_FILE" | grep 'daily' | awk '{print $1, $2, $3, $4, $5}')"
        echo "  Weekly:  $(cat "$CRON_FILE" | grep 'weekly' | awk '{print $1, $2, $3, $4, $5}')"
        echo "  Monthly: $(cat "$CRON_FILE" | grep 'monthly' | awk '{print $1, $2, $3, $4, $5}')"
    else
        echo -e "${YELLOW}No cron jobs installed.${NC}"
        echo ""
        echo "To install, run:"
        echo "  sudo $(basename "$0") --install"
    fi
    
    echo ""
    
    # Show cron service status
    if systemctl is-active --quiet cron 2>/dev/null || systemctl is-active --quiet crond 2>/dev/null; then
        echo -e "${GREEN}Cron service: Running${NC}"
    else
        echo -e "${YELLOW}Cron service: Not running${NC}"
        echo "Start with: sudo systemctl start cron"
    fi
    
    echo ""
}

# Install cron jobs
install_cron() {
    local daily="$1"
    local weekly="$2"
    local monthly="$3"
    local dest="$4"
    local enable_nfs="$5"
    local enable_smb="$6"
    
    check_root
    
    echo -e "${BLUE}Installing backup schedules...${NC}"
    
    # Create cron file
    cat > "$CRON_FILE" << EOF
# Uptime Monitor Backup Schedule
# Generated: $(date)
# Do not edit manually - use: $(basename "$0")

SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Daily backup
$daily root $SCRIPT_DIR/backup-system.sh --dest $dest --type daily >> /var/log/uptime-monitor/backup-cron.log 2>&1

# Weekly backup
$weekly root $SCRIPT_DIR/backup-system.sh --dest $dest --type weekly >> /var/log/uptime-monitor/backup-cron.log 2>&1

# Monthly backup
$monthly root $SCRIPT_DIR/backup-system.sh --dest $dest --type monthly >> /var/log/uptime-monitor/backup-cron.log 2>&1

# Run rotation after backups
$daily root $SCRIPT_DIR/backup-rotation.sh --dest $dest --quiet >> /var/log/uptime-monitor/backup-cron.log 2>&1
EOF
    
    # Add NFS backup if enabled
    if [ "$enable_nfs" = "true" ]; then
        echo "" >> "$CRON_FILE"
        echo "# NFS Backup (run after local backup)" >> "$CRON_FILE"
        echo "$daily root $SCRIPT_DIR/backup-system.sh --dest /mnt/nfs-backup/uptime-monitor/ --type daily >> /var/log/uptime-monitor/backup-cron.log 2>&1" >> "$CRON_FILE"
    fi
    
    # Add Samba backup if enabled
    if [ "$enable_smb" = "true" ]; then
        echo "" >> "$CRON_FILE"
        echo "# Samba Backup (run after local backup)" >> "$CRON_FILE"
        echo "$daily root $SCRIPT_DIR/backup-system.sh --dest /mnt/smb-backup/uptime-monitor/ --type daily >> /var/log/uptime-monitor/backup-cron.log 2>&1" >> "$CRON_FILE"
    fi
    
    # Set permissions
    chmod 644 "$CRON_FILE"
    
    # Ensure log directory exists
    mkdir -p /var/log/uptime-monitor
    touch /var/log/uptime-monitor/backup-cron.log
    
    echo -e "${GREEN}Cron jobs installed successfully!${NC}"
    echo ""
    echo -e "Configuration file: ${BLUE}$CRON_FILE${NC}"
    echo ""
    echo "Scheduled backups:"
    echo -e "  Daily:   ${YELLOW}$daily${NC}"
    echo -e "  Weekly:  ${YELLOW}$weekly${NC}"
    echo -e "  Monthly: ${YELLOW}$monthly${NC}"
    echo ""
    echo -e "Destination: ${BLUE}$dest${NC}"
    
    if [ "$enable_nfs" = "true" ]; then
        echo -e "NFS Backup: ${GREEN}Enabled${NC}"
    fi
    
    if [ "$enable_smb" = "true" ]; then
        echo -e "Samba Backup: ${GREEN}Enabled${NC}"
    fi
    
    echo ""
    echo "Logs: /var/log/uptime-monitor/backup-cron.log"
    echo ""
    echo -e "To test the backup now, run: ${YELLOW}sudo $(basename "$0") --test${NC}"
}

# Remove cron jobs
remove_cron() {
    check_root
    
    if [ -f "$CRON_FILE" ]; then
        rm -f "$CRON_FILE"
        echo -e "${GREEN}Backup schedules removed.${NC}"
    else
        echo -e "${YELLOW}No backup schedules found.${NC}"
    fi
}

# Test backups
test_backups() {
    echo -e "${BLUE}Testing backup system...${NC}"
    echo ""
    
    # Test local backup
    echo "1. Testing local backup..."
    $SCRIPT_DIR/backup-system.sh --dest "$DEFAULT_DEST" --type on-change --comment "Test backup" --verify
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Local backup test passed${NC}"
    else
        echo -e "${RED}✗ Local backup test failed${NC}"
    fi
    
    echo ""
    
    # Test NFS if mounted
    if [ -d "/mnt/nfs-backup" ] && mount | grep -q "/mnt/nfs-backup"; then
        echo "2. Testing NFS backup..."
        $SCRIPT_DIR/backup-system.sh --dest "/mnt/nfs-backup/uptime-monitor/" --type on-change --comment "Test NFS backup"
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ NFS backup test passed${NC}"
        else
            echo -e "${RED}✗ NFS backup test failed${NC}"
        fi
        echo ""
    fi
    
    # Test Samba if mounted
    if [ -d "/mnt/smb-backup" ] && mount | grep -q "/mnt/smb-backup"; then
        echo "3. Testing Samba backup..."
        $SCRIPT_DIR/backup-system.sh --dest "/mnt/smb-backup/uptime-monitor/" --type on-change --comment "Test Samba backup"
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Samba backup test passed${NC}"
        else
            echo -e "${RED}✗ Samba backup test failed${NC}"
        fi
        echo ""
    fi
    
    echo -e "${BLUE}Test completed!${NC}"
    echo ""
    echo "To view backups:"
    echo "  sudo $SCRIPT_DIR/backup-system.sh --status"
}

# Main
main() {
    local action=""
    local daily="0 2 * * *"
    local weekly="0 3 * * 0"
    local monthly="0 4 1 * *"
    local dest="$DEFAULT_DEST"
    local enable_nfs="false"
    local enable_smb="false"
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --install)
                action="install"
                shift
                ;;
            --remove)
                action="remove"
                shift
                ;;
            --status)
                action="status"
                shift
                ;;
            --test)
                action="test"
                shift
                ;;
            --daily)
                daily="$2"
                shift 2
                ;;
            --weekly)
                weekly="$2"
                shift 2
                ;;
            --monthly)
                monthly="$2"
                shift 2
                ;;
            --dest)
                dest="$2"
                shift 2
                ;;
            --enable-nfs)
                enable_nfs="true"
                shift
                ;;
            --enable-smb)
                enable_smb="true"
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
    
    # Execute action
    case "$action" in
        install)
            install_cron "$daily" "$weekly" "$monthly" "$dest" "$enable_nfs" "$enable_smb"
            ;;
        remove)
            remove_cron
            ;;
        status)
            show_status
            ;;
        test)
            test_backups
            ;;
        "")
            echo "No action specified."
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
