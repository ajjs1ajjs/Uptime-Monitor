#!/bin/bash
# =============================================================================
# Uptime Monitor - Безпечне оновлення (Production Ready)
# =============================================================================
# Цей скрипт виконує повне безпечне оновлення з:
# - Перевіркою поточного стану
# - Обов'язковим pre-update backup
# - Автоматичним визначенням методу оновлення (git/zip)
# - Перевіркою після оновлення
# - Швидким rollback при проблемах
# =============================================================================

set -e  # Зупинити при помилці

# Кольори для виводу
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функції для виводу
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# =============================================================================
# 1. Змінні
# =============================================================================
SERVICE="uptime-monitor"
APP_DIR="/opt/uptime-monitor"
BACKUP_ROOT="/backup/uptime-monitor"
TS=$(date +%Y%m%d-%H%M%S)
BACKUP_COMMENT="pre-update-$TS"

echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   Uptime Monitor - Безпечне Оновлення                     ║"
echo "║   Timestamp: $TS                                  ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# =============================================================================
# 2. Перевірка прав sudo
# =============================================================================
if [ "$EUID" -ne 0 ]; then
    log_error "Будь ласка, запустіть з sudo"
    exit 1
fi

# =============================================================================
# 3. Перевірка поточного стану сервісу
# =============================================================================
log_info "Крок 1/8: Перевірка поточного стану сервісу..."

if systemctl is-active --quiet $SERVICE; then
    log_success "Сервіс активний"
    systemctl status $SERVICE --no-pager | head -10
else
    log_warning "Сервіс не активний"
fi

log_info "Останні логи:"
journalctl -u $SERVICE -n 20 --no-pager

# =============================================================================
# 4. Перевірка вільного місця
# =============================================================================
log_info "Крок 2/8: Перевірка вільного місця..."

FREE_SPACE=$(df -BG /backup 2>/dev/null | tail -1 | awk '{print $4}' | sed 's/G//')
if [ -z "$FREE_SPACE" ] || [ "$FREE_SPACE" -lt 5 ]; then
    log_error "Недостатньо місця для бекапу (потрібно мінімум 5GB)"
    df -h /backup
    exit 1
fi
log_success "Вільно місця: ${FREE_SPACE}GB"

# =============================================================================
# 5. Створення pre-update backup (ОБОВ'ЯЗКОВО!)
# =============================================================================
log_info "Крок 3/8: Створення pre-update backup..."
log_warning "Це критичний крок. Не переривайте!"

mkdir -p "$BACKUP_ROOT"

# Перевірка чи існує скрипт бекапу
if [ -f "$APP_DIR/scripts/backup-system.sh" ]; then
    log_info "Використання скрипту бекапу..."

    "$APP_DIR/scripts/backup-system.sh" \
        --dest "$BACKUP_ROOT" \
        --type on-change \
        --comment "$BACKUP_COMMENT" \
        --verify

    log_success "Бекап створено з перевіркою"

    # Додаткова копія ключових файлів
    log_info "Збереження додаткових копій конфігурації..."
    sudo cp /etc/uptime-monitor/config.json "/backup/config.pre-update.$TS.json" 2>/dev/null || true
    sudo cp /etc/systemd/system/uptime-monitor.service "/backup/uptime-monitor.service.pre-update.$TS" 2>/dev/null || true
else
    log_warning "Скрипт бекапу не знайдено. Створення ручного бекапу..."

    sudo mkdir -p "/backup/manual/$TS"
    sudo cp -r /etc/uptime-monitor "/backup/manual/$TS/" 2>/dev/null || true
    sudo cp -r /var/lib/uptime-monitor "/backup/manual/$TS/" 2>/dev/null || true

    log_success "Ручний бекап створено: /backup/manual/$TS"
fi

# Перевірка статусу бекапу
log_info "Статус бекапів:"
if [ -f "$APP_DIR/scripts/backup-system.sh" ]; then
    "$APP_DIR/scripts/backup-system.sh" --status 2>/dev/null || true
fi

# =============================================================================
# 6. Зупинка сервісу
# =============================================================================
log_info "Крок 4/8: Зупинка сервісу..."

systemctl stop $SERVICE
sleep 2

if systemctl is-active --quiet $SERVICE; then
    log_error "Не вдалося зупинити сервіс"
    exit 1
fi
log_success "Сервіс зупинено"

# =============================================================================
# 7. Оновлення коду
# =============================================================================
log_info "Крок 5/8: Оновлення коду..."

cd "$APP_DIR"

