#!/bin/bash
#
# Uptime Monitor - Mount Backup Storage
# Mounts NFS or Samba shares for backups
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Show help
show_help() {
    cat << EOF
Uptime Monitor - Backup Storage Mount Utility

Mounts NFS or Samba shares for backup storage.

Usage: $(basename "$0") [OPTIONS]

Options:
    --type TYPE              Mount type: nfs, smb
    --server ADDRESS         Server address (IP or hostname)
    --path PATH              NFS export path (for NFS)
    --share SHARE            Share name (for Samba)
    --mount-point PATH       Local mount point
    --username USER          Username (for Samba)
    --password PASS          Password (for Samba)
    --domain DOMAIN          Domain (for Samba, default: WORKGROUP)
    --credentials FILE       Credentials file (for Samba)
    --persist                Add to /etc/fstab for auto-mount
    --unmount                Unmount instead of mount
    --test                   Test mount (mount, test, unmount)
    --help, -h               Show this help message

Examples:
    # Mount NFS
    sudo $(basename "$0") --type nfs \\
        --server 192.168.1.10 \\
        --path /exports/backups \\
        --mount-point /mnt/nfs-backup \\
        --persist

    # Mount Samba with password
    sudo $(basename "$0") --type smb \\
        --server 192.168.1.11 \\
        --share backups \\
        --mount-point /mnt/smb-backup \\
        --username backupuser \\
        --password secret \\
        --persist

    # Mount Samba with credentials file
    sudo $(basename "$0") --type smb \\
        --server nas.local \\
        --share backups \\
        --mount-point /mnt/smb-backup \\
        --credentials /root/.smb-credentials \\
        --persist

    # Unmount
    sudo $(basename "$0") --unmount --mount-point /mnt/nfs-backup

    # Test mount
    sudo $(basename "$0") --test --type nfs --server 192.168.1.10 --path /exports/backups

EOF
}

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}Error: Please run as root (use sudo)${NC}"
        exit 1
    fi
}

# Install required packages
install_packages() {
    local type="$1"
    
    echo -e "${BLUE}Checking required packages...${NC}"
    
    if [ "$type" = "nfs" ]; then
        if ! command -v mount.nfs &> /dev/null; then
            echo -e "${YELLOW}Installing NFS client...${NC}"
            apt-get update -qq
            apt-get install -y -qq nfs-common
        fi
    elif [ "$type" = "smb" ]; then
        if ! command -v mount.cifs &> /dev/null; then
            echo -e "${YELLOW}Installing Samba client...${NC}"
            apt-get update -qq
            apt-get install -y -qq cifs-utils
        fi
    fi
}

# Mount NFS
mount_nfs() {
    local server="$1"
    local path="$2"
    local mount_point="$3"
    local persist="$4"
    
    check_root
    install_packages "nfs"
    
    # Create mount point
    mkdir -p "$mount_point"
    
    # Check if already mounted
    if mount | grep -q "$mount_point"; then
        echo -e "${YELLOW}Already mounted at $mount_point${NC}"
        return 0
    fi
    
    # Mount
    echo -e "${BLUE}Mounting NFS share...${NC}"
    echo "  Server: $server"
    echo "  Path: $path"
    echo "  Mount point: $mount_point"
    
    if mount -t nfs "${server}:${path}" "$mount_point" -o vers=4,soft,intr; then
        echo -e "${GREEN}✓ NFS mounted successfully${NC}"
    else
        echo -e "${RED}✗ Failed to mount NFS${NC}"
        echo "Trying with NFS v3..."
        
        if mount -t nfs "${server}:${path}" "$mount_point" -o vers=3,soft,intr; then
            echo -e "${GREEN}✓ NFS mounted successfully (v3)${NC}"
        else
            echo -e "${RED}✗ Failed to mount NFS${NC}"
            exit 1
        fi
    fi
    
    # Create uptime-monitor subdirectory
    mkdir -p "$mount_point/uptime-monitor"
    
    # Add to fstab if requested
    if [ "$persist" = "true" ]; then
        add_to_fstab "nfs" "$server" "$path" "$mount_point"
    fi
    
    # Show usage
    echo ""
    echo -e "${BLUE}Usage:${NC}"
    echo "  Backup to NFS:"
    echo "    sudo /opt/uptime-monitor/scripts/backup-system.sh --dest $mount_point/uptime-monitor/"
    echo ""
    echo "  Schedule backups to NFS:"
    echo "    sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install --dest $mount_point/uptime-monitor/"
}

