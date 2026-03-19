#!/bin/bash
#
# Uptime Monitor - Verify Backup
# Verifies backup archive integrity
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default paths
DEFAULT_BACKUP_PATH="/backup/uptime-monitor"

# Show help
show_help() {
    cat << EOF
Uptime Monitor Backup Verification

Verifies backup archive integrity and contents.

Usage: $(basename "$0") [OPTIONS]

Options:
    BACKUP_FILE              Specific backup file to verify
    --all                    Verify all backups in default location
    --dest PATH              Verify backups in specific location
    --list                   List backup statistics
    --quiet                  Minimal output
    --help, -h               Show this help message

Examples:
    # Verify specific backup
    sudo $(basename "$0") /backup/uptime-monitor/daily/backup-20260218-020000.tar.gz

    # Verify all backups
    sudo $(basename "$0") --all

    # List statistics
    sudo $(basename "$0") --list

    # Verify with specific destination
    sudo $(basename "$0") --dest /mnt/nfs-backup/uptime-monitor/ --all

Exit Codes:
    0 - All verifications passed
    1 - One or more verifications failed

EOF
}

# Verify single backup
verify_backup() {
    local backup_file="$1"
    local quiet="$2"
    
    if [ ! -f "$backup_file" ]; then
        [ "$quiet" != "true" ] && echo -e "${RED}✗ Not found: $(basename "$backup_file")${NC}"
        return 1
    fi
    
    local filename=$(basename "$backup_file")
    local size=$(du -h "$backup_file" | cut -f1)
    
    [ "$quiet" != "true" ] && echo -n "Verifying $filename ($size)... "
    
    # Test archive integrity
    if ! tar -tzf "$backup_file" > /dev/null 2>&1; then
        [ "$quiet" != "true" ] && echo -e "${RED}FAILED${NC}"
        return 1
    fi
    
    # Check for essential files. Avoid grep -c with "|| echo 0" because
    # that can produce "0\n0" and break numeric comparisons.
    local has_metadata=0
    local has_database=0
    local has_config=0

    if tar -tzf "$backup_file" | grep -q "metadata.json"; then
        has_metadata=1
    fi

    if tar -tzf "$backup_file" | grep -q "database/sites.db"; then
        has_database=1
    fi

    if tar -tzf "$backup_file" | grep -q "config/config.json"; then
        has_config=1
    fi
    
    if [ "$has_metadata" -eq 0 ]; then
        [ "$quiet" != "true" ] && echo -e "${YELLOW}WARNING${NC} - Missing metadata"
    fi
    
    if [ "$has_database" -eq 0 ]; then
        [ "$quiet" != "true" ] && echo -e "${YELLOW}WARNING${NC} - Missing database"
    fi
    
    if [ "$has_config" -eq 0 ]; then
        [ "$quiet" != "true" ] && echo -e "${YELLOW}WARNING${NC} - Missing config"
    fi
    
    [ "$quiet" != "true" ] && echo -e "${GREEN}OK${NC}"
    
    return 0
}

# Verify all backups
verify_all() {
    local dest="$1"
    local quiet="$2"
    local failed=0
    local total=0
    
    if [ ! -d "$dest" ]; then
        echo -e "${RED}Error: Backup directory not found: $dest${NC}"
        exit 1
    fi
    
    [ "$quiet" != "true" ] && echo -e "${BLUE}Verifying all backups in $dest...${NC}"
    [ "$quiet" != "true" ] && echo ""
    
    # Find all backup files
    while IFS= read -r backup_file; do
        total=$((total + 1))
        
        if ! verify_backup "$backup_file" "$quiet"; then
            failed=$((failed + 1))
        fi
    done < <(find "$dest" -name "backup-*.tar.gz" -type f 2>/dev/null)
    
    [ "$quiet" != "true" ] && echo ""
    [ "$quiet" != "true" ] && echo "Total: $total, Failed: $failed"
    
    if [ $failed -gt 0 ]; then
        return 1
    else
        return 0
    fi
}

