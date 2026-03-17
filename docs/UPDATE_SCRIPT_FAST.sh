#!/bin/bash
# =============================================================================
# Uptime Monitor - Швидке оновлення (для тестових середовищ)
# =============================================================================
# УВАГА: Цей скрипт НЕ створює бекап автоматично!
# Використовуйте тільки на тестових середовищах.
# Для production використовуйте UPDATE_SCRIPT_SAFE.sh
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

SERVICE="uptime-monitor"
APP_DIR="/opt/uptime-monitor"

echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   Uptime Monitor - Швидке Оновлення (TEST ONLY)           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Перевірка sudo
if [ "$EUID" -ne 0 ]; then
    log_error "Запустіть з sudo"
    exit 1
fi

# Зупинка сервісу
log_info "Зупинка сервісу..."
systemctl stop $SERVICE
sleep 2

# Оновлення
cd "$APP_DIR"

if [ -d ".git" ]; then
    log_info "Git-інсталяція. Оновлення..."
    git fetch --all --prune
    git checkout main
    git pull --ff-only origin main
    log_success "Оновлено через git"
else
    log_warning "ZIP-інсталяція..."

    # Перевірка unzip
    if ! command -v unzip &> /dev/null; then
        log_error "unzip не встановлено! Виконайте: apt install -y unzip"
        exit 1
    fi

    cd /tmp

    # КРИТИЧНО: Видалити стару папку
    sudo rm -rf /tmp/Uptime-Monitor-APP-main

    wget -q https://github.com/ajjs1ajjs/Uptime-Monitor-APP/archive/refs/heads/main.zip -O uptime_update.zip

    # КРИТИЧНО: Розпакувати з sudo
    sudo unzip -o -q uptime_update.zip

    # Копіювання файлів
    sudo cp -r /tmp/Uptime-Monitor-APP-main/Uptime_Robot/* "$APP_DIR/"

    # Видалення тимчасових файлів
    sudo rm -rf uptime_update.zip /tmp/Uptime-Monitor-APP-main

    log_success "Оновлено через ZIP"
fi

# Запуск
log_info "Запуск сервісу..."
systemctl daemon-reload
systemctl start $SERVICE
sleep 3

# Перевірка
if systemctl is-active --quiet $SERVICE; then
    log_success "Сервіс запущено"
    PORT=$(grep -o '"port"[[:space:]]*:[[:space:]]*[0-9]*' /etc/uptime-monitor/config.json 2>/dev/null | grep -o '[0-9]*' || echo "8080")

    if curl -fsS --max-time 5 "http://localhost:$PORT" > /dev/null 2>&1; then
        log_success "HTTP OK"
    else
        log_warning "HTTP не відповідає"
    fi
else
    log_error "Сервіс не запустився!"
    exit 1
fi

echo ""
log_success "Оновлення завершено!"
echo ""
