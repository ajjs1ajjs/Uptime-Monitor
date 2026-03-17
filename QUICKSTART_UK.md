# Uptime Monitor — Швидкий старт

## 📦 Встановлення (Linux)

### Спосіб 1: Git (рекомендовано)

```bash
# 1. Клонуйте репозиторій
cd /opt
sudo git clone https://github.com/ajjs1ajjs/Uptime-Monitor.git
cd Uptime-Monitor

# 2. Створіть користувача
sudo useradd -r -s /bin/false uptime-monitor

# 3. Встановіть залежності
sudo apt update && sudo apt install -y python3 python3-pip python3-venv
sudo -u uptime-monitor python3 -m venv venv
sudo -u uptime-monitor venv/bin/pip install -r Uptime_Robot/requirements.txt

# 4. Створіть лог-файл
sudo touch uptime_monitor.log
sudo chown uptime-monitor:uptime-monitor uptime_monitor.log

# 5. Створіть symlink
sudo ln -sf Uptime_Robot/main.py main.py
sudo ln -sf Uptime_Robot/ui_templates.py ui_templates.py

# 6. Налаштуйте systemd
sudo nano /etc/systemd/system/uptime-monitor.service
```

**Вміст сервісу:**
```ini
[Unit]
Description=Uptime Monitor Service
After=network.target

[Service]
Type=simple
User=uptime-monitor
Group=uptime-monitor
WorkingDirectory=/opt/Uptime-Monitor
ExecStart=/opt/Uptime-Monitor/venv/bin/python /opt/Uptime-Monitor/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# 7. Запустіть
sudo systemctl daemon-reload
sudo systemctl enable uptime-monitor
sudo systemctl start uptime-monitor
sudo systemctl status uptime-monitor
```

### Спосіб 2: Docker

```bash
docker run -d \
  -p 8080:8080 \
  -v uptime-data:/data \
  --name uptime-monitor \
  ghcr.io/ajjs1ajjs/uptime-monitor:latest
```

---

## 🔄 Оновлення

### Команда для оновлення (з будь-якої папки):

```bash
sudo uptime-update
```

### Якщо команди немає — встановіть:

```bash
sudo cat > /usr/local/bin/uptime-update << 'EOF'
#!/bin/bash
INSTALL_DIR="/opt/Uptime-Monitor"
SERVICE_NAME="uptime-monitor"
echo "╔════════════════════════════════════════╗"
echo "║   Uptime Monitor - Update Script      ║"
echo "╚════════════════════════════════════════╝"
if [ "$EUID" -ne 0 ]; then echo "Error: run with sudo"; exit 1; fi
cd "$INSTALL_DIR"
systemctl stop "$SERVICE_NAME"
chown -R $(whoami):$(whoami) .git/ 2>/dev/null || true
git fetch origin
git reset --hard origin/main
rm -f main.py ui_templates.py page.html Uptime_Robot/page.html
ln -sf Uptime_Robot/main.py main.py
ln -sf Uptime_Robot/ui_templates.py ui_templates.py
find . -path ./venv -prune -o -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
chown -R uptime-monitor:uptime-monitor main.py Uptime_Robot/main.py Uptime_Robot/ui_templates.py uptime_monitor.log ui_templates.py 2>/dev/null || true
systemctl start "$SERVICE_NAME"
sleep 2
if systemctl is-active --quiet "$SERVICE_NAME"; then echo "✅ Running!"; else echo "❌ Failed!"; systemctl status "$SERVICE_NAME" --no-pager; fi
echo "📌 Browser: Ctrl+Shift+R"
EOF
sudo chmod +x /usr/local/bin/uptime-update
```

### Вручну:

```bash
cd /opt/Uptime-Monitor

# 1. Зупинити
sudo systemctl stop uptime-monitor

# 2. Оновити код
git fetch origin
git reset --hard origin/main

# 3. Оновити symlink
rm -f main.py ui_templates.py
ln -sf Uptime_Robot/main.py main.py
ln -sf Uptime_Robot/ui_templates.py ui_templates.py

# 4. Видалити кеш
find . -path ./venv -prune -o -name "__pycache__" -exec rm -rf {} + 2>/dev/null

# 5. Виправити права
sudo chown -R uptime-monitor:uptime-monitor main.py Uptime_Robot/main.py Uptime_Robot/ui_templates.py uptime_monitor.log ui_templates.py

# 6. Запустити
sudo systemctl start uptime-monitor
sudo systemctl status uptime-monitor
```

**В браузері:** `Ctrl + Shift + R`

---

## 🛠️ Команди

### Керування сервісом

```bash
# Статус
sudo systemctl status uptime-monitor

# Старт/Стоп/Рестарт
sudo systemctl start uptime-monitor
sudo systemctl stop uptime-monitor
sudo systemctl restart uptime-monitor

# Логи
sudo journalctl -u uptime-monitor -f
tail -f /opt/Uptime-Monitor/uptime_monitor.log

# Перевірка API
curl http://localhost:8080/api/server-time
curl http://localhost:8080/api/sites
```

### Оновлення

```bash
# Глобальна команда
sudo uptime-update

# Або вручну (див. вище)
```

---

## 📁 Структура

```
/opt/Uptime-Monitor/
├── main.py                    → symlink → Uptime_Robot/main.py
├── ui_templates.py            → symlink → Uptime_Robot/ui_templates.py
├── uptime_monitor.log         # Логи
├── Uptime_Robot/
│   ├── main.py               # API та маршрути
│   ├── ui_templates.py       # HTML шаблони
│   ├── monitoring.py         # Моніторинг
│   └── ...
├── venv/                     # Віртуальне середовище
└── docs/                     # Документація
```

---

## 🌐 Доступ

```
http://YOUR_SERVER_IP:8080/

Login: test
Password: 1234

⚠️ Змініть пароль після першого входу!
```

---

## 📚 Документація

- [INSTALL_AND_UPDATE.md](docs/INSTALL_AND_UPDATE.md) — Повна інструкція
- [README.md](README.md) — Загальна інформація
- [docs/](docs/) — Інші документи

---

## 🆘 Проблеми?

### Сервіс не запускається

```bash
# Перевірте логи
sudo journalctl -u uptime-monitor -n 50 --no-pager

# Спробуйте вручну
cd /opt/Uptime-Monitor
sudo -u uptime-monitor venv/bin/python main.py
```

### Помилка "Permission denied"

```bash
sudo chown -R uptime-monitor:uptime-monitor /opt/Uptime-Monitor
sudo systemctl restart uptime-monitor
```

### Браузер показує стару версію

```
Ctrl + Shift + R  (очистка кешу)
Або Ctrl + Shift + N (режим інкогніто)
```

---

**GitHub:** https://github.com/ajjs1ajjs/Uptime-Monitor  
**Останнє оновлення:** 2026-03-17
