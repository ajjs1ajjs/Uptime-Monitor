# Uptime Monitor

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/ajjs1ajjs/Uptime-Monitor/releases)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-lightgrey.svg)]()

**Enterprise uptime monitoring with automatic backups, SSL certificates tracking, and multi-channel notifications.**

<p align="center">
  <img src="https://img.shields.io/badge/uptime-24/7-green" alt="24/7 Uptime">
  <img src="https://img.shields.io/badge/SSL-monitoring-orange" alt="SSL Monitoring">
  <img src="https://img.shields.io/badge/notifications-Telegram%20%7C%20Email%20%7C%20Teams-blue" alt="Notifications">
</p>

---

## 🚀 Quick Start

### Install (Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash

# Access dashboard
http://YOUR_SERVER_IP:8080
# Login: admin / Password: admin
```

### Windows

**MSI Installer:** Download from [Releases](https://github.com/ajjs1ajjs/Uptime-Monitor/releases)

**PowerShell One-liner:**
```powershell
& { if (!(Get-Command python -ErrorAction SilentlyContinue)) { echo "Python..."; winget install Python.Python.3.12 --silent }; iwr https://github.com/ajjs1ajjs/Uptime-Monitor/archive/refs/heads/main.zip -OutFile uptime.zip; Expand-Archive uptime.zip -DestinationPath . -Force; Remove-Item uptime.zip; cd Uptime-Monitor-main/Uptime_Robot; ./install.bat /y }
```

---

## 📚 Documentation

| Document | Language | Description |
|----------|----------|-------------|
| **[README_UK.md](README_UK.md)** | 🇺🇦 UA | Головна документація (українська) |
| **[INSTALL.md](INSTALL.md)** | 🇺🇦 UA | Повна інструкція з встановлення |
| **[QUICKSTART_UK.md](QUICKSTART_UK.md)** | 🇺🇦 UA | Швидкий старт за 5 хвилин |
| **[UPDATE_PRODUCTION.md](UPDATE_PRODUCTION.md)** | 🇺🇦 UA | Оновлення Production сервера |
| **[docs/API.md](docs/API.md)** | 🇬🇧 EN | API reference |
| **[docs/BACKUP.md](docs/BACKUP.md)** | 🇺🇦 UA | Backup system guide |
| **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** | 🇺🇦 UA | Troubleshooting |
| **[docs/COMMANDS.md](docs/COMMANDS.md)** | 🇺🇦 UA | Commands reference |
| **[NOTIFICATION_TROUBLESHOOTING_UK.md](NOTIFICATION_TROUBLESHOOTING_UK.md)** | 🇺🇦 UA | Notification diagnostics |
| **[MIGRATION_GUIDE_UK.md](MIGRATION_GUIDE_UK.md)** | 🇺🇦 UA | Migration from other systems |

---

## 🌟 Features

| Category | Features |
|----------|----------|
| **Monitoring** | HTTP/HTTPS checks, SSL certificates, response time tracking |
| **Backups** | Automatic daily/weekly/monthly, NFS/Samba support, one-click restore |
| **Alerts** | Telegram, Email, Slack, Discord, Teams, SMS |
| **Security** | HTTPS/SSL, role-based access, session management |
| **Dashboard** | Real-time web UI, public status page, REST API |
| **Platform** | Linux, Windows, Docker |

---

## 📊 Dashboard

- **Real-time monitoring** — Check every 60 seconds
- **SSL tracking** — Alerts 14 days before expiry
- **Backup system** — Automatic backups with restore
- **Multi-channel alerts** — Never miss downtime
- **Public status page** — Share with customers
- **REST API** — Full automation support

---

## ⚙️ Default Settings

| Parameter | Value |
|-----------|-------|
| **Port** | 8080 |
| **Check Interval** | 60 seconds |
| **SSL Check** | Every 6 hours |
| **SSL Alert** | ≤14 days before expiry |
| **Down Threshold** | 1 failure |
| **Up Threshold** | 1 success |

---

## 🛠️ Technology Stack

- **Backend**: Python 3.9+, FastAPI
- **Database**: SQLite
- **Frontend**: HTML/CSS/JavaScript
- **Monitoring**: aiohttp (async)
- **Notifications**: SMTP, Telegram Bot API, Webhooks

---

## 📦 Installation Methods

| Method | Platform | Command |
|--------|----------|---------|
| **Git** | Linux | `git clone && cd Uptime-Monitor` |
| **Curl** | Linux | `curl ... \| sudo bash` |
| **Docker** | Any | `docker run -p 8080:8080 ...` |
| **MSI** | Windows | Download from Releases |
| **APT** | Debian/Ubuntu | `apt install uptime-monitor` |

---

## 🔧 Basic Commands

```bash
# Service management
sudo systemctl start|stop|restart|status uptime-monitor
sudo systemctl start|stop|restart|status uptime-monitor-worker

# Backup
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/

# Restore
sudo /opt/uptime-monitor/scripts/restore-system.sh --from /backup/...

# View logs
sudo journalctl -u uptime-monitor -f
sudo journalctl -u uptime-monitor-worker -f

# Diagnostics
sudo /opt/uptime-monitor/check-notifications.sh
```

---

## 🔌 API Examples

### Python

```python
import requests

# Login
session = requests.Session()
session.post('http://localhost:8080/login',
             data={'username': 'admin', 'password': 'admin'})

# Get sites
resp = session.get('http://localhost:8080/api/sites')
sites = resp.json()

# Add site
session.post('http://localhost:8080/api/sites', json={
    'name': 'My Site',
    'url': 'https://mysite.com',
    'check_interval': 60
})
```

### cURL

```bash
# Login
curl -X POST http://localhost:8080/login \
  -d "username=admin&password=admin" -c cookies.txt

# Get sites
curl -X GET http://localhost:8080/api/sites -b cookies.txt
```

More examples: [examples/api_examples.py](examples/api_examples.py)

---

## 🔔 Notifications

Configure alerts for:
- 📧 **Email** — SMTP support
- 📱 **Telegram** — Bot API
- 💬 **Slack** — Webhooks
- 🎮 **Discord** — Webhooks
- 🏢 **Microsoft Teams** — Webhooks
- 📞 **SMS** — Twilio integration

---

## 🔒 Security

- ✅ Role-based access (admin/viewer)
- ✅ Session management with bcrypt
- ✅ HTTPS/SSL support
- ✅ HSTS headers
- ✅ Password reset functionality

---

## 📈 Comparison

| Feature | Uptime Monitor | Uptime.com | Pingdom |
|---------|---------------|------------|---------|
| **Self-hosted** | ✅ Yes | ❌ No | ❌ No |
| **Free** | ✅ Open-source | ❌ Paid | ❌ Paid |
| **Backups** | ✅ Built-in | ⚠️ Limited | ⚠️ Limited |
| **SSL Monitoring** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Multi-channel** | ✅ 6+ channels | ✅ Yes | ✅ Yes |
| **Customizable** | ✅ Full control | ❌ Limited | ❌ Limited |

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open Pull Request

---

## 📝 License

MIT License — see [LICENSE](LICENSE) file.

---

## 👥 Support

- **Issues**: https://github.com/ajjs1ajjs/Uptime-Monitor/issues
- **Discussions**: https://github.com/ajjs1ajjs/Uptime-Monitor/discussions
- **Email**: support@example.com

---

## 🎯 Roadmap

### v2.1.0 (Q2 2026)
- [ ] Real-time WebSocket updates
- [ ] Dark/Light theme toggle
- [ ] Export reports (CSV/PDF)

### v2.2.0 (Q3 2026)
- [ ] Maintenance windows
- [ ] Multi-language support (i18n)
- [ ] Audit logging

### v3.0.0 (Q4 2026)
- [ ] PostgreSQL support
- [ ] Clustering/HA
- [ ] Mobile app

---

**⭐ Star this repo if you find it useful!**

**📢 Questions? Open an issue or join the discussion!**
