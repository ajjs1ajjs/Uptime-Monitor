## [3.0.22] - 2026-08-13

### Security

- **SSRF hardening for monitor targets**: `resolvesBlocked` now also blocks
  RFC1918/ULA private ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16,
  fc00::/7) unless explicitly allowed via the new `server.allow_private_networks`
  config flag. The check is now enforced by a shared `internal/netguard`
  package used both at site creation AND on every worker check cycle
  (closing a DNS-rebinding/TOCTOU gap where a host could resolve to a public
  IP at creation time and an internal one later), and HTTP redirects are now
  validated hop-by-hop instead of being followed blindly.
- **Notify secrets no longer silently fall back to plaintext**: an invalid
  `UPTIME_MONITOR_MASTER_KEY` length or an encryption failure now fails the
  settings save outright instead of storing Telegram/SMTP/webhook secrets
  unencrypted in the database.
- **`install.sh` checksum verification is fail-closed**: a missing/unreachable
  `checksums.txt`, a missing entry for the target binary, or no SHA-256 tool
  available now aborts the install instead of silently skipping verification.
  An explicit `UPTIME_MONITOR_SKIP_CHECKSUM=1` opt-out is available for
  air-gapped/legacy scenarios.
- **Foreign key constraints added** to `status_history`, `ssl_certificates`,
  `notification_history`, `maintenance_windows`, `sessions` and `api_keys`
  (`REFERENCES ... ON DELETE CASCADE`), with an automatic one-time migration
  that rebuilds pre-existing tables and drops any orphan rows first.
- **Added `Strict-Transport-Security`** header when serving over HTTPS.
- **Constant-time login check**: a nonexistent username no longer skips the
  bcrypt comparison, removing a timing side channel that could be used to
  enumerate valid usernames.
- Admin's freshly-generated password is only printed to stdout when it was
  actually auto-generated; a password supplied via
  `UPTIME_MONITOR_ADMIN_PASSWORD`/`PYMON_ADMIN_PASSWORD` is no longer echoed
  back, reducing exposure in automation logs.
- GitHub Actions are now pinned to a full commit SHA instead of a mutable tag,
  and CI runs `govulncheck` on every push.

### Fixed

- `restoreFromPath` now returns the actual failure reason (missing file,
  permissions, reopen failure, ...) instead of collapsing every error into an
  empty string, and always leaves the `Store` with a working `*sql.DB`
  afterwards even if a step fails mid-restore.
- `SaveSSLCertificate` is now a single atomic `INSERT ... ON CONFLICT DO
  UPDATE`, removing a rare race where two overlapping SSL check cycles for
  the same site could both attempt an `INSERT` and one would fail on the
  `UNIQUE` constraint.
- `CreateBackup`/`DeleteBackup` no longer leave an orphaned file or DB row
  behind if one half of the operation fails.
- `GetAppSettings` no longer swallows non-`ErrNoRows` SQL errors silently.
- `ping()` monitor checks now respect the worker's shutdown context instead
  of running to their own independent timeout.
- `limit`/`days` query parameters on audit-log, notification-history and SLA
  report/export/PDF endpoints are now capped instead of unbounded.
- `docker-compose.yml` now sets memory/CPU limits and drops all Linux
  capabilities (`no-new-privileges`, `cap_drop: ALL`).

## [3.0.21] - 2026-08-13

### Fixed

- **"up" recovery alert never fired when `up_success_threshold > 1`** — the
  alert was gated on `prev == "down"`, but the site's DB status flips to
  `"up"` after the *first* successful check, before `SuccessAttempts` reaches
  the threshold, so the gate could never be true again. `LastDownAlert` was
  also being cleared on every successful check instead of only once the
  threshold was reached. Both are now gated on the threshold being reached.
- **`retry_delays` accepted unclamped values** in `POST /api/alert-policy`,
  unlike every other numeric field on that endpoint. Now clamped to 0-3600s.
- **HTTP checks send an identifying User-Agent** instead of the default
  `Go-http-client/1.1` — some targets' WAF/anti-bot layers silently tarpit
  that default UA (hang until timeout instead of responding), which reads
  identically to a real outage in status history.

## [3.0.20] - 2026-08-12

### Security

