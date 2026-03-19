# Uptime Monitor API Documentation

Complete API reference for Uptime Monitor v2.0.0.

**Base URL:** `http://localhost:8080`

**Authentication:** All API endpoints (except `/login`) require JWT session cookie.

---

## Table of Contents

1. [Authentication](#authentication)
2. [Sites](#sites)
3. [SSL Certificates](#ssl-certificates)
4. [Statistics](#statistics)
5. [Notifications](#notifications)
6. [Public Status](#public-status)
7. [System](#system)

---

## Authentication

### Login

Get session cookie for authentication.

**Endpoint:** `POST /login`

**Request:**
```
Content-Type: application/x-www-form-urlencoded

username=admin&password=admin
```

**Response:**
```
302 Found
Set-Cookie: session_id=abc123...; Path=/; HttpOnly
Location: /
```

---

### Logout

**Endpoint:** `GET /logout`

**Response:**
```
302 Found
Location: /login
```

---

## Sites

### List All Sites

**Endpoint:** `GET /api/sites`

**Headers:**
```
Cookie: session_id=<your_session>
```

**Response:**
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

### Add Site

**Endpoint:** `POST /api/sites`

**Request:**
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

**Response:**
```json
{
  "id": 2,
  "message": "Site added"
}
```

---

### Get Site Details

**Endpoint:** `GET /api/sites/{site_id}`

**Response:**
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

### Update Site

**Endpoint:** `PUT /api/sites/{site_id}`

**Request:**
```json
{
  "name": "Updated Name",
  "check_interval": 120,
  "notify_methods": ["telegram"]
}
```

**Response:**
```json
{
  "message": "Updated"
}
```

---

### Delete Site

**Endpoint:** `DELETE /api/sites/{site_id}`

**Response:**
```json
{
  "message": "Deleted"
}
```

---

### Manual Check

Trigger immediate status check.

**Endpoint:** `POST /api/sites/{site_id}/check`

**Response:**
```json
{
  "message": "Check triggered"
}
```

---

### Get Site History

Get status history for charts.

**Endpoint:** `GET /api/sites/{site_id}/history`

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Number of records to return |

**Response:**
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

## SSL Certificates

### List All SSL Certificates

**Endpoint:** `GET /api/ssl-certificates`

**Response:**
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

### Manual SSL Check

**Endpoint:** `POST /api/ssl-certificates/check`

**Response:**
```json
{
  "message": "SSL check triggered"
}
```

---

## Statistics

### Get Response Time Statistics

**Endpoint:** `GET /api/stats/response-time`

**Response:**
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

### Get Incidents

Get downtime incidents for last 7 days.

**Endpoint:** `GET /api/incidents`

**Response:**
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

## Notifications

### Get Notification Settings

**Endpoint:** `GET /api/notify-settings`

**Response:**
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

### Update Notification Settings

**Endpoint:** `PUT /api/notify-settings`

**Request:**
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

## Public Status

### Public Status Page

Public endpoint (no authentication required).

**Endpoint:** `GET /public-status`

**Response:** HTML status page

---

### Public Status API

**Endpoint:** `GET /api/public/status`

**Response:**
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

## System

### Health Check

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-03-19T10:30:00",
  "version": "2.0.0"
}
```

---

### Get Server Time

**Endpoint:** `GET /api/server-time`

**Response:**
```json
{
  "timestamp": 1710842400.0,
  "iso": "2026-03-19T10:30:00",
  "timezone": "UTC"
}
```

---

### Get App Settings

**Endpoint:** `GET /api/app-settings`

**Response:**
```json
{
  "display_address": "Kyiv, Ukraine",
  "check_interval": 60,
  "ssl_check_interval_hours": 6
}
```

---

### Update App Settings

**Endpoint:** `PUT /api/app-settings`

**Request:**
```json
{
  "display_address": "New Address",
  "check_interval": 120
}
```

---

## Error Responses

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

## Rate Limiting

API requests are rate-limited to:
- **60 requests per minute** per IP address
- **1000 requests per hour** per session

Exceeding limits returns `429 Too Many Requests`.

---

## SDK Examples

### Python

```python
import requests

# Login
session = requests.Session()
resp = session.post('http://localhost:8080/login', data={
    'username': 'admin',
    'password': 'admin'
})

# Get sites
resp = session.get('http://localhost:8080/api/sites')
sites = resp.json()['sites']

# Add site
resp = session.post('http://localhost:8080/api/sites', json={
    'name': 'My Site',
    'url': 'https://mysite.com',
    'check_interval': 60,
    'is_active': True,
    'notify_methods': ['telegram'],
    'monitor_type': 'http'
})

# Get history
resp = session.get('http://localhost:8080/api/sites/1/history', params={'limit': 100})
history = resp.json()['history']
```

### cURL

```bash
# Login and save cookie
curl -X POST http://localhost:8080/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin" \
  -c cookies.txt

# Get sites
curl -X GET http://localhost:8080/api/sites \
  -b cookies.txt

# Add site
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

// Create instance with cookie
const api = axios.create({
  baseURL: 'http://localhost:8080',
  withCredentials: true
});

// Login
await api.post('/login', null, {
  params: { username: 'admin', password: 'admin' }
});

// Get sites
const { data } = await api.get('/api/sites');
console.log(data.sites);

// Add site
await api.post('/api/sites', {
  name: 'My Site',
  url: 'https://mysite.com',
  check_interval: 60
});
```

---

## Webhooks

### Incident Webhook

Configure webhook to receive incident notifications.

**Payload:**
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

### Recovery Webhook

**Payload:**
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

## Support

For issues or questions:
- **GitHub Issues**: https://github.com/ajjs1ajjs/Uptime-Monitor/issues
- **Documentation**: https://github.com/ajjs1ajjs/Uptime-Monitor/tree/main/docs
