# Uptime Monitor

[![Версія](https://img.shields.io/badge/версія-2.1.0-blue.svg)](https://github.com/ajjs1ajjs/Uptime-Monitor/releases)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Платформа](https://img.shields.io/badge/платформа-Linux%20%7C%20Windows-lightgrey.svg)]()

**Моніторинг доступності з автоматичним резервним копіюванням, SSL сертифікатами та сповіщеннями.**

<p align="center">
  <img src="https://img.shields.io/badge/uptime-24/7-green" alt="24/7 Uptime">
  <img src="https://img.shields.io/badge/SSL-моніторинг-orange" alt="SSL Monitoring">
  <img src="https://img.shields.io/badge/сповіщення-Telegram%20%7C%20Email%20%7C%20Teams-blue" alt="Сповіщення">
</p>

---

## 🚀 Швидкий старт

### Встановлення (Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash

# Доступ до панелі
http://YOUR_SERVER_IP:8080
# Логін: admin / Пароль: auto-generated
```

### Windows

**Варіант A — Служба Windows (рекомендовано):**
```powershell
# Запустіть від імені адміністратора в папці Uptime_Robot
.\install_service.bat
# Доступ: http://localhost:8080
```

**Варіант B — Швидке встановлення через PowerShell:**
```powershell
# Запустіть від імені адміністратора
& {
    if (!(Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Host "Installing Python..."; winget install Python.Python.3.12 --silent
    }
    iwr https://github.com/ajjs1ajjs/Uptime-Monitor/archive/refs/heads/main.zip -OutFile uptime.zip
    Expand-Archive uptime.zip -DestinationPath . -Force; Remove-Item uptime.zip
    cd Uptime-Monitor-main/Uptime_Robot
    .\install.bat /y
}
```

> 💡 Запустіть ту ж команду повторно для оновлення (автоматично виявляє існуюче встановлення, створює резервну копію конфігурації, перезапускає службу).

**Варіант C — Напряму через Python (без служби):**
```powershell
python -m Uptime_Robot.main --host 0.0.0.0 --port 8080
# Доступ: http://localhost:8080
```

> **Пароль у Windows (v2.0.0+):** Генерується випадково під час першого запуску. Перевірте вивід у консолі або знайдіть його у файлі `credentials.txt`.

---

## 📚 Документація

| Документ | Опис |
|----------|------|
| **[INSTALL.md](INSTALL.md)** | Повна інструкція з встановлення |
| **[QUICKSTART_UK.md](QUICKSTART_UK.md)** | Швидкий старт за 5 хвилин |
| **[docs/API.md](docs/API.md)** | API документація |
| **[docs/BACKUP.md](docs/BACKUP.md)** | Система резервного копіювання |
| **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** | Усунення несправностей |
| **[docs/COMMANDS.md](docs/COMMANDS.md)** | Довідник команд |
| **[UPDATE_PRODUCTION.md](UPDATE_PRODUCTION.md)** | Оновлення Production |
| **[NOTIFICATION_TROUBLESHOOTING_UK.md](NOTIFICATION_TROUBLESHOOTING_UK.md)** | Діагностика сповіщень |
| **[MIGRATION_GUIDE_UK.md](MIGRATION_GUIDE_UK.md)** | Міграція з інших систем |

---

## 🌟 Можливості

### Моніторинг
- ✅ HTTP/HTTPS/SSL/Port/Ping перевірки
- ✅ SSL сертифікати (термін дії)
- ✅ Час відповіді, keyword/regex-перевірки
- ✅ Інтервал перевірки налаштовується (за замовч. 60 секунд)

### Сповіщення
- 📱 Telegram (з inline-кнопками acknowledge/silence)
- 📧 Email (SMTP)
- 💬 Slack
- 🎮 Discord
- 🏢 Microsoft Teams
- 📞 SMS (Twilio)
- 🔗 Webhook (кастомний JSON POST)
- 🔔 Pushover / Gotify / ntfy

### Резервне копіювання
- 🔄 Автоматичні бекапи (щодня/щотижня/щомісяця)
- 💾 NFS/Samba підтримка
- 🔧 Відновлення однією командою
- 📦 Збереження: БД, конфігурації, SSL, логи

### Безпека
- 🔒 HTTPS/SSL підтримка, HSTS заголовки
- 🛡️ CSRF-захист + перевірка Origin для `/api/*`
- 🚫 SSRF-захист (блокування приватних/loopback/metadata-адрес)
- 👥 Ролі користувачів (admin/viewer), API-ключі, audit log
- 🔐 Управління сесіями, rate limiting, шифрування секретів (Fernet)
- 🔑 bcrypt-хешування паролів, політика стійкості (12+ символів)

---

## 📊 Функціонал

- **Веб-панель** — реальний час, REST API
- **Публічна сторінка статусу** — для клієнтів
- **Історія статусів** — 30 днів
- **Uptime статистика** — відсотки доступності
- **SSL дашборд** — термін дії сертифікатів

---

## ⚙️ Налаштування за замовчуванням

| Параметр | Значення |
|-----------|-------|
| **Порт** | 8080 |
| **Інтервал перевірки** | 60 секунд |
| **SSL перевірка** | Кожні 6 годин |
| **SSL сповіщення** | ≤30 днів до закінчення (30/14/7/5/3/1) |
| **Grace-період** | 0с (сповіщення з першої невдачі) |
| **Up поріг** | 2 успіхи |
| **Повтор «досі не працює»** | Кожні 10 хвилин |
| **Rate limit** | 5 спроб / 15 хв на IP |
| **CORS origins** | `["http://localhost:8080"]` (налаштовується) |

---

## 🛠️ Технології

- **Backend**: Python 3.9+, FastAPI
- **Database**: SQLite
- **Frontend**: HTML/CSS/JavaScript
- **Monitoring**: aiohttp (async)
- **Notifications**: SMTP, Telegram API, Webhooks

---

## 📦 Методи встановлення

| Метод | Платформа | Команда |
|--------|----------|---------|
| **Git** | Linux | `git clone && cd Uptime-Monitor` |
| **Curl** | Linux | `curl ... \| sudo bash` |
| **Docker** | Будь-яка | `docker run -p 8080:8080 ...` |
| **MSI** | Windows | Завантажити з Releases |
| **APT** | Debian/Ubuntu | `apt install uptime-monitor` |

---

## 🔧 Основні команди

```bash
# Управління службами
sudo systemctl start|stop|restart|status uptime-monitor
sudo systemctl start|stop|restart|status uptime-monitor-worker

# Резервне копіювання
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/

# Відновлення
sudo /opt/uptime-monitor/scripts/restore-system.sh --from /backup/...

# Перегляд логів
sudo journalctl -u uptime-monitor -f
sudo journalctl -u uptime-monitor-worker -f

# Діагностика
sudo /opt/uptime-monitor/check-notifications.sh
```

---

## 🔌 API Приклади

### Python

```python
import requests

# Логін
session = requests.Session()
session.post('http://localhost:8080/login',
             data={'username': 'admin', 'password': 'admin'})

# Отримати сайти
resp = session.get('http://localhost:8080/api/sites')
sites = resp.json()

# Додати сайт
session.post('http://localhost:8080/api/sites', json={
    'name': 'Мій Сайт',
    'url': 'https://mysite.com',
    'check_interval': 60
})
```

### cURL

```bash
# Логін
curl -X POST http://localhost:8080/login \
  -d "username=admin&password=admin" -c cookies.txt

# Отримати сайти
curl -X GET http://localhost:8080/api/sites -b cookies.txt
```

Більше прикладів: [examples/api_examples.py](examples/api_examples.py)

---

## 🆘 Усунення несправностей

### Служба не запускається

```bash
# Перевірити статус
sudo systemctl status uptime-monitor

# Переглянути логи
sudo journalctl -u uptime-monitor -n 50

# Перезапустити
sudo systemctl restart uptime-monitor
```

### Сповіщення не працюють

```bash
# Запустити діагностику
sudo /opt/uptime-monitor/check-notifications.sh

# Перевірити налаштування в БД
sudo sqlite3 /var/lib/uptime-monitor/sites.db \
  "SELECT config FROM notify_config WHERE id = 1;" | python3 -m json.tool
```

### Проблеми з бекапом

Дивіться: [docs/BACKUP.md](docs/BACKUP.md)

---

## 📈 Порівняння

| Функція | Uptime Monitor | Uptime.com | Pingdom |
|---------|---------------|------------|---------|
| **Self-hosted** | ✅ Так | ❌ Ні | ❌ Ні |
| **Безкоштовно** | ✅ Open-source | ❌ Платно | ❌ Платно |
| **Бекапи** | ✅ Вбудовані | ⚠️ Обмежено | ⚠️ Обмежено |
| **SSL моніторинг** | ✅ Так | ✅ Так | ✅ Так |
| **Сповіщень** | ✅ 6+ каналів | ✅ Так | ✅ Так |
| **Кастомізація** | ✅ Повна | ❌ Обмежено | ❌ Обмежено |

---

## 🤝 Внесок у проект

1. Fork репозиторій
2. Створіть гілку (`git checkout -b feature/amazing`)
3. Зробіть коміт (`git commit -m 'Додано amazing функцію'`)
4. Push (`git push origin feature/amazing`)
5. Відкрийте Pull Request

---

## 📝 Ліцензія

MIT License — дивіться файл [LICENSE](LICENSE).

---

## 👥 Підтримка

- **Issues**: https://github.com/ajjs1ajjs/Uptime-Monitor/issues
- **Discussions**: https://github.com/ajjs1ajjs/Uptime-Monitor/discussions
- **Email**: support@example.com

---

## 🎯 Roadmap

### v2.1.0 (Q2 2026)
- [ ] WebSocket оновлення в реальному часі
- [ ] Темна/Світла тема
- [ ] Експорт звітів (CSV/PDF)

### v2.2.0 (Q3 2026)
- [ ] Технічні вікна обслуговування
- [ ] Багатомовність (i18n)
- [ ] Аудит логів

### v3.0.0 (Q4 2026)
- [ ] PostgreSQL підтримка
- [ ] Кластеризація/HA
- [ ] Мобільний додаток

---

**⭐ Додайте зірку якщо проект корисний!**

**📢 Питання? Відкрийте issue або приєднуйтесь до обговорення!**
