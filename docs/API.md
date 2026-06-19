# Документація API Uptime Monitor

Повний довідник API для Uptime Monitor v2.1.0.

**Базова URL-адреса:** `http://localhost:8080`

**Автентифікація:** Усі ендпоінти API (окрім `/login`) потребують JWT-куки сесії.

---

## Зміст

1. [Автентифікація](#authentication)
2. [Сайти](#sites)
3. [SSL-сертифікати](#ssl-certificates)
4. [Статистика](#statistics)
5. [Сповіщення](#notifications)
6. [Публічний статус](#public-status)
7. [Система](#system)

---

## Автентифікація

### Вхід

Отримати куку сесії для автентифікації.

**Ендпоінт:** `POST /login`

**Запит:**
```
Content-Type: application/x-www-form-urlencoded

username=admin&password=<your_password>
```

> **Примітка (v2.0.0):** Облікові дані за замовчуванням — `admin` / `auto-generated`.
> **Ліміт запитів:** 5 невдалих спроб на 15 хвилин для кожної IP-адреси. Після перевищення — 429 Too Many Requests.

**Відповідь:**
```
302 Found
Set-Cookie: session_id=abc123...; Path=/; HttpOnly
Location: /
```

---

### Вихід

**Ендпоінт:** `GET /logout`

**Відповідь:**
```
302 Found
Location: /login
```

---

## Сайти

### Перелік усіх сайтів

**Ендпоінт:** `GET /api/sites`

**Заголовки:**
```
Cookie: session_id=<your_session>
```

**Відповідь:**
```json
{
  "sites": [
    {
      "id": 1,
      "name": "Example Website",
      "url": "https://example.com",
      "check_interval": 60,
      "is_active": true,
      "status": "up",
      "status_code": 200,
      "response_time": 125.5,
      "uptime": 99.5,
      "notify_methods": ["telegram", "email"],
      "monitor_type": "http"
    }
  ]
}
```

---

### Додавання сайту

**Ендпоінт:** `POST /api/sites`

**Запит:**
```json
{
  "name": "My Website",
  "url": "https://mywebsite.com",
  "check_interval": 60,
  "is_active": true,
  "notify_methods": ["telegram", "email"],
  "monitor_type": "http"
}
```

**Відповідь:**
```json
{
  "id": 2,
  "message": "Site added"
}
```

---

### Отримання деталей сайту

**Ендпоінт:** `GET /api/sites/{site_id}`

**Відповідь:**
```json
{
  "id": 1,
  "name": "Example Website",
  "url": "https://example.com",
  "check_interval": 60,
  "is_active": true,
  "status": "up",
  "status_code": 200,
  "response_time": 125.5,
  "notify_methods": ["telegram", "email"],
  "monitor_type": "http"
}
```

---

### Оновлення сайту

**Ендпоінт:** `PUT /api/sites/{site_id}`

**Запит:**
```json
{
  "name": "Updated Name",
  "check_interval": 120,
  "notify_methods": ["telegram"]
}
```

**Відповідь:**
```json
{
  "message": "Updated"
}
```

---

### Видалення сайту

**Ендпоінт:** `DELETE /api/sites/{site_id}`

**Відповідь:**
```json
{
  "message": "Deleted"
}
```

---

### Ручна перевірка

Ініціювати негайну перевірку статусу.

**Ендпоінт:** `POST /api/sites/{site_id}/check`

**Відповідь:**
```json
{
  "message": "Check triggered"
}
```

---

### Отримання історії сайту

Отримати історію статусів для графіків.

**Ендпоінт:** `GET /api/sites/{site_id}/history`

**Параметри запиту:**
| Параметр | Тип | За замовчуванням | Опис |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Кількість записів, які потрібно повернути |

**Відповідь:**
```json
{
  "history": [
    {
      "status": "up",
      "status_code": 200,
      "response_time": 125.5,
      "checked_at": "2026-03-19T10:30:00"
    },
    {
      "status": "down",
      "status_code": 503,
      "response_time": null,
      "checked_at": "2026-03-19T10:29:00"
    }
  ]
}
```

---

## SSL-сертифікати

### Перелік усіх SSL-сертифікатів

**Ендпоінт:** `GET /api/ssl-certificates`

**Відповідь:**
```json
{
  "certificates": [
    {
      "id": 1,
      "site_id": 1,
      "site_name": "Example Website",
      "hostname": "example.com",
      "issuer": "Let's Encrypt",
      "expire_date": "2026-06-19T00:00:00",
      "days_until_expire": 92,
      "is_valid": true,
      "last_checked": "2026-03-19T06:00:00"
    }
  ]
}
```

---

### Ручна перевірка SSL

**Ендпоінт:** `POST /api/ssl-certificates/check`

**Відповідь:**
```json
{
  "message": "SSL check triggered"
}
```

---

## Статистика

### Отримання статистики часу відповіді

**Ендпоінт:** `GET /api/stats/response-time`

**Відповідь:**
```json
{
  "stats": [
    {
      "site_id": 1,
      "site_name": "Example Website",
      "avg_time": 125.5,
      "min_time": 89.2,
      "max_time": 245.8,
      "checks": 1440
    }
  ]
}
```

---

### Отримання інцидентів

Отримати інциденти простою за останні 7 днів.

**Ендпоінт:** `GET /api/incidents`

**Відповідь:**
```json
{
  "incidents": [
    {
      "id": 1,
      "site_id": 1,
      "site_name": "Example Website",
      "status": "down",
      "status_code": 503,
      "error_message": "Connection timeout",
      "checked_at": "2026-03-18T15:30:00",
      "duration_minutes": 15
    }
  ]
}
```

---

## Сповіщення

### Отримання налаштувань сповіщень

**Ендпоінт:** `GET /api/notify-settings`

**Відповідь:**
```json
{
  "telegram": {
    "enabled": true,
    "channels": [
      {"token": "bot_token", "chat_id": "chat_id"}
    ]
  },
  "email": {
    "enabled": false,
    "channels": []
  },
  "discord": {
    "enabled": true,
    "channels": [
      {"webhook_url": "https://discord.com/api/webhooks/..."}
    ]
  }
}
```

---

### Оновлення налаштувань сповіщень

**Ендпоінт:** `PUT /api/notify-settings`

**Запит:**
```json
{
  "telegram": {
    "enabled": true,
    "channels": [
      {"token": "new_bot_token", "chat_id": "new_chat_id"}
    ]
  },
  "email": {
    "enabled": true,
    "channels": [
      {
        "smtp_server": "smtp.example.com",
        "smtp_port": 587,
        "username": "user@example.com",
        "password": "password",
        "to_email": "admin@example.com"
      }
    ]
  }
}
```

---

## Публічний статус

### Сторінка публічного статусу

Публічний ендпоінт (автентифікація не потрібна).

**Ендпоінт:** `GET /public-status`

**Відповідь:** HTML-сторінка статусу

---

### API публічного статусу

**Ендпоінт:** `GET /api/public/status`

**Відповідь:**
```json
{
  "overall_status": "operational",
  "total_sites": 10,
  "up_sites": 9,
  "down_sites": 1,
  "last_updated": "2026-03-19T10:30:00",
  "sites": [
    {
      "id": 1,
      "name": "Example Website",
      "url": "https://example.com",
      "status": "up",
      "uptime_percentage": 99.5
    }
  ]
}
```

---

## Система

### Перевірка стану (Health Check)

**Ендпоінт:** `GET /health`

**Відповідь:**
```json
{
  "status": "healthy",
  "timestamp": "2026-03-19T10:30:00",
  "version": "2.0.0"
}
```

---

### Отримання серверного часу

**Ендпоінт:** `GET /api/server-time`

**Відповідь:**
```json
{
  "timestamp": 1710842400.0,
  "iso": "2026-03-19T10:30:00",
  "timezone": "UTC"
}
```

---

### Отримання налаштувань застосунку

**Ендпоінт:** `GET /api/app-settings`

**Відповідь:**
```json
{
  "display_address": "Kyiv, Ukraine",
  "check_interval": 60,
  "ssl_check_interval_hours": 6
}
```

---

### Оновлення налаштувань застосунку

**Ендпоінт:** `PUT /api/app-settings`

**Запит:**
```json
{
  "display_address": "New Address",
  "check_interval": 120
}
```

---

## Відповіді з помилками

### 400 Bad Request
```json
{
  "detail": "Invalid request body"
}
```

### 401 Unauthorized
```json
{
  "detail": "Authentication required"
}
```

### 403 Forbidden
```json
{
  "detail": "Admin access required"
}
```

### 404 Not Found
```json
{
  "detail": "Site not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Error message here"
}
```

---

## Обмеження частоти запитів (Rate Limiting)

Обмеження частоти запитів застосовується до ендпоінтів автентифікації:

| Ендпоінт | Ліміт | Вікно | Тривалість блокування |
|----------|-------|--------|----------------|
| `POST /login` | 5 невдалих спроб | 15 хвилин на IP-адресу | До завершення вікна |

Перевищення ліміту повертає `429 Too Many Requests` з повідомленням:
```
Too many login attempts. Try again later.
```

Інші ендпоінти API наразі **не** мають обмеження частоти запитів (заплановано для v2.1).

---

## Приклади SDK

### Python

```python
import requests

# Вхід (використовуйте ваш фактичний пароль із виводу інсталяції)
session = requests.Session()
resp = session.post('http://localhost:8080/login', data={
    'username': 'admin',
    'password': 'YOUR_ADMIN_PASSWORD'
})

# Отримати сайти
resp = session.get('http://localhost:8080/api/sites')
sites = resp.json()

# Додати сайт
resp = session.post('http://localhost:8080/api/sites', json={
    'name': 'My Site',
    'url': 'https://mysite.com',
    'check_interval': 60,
    'is_active': True,
    'notify_methods': ['telegram'],
    'monitor_type': 'http'
})

# Отримати історію
resp = session.get('http://localhost:8080/api/sites/1/history', params={'limit': 100})
history = resp.json()['history']
```

### cURL

```bash
# Вхід і збереження куки (використовуйте ваш фактичний пароль із виводу інсталяції)
curl -X POST http://localhost:8080/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=YOUR_ADMIN_PASSWORD" \
  -c cookies.txt

# Отримати сайти
curl -X GET http://localhost:8080/api/sites \
  -b cookies.txt

# Додати сайт
curl -X POST http://localhost:8080/api/sites \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Site",
    "url": "https://mysite.com",
    "check_interval": 60
  }'
```

### JavaScript (Node.js)

```javascript
const axios = require('axios');

// Створення екземпляра з кукою
const api = axios.create({
  baseURL: 'http://localhost:8080',
  withCredentials: true
});

// Вхід (використовуйте ваш фактичний пароль із виводу інсталяції)
await api.post('/login', null, {
  params: { username: 'admin', password: 'YOUR_ADMIN_PASSWORD' }
});

// Отримати сайти
const { data } = await api.get('/api/sites');
console.log(data.sites);

// Додати сайт
await api.post('/api/sites', {
  name: 'My Site',
  url: 'https://mysite.com',
  check_interval: 60
});
```

---

## Вебхуки

### Вебхук інциденту

Налаштуйте вебхук для отримання сповіщень про інциденти.

**Корисне навантаження (payload):**
```json
{
  "event": "incident",
  "type": "down",
  "site_id": 1,
  "site_name": "Example Website",
  "url": "https://example.com",
  "status_code": 503,
  "error": "Connection timeout",
  "timestamp": "2026-03-19T10:30:00"
}
```

### Вебхук відновлення

**Корисне навантаження (payload):**
```json
{
  "event": "recovery",
  "type": "up",
  "site_id": 1,
  "site_name": "Example Website",
  "url": "https://example.com",
  "status_code": 200,
  "response_time": 125.5,
  "timestamp": "2026-03-19T10:45:00"
}
```

---

## Підтримка

З питань або проблем:
- **GitHub Issues**: https://github.com/ajjs1ajjs/Uptime-Monitor/issues
- **Документація**: https://github.com/ajjs1ajjs/Uptime-Monitor/tree/main/docs
