# Troubleshooting Guide

Solutions for common Uptime Monitor issues.

## Service Won't Start

### Check Status
```bash
sudo systemctl status uptime-monitor
sudo journalctl -u uptime-monitor -n 50
```

### Check Permissions
```bash
sudo chown -R uptime-monitor:uptime-monitor /opt/uptime-monitor
```

## Worker Not Working (Monitoring)

```bash
sudo systemctl status uptime-monitor-worker
sudo journalctl -u uptime-monitor-worker -f
```

## Backup Issues

### Permission Denied
```bash
sudo mkdir -p /backup/uptime-monitor
sudo chown -R root:root /backup/uptime-monitor/
sudo chmod 755 /backup/uptime-monitor/
```

### NFS Mount Fails
```bash
sudo apt-get install -y nfs-common
showmount -e <NFS_SERVER_IP>
```

## SSL/TLS Issues

```bash
# Verify certificate
openssl x509 -in /etc/uptime-monitor/ssl/cert.pem -text -noout

# Check expiry
openssl x509 -in /etc/uptime-monitor/ssl/cert.pem -enddate -noout
```

## Password Issues

### Recover / Reset Admin Password
The generated password is shown once at install and saved to
`/etc/uptime-monitor/credentials.txt`; it is **not** written to the journal.
```bash
# Reveal the current admin password
sudo /opt/uptime-monitor/venv/bin/python -m Uptime_Robot.auth_cli show-password

# Or set a new one (min 12 chars, upper+lower+digit)
sudo /opt/uptime-monitor/venv/bin/python -m Uptime_Robot.auth_cli reset-password --user admin --password NEW_PASSWORD
```

### Change Password
- Login to dashboard
- Go to settings
- Enter new password (min 12 chars, upper+lower+digit)

---

**Last updated:** 2026-06-08
