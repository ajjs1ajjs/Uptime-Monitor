# Installation and Update Guide

**For complete installation instructions, see:**

- **[INSTALL.md](../INSTALL.md)** — Full installation guide (Ukrainian)
- **[QUICKSTART_UK.md](../QUICKSTART_UK.md)** — Quick start (5 minutes)
- **[UPDATE_PRODUCTION.md](../UPDATE_PRODUCTION.md)** — Production update guide

---

## Quick Install (Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash
```

Access: `http://YOUR_SERVER_IP:8080`  
Login: `admin` / Password: `admin`

---

## Update (Production)

```bash
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash
```

Or see **[UPDATE_PRODUCTION.md](../UPDATE_PRODUCTION.md)** for safe update with backup.

---

## Basic Commands

```bash
# Service management
sudo systemctl start|stop|restart|status uptime-monitor
sudo systemctl start|stop|restart|status uptime-monitor-worker

# Backup
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/

# Logs
sudo journalctl -u uptime-monitor -f
```

---

## Troubleshooting

- **[docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md)** — General issues
- **[docs/BACKUP.md](BACKUP.md)** — Backup problems
- **[NOTIFICATION_TROUBLESHOOTING_UK.md](../NOTIFICATION_TROUBLESHOOTING_UK.md)** — Notification issues