# Перевірка типу інсталяції
if [ -d ".git" ]; then
    log_info "Виявлено Git-інсталяцію. Оновлення через git..."

    # Поточна версія (commit)
    CURRENT_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
    log_info "Поточний commit: $CURRENT_COMMIT"

    # Оновлення
    git fetch --all --prune
    git checkout main
    git pull --ff-only origin main

    # Нова версія
    NEW_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
    log_success "Оновлено: $CURRENT_COMMIT → $NEW_COMMIT"

    UPDATE_METHOD="git"
else
    log_warning "Git-репозиторій не знайдено. Оновлення через ZIP..."

    # Перевірка наявності unzip
    if ! command -v unzip &> /dev/null; then
        log_error "unzip не встановлено. Виконайте: apt install -y unzip"
        exit 1
    fi

    # Завантаження
    log_info "Завантаження останньої версії..."
    cd /tmp

    wget -q --show-progress https://github.com/ajjs1ajjs/Uptime-Monitor-APP/archive/refs/heads/main.zip -O uptime_update.zip

    if [ ! -f "uptime_update.zip" ]; then
        log_error "Не вдалося завантажити ZIP"
        exit 1
    fi

    log_success "ZIP завантажено"

    # КРИТИЧНО: Видалити стару папку
    sudo rm -rf /tmp/Uptime-Monitor-APP-main

    # КРИТИЧНО: Розпакувати з sudo
    sudo unzip -o -q uptime_update.zip

    # Копіювання файлів
    sudo cp -r /tmp/Uptime-Monitor-APP-main/Uptime_Robot/* "$APP_DIR/"

    # Видалення тимчасових файлів
    sudo rm -rf uptime_update.zip /tmp/Uptime-Monitor-APP-main

    log_success "Оновлення через ZIP завершено"

    UPDATE_METHOD="zip"
fi

# =============================================================================
# 8. Запуск сервісу
# =============================================================================
log_info "Крок 6/8: Запуск сервісу..."

systemctl daemon-reload
systemctl start $SERVICE
sleep 3

if ! systemctl is-active --quiet $SERVICE; then
    log_error "Сервіс не запустився!"
    log_info "Перевірте логи: journalctl -u $SERVICE -n 50"
    exit 1
fi
log_success "Сервіс запущено"

# =============================================================================
# 9. Перевірка після оновлення
# =============================================================================
log_info "Крок 7/8: Перевірка після оновлення..."

# Статус сервісу
log_info "Статус сервісу:"
systemctl status $SERVICE --no-pager | head -15

# Останні логи
log_info "Останні логи:"
journalctl -u $SERVICE -n 30 --no-pager

# Перевірка HTTP
log_info "Крок 8/8: Перевірка HTTP доступності..."

# Отримання порту з конфігурації
PORT=$(grep -o '"port"[[:space:]]*:[[:space:]]*[0-9]*' /etc/uptime-monitor/config.json 2>/dev/null | grep -o '[0-9]*' || echo "8080")

log_info "Перевірка порту $PORT..."

if curl -fsS --max-time 5 "http://localhost:$PORT" > /dev/null 2>&1; then
    log_success "HTTP OK (порт $PORT)"
else
    log_warning "HTTP не відповідає на порту $PORT"
fi

# Перевірка процесу
log_info "Процеси:"
ps aux | grep -E "(python.*main|uptime)" | grep -v grep || true

# =============================================================================
# 10. Підсумки
# =============================================================================
echo ""
echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   ОНОВЛЕННЯ УСПІШНО ЗАВЕРШЕНО                             ║"
echo "╠═══════════════════════════════════════════════════════════╣"
echo "║   Метод: $UPDATE_METHOD"
echo "║   Бекап: $BACKUP_COMMENT"
echo "║   Час: $(date '+%Y-%m-%d %H:%M:%S')"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# =============================================================================
# 11. Команди для перевірки
# =============================================================================
echo ""
log_info "Корисні команди для перевірки:"
echo "  # Статус сервісу:"
echo "  sudo systemctl status $SERVICE"
echo ""
echo "  # Логи в реальному часі:"
echo "  sudo journalctl -u $SERVICE -f"
echo ""
echo "  # Перевірка HTTP:"
echo "  curl -fsS http://localhost:$PORT"
echo ""
echo "  # Статус бекапів:"
echo "  sudo $APP_DIR/scripts/backup-system.sh --status"
echo ""

# =============================================================================
# 12. Rollback (якщо потрібно)
# =============================================================================
log_warning "Якщо щось не працює, виконайте rollback:"
echo ""
echo "  # Останній бекап:"
echo "  sudo $APP_DIR/scripts/restore-system.sh --auto --force"
echo ""
echo "  # Конкретний бекап:"
echo "  sudo $APP_DIR/scripts/restore-system.sh --from /backup/uptime-monitor/on-change/backup-$TS.tar.gz --force"
echo ""

exit 0
