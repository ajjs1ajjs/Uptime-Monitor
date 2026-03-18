#!/bin/bash
set -e

# ============================================
# Uptime Monitor Migration Script
# Автоматична міграція даних на новий сервер
# ============================================

OLD_SERVER_IP="${1:-}"
OLD_SERVER_USER="${2:-ubuntu}"

# Кольори
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функція для друку заголовків
print_header() {
    echo ""
    echo -e "${BLUE}======================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}======================================${NC}"
    echo ""
}

# Функція для перевірки помилок
check_error() {
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Помилка: $1${NC}"
        exit 1
    fi
}

# Перевірка аргументів
if [ -z "$OLD_SERVER_IP" ]; then
    print_header "🚀 Uptime Monitor Migration"
    echo "Використання: $0 <OLD_SERVER_IP> [OLD_SERVER_USER]"
    echo ""
    echo "Приклади:"
    echo "  $0 192.168.1.100 ubuntu"
    echo "  $0 10.0.0.50 admin"
    echo ""
    echo "Або встановіть змінні оточення:"
    echo "  OLD_SERVER_IP=192.168.1.100 OLD_SERVER_USER=ubuntu $0"
    exit 1
fi

print_header "🚀 Міграція Uptime Monitor"

echo -e "${YELLOW}Старий сервер:${NC} $OLD_SERVER_IP"
echo -e "${YELLOW}Користувач:${NC} $OLD_SERVER_USER"
echo ""

# 1. Встановлення
print_header "📦 Крок 1: Встановлення"

if [ ! -d "/opt/uptime-monitor" ]; then
    echo "Встановлення Uptime Monitor..."
    curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash
    check_error "Встановлення не вдалось"
    echo -e "${GREEN}✅ Встановлено${NC}"
else
    echo -e "${GREEN}✅ Вже встановлено${NC}"
fi

# 2. Зупинка служби
print_header "⏹️  Крок 2: Зупинка служби"

echo "Зупинка служби uptime-monitor..."
sudo systemctl stop uptime-monitor
check_error "Не вдалось зупинити службу"
echo -e "${GREEN}✅ Зупинено${NC}"

# 3. Копіювання даних
print_header "📥 Крок 3: Копіювання даних"

echo "Створення тимчасової директорії..."
mkdir -p /tmp/uptime-migration
cd /tmp/uptime-migration

COPIED_COUNT=0

echo "Копіювання sites.db (база даних)..."
if scp -o StrictHostKeyChecking=no ${OLD_SERVER_USER}@${OLD_SERVER_IP}:/var/lib/uptime-monitor/sites.db ./sites.db 2>/dev/null; then
    echo -e "${GREEN}✅ sites.db скопійовано${NC}"
    COPIED_COUNT=$((COPIED_COUNT + 1))
else
    echo -e "${RED}❌ Не вдалось скопіювати sites.db${NC}"
fi

echo "Копіювання config.json (конфігурація)..."
if scp -o StrictHostKeyChecking=no ${OLD_SERVER_USER}@${OLD_SERVER_IP}:/etc/uptime-monitor/config.json ./config.json 2>/dev/null; then
    echo -e "${GREEN}✅ config.json скопійовано${NC}"
    COPIED_COUNT=$((COPIED_COUNT + 1))
else
    echo -e "${YELLOW}⚠️  Не вдалось скопіювати config.json${NC}"
fi

echo "Копіювання .env (змінні оточення)..."
if scp -o StrictHostKeyChecking=no ${OLD_SERVER_USER}@${OLD_SERVER_IP}:/opt/uptime-monitor/.env ./.env 2>/dev/null; then
    echo -e "${GREEN}✅ .env скопійовано${NC}"
    COPIED_COUNT=$((COPIED_COUNT + 1))
else
    echo -e "${YELLOW}⚠️  Не вдалось скопіювати .env${NC}"
fi

echo "Копіювання SSL сертифікатів..."
if scp -o StrictHostKeyChecking=no -r ${OLD_SERVER_USER}@${OLD_SERVER_IP}:/etc/uptime-monitor/ssl/ ./ssl/ 2>/dev/null; then
    echo -e "${GREEN}✅ SSL сертифікати скопійовано${NC}"
    COPIED_COUNT=$((COPIED_COUNT + 1))
else
    echo -e "${YELLOW}⚠️  SSL не знайдено (опціонально)${NC}"
fi

