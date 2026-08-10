# ⏱️ Uptime Monitor

**Enterprise uptime & SSL monitoring system** — перевірка доступності сайтів, сервісів та SSL-сертифікатів з багатоканальними сповіщеннями.

[![Go 1.25](https://img.shields.io/badge/Go-1.25-blue.svg)](https://go.dev)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-3.0.0-orange.svg)](CHANGELOG.md)

---

## ✨ Можливості

- **Перевірки**: HTTP/HTTPS, TCP/Port, Ping, DNS, SSL — з інтервалами від 5с
- **SSL-моніторинг**: строк дії сертифікатів, пороги 30/14/7/5/3/1 день
- **Сповіщення**: Telegram, Discord, Slack, MS Teams, Email/SMTP, SMS/Twilio, Webhook, Pushover, Gotify, ntfy
- **Публічна сторінка статусу** (`/status`) — без автентифікації
- **Інциденти та uptime %** за період
- **SLA-звіти**: JSON, CSV, HTML-PDF
- **Ролі**: admin / viewer; API-ключі; сесії; CSRF; rate-limit
- **Періоди обслуговування** (maintenance windows)
- **Бекапи БД** та відновлення
- **PWA** — встановлюється на телефон

---

## 🚀 Швидкий старт

**Linux:**
```bash
curl -sSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash
```

**Windows** (PowerShell):
```powershell
iwr https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh -OutFile install.sh
```

> **Одна й та сама команда** і встановлює, і оновлює. При оновленні зберігаються конфіг, БД, користувачі та паролі; замінюється лише бінарник (попередній лишається як `.old`).

### 🗝️ Перший вхід

При **першому** встановленні скрипт друкує логін/пароль прямо у висновку:

```
====================================
  Логін:    admin
  Пароль:   <згенерований>
====================================
```

- Пароль також зберігається одноразово у `/var/lib/uptime-monitor/admin_password.txt`
- При вході система **попросить змінити пароль** перед використанням

**Втратили пароль:**
```bash
sudo UPTIME_MONITOR_ADMIN_PASSWORD='YourStrongPass123' /opt/uptime-monitor/uptime-monitor reset-admin --config /etc/uptime-monitor/config.json
sudo systemctl restart uptime-monitor
```

### Docker

```bash
docker compose up -d
curl http://localhost:8080/health
```

---

## 🔧 Команди

```bash
sudo systemctl start|stop|restart|status uptime-monitor

# Оновлення = та сама команда встановлення
curl -sSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash

# З сирців (для розробки)
go build -o uptime-monitor ./cmd/uptime-monitor
./uptime-monitor server --port 8080
```

---

## ⚙️ Конфігурація

Конфіг — у `config.json` (Linux: `/etc/uptime-monitor/config.json`):

```json
{
  "server": { "port": 8080, "host": "0.0.0.0" },
  "data_dir": "/var/lib/uptime-monitor",
  "log_dir": "/var/log/uptime-monitor",
  "check_interval": 60,
  "alert_policy": {
    "request_timeout_seconds": 30,
    "grace_period_seconds": 0,
    "up_success_threshold": 2,
    "still_down_repeat_seconds": 600,
    "treat_4xx_as_down": true,
    "verify_ssl": true,
    "ssl_notification_days": [30,14,7,5,3,1],
    "ssl_check_interval_hours": 6
  }
}
```

Налаштування сповіщень та зовнішній вигляд — через дашборд (Налаштування).
<img width="897" height="467" alt="image" src="https://github.com/user-attachments/assets/9d6751d8-c169-46b6-9bf4-37f06b08bca1" />

---

## 🔒 Безпека

- **Пароль адміна** генерується при першій інсталяції і показується лише раз; зберігається bcrypt-хеш
- **Ролі**: viewer — тільки читання; admin — керування
- **CSRF**: same-origin перевірка для cookie-авторизованих змін API; API-ключі звільнені
- **Rate-limit**: логін 5/15хв, публічна сторінка 30/60с
- **SSRF-guard** при створенні сайтів (заборона loopback/link-local/metadata)
- **Секрети** каналів сповіщень шифруються (AES-GCM, ключ `master.key` поруч із конфігом)

---

## 🧩 Технології

**Бекенд:** Go 1.25 · net/http · SQLite (WAL, modernc.org/sqlite) · gorilla/websocket · pongo2 (Jinja2-шаблони) · golang.org/x/crypto
**Фронтенд:** Vanilla JS · Tailwind · PWA · WebSocket (embedded через `go:embed`)
