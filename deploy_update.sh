#!/bin/bash

# =============================================================================
# Uptime Monitor - Enterprise Safe Deployment Script
# =============================================================================
# Features:
#   - Pre-update full system backup
#   - Git-based or ZIP-based update
#   - Post-update health verification
#   - One-command rollback
#   - Change log tracking
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Color constants
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# Configuration — override via environment variables
# ---------------------------------------------------------------------------
INSTALL_DIR="${INSTALL_DIR:-/opt/uptime-monitor}"
SERVICE_NAME="${SERVICE_NAME:-uptime-monitor}"
WORKER_NAME="${WORKER_NAME:-uptime-monitor-worker}"
APP_USER="${APP_USER:-uptime-monitor}"
APP_GROUP="${APP_GROUP:-uptime-monitor}"
BACKUP_ROOT="${BACKUP_ROOT:-/backup/uptime-monitor}"
LOG_FILE="${LOG_FILE:-/var/log/uptime-monitor/deploy.log}"
CONFIG_FILE="${CONFIG_FILE:-/etc/uptime-monitor/config.json}"
DB_PATH="${DB_PATH:-/var/lib/uptime-monitor/sites.db}"
HEALTH_CHECK_URL="${HEALTH_CHECK_URL:-http://localhost:8080/health}"
GIT_REMOTE="${GIT_REMOTE:-origin}"
GIT_BRANCH="${GIT_BRANCH:-main}"
BACKUP_SCRIPT="${BACKUP_SCRIPT:-$INSTALL_DIR/scripts/backup-system.sh}"
RESTORE_SCRIPT="${RESTORE_SCRIPT:-$INSTALL_DIR/scripts/restore-system.sh}"

