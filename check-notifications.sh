#!/bin/bash
# Script to diagnose notification issues in Uptime Monitor
# Usage: sudo ./check-notifications.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Uptime Monitor - Notification Check${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Find installation directory
INSTALL_DIR="/opt/uptime-monitor"
if [ ! -d "$INSTALL_DIR" ]; then
    INSTALL_DIR=$(find /opt -name "main.py" -path "*/Uptime_Robot/*" 2>/dev/null | head -1 | xargs dirname 2>/dev/null || echo "")
    if [ -z "$INSTALL_DIR" ]; then
        echo -e "${RED}Error: Cannot find Uptime Monitor installation${NC}"
        exit 1
    fi
fi

CONFIG_PATH="/etc/uptime-monitor/config.json"
DATA_DIR=$(python3 -c "import json; print(json.load(open('$CONFIG_PATH')).get('data_dir', '/var/lib/uptime-monitor'))" 2>/dev/null || echo "/var/lib/uptime-monitor")
DB_PATH="$DATA_DIR/sites.db"

echo -e "${GREEN}✓ Installation Directory:${NC} $INSTALL_DIR"
echo -e "${GREEN}✓ Database Path:${NC} $DB_PATH"
echo ""

# 1. Check service status
echo -e "${YELLOW}[1/6] Checking service status...${NC}"
systemctl is-active --quiet uptime-monitor && echo -e "${GREEN}✓ uptime-monitor.service is ACTIVE${NC}" || echo -e "${RED}✗ uptime-monitor.service is NOT ACTIVE${NC}"
systemctl is-active --quiet uptime-monitor-worker && echo -e "${GREEN}✓ uptime-monitor-worker.service is ACTIVE${NC}" || echo -e "${YELLOW}! uptime-monitor-worker.service is NOT ACTIVE (may be OK if using integrated mode)${NC}"
echo ""

