# Uptime Monitor — Повна інструкція

## 📦 Встановлення з нуля

### 1. Підготовка сервера (Ubuntu/Debian)

```bash
# Оновіть систему
sudo apt update && sudo apt upgrade -y

# Встановіть залежності
sudo apt install -y python3 python3-pip python3-venv git curl wget

# Створіть користувача для сервісу
sudo useradd -r -s /bin/false uptime-monitor
```

### 2. Завантаження додатку

```bash
# Перейдіть в /opt
cd /opt

# Завантажте з GitHub
sudo git clone https://github.com/ajjs1ajjs/Uptime-Monitor.git
cd Uptime-Monitor

# Виправте права
sudo chown -R uptime-monitor:uptime-monitor .
```

### 3. Налаштування середовища

```bash
# Створіть віртуальне середовище
sudo -u uptime-monitor python3 -m venv venv

# Актибуйте та встановіть залежності
sudo -u uptime-monitor /opt/Uptime-Monitor/venv/bin/pip install -r Uptime_Robot/requirements.txt
```

### 4. Створення лог-файлу

```bash
cd /opt/Uptime-Monitor

# Створіть лог-файл
sudo touch uptime_monitor.log
sudo chown uptime-monitor:uptime-monitor uptime_monitor.log
sudo chmod 644 uptime_monitor.log
```

### 5. Створення symlink для ui_templates

```bash
cd /opt/Uptime-Monitor

# Створіть symlink
sudo ln -sf Uptime_Robot/ui_templates.py ui_templates.py
```

### 6. Налаштування systemd сервісу

```bash
# Створіть файл сервісу
sudo nano /etc/systemd/system/uptime-monitor.service
```

**Вміст файлу:**
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

### 7. Запуск сервісу

```bash
# Перезавантажте systemd
sudo systemctl daemon-reload

# Увімкніть автозапуск
sudo systemctl enable uptime-monitor

# Запустіть
sudo systemctl start uptime-monitor

# Перевірте статус
sudo systemctl status uptime-monitor
```

### 8. Відкрийте веб-інтерфейс

```
http://YOUR_SERVER_IP:8080/
```

**Логін за замовчуванням:**
- Username: `test`
- Password: `1234`

---

## 🔄 Оновлення існуючої установки

### Спосіб 1: Глобальна команда (найпростіший)

```bash
# З будь-якої папки
sudo uptime-update
```

### Спосіб 2: Через deploy_update.sh

```bash
cd /opt/uptime-monitor
sudo ./deploy_update.sh
```

### Спосіб 3: Вручну

```bash
cd /opt/uptime-monitor

# 1. Зупинити сервіс
sudo systemctl stop uptime-monitor

# 2. Оновити код
sudo chown -R sa:sa .git/
git fetch origin
git reset --hard origin/main

# 3. Видалити старі файли
rm -f ui_templates.py page.html Uptime_Robot/page.html
ln -sf Uptime_Robot/ui_templates.py ui_templates.py

# 4. Видалити кеш
find . -path ./venv -prune -o -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -path ./venv -prune -o -name "*.pyc" -delete 2>/dev/null

# 5. Виправити права
sudo chown -R uptime-monitor:uptime-monitor main.py Uptime_Robot/main.py Uptime_Robot/ui_templates.py uptime_monitor.log ui_templates.py

# 6. Запустити сервіс
sudo systemctl start uptime-monitor
sudo systemctl status uptime-monitor
```

### Спосіб 4: Простий скрипт

```bash
cd /opt/uptime-monitor
sudo ./update.sh
```

---

## 🛠️ Корисні команди

### Керування сервісом

```bash
# Статус
sudo systemctl status uptime-monitor

# Запустити
sudo systemctl start uptime-monitor

# Зупинити
sudo systemctl stop uptime-monitor

# Перезапустити
sudo systemctl restart uptime-monitor

# Перезавантажити systemd
sudo systemctl daemon-reload

# Увімкнути автозапуск
sudo systemctl enable uptime-monitor

# Вимкнути автозапуск
sudo systemctl disable uptime-monitor
```