TS=$(date +%Y%m%d-%H%M%S)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()    { echo -e "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG_FILE"; }
info()   { log "${GREEN}[INFO]${NC} $*"; }
warn()   { log "${YELLOW}[WARN]${NC} $*"; }
error()  { log "${RED}[ERROR]${NC} $*"; }
header() { echo ""; echo -e "${BLUE}========================================${NC}"; echo -e "${BLUE}  $*${NC}"; echo -e "${BLUE}========================================${NC}"; }

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
preflight_check() {
    header "Pre-flight Checks"

    if [ "$EUID" -ne 0 ]; then
        error "Please run with sudo"
        exit 1
    fi

    for cmd in systemctl curl; do
        if ! command -v "$cmd" &>/dev/null; then
            error "Required command not found: $cmd"
            exit 1
        fi
    done

    mkdir -p "$(dirname "$LOG_FILE")" "$BACKUP_ROOT"

    info "Install dir: $INSTALL_DIR"
    info "App user:    $APP_USER"
    info "Backup root: $BACKUP_ROOT"
    info "Config:      $CONFIG_FILE"
    info "DB:          $DB_PATH"

    if [ ! -d "$INSTALL_DIR" ]; then
        error "Install directory does not exist: $INSTALL_DIR"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Step 1: Pre-update backup
# ---------------------------------------------------------------------------
step_backup() {
    header "Step 1/5: Pre-update Backup"

    if [ -x "$BACKUP_SCRIPT" ]; then
        info "Creating system backup..."
        "$BACKUP_SCRIPT" \
            --dest "$BACKUP_ROOT" \
            --type full \
            --comment "pre-update-$TS" \
            --verify || warn "System backup reported issues (non-fatal)"
    else
        warn "backup-system.sh not found at $BACKUP_SCRIPT — creating manual backup"
    fi

    info "Backing up config and database..."
    cp "$CONFIG_FILE" "$BACKUP_ROOT/config.pre-update.$TS.json" 2>/dev/null || warn "Config backup skipped (no config at $CONFIG_FILE)"
    if [ -f "$DB_PATH" ]; then
        cp "$DB_PATH" "$BACKUP_ROOT/sites.pre-update.$TS.db" || warn "DB backup failed"
    fi

    for unit in "$SERVICE_NAME" "$WORKER_NAME"; do
        cp "/etc/systemd/system/${unit}.service" "$BACKUP_ROOT/${unit}.service.pre-update.$TS" 2>/dev/null || true
    done

    local pre_commit
    pre_commit=$(cd "$INSTALL_DIR" && git log -1 --oneline 2>/dev/null || echo "no-git")
    echo "$pre_commit" > "$BACKUP_ROOT/pre-update-commit.$TS.txt"

    info "Backup completed: $BACKUP_ROOT/pre-update-$TS*"
}

# ---------------------------------------------------------------------------
# Step 2: Stop services
# ---------------------------------------------------------------------------
step_stop_services() {
    header "Step 2/5: Stopping Services"

    for unit in "$SERVICE_NAME" "$WORKER_NAME"; do
        if systemctl is-active --quiet "$unit" 2>/dev/null; then
            info "Stopping $unit..."
            systemctl stop "$unit"
        else
            info "$unit is not running"
        fi
    done
    sleep 2
}

# ---------------------------------------------------------------------------
# Step 3: Update code
# ---------------------------------------------------------------------------
step_update_code() {
    header "Step 3/5: Updating Code"

    cd "$INSTALL_DIR"

    if [ -d ".git" ]; then
        info "Git repository detected — pulling $GIT_REMOTE/$GIT_BRANCH..."
        
        git fetch --all --prune
        git checkout "$GIT_BRANCH"
        git pull --ff-only "$GIT_REMOTE" "$GIT_BRANCH"

        info "Setting ownership to $APP_USER:$APP_GROUP..."
        chown -R "$APP_USER:$APP_GROUP" "$INSTALL_DIR"

        local new_commit
        new_commit=$(git log -1 --oneline)
        info "Updated to: $new_commit"
        echo "$new_commit" > "$BACKUP_ROOT/post-update-commit.$TS.txt"
    else
        warn "No .git directory — using ZIP fallback"
        if ! command -v unzip &>/dev/null; then
            apt update && apt install -y unzip
        fi

        local tmp_dir
        tmp_dir=$(mktemp -d)
        local zip_file="$tmp_dir/uptime_update.zip"

        cd "$tmp_dir"
        wget -q "https://github.com/ajjs1ajjs/Uptime-Monitor/archive/refs/heads/main.zip" -O "$zip_file"
        unzip -o "$zip_file"
        cp -r Uptime-Monitor-main/Uptime_Robot/* "$INSTALL_DIR/"
        chown -R "$APP_USER:$APP_GROUP" "$INSTALL_DIR"
        rm -rf "$tmp_dir"
        info "ZIP update completed"
    fi

    info "Cleaning old compiled files..."
    find "$INSTALL_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find "$INSTALL_DIR" -name "*.pyc" -delete 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# Step 4: Restart services
# ---------------------------------------------------------------------------
step_start_services() {
    header "Step 4/5: Starting Services"

    systemctl daemon-reload

    systemctl start "$SERVICE_NAME"
    info "$SERVICE_NAME started"

    systemctl start "$WORKER_NAME"
    info "$WORKER_NAME started"

    sleep 3
}

# ---------------------------------------------------------------------------
# Step 5: Verification
# ---------------------------------------------------------------------------
step_verify() {
    header "Step 5/5: Verification"

    local failed=0

    # Service status
    for unit in "$SERVICE_NAME" "$WORKER_NAME"; do
        if systemctl is-active --quiet "$unit"; then
            info "✓ $unit is running"
        else
            error "✗ $unit is NOT running"
            failed=1
        fi
        systemctl status "$unit" --no-pager -n 3
    done

    # Health check
    if curl -fsS "$HEALTH_CHECK_URL" >/dev/null 2>&1; then
        info "✓ Health check passed ($HEALTH_CHECK_URL)"
    else
        error "✗ Health check FAILED ($HEALTH_CHECK_URL)"
        failed=1
    fi

    # Recent logs
    info "Recent service logs (last 20 lines):"
    journalctl -u "$SERVICE_NAME" -n 20 --no-pager || true

    if [ $failed -eq 0 ]; then
        header "✓ DEPLOYMENT COMPLETED SUCCESSFULLY"
        info "Timestamp: $TS"
        info "Rollback available at: $BACKUP_ROOT/pre-update-$TS*"
        exit 0
    else
        header "⚠ DEPLOYMENT COMPLETED WITH ISSUES"
        warn "Some checks failed — review logs above"
        warn "Run with --rollback to revert"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------
do_rollback() {
    header "Rollback Procedure"

    local latest_snap
    latest_snap=$(ls -t "$BACKUP_ROOT"/sites.pre-update.*.db 2>/dev/null | head -1)

    if [ -n "$latest_snap" ]; then
        info "Found backup snapshot: $latest_snap"
    else
        warn "No database backup found — proceeding with code rollback only"
    fi

    # Try git rollback first
    cd "$INSTALL_DIR"
    if [ -d ".git" ]; then
        info "Rolling back via git..."
        git reset --hard HEAD@{1} || git reset --hard "HEAD~1" || warn "Git rollback failed"
        chown -R "$APP_USER:$APP_GROUP" "$INSTALL_DIR"
    fi

    # Restore DB if we have a backup
    if [ -n "$latest_snap" ] && [ -f "$latest_snap" ]; then
        systemctl stop "$SERVICE_NAME" "$WORKER_NAME" 2>/dev/null || true
        cp "$latest_snap" "$DB_PATH"
        chown "$APP_USER:$APP_GROUP" "$DB_PATH" 2>/dev/null || true
        info "Database restored from: $latest_snap"
    fi

    systemctl daemon-reload
    systemctl start "$SERVICE_NAME" "$WORKER_NAME"
    sleep 3

    info "Rollback complete. Verifying..."
    step_verify
}

# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------
usage() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  (none)       Run full deployment (backup → update → restart → verify)"
    echo "  --status     Check service and health status"
    echo "  --rollback   Rollback to previous version (code + DB)"
    echo "  --logs       Show recent service logs"
    echo "  --backup     Backup only (skip update)"
    echo "  --help       Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  INSTALL_DIR    Application directory (default: /opt/uptime-monitor)"
    echo "  APP_USER       System user (default: uptime-monitor)"
    echo "  BACKUP_ROOT    Backup storage path (default: /backup/uptime-monitor)"
    echo "  HEALTH_CHECK_URL  Health endpoint (default: http://localhost:8080/health)"
}

case "${1:-}" in
    --status)
        header "Service Status"
        systemctl status "$SERVICE_NAME" "$WORKER_NAME" --no-pager
        echo ""
        curl -s "$HEALTH_CHECK_URL" | python3 -m json.tool 2>/dev/null || echo "Health check unavailable"
        ;;
    --rollback)
        do_rollback
        ;;
    --logs)
        journalctl -u "$SERVICE_NAME" -n 50 --no-pager
        ;;
    --backup)
        preflight_check
        step_backup
        info "Backup only — no changes applied"
        ;;
    --help|-h)
        usage
        ;;
    "")
        preflight_check
        step_backup
        step_stop_services
        step_update_code
        step_start_services
        step_verify
        ;;
    *)
        error "Unknown option: $1"
        usage
        exit 1
        ;;
esac
