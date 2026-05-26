# Changelog

All notable changes to Uptime Monitor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.1.0] - 2026-05-26

### Added

- **DB-backed Rate Limiting** — Rate limits persist across restarts and worker processes
- **Dark/Light Theme** — Toggleable theme with system preference detection
- **Site Tags/Groups** — Organize monitors with custom tags for filtering
- **Custom Uptime Periods** — Configurable SLA report periods (7/30/90 days)
- **Enhanced Healthcheck** — Now checks DB connectivity and monitoring thread status
- **Enhanced Prometheus Metrics** — Response time histograms, notification counters, maintenance status
- **Telegram Inline Buttons** — Acknowledge/silence alerts directly from Telegram chat
- **CSV/PDF Export** — Export SLA reports, sites list, and notification history
- **Worker Container Healthcheck** — Separate healthcheck for worker in docker-compose
- **Grafana Dashboard** — Pre-built dashboard JSON for monitoring the monitor

### Changed

- Rate limiter moved from in-memory dict to SQLite for multi-process safety
- Improved monitoring loop stability with better error recovery
- Reduced `check_site_status` complexity via extraction of sub-functions
- HTML card generation moved from inline Python to Jinja2 template partials
- Documentation: fixed version inconsistencies and incorrect default credentials

### Fixed

- QUICKSTART_UK.md showed wrong default credentials (`test/1234` instead of `admin/291263`)
- `pyproject.toml` version now matches README badge (2.1.0)

---

## [2.0.0] - 2026-05-13

### 🎉 Major Release - Enterprise Security & Production Hardening

#### Added

##### Enterprise Security
- **Rate Limiting** — `/login` endpoint: 5 attempts per 15 min per IP
- **Password Policy** — Min 12 chars, requires uppercase + lowercase + digit
- **Random Admin Password** — Generated on first install (no more `admin/admin`)
- **Encrypted Secrets** — Email passwords encrypted via Fernet (`cryptography`)
- **Configurable CORS** — `cors.allow_origins` in `config.json`
- **SSL Verification** — Configurable `verify_ssl` in `alert_policy`
- **Security Headers** — X-Content-Type-Options, X-Frame-Options, X-XSS-Protection

##### Deployment
- **Enterprise deploy script** — `deploy_update.sh` with full backup + rollback
- **Database migrations** — Automatic schema migration support
- **Pre-update checklist** — Verification before any update

##### Backup System
- **Automatic backups** - Daily, weekly, monthly, yearly schedules
- **On-change backups** - Auto backup before config changes
- **Multiple destinations** - Local, NFS, Samba shares
- **One-command restore** - Full system restore with single command
- **Backup verification** - Verify backup integrity
- **Retention policy** - Automatic cleanup of old backups

##### Configuration Management
- **JSON configuration** - Easy to read and edit config.json
- **Auto IP detection** - Server automatically determines IP address
- **Config rollback** - Revert to previous configurations
- **Change logging** - Track all configuration changes

##### SSL/HTTPS Support
- **Custom certificates** - Use your own SSL certificates
- **Auto redirect** - HTTP → HTTPS automatically
- **HSTS headers** - Enhanced security

##### Notifications
- **Improved SSL alerts** - Notify 14 days before expiry
- **Multi-channel** - Telegram, Email, Slack, Discord, Teams, SMS
- **Configurable thresholds** - Customize when to alert
- **Slack/SMS dispatch** — Fixed missing Slack/SMS in send_notification

#### Changed

- **Default port** - Changed to 8080
- **Host detection** - Auto-detect server IP
- **SSL check interval** - Every 6 hours
- **Documentation** - Comprehensive Ukrainian documentation
- **Updated CI/CD** — Removed `|| true` suppression, pinned actions to v4/v5
- **Version sync** — All version references updated to 2.0.0
- **Requirements pinned** — All dependencies have minimum version constraints

#### Fixed

- **CORS** — `allow_origins=["*"]` → configurable via `config.json`
- **SSL disabled** — `ssl=False` → configurable `verify_ssl` policy
- **Duplicate code** — Removed duplicate `init_paths()`, `import monitoring`, `sys.exit(1)`
- **Unused imports** — Removed `aiohttp` from `ssl_checker.py`
- **Bare excepts** — Replaced `except: pass` with specific exception handlers
- **print() → logger** — All production `print()` calls migrated to structured logging
- **Async/sync wrappers** — Removed fragile `iscoroutinefunction()` pattern (12 locations)
- **`deploy_update.sh`** — Fixed hardcoded `sa:sa` user, improved backup scope
- **Notification dispatch** — Fixed missing Slack/SMS dispatch in `send_notification()`
- **Type safety** — Fixed `send_slack` to accept `Union[str, Dict]`
- **Small fixes** — `state.py`, `worker.py`, `config_manager.py` bugs