- **CRITICAL: viewer no longer receives channel secrets** — `redactNotify` was a
  no-op shallow copy, so any `viewer` role got the full decrypted notify config
  (Telegram bot tokens, SMTP credentials, Twilio auth tokens, webhook URLs)
  embedded in the dashboard HTML. Viewers now get a real `RedactSecrets` pass.
- **Stored XSS fixed on the dashboard** — site name/url, monitor_type, tags,
  SSL hostname, incident error messages, notification previews and maintenance
  window names are now HTML-escaped in every `innerHTML` sink.
- **`monitor_type` validated on the backend** — unknown values are rejected
  instead of being stored and later rendered unescaped.
- **URL scheme allowlist for non-HTTP monitors** — `javascript:`/`data:`/`file:`
  URLs are rejected at creation time.
- **Login rate limit counts failed attempts only** — successful logins can no
  longer lock a user out (previous behaviour: 5 POST /login → 15 min block).
- **Email header injection guard** — CR/LF in SMTP subject (user-supplied site
  name) is neutralized.
- **`master.key` is never silently overwritten** — a short/corrupt key file now
  fails loudly instead of being replaced with a new key (which would have made
  all stored secrets permanently unrecoverable).
- **Service worker no longer caches authenticated pages** — the dashboard HTML
  (which embeds session data) is excluded from the offline cache.

### Reliability

- **Scheduled backups** — the worker creates a daily backup when
  `backup.enabled` is set and rotates old ones down to `backup.max_backups`
  (previously the config was dead and only manual API backups existed).
- **WebSocket writes are serialized per connection** — concurrent broadcasts
  from worker goroutines could race on the same socket (corrupt frames/panic);
  each connection now has a write mutex and a write deadline.
- **One-off maintenance windows now work** — the UI sends RFC3339 times, but the
  parser only accepted `2006-01-02T15:04`, so one-off windows never suppressed
  checks. Parsing now accepts RFC3339 and the legacy layout.

### Performance

- **Bounded history scans** — `GetSites` no longer walks the entire
  `status_history` table on every dashboard/public load (7-day window for the
  last status, 30-day window for uptime).
- **Maintenance windows are cached** (5s TTL) instead of re-querying the DB for
  every site on every check cycle.
- **Keyword check reads at most 512 KiB** of the response body instead of an
  unbounded stream (memory-exhaustion guard).

## [3.0.19] - 2026-08-12

### Fixed

- **Schema migration for old databases** — databases created by the Python/FastAPI
  backend (or any version lacking newer columns) are now upgraded automatically:
  `sites.first_failure_at`, `sites.silenced_until`, `sites.acknowledged`,
  `ssl_certificates.ssl_notified_thresholds`. Previously the monitor worker crashed
  with `SQL logic error: no such column: first_failure_at` and `/api/sites` returned
  500 on an old DB.
- **Login error messages** — raw error codes (`invalid_credentials`, `csrf`, ...)
  on `/login`, `/change-password` and `/forgot-password` are replaced with
  user-friendly Ukrainian messages.
- **Rate-limit on forms** — hitting the login/change-password/forgot-password rate
  limit now redirects back to the page with a readable message instead of showing
  a raw JSON `429 Too many requests`.
- **Login page version** — the footer no longer hardcodes `v2.1.0`; it shows the
  actual binary version.

## [3.0.17] - 2026-08-11

### Security

- **WebSocket Origin validation** — `/ws` rejects cross-origin handshakes (CSWSH);
  session cookies can no longer be hijacked by third-party pages.
- **Reverse-proxy aware client IP** — `X-Forwarded-For` / `X-Forwarded-Proto` are
  honoured only from CIDRs listed in `server.trusted_proxies`; otherwise the direct
  peer IP is used, so rate limits can no longer be bypassed by spoofed headers.
- **SSRF hardening** — `localhost` is now blocked by default when creating monitors
  (opt-in via `server.allow_localhost`); DNS resolution in the guard has a timeout.
- **Secure session cookie** — the `Secure` flag is set whenever the request arrives
  over TLS (direct or trusted proxy).
- **Per-key API-key salt** — new keys embed a random salt (`um_<salt>.<secret>`);
  keys minted by older versions still verify via the legacy fixed salt.
- **Admin password no longer written to disk** — the generated password is shown once
  on stdout only (install.sh still writes its own one-time file for headless setup).