# Mount Samba
mount_smb() {
    local server="$1"
    local share="$2"
    local mount_point="$3"
    local username="$4"
    local password="$5"
    local domain="$6"
    local credentials="$7"
    local persist="$8"
    
    check_root
    install_packages "smb"
    
    # Create mount point
    mkdir -p "$mount_point"
    
    # Check if already mounted
    if mount | grep -q "$mount_point"; then
        echo -e "${YELLOW}Already mounted at $mount_point${NC}"
        return 0
    fi
    
    # Build mount options
    local mount_opts="uid=0,gid=0,iocharset=utf8,file_mode=0755,dir_mode=0755"
    
    if [ -n "$credentials" ] && [ -f "$credentials" ]; then
        mount_opts="$mount_opts,credentials=$credentials"
    elif [ -n "$username" ]; then
        mount_opts="$mount_opts,username=$username"
        if [ -n "$password" ]; then
            mount_opts="$mount_opts,password=$password"
        fi
        if [ -n "$domain" ]; then
            mount_opts="$mount_opts,domain=$domain"
        fi
    fi
    
    # Mount
    echo -e "${BLUE}Mounting Samba share...${NC}"
    echo "  Server: $server"
    echo "  Share: $share"
    echo "  Mount point: $mount_point"
    
    if mount -t cifs "//${server}/${share}" "$mount_point" -o "$mount_opts"; then
        echo -e "${GREEN}✓ Samba mounted successfully${NC}"
    else
        echo -e "${RED}✗ Failed to mount Samba share${NC}"
        exit 1
    fi
    
    # Create uptime-monitor subdirectory
    mkdir -p "$mount_point/uptime-monitor"
    
    # Add to fstab if requested
    if [ "$persist" = "true" ]; then
        # For fstab, we need credentials file for security
        local creds_file=""
        if [ -n "$credentials" ]; then
            creds_file="$credentials"
        elif [ -n "$username" ]; then
            # Create credentials file
            creds_file="/root/.uptime-smb-credentials"
            echo "username=$username" > "$creds_file"
            echo "password=$password" >> "$creds_file"
            if [ -n "$domain" ]; then
                echo "domain=$domain" >> "$creds_file"
            fi
            chmod 600 "$creds_file"
            echo -e "${YELLOW}Credentials saved to: $creds_file${NC}"
        fi
        
        add_to_fstab "smb" "$server" "$share" "$mount_point" "$creds_file"
    fi
    
    # Show usage
    echo ""
    echo -e "${BLUE}Usage:${NC}"
    echo "  Backup to Samba:"
    echo "    sudo /opt/uptime-monitor/scripts/backup-system.sh --dest $mount_point/uptime-monitor/"
    echo ""
    echo "  Schedule backups to Samba:"
    echo "    sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install --dest $mount_point/uptime-monitor/"
}

# Add to fstab
add_to_fstab() {
    local type="$1"
    local server="$2"
    local path="$3"
    local mount_point="$4"
    local creds="$5"
    
    echo -e "${BLUE}Adding to /etc/fstab...${NC}"
    
    # Backup fstab
    cp /etc/fstab "/etc/fstab.backup.$(date +%Y%m%d-%H%M%S)"
    
    # Remove existing entry if present
    grep -v " $mount_point " /etc/fstab > /tmp/fstab.tmp || true
    mv /tmp/fstab.tmp /etc/fstab
    
    # Add new entry
    if [ "$type" = "nfs" ]; then
        echo "${server}:${path} $mount_point nfs vers=4,soft,intr,_netdev 0 0" >> /etc/fstab
    elif [ "$type" = "smb" ]; then
        echo "//${server}/${path} $mount_point cifs credentials=$creds,uid=0,gid=0,iocharset=utf8,_netdev 0 0" >> /etc/fstab
    fi
    
    echo -e "${GREEN}✓ Added to fstab${NC}"
    echo "The mount will persist after reboot."
}

# Unmount
unmount_share() {
    local mount_point="$1"
    
    check_root
    
    if [ ! -d "$mount_point" ]; then
        echo -e "${RED}Mount point not found: $mount_point${NC}"
        exit 1
    fi
    
    if ! mount | grep -q "$mount_point"; then
        echo -e "${YELLOW}Not mounted: $mount_point${NC}"
        return 0
    fi
    
    echo -e "${BLUE}Unmounting $mount_point...${NC}"
    
    if umount "$mount_point"; then
        echo -e "${GREEN}✓ Unmounted successfully${NC}"
        
        # Remove from fstab
        grep -v " $mount_point " /etc/fstab > /tmp/fstab.tmp || true
        mv /tmp/fstab.tmp /etc/fstab
        echo -e "${GREEN}✓ Removed from fstab${NC}"
    else
        echo -e "${RED}✗ Failed to unmount${NC}"
        echo "Trying force unmount..."
        umount -f "$mount_point" || true
    fi
}