# 2. Check database notification settings
echo -e "${YELLOW}[2/6] Checking notification settings in database...${NC}"
if [ -f "$DB_PATH" ]; then
    NOTIFY_CONFIG=$(sqlite3 "$DB_PATH" "SELECT config FROM notify_config WHERE id = 1;" 2>/dev/null || echo "")
    if [ -n "$NOTIFY_CONFIG" ]; then
        echo -e "${GREEN}✓ Notification config found in database:${NC}"
        echo "$NOTIFY_CONFIG" | python3 -m json.tool 2>/dev/null || echo "$NOTIFY_CONFIG"

        # Check if Telegram is enabled
        TELEGRAM_ENABLED=$(echo "$NOTIFY_CONFIG" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('telegram',{}).get('enabled',False))" 2>/dev/null || echo "False")
        if [ "$TELEGRAM_ENABLED" = "True" ]; then
            echo -e "${GREEN}✓ Telegram is ENABLED${NC}"

            # Check for channels
            TELEGRAM_CHANNELS=$(echo "$NOTIFY_CONFIG" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('telegram',{}).get('channels',[])))" 2>/dev/null || echo "0")
            if [ "$TELEGRAM_CHANNELS" -gt 0 ]; then
                echo -e "${GREEN}✓ Found $TELEGRAM_CHANNELS Telegram channel(s)${NC}"

                # Check if channels have credentials
                EMPTY_CHANNELS=$(echo "$NOTIFY_CONFIG" | python3 -c "
import sys,json
d=json.load(sys.stdin)
channels = d.get('telegram',{}).get('channels',[])
empty = sum(1 for c in channels if not c.get('token') or not c.get('chat_id'))
print(empty)
" 2>/dev/null || echo "0")
                if [ "$EMPTY_CHANNELS" -gt 0 ]; then
                    echo -e "${RED}✗ $EMPTY_CHANNELS channel(s) have NO token or chat_id!${NC}"
                else
                    echo -e "${GREEN}✓ All channels have credentials${NC}"
                fi
            else
                echo -e "${RED}✗ No Telegram channels configured!${NC}"
            fi
        else
            echo -e "${YELLOW}! Telegram is DISABLED${NC}"
        fi
    else
        echo -e "${RED}✗ No notification config in database!${NC}"
        echo -e "${YELLOW}Configure notifications via Web UI first${NC}"
    fi
else
    echo -e "${RED}✗ Database file not found: $DB_PATH${NC}"
fi
echo ""

# 3. Check recent logs for notification errors
echo -e "${YELLOW}[3/6] Checking recent logs for notification activity...${NC}"
echo -e "${BLUE}Last 20 log entries with 'telegram', 'notification', or 'error':${NC}"
journalctl -u uptime-monitor --since "2 hours ago" --no-pager -n 100 2>/dev/null | grep -iE "telegram|notification|error|send" | tail -20 || echo -e "${YELLOW}No matching log entries found${NC}"
echo ""

# 4. Check if monitor loop is running
echo -e "${YELLOW}[4/6] Checking monitoring process...${NC}"
if pgrep -f "python.*main.py" > /dev/null; then
    echo -e "${GREEN}✓ Main web process is running${NC}"
    MONITOR_PID=$(pgrep -f "python.*main.py")
    echo -e "${BLUE}  PID: $MONITOR_PID${NC}"

    # Check if monitoring thread is active (look for monitor_loop in stack)
    if ps -T -p $MONITOR_PID 2>/dev/null | grep -q .; then
        THREAD_COUNT=$(ps -T -p $MONITOR_PID 2>/dev/null | wc -l)
        echo -e "${BLUE}  Threads: $((THREAD_COUNT - 1))${NC}"
    fi
else
    echo -e "${RED}✗ Main process is NOT running!${NC}"
fi

if pgrep -f "python.*worker.py" > /dev/null; then
    echo -e "${GREEN}✓ Worker process is running${NC}"
    WORKER_PID=$(pgrep -f "python.*worker.py")
    echo -e "${BLUE}  PID: $WORKER_PID${NC}"
else
    echo -e "${YELLOW}! Worker process is NOT running (may be OK if using integrated mode)${NC}"
fi
echo ""

# 5. Check active sites and their notification methods
echo -e "${YELLOW}[5/6] Checking sites and their notification methods...${NC}"
if [ -f "$DB_PATH" ]; then
    SITES_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM sites WHERE is_active = 1;" 2>/dev/null || echo "0")
    echo -e "${BLUE}Active sites: $SITES_COUNT${NC}"

    if [ "$SITES_COUNT" -gt 0 ]; then
        echo -e "${BLUE}Sites with notification methods:${NC}"
        sqlite3 "$DB_PATH" "SELECT name, notify_methods FROM sites WHERE is_active = 1;" 2>/dev/null | while IFS='|' read -r name methods; do
            if [ -n "$methods" ] && [ "$methods" != "[]" ]; then
                echo -e "  ${GREEN}✓${NC} $name: $methods"
            else
                echo -e "  ${YELLOW}!${NC} $name: NO notification methods"
            fi
        done
    fi
fi
echo ""

# 6. Test notification endpoint (if web UI is accessible)
echo -e "${YELLOW}[6/6] Checking web UI accessibility...${NC}"
PORT=$(python3 -c "import json; print(json.load(open('$CONFIG_PATH')).get('server',{}).get('port',8080))" 2>/dev/null || echo "8080")
if curl -s --max-time 5 "http://localhost:$PORT/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Web UI is accessible on port $PORT${NC}"
    echo -e "${BLUE}  Health: $(curl -s "http://localhost:$PORT/health" 2>/dev/null)${NC}"
else
    echo -e "${RED}✗ Web UI is NOT accessible on port $PORT${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Summary & Recommendations${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if ! systemctl is-active --quiet uptime-monitor; then
    echo -e "${RED}⚠ CRITICAL: uptime-monitor service is not running!${NC}"
    echo -e "${YELLOW}  Fix: sudo systemctl start uptime-monitor${NC}"
    echo ""
fi

if [ -z "$NOTIFY_CONFIG" ]; then
    echo -e "${YELLOW}⚠ No notification configuration found!${NC}"
    echo -e "${YELLOW}  Fix: Configure notifications via Web UI (Settings → Notifications)${NC}"
    echo ""
fi

if [ "$TELEGRAM_ENABLED" = "True" ] && [ "$EMPTY_CHANNELS" -gt 0 ]; then
    echo -e "${RED}⚠ Telegram channels are missing credentials!${NC}"
    echo -e "${YELLOW}  Fix: Re-enter Telegram Bot Token and Chat ID in Web UI${NC}"
    echo ""
fi

echo -e "${BLUE}To restart services:${NC}"
echo "  sudo systemctl restart uptime-monitor"
echo "  sudo systemctl restart uptime-monitor-worker  # if using separate worker"
echo ""
echo -e "${BLUE}To view live logs:${NC}"
echo "  sudo journalctl -u uptime-monitor -f"
echo ""
echo -e "${BLUE}To manually trigger a site check:${NC}"
echo "  curl -X POST http://localhost:$PORT/api/sites/{site_id}/check -H 'Authorization: Bearer YOUR_TOKEN'"
echo ""