- **Request body limits** — all JSON/form handlers cap bodies at 1 MiB (DoS guard).
- **CSV injection guard** — SLA export prefixes cells starting with `= + - @` to
  prevent spreadsheet formula execution.
- **Strict CSP** — `script-src 'self'`; no `unsafe-inline`/`unsafe-eval`, no third-party
  CDN origins (all assets are self-hosted now).
- **In-memory rate limiting** — replaces the DB-backed limiter (one DB write per
  request) with a process-local fixed-window limiter.
- **Backup restore moved to CLI** — `uptime-monitor restore --backup <file>`; the
  runtime API endpoint refuses restore, which previously swapped the live DB while
  the server was running.
- **Removed `rowExists` / unused `inClause`** — eliminated dead SQL that used dynamic
  identifiers.

### Observability

- **Structured logging (`log/slog`)** — every request logs method/path/status/duration
  plus a `X-Request-ID` correlation header; worker, notify and panic logs are
  structured and never include secrets (URLs that may embed tokens are not logged).

### Frontend

- **Self-hosted dependencies** — htmx 2.0.4 and Chart.js 4.4.7 vendored in
  `/static/vendor/`; Tailwind Play CDN replaced by a static `tailwind.css` build
  (`tailwind.config.js`, `tailwind-input.css`).
- **No inline scripts** — all JavaScript extracted to `/static/app.js`,
  `/static/dashboard.js`, `/static/users.js`, `/static/change_password.js`; inline
  event attributes replaced by `data-action` delegation.
- **Toast notifications** — blocking `alert()` dialogs (rate-limit, validation)
  replaced with non-blocking toasts.
- **`.dockerignore`** — keeps secrets/build context out of the image.

### Fixed

- **`/api/htmx/monitors` never rendered** — the partial used a nonexistent pongo2
  `format` filter; uptime is now pre-formatted (`uptime_str`).
- **Monitor tags rendered as byte codes** ("📁 91") — `json.RawMessage` tags are now
  parsed into a string slice before rendering.

## [3.0.0] - 2026-08-06

### Main highlights

- **Rewritten on Go 1.25** — single static binary, no runtime dependencies.
- **SQLite via modernc.org/sqlite** (pure-Go, WAL), no external dependencies.
- **Templates moved to pongo2** (embedded with go:embed).
- **Unified API with auth**: JWT-style sessions, admin/viewer roles, must_change_password, CSRF, rate-limit, API keys.
- **10 notification channels**: Telegram, Discord, Slack, Teams, Email, SMS/Twilio, Webhook, Pushover, Gotify, ntfy.
- **Encrypted secrets** (AES-GCM, master.key never stored in the database).
- **CLI**: server / reset-admin / has-admin / --version.
- **User management**: role-based access, force password change, multi-user support.
- **Security**: API keys (read, must_change, CSRF, RBAC), empty lists as [], validation, detail-errors.

---
# Changelog

All notable changes to Uptime Monitor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.2.0] - 2026-06-19

### Security

- **CSRF defense-in-depth enabled** — the CSRF middleware (previously defined but
  never registered) is now active: same-origin `Origin`/`Referer` enforcement on
  `/api/*` and one-time token validation on the `forgot-password` / `change-password`
  forms.
- **SSRF hardening** — monitor URL validation now resolves the hostname and rejects
  targets that point at private, loopback, link-local (incl. `169.254.169.254`
  cloud-metadata), reserved or multicast addresses — not just literal private IPs.
- **No passwords in logs** — the admin password is shown once on stdout at creation
  and is no longer written to the application logger or re-printed on every restart.
  Use `auth_cli show-password` for on-demand recovery.
- **Stronger password policy on reset** — admin password reset via `PUT /api/users/{username}`
  now enforces the same strength rules as user creation.
- **Reverse-proxy aware rate limiting** — set `UPTIME_MONITOR_TRUSTED_PROXIES`
  (comma-separated proxy IPs) to honour `X-Forwarded-For` so per-IP limits apply to
  real clients instead of the proxy. Defaults to off (direct peer IP).
- **CSRF fail-closed** — cookie-authenticated `/api/*` state-changing requests are
  now rejected when the `Origin`/`Referer` is missing or cross-origin (API-key
  clients are exempt; CSRF tokens compared in constant time).
- **Secrets fail closed** — when the encryption backend is unavailable, secrets are
  no longer silently written in plaintext; the save is refused instead.