### Перегляд логів

```bash
# Логи сервісу
sudo journalctl -u uptime-monitor -f

# Логи сервісу (останні 50 рядків)
sudo journalctl -u uptime-monitor -n 50 --no-pager

# Логи додатку
tail -f /opt/uptime-monitor/uptime_monitor.log

# Логи додатку (останні 100 рядків)
tail -100 /opt/uptime-monitor/uptime_monitor.log
```

### Перевірка роботи

```bash
# Перевірити API
curl http://localhost:8080/api/server-time

# Перевірити монітори
curl http://localhost:8080/api/sites

# Перевірити процес
ps aux | grep uptime-monitor

# Перевірити порт
sudo netstat -tlnp | grep 8080
```

---

## 🚨 Вирішення проблем

### Сервіс не запускається

```bash
# Перевірте статус
sudo systemctl status uptime-monitor

# Подивіться логи
sudo journalctl -u uptime-monitor -n 50 --no-pager

# Спробуйте запустити вручну
cd /opt/uptime-monitor
sudo -u uptime-monitor /opt/uptime-monitor/venv/bin/python /opt/uptime-monitor/main.py
```

### Помилка "Permission denied: uptime_monitor.log"

```bash
cd /opt/uptime-monitor
sudo touch uptime_monitor.log
sudo chown uptime-monitor:uptime-monitor uptime_monitor.log
sudo chmod 644 uptime_monitor.log
sudo systemctl restart uptime-monitor
```

### Помилка "ModuleNotFoundError: ui_templates"

```bash
cd /opt/uptime-monitor
rm -f ui_templates.py
ln -sf Uptime_Robot/ui_templates.py ui_templates.py
sudo chown uptime-monitor:uptime-monitor ui_templates.py
sudo systemctl restart uptime-monitor
```

### Браузер показує стару версію

1. **Ctrl + Shift + R** (очистка кешу)
2. Або **Ctrl + Shift + N** (режим інкогніто)
3. Або повна очистка: **Ctrl + Shift + Delete**

---

## 📌 Шпаргалка команд

| Дія | Команда |
|-----|---------|
| **Оновити** | `sudo uptime-update` |
| **Статус** | `sudo systemctl status uptime-monitor` |
| **Перезапустити** | `sudo systemctl restart uptime-monitor` |
| **Логи** | `sudo journalctl -u uptime-monitor -f` |
| **Перевірити API** | `curl http://localhost:8080/api/server-time` |
| **В браузері** | `Ctrl + Shift + R` |

---

## 📁 Структура файлів

```
/opt/uptime-monitor/
├── main.py                    # Головний файл
├── ui_templates.py            # Symlink → Uptime_Robot/ui_templates.py
├── uptime_monitor.log         # Логи
├── Uptime_Robot/
│   ├── main.py               # API та маршрути
│   ├── ui_templates.py       # HTML шаблони
│   ├── monitoring.py         # Моніторинг
│   └── ...
├── venv/                     # Віртуальне середовище
└── deploy_update.sh          # Скрипт оновлення
```

---

## 🔐 Безпека

### Змінити пароль за замовчуванням

1. Увійдіть з `test` / `1234`
2. Перейдіть в **Користувачі**
3. Змініть пароль

### Налаштувати HTTPS

```bash
# Встановіть certbot
sudo apt install certbot python3-certbot-nginx -y

# Отримайте сертифікат
sudo certbot --nginx -d your-domain.com
```

### Змінити порт

Відредагуйте `config.json`:
```json
{
    "server": {
        "port": 8080
    }
}
```

---

**Останнє оновлення:** 2026-03-17  
**Версія:** main branch  
**GitHub:** https://github.com/ajjs1ajjs/Uptime-Monitor
