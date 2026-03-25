# 🔔 Перевірка сповіщень Uptime Monitor

Цей документ містить команди для діагностики проблем зі сповіщеннями після оновлення.

## 📋 Швидка перевірка

### 1. Запустіть скрипт діагностики

```bash
sudo chmod +x /opt/uptime-monitor/check-notifications.sh
sudo /opt/uptime-monitor/check-notifications.sh
```

Або скопіюйте скрипт і запустіть:

```bash
sudo chmod +x ~/check-notifications.sh
sudo ~/check-notifications.sh
```

---

## 🔍 Детальна перевірка (команди вручну)

### 1. Перевірка статусу служб

```bash
# Перевірка основної служби
sudo systemctl status uptime-monitor

# Перевірка worker служби (якщо використовується окремо)
sudo systemctl status uptime-monitor-worker
```

**Очікуваний результат:** Обидві служби мають бути `active (running)`

---

### 2. Перевірка налаштувань сповіщень в БД

```bash
# Для стандартного встановлення
sudo sqlite3 /var/lib/uptime-monitor/sites.db "SELECT config FROM notify_config WHERE id = 1;" | python3 -m json.tool

# Або якщо інший шлях до даних
sudo sqlite3 /opt/uptime-monitor/data/sites.db "SELECT config FROM notify_config WHERE id = 1;" | python3 -m json.tool
```

**Очікуваний результат:** Має бути JSON з налаштуваннями, наприклад:
```json
{
  "telegram": {
    "enabled": true,
    "channels": [
      {
        "id": "default",
        "name": "Основний",
        "token": "123456789:ABCdefGHI...",
        "chat_id": "-1001234567890"
      }
    ]
  }
}
```

---

### 3. Перевірка логів сповіщень

```bash
# Логи за останні 2 години
sudo journalctl -u uptime-monitor --since "2 hours ago" | grep -iE "telegram|notification|error"

# Логи в реальному часі
sudo journalctl -u uptime-monitor -f
```

**Очікуваний результат:** Мають бути повідомлення про відправку сповіщень або помилки

---

### 4. Перевірка активних сайтів

```bash
sudo sqlite3 /var/lib/uptime-monitor/sites.db "SELECT id, name, url, notify_methods, is_active FROM sites;"
```

**Очікуваний результат:** Сайти мають мати заповнене поле `notify_methods`

---

### 5. Перевірка процесів

```bash
# Перевірка основних процесів
ps aux | grep -E "uptime|main.py|worker.py" | grep -v grep

# Перевірка потоків
pgrep -f "python.*main.py" | xargs ps -T -p
```

---

## 🛠️ Виправлення проблем

### Проблема 1: Служба не активна

```bash
sudo systemctl start uptime-monitor
sudo systemctl enable uptime-monitor
```

---

### Проблема 2: Немає налаштувань в БД

**Рішення:** Налаштуйте сповіщення через Web UI:
1. Відкрийте `http://your-server:8080`
2. Перейдіть в **Settings → Notifications**
3. Увімкніть Telegram та заповніть:
   - **Bot Token** (отримайте від @BotFather)
   - **Chat ID** (дізнайтеся через @myidbot)
4. Натисніть **Save**

---

### Проблема 3: Worker служба не запущена

Якщо використовується окрема worker служба:

```bash
sudo systemctl start uptime-monitor-worker
sudo systemctl enable uptime-monitor-worker
```

---

### Проблема 4: Сповіщення не приходять після оновлення

**Причина:** Після оновлення на версію 2.0.0, `main.py` не запускав моніторинг автоматично.

**Рішення:**

#### Варіант A: Оновити код (рекомендовано)

1. Завантажте оновлені файли:
```bash
cd /opt/uptime-monitor
sudo git pull origin main
```

2. Або оновіть окремі файли:
```bash
# Завантажити оновлений monitoring.py
sudo curl -o /opt/uptime-monitor/Uptime_Robot/monitoring.py \
  https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/Uptime_Robot/monitoring.py

# Завантажити оновлений main.py
sudo curl -o /opt/uptime-monitor/Uptime_Robot/main.py \
  https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/Uptime_Robot/main.py
```

3. Перезапустіть службу:
```bash
sudo systemctl restart uptime-monitor
```

#### Варіант B: Запустити worker окремо

Якщо не можна оновити код, запустіть worker службу:

```bash
# Створіть службу worker, якщо її немає
sudo nano /etc/systemd/system/uptime-monitor-worker.service
```

Вміст файлу:
```ini
[Unit]
Description=Uptime Monitor Background Worker
After=network.target uptime-monitor.service
PartOf=uptime-monitor.service

[Service]
Type=simple
User=uptime-monitor
Group=uptime-monitor
WorkingDirectory=/opt/uptime-monitor
Environment="PATH=/opt/uptime-monitor/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="CONFIG_PATH=/etc/uptime-monitor/config.json"
ExecStart=/opt/uptime-monitor/venv/bin/python /opt/uptime-monitor/Uptime_Robot/worker.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Потім:
```bash
sudo systemctl daemon-reload
sudo systemctl start uptime-monitor-worker
sudo systemctl enable uptime-monitor-worker
```

---

## 🧪 Тестування сповіщень

### Тест 1: Вимкнути/увімкнути сайт

1. Вимкніть сайт в Web UI
2. Зачекайте 1-2 хвилини
3. Має прийти сповіщення "САЙТ НЕ ПРАЦЮЄ"

### Тест 2: Ручна перевірка через API

```bash
# Отримати токен (логін в Web UI)
# Потім викликати перевірку сайту
curl -X POST http://localhost:8080/api/sites/1/check \
  -H 'Authorization: Bearer YOUR_TOKEN'
```

---

## 📊 Корисні команди

### Перегляд повних логів

```bash
sudo journalctl -u uptime-monitor --since today --no-pager
```

### Перезапуск всіх служб

```bash
sudo systemctl restart uptime-monitor
sudo systemctl restart uptime-monitor-worker  # якщо використовується
```

### Перевірка версії

```bash
# Через Web UI
curl http://localhost:8080/health

# Або через файл
cat /opt/uptime-monitor/Uptime_Robot/CHANGELOG.md | head -20
```

---

## 🆘 Якщо нічого не допомагає

1. **Збережіть логи:**
```bash
sudo journalctl -u uptime-monitor --since yesterday > ~/uptime-logs.txt
```

2. **Перевірте конфігурацію:**
```bash
sudo cat /etc/uptime-monitor/config.json | python3 -m json.tool
```

3. **Створіть backup:**
```bash
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/
```

4. **Зверніться до документації:**
- [INSTALL.md](INSTALL.md)
- [QUICKSTART_UK.md](QUICKSTART_UK.md)
- [MIGRATION_GUIDE_UK.md](MIGRATION_GUIDE_UK.md)