- **Least-privilege roles** — new users default to `viewer` (was `admin`); the last
  remaining admin can no longer be demoted or deleted (API and CLI).
- **Check-time SSRF defense** — HTTP/Ping/Port/DNS monitors re-validate the resolved
  IP at check time and HTTP redirects are followed manually with per-hop validation,
  defeating DNS rebinding and redirect-based SSRF to internal hosts.
- **Session invalidation** — changing or admin-resetting a password now revokes all
  of that user's existing sessions (the actor is re-issued a fresh session).
- **Temporary-password gate enforced on the API** — accounts flagged
  `must_change_password` (incl. API-key auth) can no longer drive the JSON API
  until the password is changed.
- **ReDoS guard** — user-supplied `regex:` keyword checks run in a worker thread with
  a timeout so a catastrophic pattern cannot block the monitoring loop.
- **Key/credentials file permissions on Windows** — `master.key` and `credentials.txt`
  get an explicit ACL lockdown (icacls), matching the POSIX `chmod 0o600`.

### Fixed

- **Crash in monitor retries** — `check_site_status` raised `IndexError` and stopped
  monitoring a site when `max_retries` exceeded the configured `retry_delays`; the
  last delay is now reused.
- **WAL-safe backups** — `create_backup` uses `VACUUM INTO` (consistent snapshot incl.
  WAL), and restore now removes stale `-wal`/`-shm` sidecar files so restored data is
  not overwritten on next open.
- Redundant/duplicate flapping check removed from `check_site_status`.
- `monitor_loop` no longer re-queries notification settings every 5 s when the DB
  config is empty.
- Telegram `reply_markup` no longer raises on plain-string messages.
- **SMS alerts no longer crash** — `send_sms` normalises dict alert payloads to text
  (previously raised `TypeError` and silently dropped every SMS).
- **Windows service startup** — no longer calls `asyncio.get_running_loop()` with no
  running loop (which reported the service STOPPED); it owns an explicit loop.
- **Atomic monitor writes** — `check_site_status` persists status, history and
  counters in a single transaction; the alert decision is computed before the write
  and notifications are sent after commit. `failed_attempts` now increments for sites
  without notification channels, and write failures are no longer swallowed.
- **Truthful uptime %** — a `status_history` row is recorded on every check (bounded
  by the 30-day retention), so uptime = up/total is a real ratio, not transition rows.
- **Notification accuracy** — `send_slack` formats dict alerts instead of dumping a
  Python `repr`; per-method sent/failed status is recorded; the duplicate
  `notifications_sent` metric increment was removed; Telegram `callback_data` is
  truncated to 64 bytes (not characters).
- **Maintenance windows** — daily/weekly windows are evaluated in local wall-clock
  time instead of UTC.
- **Worker shutdown** — cancels the main task and cleans up in a `finally` block
  instead of racing `loop.stop()`.
- **No orphan rows** — `delete_site` also removes the site's `maintenance_windows`
  and `notification_history`; retention added for `audit_log` and `backups`.
- **SLA report** — counts distinct outages (status transitions), not every down check.
- Background `create_task` calls keep a strong reference and log exceptions.

### Changed

- **Database connections** — `get_db_connection()` now opens a dedicated connection
  per `with` block instead of sharing one process-wide connection across all
  concurrent coroutines (safe WAL pattern; matches the existing hot write path).
- **Performance** — eliminated N+1 query patterns in the public status page, SLA
  report, and incidents endpoint (bulk aggregation in a single query instead of
  per-site queries).
- **Refactor** — extracted pure helpers (`_compute_down_times`, `_build_incidents`,
  `_format_incident_duration`) from `get_incidents` and covered them with unit tests.
- Documented intentional design choices: API-key fixed salt (deterministic lookup
  over high-entropy keys), and the startup config snapshot for SSL/HSTS (TLS binds
  at startup → requires restart).

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
## [3.0.23] - 2026-08-16

### Added

- **Per-monitor anti-flapping settings**: request timeout, retry interval,
  retry count, and successful checks required before recovery are now stored
  and configured per monitor.
- Existing databases automatically receive safe defaults for the new monitor
  settings during migration.

### Changed

- Removed anti-flapping controls from the global settings screen; SSL and
  other truly global checks remain there.
- Monitor checks now use each monitor's own retry and recovery policy.
