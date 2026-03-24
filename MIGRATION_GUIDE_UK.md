# Uptime Monitor — Повна інструкція з оновлення та міграції

## 📋 Зміст

1. [Чиста установка (новий сервер)](#чиста-установка-новий-сервер)
2. [Оновлення існуючої інсталяції](#оновлення-існуючої-інсталяції)
3. [Міграція БД на інший сервер](#міграція-бд-на-інший-сервер)
4. [Вирішення проблем](#вирішення-проблем)

---

## 🚀 Чиста установка (новий сервер)

### 1. Встановити
```bash
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash
```

### 2. Відкрити веб-інтерфейс
```
http://SERVER_IP:8080
```

### 3. Увійти
- **Логін:** `admin`
- **Пароль:** `admin`

### 4. Змінити пароль
**КРИТИЧНО!** Змініть пароль після першого входу!

### 5. Налаштувати резервне копіювання
```bash
# Створити першу резервну копію
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/

# Налаштувати автоматичне резервне копіювання
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install --dest /backup/uptime-monitor/
```

---

## ⬆️ Оновлення існуючої інсталяції

### ⚠️ ВАЖЛИВО: Перевірте схему БД

Перед оновленням перевірте, чи має ваша БД потрібні колонки:

```bash
# Перевірте схему
sqlite3 /var/lib/uptime-monitor/sites.db ".schema sites"
```

**Очікувана схема (v2.0.0+):**
```sql
CREATE TABLE sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    check_interval INTEGER DEFAULT 60,
    is_active BOOLEAN DEFAULT 1,
    last_notification TEXT,
    notify_methods TEXT DEFAULT '[]',
    status TEXT DEFAULT 'unknown',        -- НОВЕ в v2.0.0
    status_code INTEGER,                  -- НОВЕ в v2.0.0
    response_time REAL,                   -- НОВЕ в v2.0.0
    error_message TEXT,                   -- НОВЕ в v2.0.0
    monitor_type TEXT DEFAULT 'http',
    failed_attempts INTEGER DEFAULT 0,
    success_attempts INTEGER DEFAULT 0,
    last_down_alert TEXT
);
```

### Якщо схема застаріла — додайте колонки:

```bash
# Зупиніть службу
sudo systemctl stop uptime-monitor

# Додайте відсутні колонки
sqlite3 /var/lib/uptime-monitor/sites.db "ALTER TABLE sites ADD COLUMN status TEXT DEFAULT 'unknown';"
sqlite3 /var/lib/uptime-monitor/sites.db "ALTER TABLE sites ADD COLUMN status_code INTEGER;"
sqlite3 /var/lib/uptime-monitor/sites.db "ALTER TABLE sites ADD COLUMN response_time REAL;"
sqlite3 /var/lib/uptime-monitor/sites.db "ALTER TABLE sites ADD COLUMN error_message TEXT;"

# Перевірте схему
sqlite3 /var/lib/uptime-monitor/sites.db ".schema sites"

# Запустіть службу
sudo systemctl start uptime-monitor
```

### Після оновлення схеми — оновіть код:

```bash
# Зупиніть службу
sudo systemctl stop uptime-monitor

# Зробіть бекап
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/ --type on-change --comment "Pre-update backup"

# Оновіть код
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash

# Перевірте
sudo systemctl status uptime-monitor
```

---

## 🔄 Міграція БД на інший сервер

### Крок 1: На старому сервері (звідки копіюємо)

```bash
# 1. Зупиніть службу
sudo systemctl stop uptime-monitor

# 2. Зробіть бекап БД
sudo cp /var/lib/uptime-monitor/sites.db /tmp/sites_migration_backup.db

# 3. Перевірте схему (має бути з колонками v2.0.0)
sqlite3 /tmp/sites_migration_backup.db ".schema sites"

# 4. Перевірте дані
sqlite3 /tmp/sites_migration_backup.db "SELECT COUNT(*) FROM sites;"

# 5. (Опціонально) Зробіть повний бекап
sudo tar -czf /tmp/uptime-full-backup.tar.gz \
    /var/lib/uptime-monitor/sites.db \
    /etc/uptime-monitor/config.json \
    /etc/uptime-monitor/ssl/

# 6. Скопіюйте на локальний комп'ютер
scp sa@OLD_SERVER:/tmp/sites_migration_backup.db ./sites_backup.db
```

### Крок 2: На новому сервері (куди переносимо)

```bash
# 1. Встановіть Uptime Monitor (чиста установка)
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash

# 2. Зупиніть службу
sudo systemctl stop uptime-monitor

# 3. Завантажте БД
scp ./sites_backup.db sa@NEW_SERVER:/tmp/sites_backup.db

# 4. Скопіюйте БД в правильне місце
sudo cp /tmp/sites_backup.db /var/lib/uptime-monitor/sites.db

# 5. Встановіть правильні права
sudo chown uptime-monitor:uptime-monitor /var/lib/uptime-monitor/sites.db
sudo chmod 644 /var/lib/uptime-monitor/sites.db

# 6. Перевірте схему і дані
sqlite3 /var/lib/uptime-monitor/sites.db ".schema sites"
sqlite3 /var/lib/uptime-monitor/sites.db "SELECT COUNT(*) FROM sites;"

# 7. (Опціонально) Відновіть config.json
sudo cp /tmp/config.json /etc/uptime-monitor/config.json
# Відредагуйте server.domain на новий IP

# 8. Запустіть службу
sudo systemctl start uptime-monitor

# 9. Перевірте
sudo systemctl status uptime-monitor
```

### Крок 3: Перевірка

```bash
# Відкрийте в браузері
http://NEW_SERVER_IP:8080

# Увійдіть з паролем зі старого сервера
```

---

## 🛠️ Вирішення проблем

### Помилка: `no such column: status`

**Причина:** Стара схема БД (до v2.0.0)

**Вирішення:**
```bash
sudo systemctl stop uptime-monitor
sqlite3 /var/lib/uptime-monitor/sites.db "ALTER TABLE sites ADD COLUMN status TEXT DEFAULT 'unknown';"
sqlite3 /var/lib/uptime-monitor/sites.db "ALTER TABLE sites ADD COLUMN status_code INTEGER;"
sqlite3 /var/lib/uptime-monitor/sites.db "ALTER TABLE sites ADD COLUMN response_time REAL;"
sqlite3 /var/lib/uptime-monitor/sites.db "ALTER TABLE sites ADD COLUMN error_message TEXT;"
sudo systemctl start uptime-monitor
```

### Помилка: `attempt to write a readonly database`

**Причина:** Неправильні права на БД

**Вирішення:**
```bash
sudo chown uptime-monitor:uptime-monitor /var/lib/uptime-monitor/sites.db
sudo chmod 644 /var/lib/uptime-monitor/sites.db
```

### Помилка: `ImportError: attempted relative import`

**Причина:** Проблеми з імпортом в `main.py`

**Вирішення:**
```bash
# Видаліть кеш
sudo rm -rf /opt/uptime-monitor/__pycache__
sudo rm -rf /opt/uptime-monitor/Uptime_Robot/__pycache__
sudo rm -rf /opt/uptime-monitor/routers/__pycache__

# Перезапустіть службу
sudo systemctl restart uptime-monitor
```

### Помилка: `TypeError: object dict can't be used in 'await' expression`

**Причина:** Несумісність async/await в `dependencies.py`

**Вирішення:** Переконайтеся, що `dependencies.py` має правильний код:

```python
from fastapi import Depends, HTTPException, Request
try:
    import auth_module
    from state import DB_PATH
except ImportError:
    from . import auth_module
    from .state import DB_PATH

async def get_current_user(request: Request):
    session_id = request.cookies.get("session_id")
    user = await auth_module.validate_session(session_id, DB_PATH)
    if not user:
        return None
    return user
```

---

## 📊 Контрольний список

### Перед оновленням/міграцією:
- [ ] Зробити бекап БД
- [ ] Перевірити схему БД
- [ ] Додати відсутні колонки (якщо потрібно)
- [ ] Зупинити службу

### Після оновлення/міграції:
- [ ] Перевірити статус служби
- [ ] Перевірити логи
- [ ] Відкрити веб-інтерфейс
- [ ] Увійти в систему
- [ ] Перевірити всі сайти
- [ ] Перевірити сповіщення

---

## 📞 Контакти для підтримки

- **GitHub Issues:** https://github.com/ajjs1ajjs/Uptime-Monitor/issues
- **Документація:** https://github.com/ajjs1ajjs/Uptime-Monitor/tree/main/docs

---

**Останнє оновлення:** 2026-03-24
**Версія:** 2.0.0
