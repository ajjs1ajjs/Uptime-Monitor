# Installation and Update Guide

**For complete installation instructions, see:**

- **[INSTALL.md](../INSTALL.md)** — Full installation guide (Ukrainian)
- **[QUICKSTART_UK.md](../QUICKSTART_UK.md)** — Quick start (5 minutes)
- **[UPDATE_PRODUCTION.md](../UPDATE_PRODUCTION.md)** — Production update guide (with backup & rollback)

---

## Quick Install (Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash
```

Access: `http://YOUR_SERVER_IP:8080`

> **Security:** Default credentials are `admin` / `291263`.

---

## Update (Production)

### Recommended: Automated deploy script

```bash
sudo /opt/uptime-monitor/deploy_update.sh
```

### Manual update

See **[UPDATE_PRODUCTION.md](../UPDATE_PRODUCTION.md)** for safe update with:
- Pre-update backup system
- Code update (Git or ZIP)
- Database migration steps
- Post-update verification (smoke tests)
- Rollback procedure (with DB restore)

---

## Basic Commands

```bash
# Service management
sudo systemctl start|stop|restart|status uptime-monitor
sudo systemctl start|stop|restart|status uptime-monitor-worker

# Deploy update
sudo /opt/uptime-monitor/deploy_update.sh
sudo /opt/uptime-monitor/deploy_update.sh --rollback

# Backup
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/ --verify

# Logs
sudo journalctl -u uptime-monitor -f
sudo journalctl -u uptime-monitor-worker -f
```

---

## Configuration Changes (v2.0.0)

New config options in `/etc/uptime-monitor/config.json`:

```json
{
  "cors": {
    "allow_origins": ["*"]
  },
  "alert_policy": {
    "verify_ssl": true
  }
}
```

- `cors.allow_origins` — Restrict to specific origins (e.g., `["https://myapp.com"]`)
- `alert_policy.verify_ssl` — Set to `false` if monitoring sites with self-signed certificates

---

## Troubleshooting

- **[docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md)** — General issues
- **[docs/BACKUP.md](BACKUP.md)** — Backup problems
- **[NOTIFICATION_TROUBLESHOOTING_UK.md](../NOTIFICATION_TROUBLESHOOTING_UK.md)** — Notification issues
