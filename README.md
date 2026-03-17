# Монітор безвідмовної роботи

**Версія 2.0.0** - Сервіс моніторингу веб-сайтів з автоматичними бекапами, SSL сертифікатами та багатоканальними сповіщеннями.

---

## 📋 Опис проекту

Uptime Monitor - це open-source рішення для моніторингу доступності веб-сайтів та сервісів. Система автоматично перевіряє стан ваших ресурсів і надсилає сповіщення при виявленні проблем.

### 🔑 Ключові особливості:
- ✅ **Моніторинг 24/7** - автоматична перевірка кожні 60 секунд
- ✅ **Система бекапів** - повне резервне копіювання з відновленням в один клік
- ✅ **SSL моніторинг** - відстеження терміну дії сертифікатів (кожні 6 годин)
- ✅ **Багатоканальні сповіщення** - Telegram, Email, Slack, Discord, Teams, SMS
- ✅ **Веб-інтерфейс** - зручний dashboard для управління
- ✅ **Легке налаштування** - встановлення за 5 хвилин
- ✅ **Авто-визначення IP** - сервер автоматично визначає вашу IP-адресу

---

## 🚀 Швидкий старт

```bash
# Встановлення (Git)
cd /opt
sudo git clone https://github.com/ajjs1ajjs/Uptime-Monitor.git
cd Uptime-Monitor

# АБО команда оновлення (з будь-якої папки)
sudo uptime-update

# Доступ
http://YOUR_SERVER_IP:8080
Login: test / Password: 1234
```

**📚 Повна інструкція:** [QUICKSTART_UK.md](QUICKSTART_UK.md)

---

## 📚 Документація

| Документ | Опис |
|----------|------|
| **[🚀 MIGRATION.md](docs/MIGRATION.md)** | **Міграція в хмару (AWS/Azure)** |
| **[QUICKSTART.md](docs/QUICKSTART.md)** | Швидкий старт за 5 хвилин |
| **[COMMANDS.md](docs/COMMANDS.md)** | Всі команди в одному місці |
| **[UPDATE_INSTRUCTIONS.md](docs/UPDATE_INSTRUCTIONS.md)** | Безпечне оновлення (backup + rollback) |
| **[SAFE_UPDATE_RUNBOOK.md](docs/SAFE_UPDATE_RUNBOOK.md)** | Покроковий production runbook для оновлення |
| **[BACKUP.md](docs/BACKUP.md)** | Налаштування бекапів |
| **[TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** | Вирішення проблем |
| **[INSTALL.md](INSTALL.md)** | Повна інструкція з установки |

---

## ✨ Функціонал

### Основні можливості
- 📊 **Моніторинг сайтів** - HTTP/HTTPS перевірка
- 🔒 **SSL сертифікати** - контроль терміну дії (перевірка кожні 6 год)
- 🌐 **Веб-інтерфейс** - зручне управління (порт 8080)
- 🔌 **REST API** - програмний доступ
- 💻 **Кросплатформеність** - Linux, Windows, Docker

### Новий функціонал 🆕 (v2.0.0)
- 💾 **Система бекапів** - локальні, NFS, Samba
- ⚙️ **Управління конфігурацією** - JSON, авто-IP, відкат
- 🔐 **SSL/HTTPS** - власні сертифікати, автоматичний редирект
- 🎯 **Авто-визначення IP** - хост визначається автоматично
- 📊 **Покращені сповіщення** - SSL за 7 днів (було 21)

---

## 🛠️ Технології

- **Бекенд**: Python, FastAPI
- **База даних**: SQLite
- **Інтерфейс**: HTML/JavaScript
- **Моніторинг**: aiohttp
- **Сповіщення**: SMTP, Telegram Bot API, Webhooks

---

## 📦 Встановлення

### Linux (рекомендовано)
```bash
cd /opt
sudo git clone https://github.com/ajjs1ajjs/Uptime-Monitor.git
cd Uptime-Monitor
# Дивіться повну інструкцію в QUICKSTART_UK.md
```

### Докер
```bash
docker run -d -p 8080:8080 -v uptime-data:/data \
  --name uptime-monitor \
  ghcr.io/ajjs1ajjs/uptime-monitor:latest
```

### Windows
1. Завантажте ZIP з [Releases](https://github.com/ajjs1ajjs/Uptime-Monitor/releases)
2. Витягніть у потрібне місце
3. Запустіть від імені адміністратора
4. Відкрийте `http://localhost:8080`

---

## ⚙️ Налаштування за замовчуванням (v2.0.0)

| Параметр | Значення |
|----------|----------|
| **Порт** | 8080 |
| **Host** | auto (авто-визначення IP) |
| **Check Interval** | 60 сек |
| **Request Timeout** | 60 сек |
| **SSL Check Interval** | 6 годин |
| **SSL Notification** | ≤7 днів до закінчення |
| **Down Failures Threshold** | 3 (потрібно 3 помилки для алерту) |
| **Up Success Threshold** | 2 (потрібно 2 успіхи для відновлення) |

---

## 🆘 Допомога

- **Безпечне оновлення (prod)** → [SAFE_UPDATE_RUNBOOK.md](docs/SAFE_UPDATE_RUNBOOK.md)
- **Детальні інструкції з оновлення** → [UPDATE_INSTRUCTIONS.md](docs/UPDATE_INSTRUCTIONS.md)
- **Проблеми?** → [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- **Команди** → [COMMANDS.md](docs/COMMANDS.md)
- **Бекапи** → [BACKUP.md](docs/BACKUP.md)

---

## 📝 Ліцензія

МОЯ ліцензія

---

**⭐ Поставте зірку, якщо проект корисний!**

**📢 Останні зміни v2.0.0:** Порт 8080, авто-IP, SSL кожні 6 год, сповіщення за 7 днів
