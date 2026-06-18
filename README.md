# Uptime Monitor

[![Version](https://img.shields.io/badge/version-2.1.0-blue.svg)](https://github.com/ajjs1ajjs/Uptime-Monitor/releases)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-lightgrey.svg)]()
[![CI/CD](https://github.com/ajjs1ajjs/Uptime-Monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/ajjs1ajjs/Uptime-Monitor/actions)
[![Tests](https://img.shields.io/badge/tests-229%20passed-brightgreen.svg)]()

**Enterprise uptime monitoring with automatic backups, SSL certificate tracking, and multi-channel notifications.**

A self-hosted alternative to UptimeRobot: HTTP/SSL/Port/Ping checks, a real-time dashboard, a public status page, 10+ alert channels, and a REST API — on Linux, Windows, or Docker.

---

## 🚀 Quick Start

### Install (Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash
```

### Install (Windows — Service)

```powershell
# Run as Administrator in Uptime_Robot folder
git clone https://github.com/ajjs1ajjs/Uptime-Monitor.git
cd Uptime-Monitor\Uptime_Robot
.\install_service.bat

# Or quick install:
.\install.bat /y
```

> 💡 Run the same command again to update (auto-detects existing installation, backs up config, restarts service).

### Run directly (any platform)

```bash
python -m Uptime_Robot.main --host 0.0.0.0 --port 8080
```

> **Security (v2.0.0+):** Default credentials are `admin` / `auto-generated`.

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
| **Monitoring** | HTTP/HTTPS/SSL/Port/Ping checks, response time, configurable intervals |
| **Backups** | One-click API backup/restore, automatic DB snapshots, restore via dashboard |
| **Alerts** | Telegram, Email, Slack, Discord, Teams, SMS, Webhook, Pushover, Gotify, ntfy |
| **Security** | CSRF + Origin checks, SSRF-safe target validation, encrypted secrets, rate limiting, RBAC (admin/viewer), API keys, audit log |
| **Dashboard** | Real-time WebSocket, response time charts, SSL timeline, uptime bars, incident history |
| **Status Page** | Public status page with 30d uptime %, response time, incident timeline, customizable branding |
| **Notification History** | Full audit trail of all sent notifications with timestamps and delivery status |
| **Healthcheck** | `/health` endpoint for Docker/k8s readiness probes |
| **Platform** | Linux (systemd), Docker Compose, Windows service, Debian package |

---

## 🔒 Security

Enterprise-grade security, hardened across the 2.x line:

- **Rate Limiting** — 5 login attempts per 15 minutes per IP
- **Password Policy** — Minimum 12 characters, requires uppercase + lowercase + digit
- **Default Credentials** — Admin: `admin` / `auto-generated` (change after first login)
- **Encrypted Secrets** — Email passwords and tokens encrypted with Fernet at rest
- **Configurable CORS** — Restrict origins via `cors.allow_origins` in `config.json`
- **SSL Verification** — Configurable `verify_ssl` in `alert_policy`
- **Security Headers** — X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, HSTS
- **CSRF Protection** — Same-origin enforcement on `/api/*`, one-time tokens on auth forms
- **SSRF Protection** — Monitor targets resolving to private/loopback/metadata IPs are rejected
- **Reverse-proxy aware** — Set `UPTIME_MONITOR_TRUSTED_PROXIES` to rate-limit by real client IP

See [Security details](Uptime_Robot/README_SECURITY.md) and [Admin/password guide](docs/ADMIN_GUIDE.md).

---

## 📊 Dashboard

- **Real-time monitoring** — Check every 60 seconds (configurable per site)
- **SSL tracking** — Alerts up to 30 days before expiry, configurable cooldown
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
| **SSL Alert** | ≤30 days before expiry (30/14/7/5/3/1) |
| **Grace Period** | 0s (alert on first failure) |
| **Up Threshold** | 2 successes |
| **Still Down Repeat** | Every 10 minutes |
| **SSL Verify** | Enabled (configurable) |
| **CORS Origins** | `["http://localhost:8080"]` (configurable) |
| **Rate Limit** | 5 attempts / 15 min per IP |
| **Password Policy** | 12+ chars, upper+lower+digit |

---

## 🛠️ Technology Stack

- **Backend**: Python 3.9+, FastAPI, Uvicorn, Jinja2
- **Database**: SQLite (aiosqlite)
- **Frontend**: HTML/CSS/JS with Jinja2 templates, Chart.js, HTMX
- **Security**: bcrypt, Fernet (cryptography), API keys with SHA-256 hashing
- **Monitoring**: aiohttp (async), asyncio
- **Notifications**: SMTP, Telegram Bot API, Discord/Teams/Slack Webhooks, Pushover, Gotify, ntfy
- **Infrastructure**: Docker Compose, Prometheus metrics, WebSocket live updates
- **Testing**: pytest (229 tests), pytest-asyncio, coverage ~52%

---

## 📦 Installation Methods

| Method | Platform | Command |
|--------|----------|---------|
| **Curl** | Linux | `curl -fsSL https://... \| sudo bash` |
| **Git** | Linux | `git clone && cd Uptime-Monitor && sudo ./install.sh` |
| **Service** | Windows | `cd Uptime_Robot && .\install_service.bat` |
| **Quick** | Windows | `cd Uptime_Robot && .\install.bat /y` |
| **Docker** | Any | `docker compose up -d --build` (see [docker-compose.yml](docker-compose.yml)) |
| **APT** | Debian | `sudo apt install uptime-monitor` |

---

## 🔧 Basic Commands

### Linux (systemd)

```bash
# Service management
sudo systemctl start|stop|restart|status uptime-monitor
sudo systemctl start|stop|restart|status uptime-monitor-worker

# One-command update (auto backup + rollback)
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash

# Or via deploy script (if installed from Git)
sudo /opt/uptime-monitor/deploy_update.sh

# Backup & Restore
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/ --verify
sudo /opt/uptime-monitor/scripts/restore-system.sh --from /backup/...

# Logs
sudo journalctl -u uptime-monitor -f
sudo journalctl -u uptime-monitor-worker -f

# Diagnostics
sudo /opt/uptime-monitor/check-notifications.sh
```

### Windows (Service)

```powershell
# Service management
net start UptimeMonitor
net stop UptimeMonitor
python main_service.py remove

# Install service
.\install_service.bat
.\install.bat /y

# Test mode
python main_service.py console
python -m Uptime_Robot.main --host 0.0.0.0 --port 8080

# Scheduled Task (alternative to service)
powershell -ExecutionPolicy Bypass -File create_task_simple.ps1

# Build EXE
.\build_exe.bat
```

---

## 🔔 Notifications

- 📧 **Email** — SMTP with STARTTLS
- 📱 **Telegram** — Bot API with HTML formatting and inline acknowledge/silence buttons
- 💬 **Slack** — Webhooks
- 🎮 **Discord** — Webhooks with rich embeds
- 🏢 **Microsoft Teams** — Message Cards
- 📞 **SMS** — Twilio integration
- 🔗 **Webhook** — Custom JSON POST to any endpoint
- 🔔 **Pushover / Gotify / ntfy** — Self-hostable push notifications

Per-site channel selection, multiple channels per provider, and a full delivery history are supported.

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
