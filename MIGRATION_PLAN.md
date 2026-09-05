# Uptime-Monitor — План міграції Python → Go

## Мета

Переписати бекенд з Python (FastAPI + aiohttp) на **Go** для нижчого споживання ресурсів та вищої продуктивності перевірок.

| Аспект | Було (Python) | Стало (Go) |
|--------|---------------|------------|
| Мова | Python 3.11 | **Go 1.26.6** |
| Веб | FastAPI + Uvicorn | **net/http** |
| Перевірки | aiohttp + asyncio | **goroutines + net/http** |
| БД | aiosqlite | **modernc.org/sqlite** (pure-Go, WAL) |
| WebSocket | — | **gorilla/websocket** |
| bcrypt | passlib | **golang.org/x/crypto** |
| PDF-звіти | WeasyPrint | **HTML-звіт** + друк у PDF |
| Крипта | Fernet (AES-CBC+HMAC) | **AES-GCM** (сумісний префікс `__ENC__`) |

## Стратегія

- **Той самий REST API + контракти** → фронтенд (Jinja2 templates) перевикористовується як embedded assets через `go:embed`.
- **Один процес**: web-сервер + worker в одному бінарі (worker як горутина), з можливістю `--monitor` флага.
- **Схема БД ідентична** → сумісність з існуючими `sites.db`.
- **Алертинг** — портувати state-machine `_process_alerting` (grace, still_down, recovery threshold).
- **Сповіщення** — Telegram (+ long-poll кнопки ack/silence), Discord, Slack, Teams, Email, SMS/Twilio, Webhook, Pushover, Gotify, ntfy.
- **SSL** — TLS-з'єднання, парсинг сертифіката, пороги 30/14/7/5/3/1 днів.

## Етапи

1. Скелет: `cmd/uptime-monitor/main.go`, конфіг (config.json).
2. Storage: схема, CRUD для sites/status_history/ssl_certificates/notify_config/app_settings/notification_history/backups/users/sessions/api_keys/audit_log/maintenance_windows/csrf_tokens/rate_limits.
3. Auth: сесії (cookie), bcrypt, API-ключі (PBKDF2), ролі admin/viewer, CSRF, rate-limit.
4. REST API: всі роутери /api/* (sites, ssl, stats, incidents, settings, users, maintenance, reports, api-keys, audit, backup).
5. UI: `/`, `/users`, `/status` (public), `/login`, `/change-password`, `/forgot-password`, htmx-фрагменти.
6. Моніторинг: worker-цикл (5s tick), перевірки http/https/ping/dns/port/ssl, ретраї, SSRF-guard, maintenance windows.
7. Алертинг + 10 каналів сповіщень + Telegram poller.
8. SSL-чекер + пороги.
9. Звіти SLA (JSON/CSV/HTML-PDF).
10. Backup/restore, аудит, retention.
11. Тести Go + CI + Docker + README/CHANGELOG.