#### Technical

- FastAPI backend
- SQLite database (aiosqlite)
- Async monitoring with aiohttp
- Role-based access control (admin/viewer)
- Fernet encryption for secrets at rest
- In-memory rate limiting

---

## [1.5.0] - 2026-02-01

### Added

- Windows Service support
- MSI installer for Windows
- Portable version (no installation required)
- User roles (admin/viewer)
- Password reset functionality
- Session management

### Changed

- Improved authentication system
- Better error handling
- Enhanced logging

---

## [1.4.0] - 2026-01-15

### Added

- SSL certificate monitoring
- Certificate expiration alerts
- SSL dashboard
- Background SSL checks

### Changed

- Improved notification system
- Better SSL validation

---

## [1.3.0] - 2025-12-20

### Added

- Multi-channel notifications (Telegram, Discord, Slack)
- Email notifications via SMTP
- Webhook support
- Custom notification templates

### Changed

- Notification settings per site
- Improved alert formatting

---

## [1.2.0] - 2025-11-10

### Added

- Public status page
- REST API
- Docker support
- Linux systemd service

### Changed

- Improved web interface
- Better mobile responsiveness

---

## [1.1.0] - 2025-10-05

### Added

- Web dashboard
- Site management UI
- Real-time status updates
- Basic authentication

### Changed

- Migrated to FastAPI
- Improved performance

---

## [1.0.0] - 2025-09-01

### Initial Release

- Basic HTTP/HTTPS monitoring
- SQLite storage
- Command-line interface
- Simple notifications

---

## Version History

| Version | Date | Key Features |
|---------|------|--------------|
| 2.0.0 | 2026-03-19 | Backup system, config management, SSL/HTTPS |
| 1.5.0 | 2026-02-01 | Windows service, MSI installer, user roles |
| 1.4.0 | 2026-01-15 | SSL certificate monitoring |
| 1.3.0 | 2025-12-20 | Multi-channel notifications |
| 1.2.0 | 2025-11-10 | Public status page, REST API, Docker |
| 1.1.0 | 2025-10-05 | Web dashboard, FastAPI |
| 1.0.0 | 2025-09-01 | Initial release |

---

## Upcoming Features (Roadmap)

### v2.1.0 (Planned)
- [ ] Real-time WebSocket updates
- [ ] Dark/Light theme toggle
- [ ] Export reports (CSV/PDF)
- [ ] Incident timeline visualization

### v2.2.0 (Planned)
- [ ] Maintenance windows
- [ ] Scheduled downtime
- [ ] Multi-user support with granular permissions
- [ ] Audit logging

### v3.0.0 (Future)
- [ ] PostgreSQL support
- [ ] Clustering/HA
- [ ] Machine learning anomaly detection
- [ ] Mobile app (iOS/Android)
- [ ] Multi-language support (i18n)

---

## Breaking Changes

### v2.0.0
- Default port changed from 5000 to 8080
- Configuration moved to JSON format
- SSL notification threshold changed from 21 to 14 days
- **Admin password** — Random on first install (check install output)
- **Password policy** — Min 12 chars with upper+lower+digit (was 6)
- **CORS** — Now configurable via `config.json: cors.allow_origins`
- **SSL verification** — Default `true` (configurable via `alert_policy.verify_ssl`)
- **Login rate limiting** — 5 attempts per 15 min per IP
- **Dependency:** `cryptography>=41.0.0` added for secrets encryption

### v1.5.0
- Session-based authentication replaced cookie-based auth
- Password hashing algorithm changed to bcrypt

---

## Migration Guide

### From v1.x to v2.0.0

1. **Backup your data:**
   ```bash
   sudo cp /opt/uptime-monitor/sites.db /backup/sites.db.backup
   sudo cp /opt/uptime-monitor/config.json /backup/config.json.backup
   ```

2. **Update configuration:**
   - Edit `/etc/uptime-monitor/config.json`
   - Update port if needed (default: 8080)

3. **Restart service:**
   ```bash
   sudo systemctl restart uptime-monitor
   ```

---

## Contributing

To contribute to Uptime Monitor:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Update CHANGELOG.md
6. Submit a pull request

---

## Support

- **Issues**: https://github.com/ajjs1ajjs/Uptime-Monitor/issues
- **Discussions**: https://github.com/ajjs1ajjs/Uptime-Monitor/discussions
- **Documentation**: https://github.com/ajjs1ajjs/Uptime-Monitor/tree/main/docs

---

## Security

### Reported Vulnerabilities

| Date | Severity | Description | Status |
|------|----------|-------------|--------|
| - | - | - | - |

To report a security vulnerability, please email security@example.com

---

**Last updated:** 2026-03-19