# Test mount
test_mount() {
    local type="$1"
    local server="$2"
    local path="$3"
    local share="$4"
    local username="$5"
    local password="$6"
    
    local test_mount_point="/tmp/test-backup-mount-$$"
    
    echo -e "${BLUE}Testing mount...${NC}"
    echo "This will mount, test, and unmount the share."
    echo ""
    
    # Mount
    if [ "$type" = "nfs" ]; then
        mount_nfs "$server" "$path" "$test_mount_point" "false"
    elif [ "$type" = "smb" ]; then
        mount_smb "$server" "$share" "$test_mount_point" "$username" "$password" "" "" "false"
    fi
    
    # Test write
    echo ""
    echo "Testing write access..."
    if touch "$test_mount_point/test-file-$$.tmp" 2>/dev/null; then
        rm -f "$test_mount_point/test-file-$$.tmp"
        echo -e "${GREEN}✓ Write test passed${NC}"
    else
        echo -e "${RED}✗ Write test failed${NC}"
    fi
    
    # Create uptime-monitor directory
    mkdir -p "$test_mount_point/uptime-monitor"
    
    # Test backup
    echo ""
    echo "Testing backup..."
    if /opt/uptime-monitor/scripts/backup-system.sh --dest "$test_mount_point/uptime-monitor/" --type on-change --comment "Test mount" --verify 2>/dev/null; then
        echo -e "${GREEN}✓ Backup test passed${NC}"
    else
        echo -e "${RED}✗ Backup test failed${NC}"
    fi
    
    # Unmount
    echo ""
    echo "Cleaning up..."
    umount "$test_mount_point" || umount -f "$test_mount_point" || true
    rmdir "$test_mount_point" 2>/dev/null || true
    
    echo ""
    echo -e "${GREEN}Test completed!${NC}"
}

# Main
main() {
    local action="mount"
    local type=""
    local server=""
    local path=""
    local share=""
    local mount_point=""
    local username=""
    local password=""
    local domain="WORKGROUP"
    local credentials=""
    local persist="false"
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --type)
                type="$2"
                shift 2
                ;;
            --server)
                server="$2"
                shift 2
                ;;
            --path)
                path="$2"
                shift 2
                ;;
            --share)
                share="$2"
                shift 2
                ;;
            --mount-point)
                mount_point="$2"
                shift 2
                ;;
            --username)
                username="$2"
                shift 2
                ;;
            --password)
                password="$2"
                shift 2
                ;;
            --domain)
                domain="$2"
                shift 2
                ;;
            --credentials)
                credentials="$2"
                shift 2
                ;;
            --persist)
                persist="true"
                shift
                ;;
            --unmount)
                action="unmount"
                shift
                ;;
            --test)
                action="test"
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
        mount)
            if [ -z "$type" ]; then
                echo -e "${RED}Error: Mount type not specified (--type nfs|smb)${NC}"
                exit 1
            fi
            
            if [ -z "$server" ]; then
                echo -e "${RED}Error: Server not specified (--server)${NC}"
                exit 1
            fi
            
            if [ -z "$mount_point" ]; then
                # Use default mount points
                if [ "$type" = "nfs" ]; then
                    mount_point="/mnt/nfs-backup"
                elif [ "$type" = "smb" ]; then
                    mount_point="/mnt/smb-backup"
                fi
                echo -e "${YELLOW}Using default mount point: $mount_point${NC}"
            fi
            
            if [ "$type" = "nfs" ]; then
                if [ -z "$path" ]; then
                    echo -e "${RED}Error: NFS path not specified (--path)${NC}"
                    exit 1
                fi
                mount_nfs "$server" "$path" "$mount_point" "$persist"
            elif [ "$type" = "smb" ]; then
                if [ -z "$share" ]; then
                    echo -e "${RED}Error: Samba share not specified (--share)${NC}"
                    exit 1
                fi
                mount_smb "$server" "$share" "$mount_point" "$username" "$password" "$domain" "$credentials" "$persist"
            else
                echo -e "${RED}Error: Unknown type: $type (use nfs or smb)${NC}"
                exit 1
            fi
            ;;
        unmount)
            if [ -z "$mount_point" ]; then
                echo -e "${RED}Error: Mount point not specified (--mount-point)${NC}"
                exit 1
            fi
            unmount_share "$mount_point"
            ;;
        test)
            if [ -z "$type" ]; then
                echo -e "${RED}Error: Mount type not specified (--type)${NC}"
                exit 1
            fi
            test_mount "$type" "$server" "$path" "$share" "$username" "$password"
            ;;
    esac
}

main "$@"