# List backup statistics
list_stats() {
    local dest="${1:-$DEFAULT_BACKUP_PATH}"
    
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}   Backup Statistics${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    if [ ! -d "$dest" ]; then
        echo -e "${RED}Backup directory not found: $dest${NC}"
        return 1
    fi
    
    local total_backups=0
    local total_size=0
    local oldest_backup=""
    local newest_backup=""
    
    echo -e "${GREEN}Backup Types:${NC}"
    
    for type in on-change daily weekly monthly yearly; do
        if [ -d "$dest/$type" ]; then
            local count=$(find "$dest/$type" -name "backup-*.tar.gz" -type f | wc -l)
            local size=$(find "$dest/$type" -name "backup-*.tar.gz" -type f -exec du -ch {} + 2>/dev/null | tail -1 | cut -f1)
            
            total_backups=$((total_backups + count))
            
            printf "  %-10s: %3d backups (%s)\n" "$type" "$count" "$size"
            
            # Track oldest/newest
            local type_newest=$(find "$dest/$type" -name "backup-*.tar.gz" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
            local type_oldest=$(find "$dest/$type" -name "backup-*.tar.gz" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | head -1 | cut -d' ' -f2-)
            
            if [ -n "$type_newest" ]; then
                if [ -z "$newest_backup" ] || [ "$type_newest" -nt "$newest_backup" ]; then
                    newest_backup="$type_newest"
                fi
            fi
            
            if [ -n "$type_oldest" ]; then
                if [ -z "$oldest_backup" ] || [ "$type_oldest" -ot "$oldest_backup" ]; then
                    oldest_backup="$type_oldest"
                fi
            fi
        fi
    done
    
    echo ""
    echo -e "${GREEN}Summary:${NC}"
    echo "  Total backups: $total_backups"
    
    local total_size=$(du -sh "$dest" 2>/dev/null | cut -f1)
    echo "  Total size: $total_size"
    
    if [ -n "$oldest_backup" ]; then
        local oldest_date=$(stat -c %y "$oldest_backup" 2>/dev/null | cut -d' ' -f1)
        echo "  Oldest backup: $oldest_date ($(basename "$oldest_backup"))"
    fi
    
    if [ -n "$newest_backup" ]; then
        local newest_date=$(stat -c %y "$newest_backup" 2>/dev/null | cut -d' ' -f1)
        echo "  Newest backup: $newest_date ($(basename "$newest_backup"))"
    fi
    
    echo ""
}

# Main
main() {
    local backup_file=""
    local verify_all_backups="false"
    local dest="$DEFAULT_BACKUP_PATH"
    local show_stats="false"
    local quiet="false"
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --all)
                verify_all_backups="true"
                shift
                ;;
            --dest)
                dest="$2"
                shift 2
                ;;
            --list)
                show_stats="true"
                shift
                ;;
            --quiet)
                quiet="true"
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            -*)
                echo "Unknown option: $1"
                show_help
                exit 1
                ;;
            *)
                backup_file="$1"
                shift
                ;;
        esac
    done
    
    # Show stats
    if [ "$show_stats" = "true" ]; then
        list_stats "$dest"
        exit 0
    fi
    
    # Verify single backup
    if [ -n "$backup_file" ]; then
        verify_backup "$backup_file" "$quiet"
        exit $?
    fi
    
    # Verify all
    if [ "$verify_all_backups" = "true" ]; then
        if verify_all "$dest" "$quiet"; then
            [ "$quiet" != "true" ] && echo -e "${GREEN}All backups verified successfully!${NC}"
            exit 0
        else
            [ "$quiet" != "true" ] && echo -e "${RED}Some backups failed verification!${NC}"
            exit 1
        fi
    fi
    
    # No action specified
    show_help
    exit 1
}

main "$@"