if [ $COPIED_COUNT -eq 0 ]; then
    echo -e "${RED}❌ Жоден файл не скопійовано. Перевірте доступ до старого сервера.${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Скопійовано файлів: $COPIED_COUNT${NC}"

# 4. Відновлення даних
print_header "🔄 Крок 4: Відновлення даних"

echo "Копіювання файлів у системні директорії..."

if [ -f "/tmp/uptime-migration/sites.db" ]; then
    sudo cp /tmp/uptime-migration/sites.db /var/lib/uptime-monitor/
    echo -e "${GREEN}✅ sites.db відновлено${NC}"
fi

if [ -f "/tmp/uptime-migration/config.json" ]; then
    sudo cp /tmp/uptime-migration/config.json /etc/uptime-monitor/
    echo -e "${GREEN}✅ config.json відновлено${NC}"
fi

if [ -f "/tmp/uptime-migration/.env" ]; then
    sudo cp /tmp/uptime-migration/.env /opt/uptime-monitor/
    echo -e "${GREEN}✅ .env відновлено${NC}"
fi

if [ -d "/tmp/uptime-migration/ssl" ]; then
    sudo mkdir -p /etc/uptime-monitor/ssl
    sudo cp -r /tmp/uptime-migration/ssl/* /etc/uptime-monitor/ssl/
    echo -e "${GREEN}✅ SSL сертифікати відновлено${NC}"
fi

echo ""
echo "Налаштування прав доступу..."
sudo chown -R uptime-monitor:uptime-monitor /var/lib/uptime-monitor/sites.db
sudo chown -R uptime-monitor:uptime-monitor /etc/uptime-monitor/config.json
sudo chown -R uptime-monitor:uptime-monitor /opt/uptime-monitor/.env
sudo chown -R uptime-monitor:uptime-monitor /etc/uptime-monitor/ssl/ 2>/dev/null || true

sudo chmod 640 /var/lib/uptime-monitor/sites.db
sudo chmod 640 /etc/uptime-monitor/config.json
sudo chmod 600 /opt/uptime-monitor/.env
sudo chmod 600 /etc/uptime-monitor/ssl/*.pem 2>/dev/null || true

echo -e "${GREEN}✅ Права доступу налаштовано${NC}"

# 5. Запуск служби
print_header "▶️  Крок 5: Запуск служби"

echo "Запуск uptime-monitor..."
sudo systemctl start uptime-monitor
check_error "Не вдалось запустити службу"

sudo systemctl enable uptime-monitor
echo -e "${GREEN}✅ Служба запущена та додана в автозавантаження${NC}"

# 6. Перевірка
print_header "✅ Крок 6: Перевірка"

sleep 3

echo "Статус служби:"
sudo systemctl status uptime-monitor --no-pager -n 5

echo ""
echo "Перевірка порту 8080:"
if sudo netstat -tlnp 2>/dev/null | grep -q ":8080"; then
    echo -e "${GREEN}✅ Порт 8080 відкрито${NC}"
else
    echo -e "${YELLOW}⚠️  Порт 8080 не відкрито (перевірте firewall)${NC}"
fi

echo ""
echo "Перевірка бази даних:"
if [ -f "/var/lib/uptime-monitor/sites.db" ]; then
    SITES_COUNT=$(sqlite3 /var/lib/uptime-monitor/sites.db "SELECT COUNT(*) FROM sites;" 2>/dev/null || echo "0")
    echo -e "${GREEN}✅ База даних існує${NC}"
    echo "   Кількість сайтів: $SITES_COUNT"
else
    echo -e "${RED}❌ База даних не знайдена${NC}"
fi

# 7. Фінальна інформація
print_header "🎉 МІГРАЦІЯ ЗАВЕРШЕНА!"

PUBLIC_IP=$(hostname -I | awk '{print $1}')

echo -e "${GREEN}Веб-інтерфейс:${NC} http://${PUBLIC_IP}:8080"
echo ""
echo "📝 Наступні кроки:"
echo "   1. Відкрийте http://${PUBLIC_IP}:8080 у браузері"
echo "   2. Увійдіть (admin/admin або ваші старі дані)"
echo "   3. Перевірте що всі сайти на місці"
echo "   4. Перевірте сповіщення (Telegram/Email)"
echo ""
echo "🔧 Корисні команди:"
echo "   sudo systemctl status uptime-monitor"
echo "   sudo journalctl -u uptime-monitor -f"
echo "   sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/"
echo ""

# Очищення
rm -rf /tmp/uptime-migration

print_header "✅ Успіх!"
