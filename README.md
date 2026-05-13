# Uptime Monitor

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/ajjs1ajjs/Uptime-Monitor/releases)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-lightgrey.svg)]()
[![CI/CD](https://github.com/ajjs1ajjs/Uptime-Monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/ajjs1ajjs/Uptime-Monitor/actions)

**Enterprise uptime monitoring with automatic backups, SSL certificates tracking, and multi-channel notifications.**

---

## 🚀 Quick Start

### Install (Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash

# Access dashboard
http://YOUR_SERVER_IP:8080
```

> **Security:** Since v2.0.0, the default admin password is randomly generated on first run — check the install output or `/var/log/uptime-monitor/` for the initial credentials.

---

## 📚 Documentation

| Document | Language | Description |
|----------|----------|-------------|
| **[UPDATE_PRODUCTION.md](UPDATE_PRODUCTION.md)** | 🇺🇦 UA | Production update with backup & rollback |
| **[README_UK.md](README_UK.md)** | 🇺🇦 UA | Main documentation (Ukrainian) |
| **[INSTALL.md](INSTALL.md)** | 🇺🇦 UA | Installation guide |
| **[QUICKSTART_UK.md](QUICKSTART_UK.md)** | 🇺🇦 UA | Quick start (5 minutes) |
| **[docs/API.md](docs/API.md)** | 🇬🇧 EN | API reference |
| **[docs/COMMANDS.md](docs/COMMANDS.md)** | 🇺🇦 UA | Commands reference |
| **[docs/BACKUP.md](docs/BACKUP.md)** | 🇺🇦 UA | Backup system guide |
| **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** | 🇺🇦 UA | Troubleshooting |
| **[NOTIFICATION_TROUBLESHOOTING_UK.md](NOTIFICATION_TROUBLESHOOTING_UK.md)** | 🇺🇦 UA | Notification diagnostics |
| **[MIGRATION_GUIDE_UK.md](MIGRATION_GUIDE_UK.md)** | 🇺🇦 UA | Migration from other systems |

---

## ✨ Features

| Category | Features |
|----------|----------|
| **Monitoring** | HTTP/HTTPS checks, SSL certificates, response time, configurable intervals |
| **Backups** | Daily/weekly/monthly rotation, NFS/Samba, one-click restore with verify |
| **Alerts** | Telegram, Email, Slack, Discord, Teams, SMS (Twilio) |
| **Security** | CORS config, encrypted secrets, rate limiting, RBAC, security headers |
| **Dashboard** | Real-time, public status page, incident history, uptime stats |
| **Platform** | Linux (systemd), Docker, Windows service, Debian package |

---

## 🔒 Security (v2.0.0)

Starting from v2.0.0, the project includes enterprise-grade security:

- **Rate Limiting** — 5 login attempts per 15 minutes per IP
- **Password Policy** — Minimum 12 characters, requires uppercase + lowercase + digit
- **Random Admin Password** — Generated on first install (no more `admin/admin`)
- **Encrypted Secrets** — Email passwords and tokens encrypted with Fernet at rest
- **Configurable CORS** — Restrict origins via `cors.allow_origins` in `config.json`
- **SSL Verification** — Configurable `verify_ssl` in `alert_policy`
- **Security Headers** — X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, HSTS

---

## 📊 Dashboard

- **Real-time monitoring** — Check every 60 seconds (configurable per site)
- **SSL tracking** — Alerts 14 days before expiry, configurable cooldown
- **Backup system** — Automatic with verification and restore
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
| **SSL Verify** | Enabled (configurable) |
| **CORS Origins** | `["*"]` (configurable) |

---

## 🛠️ Technology Stack

- **Backend**: Python 3.9+, FastAPI, Uvicorn
- **Database**: SQLite (aiosqlite)
- **Frontend**: HTML/CSS/JS with Jinja2 templates
- **Security**: bcrypt, Fernet (cryptography)
- **Monitoring**: aiohttp (async)
- **Notifications**: SMTP, Telegram Bot API, Webhooks

---

## 📦 Installation Methods

| Method | Platform | Command |
|--------|----------|---------|
| **Curl** | Linux | `curl -fsSL https://raw.githubusercontent.com/... \| sudo bash` |
| **Git** | Linux | `git clone && cd Uptime-Monitor && sudo ./install.sh` |
| **Docker** | Any | `docker compose up -d --build` |
| **MSI** | Windows | Download from Releases |
| **APT** | Debian/Ubuntu | `sudo apt install uptime-monitor` |

---

## 🔧 Basic Commands

```bash
# Service management
sudo systemctl start|stop|restart|status uptime-monitor
sudo systemctl start|stop|restart|status uptime-monitor-worker

# Deploy update (with backup + rollback)
sudo /opt/uptime-monitor/deploy_update.sh
sudo /opt/uptime-monitor/deploy_update.sh --rollback

# Backup
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/ --verify

# Restore
sudo /opt/uptime-monitor/scripts/restore-system.sh --from /backup/...

# Logs
sudo journalctl -u uptime-monitor -f
sudo journalctl -u uptime-monitor-worker -f

# Diagnostics
sudo /opt/uptime-monitor/check-notifications.sh
```

---

## 🔔 Notifications

- 📧 **Email** — SMTP with TLS
- 📱 **Telegram** — Bot API with HTML formatting
- 💬 **Slack** — Webhooks
- 🎮 **Discord** — Webhooks with rich embeds
- 🏢 **Microsoft Teams** — Message Cards
- 📞 **SMS** — Twilio integration

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes
4. Push to branch
5. Open Pull Request

---

## 📝 License

MIT License — see [LICENSE](LICENSE) file.

---

## 👥 Support

- **Issues**: https://github.com/ajjs1ajjs/Uptime-Monitor/issues
- **Discussions**: https://github.com/ajjs1ajjs/Uptime-Monitor/discussions

---

**⭐ Star this repo if you find it useful!**
