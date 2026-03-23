# Uptime Monitor

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/ajjs1ajjs/Uptime-Monitor/releases)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-lightgrey.svg)]()
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)]()

**Enterprise uptime monitoring with automatic backups, SSL certificates tracking, and multi-channel notifications.**

<p align="center">
  <img src="https://img.shields.io/badge/uptime-24/7-green" alt="24/7 Uptime">
  <img src="https://img.shields.io/badge/ssl-monitoring-orange" alt="SSL Monitoring">
  <img src="https://img.shields.io/badge/notifications-Telegram%20%7C%20Email%20%7C%20Slack-blue" alt="Notifications">
</p>

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

## 🚀 Quick Start

### Install (Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash

# Access dashboard
http://YOUR_SERVER_IP:8080
# Login: admin / Password: admin
```

### Windows

**Option 1: MSI Installer**  
Download from [Releases](https://github.com/ajjs1ajjs/Uptime-Monitor/releases)

**Option 2: PowerShell One-liner (Fast Install)**  
Run in PowerShell as Administrator:
```powershell
iwr https://github.com/ajjs1ajjs/Uptime-Monitor/archive/refs/heads/main.zip -OutFile uptime.zip; Expand-Archive uptime.zip -DestinationPath . -Force; Remove-Item uptime.zip; cd Uptime-Monitor-main/Uptime_Robot; ./install.bat
```

---

## 📊 Dashboard Preview

- **Real-time monitoring** - Check every 60 seconds
- **SSL tracking** - Alerts 7 days before expiry
- **Backup system** - Automatic backups with restore
- **Multi-channel alerts** - Never miss downtime

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| **[INSTALL.md](INSTALL.md)** | Full installation guide |
| **[QUICKSTART_UK.md](QUICKSTART_UK.md)** | 5-minute quick start |
| **[docs/API.md](docs/API.md)** | Complete API reference |
| **[docs/BACKUP.md](docs/BACKUP.md)** | Backup configuration |
| **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** | Troubleshooting guide |
| **[CHANGELOG.md](CHANGELOG.md)** | Version history |

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
sites = resp.json()['sites']

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

See [examples/api_examples.py](examples/api_examples.py) for more.

---

## ⚙️ Configuration

### Default Settings

| Parameter | Value |
|-----------|-------|
| **Port** | 8080 |
| **Check Interval** | 60 seconds |
| **SSL Check** | Every 6 hours |
| **SSL Alert** | ≤7 days before expiry |
| **Down Threshold** | 3 failures |
| **Up Threshold** | 2 successes |

### config.json

```json
{
  "server": {
    "port": 8080,
    "host": "auto"
  },
  "check_interval": 60,
  "alert_policy": {
    "ssl_check_interval_hours": 6,
    "ssl_notification_days": 7
  }
}
```

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
| **Docker** | Any | `docker run -p 8080:8080 ...` |
| **MSI** | Windows | Download from Releases |
| **APT** | Debian/Ubuntu | `apt install uptime-monitor` |

---

## 🔔 Notifications

Configure alerts for:
- 📧 **Email** - SMTP support
- 📱 **Telegram** - Bot API
- 💬 **Slack** - Webhooks
- 💬 **Discord** - Webhooks
- 🏢 **Microsoft Teams** - Webhooks
- 📞 **SMS** - Twilio integration

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

MIT License - see [LICENSE](LICENSE) file.

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
