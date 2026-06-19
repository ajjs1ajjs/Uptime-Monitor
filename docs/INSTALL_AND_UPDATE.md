# Посібник зі встановлення та оновлення

**Повні інструкції зі встановлення дивіться тут:**

- **[INSTALL.md](../INSTALL.md)** — Повний посібник зі встановлення (українською)
- **[QUICKSTART_UK.md](../QUICKSTART_UK.md)** — Швидкий старт (5 хвилин)
- **[UPDATE_PRODUCTION.md](../UPDATE_PRODUCTION.md)** — Посібник з оновлення на продакшені (з резервним копіюванням та відкатом)

---

## Швидке встановлення (Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash
```

Доступ: `http://YOUR_SERVER_IP:8080`

> **Безпека:** Облікові дані за замовчуванням — `admin` / `auto-generated`.

---

## Оновлення (продакшен)

### ⭐ Рекомендовано: оновлення однією командою (для встановлення через curl)

```bash
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash
```
Інсталятор автоматично виявляє наявне встановлення, створює резервну копію БД та конфігурації, оновлює код і перезапускає сервіси.

### Альтернатива: автоматизований скрипт розгортання (для встановлення через Git)

```bash
sudo /opt/uptime-monitor/deploy_update.sh
```

### Оновлення вручну

Дивіться **[UPDATE_PRODUCTION.md](../UPDATE_PRODUCTION.md)** для безпечного оновлення з:
- Системою резервного копіювання перед оновленням
- Оновленням коду (Git, ZIP або curl)
- Кроками міграції бази даних
- Перевіркою після оновлення (smoke-тести)
- Процедурою відкату (з відновленням БД)

---

## Основні команди

```bash
# Керування сервісом
sudo systemctl start|stop|restart|status uptime-monitor
sudo systemctl start|stop|restart|status uptime-monitor-worker

# Оновлення однією командою (curl)
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash

# Або скрипт розгортання (на основі git)
sudo /opt/uptime-monitor/deploy_update.sh
sudo /opt/uptime-monitor/deploy_update.sh --rollback

# Резервне копіювання
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/ --verify

# Логи
sudo journalctl -u uptime-monitor -f
sudo journalctl -u uptime-monitor-worker -f
```

---

## Зміни в конфігурації (v2.0.0)

Нові параметри конфігурації у `/etc/uptime-monitor/config.json`:

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

- `cors.allow_origins` — Обмежте конкретними джерелами (наприклад, `["https://myapp.com"]`)
- `alert_policy.verify_ssl` — Встановіть `false`, якщо моніторите сайти з самопідписаними сертифікатами

---

## Усунення несправностей

- **[docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md)** — Загальні проблеми
- **[docs/BACKUP.md](BACKUP.md)** — Проблеми з резервним копіюванням
- **[NOTIFICATION_TROUBLESHOOTING_UK.md](../NOTIFICATION_TROUBLESHOOTING_UK.md)** — Проблеми зі сповіщеннями
