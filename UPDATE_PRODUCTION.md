# 🔄 Оновлення Uptime Monitor на Production

**Останнє оновлення:** 2026-05-13  
**Версія:** 2.0.0

---

## 📋 Зміст

1. [Pre-Update Checklist](#-pre-update-checklist)
2. [Швидке оновлення (рекомендовано)](#-швидке-оновлення-рекомендовано)
3. [Безпечне оновлення з бекапом](#-безпечне-оновлення-з-бекапом)
4. [Database Migrations](#-database-migrations)
5. [Оновлення через Git](#-оновлення-через-git)
6. [Оновлення через ZIP](#-оновлення-через-zip)
7. [Post-Update Verification](#-post-update-verification)
8. [Відновлення після оновлення (Rollback)](#-відновлення-після-оновлення-rollback)
9. [Rollback з міграцією БД](#-rollback-з-міграцією-бд)
10. [Усунення несправностей](#-усунення-несправностей)
11. [Security Notes (v2.0.0)](#-security-notes-v200)

---

## ✅ Pre-Update Checklist

Перед будь-яким оновленням виконайте:

- [ ] **Прочитайте CHANGELOG.md** — перевірте наявність breaking changes
- [ ] **Перевірте вільне місце:** `df -h` (мінімум 500MB)
- [ ] **Перевірте розмір БД:** `du -sh /var/lib/uptime-monitor/sites.db` (<1GB для швидкої міграції)
- [ ] **Перевірте наявність unzip:** `command -v unzip || sudo apt install -y unzip`
- [ ] **Запишіть поточну версію:** `cd /opt/uptime-monitor && git log -1 --oneline`
- [ ] **Зробіть повний backup** (див. інструкцію нижче)
- [ ] **Повідомте команду** про плановий даунтайм (якщо критично)

---

## ⚡ Швидке оновлення (рекомендовано)

Для більшості випадків — скрипт `deploy_update.sh`:

```bash
sudo /opt/uptime-monitor/deploy_update.sh
```

Скрипт автоматично:
1. Робить pre-update backup (БД + конфіг + systemd units)
2. Зупиняє сервіси
3. Оновлює код (Git pull або ZIP)
4. Запускає сервіси
5. Перевіряє health + статус

Для кастомних параметрів:
```bash
sudo INSTALL_DIR=/opt/uptime-monitor APP_USER=uptime-monitor \
  BACKUP_ROOT=/backup/uptime-monitor \
  /opt/uptime-monitor/deploy_update.sh
```

**Час:** ~2-5 хвилин  
**Ризики:** Низькі (автоматичний бекап + rollback)

---

## 🛡️ Безпечне оновлення з бекапом

### Крок 1: Підготовка

```bash
SERVICE=uptime-monitor
APP_DIR=/opt/uptime-monitor
BACKUP_ROOT=/backup/uptime-monitor
TS=$(date +%Y%m%d-%H%M%S)
```

### Крок 2: Перевірка поточного стану

```bash
# Статус служб
sudo systemctl status $SERVICE --no-pager
sudo systemctl status ${SERVICE}-worker --no-pager

# Останні логи
sudo journalctl -u $SERVICE -n 50 --no-pager

# Поточна версія
cd $APP_DIR && git log -1 --oneline
```

### Крок 3: BECKAP (ОБОВ'ЯЗКОВО!)

```bash
# Повний бекап системи
sudo mkdir -p "$BACKUP_ROOT"
sudo $APP_DIR/scripts/backup-system.sh \
  --dest "$BACKUP_ROOT" \
  --type on-change \
  --comment "pre-update-$TS" \
  --verify

# Додатковий бекап конфігу та БД
sudo cp /etc/uptime-monitor/config.json "$BACKUP_ROOT/config.pre-update.$TS.json"
sudo cp /var/lib/uptime-monitor/sites.db "$BACKUP_ROOT/sites.pre-update.$TS.db"
sudo cp /etc/systemd/system/uptime-monitor.service "$BACKUP_ROOT/" 2>/dev/null || true
sudo cp /etc/systemd/system/uptime-monitor-worker.service "$BACKUP_ROOT/" 2>/dev/null || true
cd $APP_DIR && git log -1 --oneline > "$BACKUP_ROOT/pre-update-commit.$TS.txt"
```

### Крок 4: Оновлення

```bash
# Зупинити служби
sudo systemctl stop $SERVICE
sudo systemctl stop ${SERVICE}-worker
sleep 2

# Оновити код (Git або ZIP)
cd $APP_DIR
if [ -d .git ]; then
    sudo git fetch --all --prune
    sudo git checkout main
    sudo git pull --ff-only origin main
    sudo chown -R uptime-monitor:uptime-monitor $APP_DIR
else
    cd /tmp
    sudo wget -q https://github.com/ajjs1ajjs/Uptime-Monitor/archive/refs/heads/main.zip -O uptime.zip
    sudo unzip -o uptime.zip
    sudo cp -r Uptime-Monitor-main/Uptime_Robot/* $APP_DIR/
    sudo chown -R uptime-monitor:uptime-monitor $APP_DIR
    sudo rm -rf uptime.zip Uptime-Monitor-main
fi

# Оновити залежності (якщо змінились)
# sudo -u uptime-monitor $APP_DIR/venv/bin/pip install -r $APP_DIR/requirements.txt -U

# Запустити служби
sudo systemctl daemon-reload
sudo systemctl start $SERVICE
sudo systemctl start ${SERVICE}-worker
sleep 3
```

### Крок 5: Перевірка

```bash
# Статус служб
sudo systemctl status $SERVICE --no-pager
sudo systemctl status ${SERVICE}-worker --no-pager

# Health check
curl -s http://localhost:8080/health

# Перевірка API
curl -s http://localhost:8080/api/sites | python3 -m json.tool | head -10

# Логи (без помилок)
sudo journalctl -u $SERVICE -n 50 --no-pager | grep -i "error\|traceback" || echo "No errors"

# Версія після апдейту
cd $APP_DIR && git log -1 --oneline
```

---

## 🗃️ Database Migrations

Якщо оновлення включає зміни в схемі БД (нові таблиці, колонки), виконайте міграцію:

```bash
# Автоматична міграція (модель init_database виконує ALTER TABLE IF NOT EXISTS)
sudo -u uptime-monitor /opt/uptime-monitor/venv/bin/python -c "
import asyncio
from Uptime_Robot.models import init_database
asyncio.run(init_database('/var/lib/uptime-monitor/sites.db'))
print('Migration completed')
"

# Перевірка схеми
sudo sqlite3 /var/lib/uptime-monitor/sites.db ".schema sites" | head -5
```

> **Важливо:** Перед міграцією обов'язково зробіть backup БД. Міграції в цьому проекті є ідемпотентними (використовують `ALTER TABLE ADD COLUMN IF NOT EXISTS` через `PRAGMA table_info`).

---

## 📦 Оновлення через Git

Якщо встановлено через `git clone`:

```bash
cd /opt/uptime-monitor
sudo cp /var/lib/uptime-monitor/sites.db /backup/sites.pre-update.$(date +%Y%m%d-%H%M%S).db
sudo cp -r Uptime_Robot Uptime_Robot.backup.$(date +%Y%m%d-%H%M%S)

sudo git fetch --all --prune
sudo git checkout main
sudo git pull --ff-only origin main
sudo chown -R uptime-monitor:uptime-monitor .

sudo systemctl restart uptime-monitor
sudo systemctl restart uptime-monitor-worker
sudo systemctl status uptime-monitor uptime-monitor-worker
```

---

## 📥 Оновлення через ZIP

```bash
sudo cp /var/lib/uptime-monitor/sites.db /backup/sites.pre-update.$(date +%Y%m%d-%H%M%S).db

cd /tmp
wget -q https://github.com/ajjs1ajjs/Uptime-Monitor/archive/refs/heads/main.zip -O uptime.zip
unzip -o uptime.zip
sudo cp -r Uptime-Monitor-main/Uptime_Robot/* /opt/uptime-monitor/
sudo chown -R uptime-monitor:uptime-monitor /opt/uptime-monitor
rm -rf uptime.zip Uptime-Monitor-main

sudo systemctl restart uptime-monitor
sudo systemctl restart uptime-monitor-worker
```

---

## 🔄 Відновлення після оновлення (Rollback)

### Спосіб 1: Git rollback (без змін БД)

```bash
cd /opt/uptime-monitor
sudo systemctl stop uptime-monitor uptime-monitor-worker
sudo git reset --hard HEAD@{1}
sudo systemctl start uptime-monitor uptime-monitor-worker
sudo systemctl status uptime-monitor uptime-monitor-worker
```

### Спосіб 2: Відновлення з бекапу файлів

```bash
# Знайти останній бекап
ls -la /opt/uptime-monitor/Uptime_Robot.backup.*
ls -la /backup/uptime-monitor/sites.pre-update.*

# Відновити код
sudo rm -rf /opt/uptime-monitor/Uptime_Robot
sudo cp -r /opt/uptime-monitor/Uptime_Robot.backup.*/ /opt/uptime-monitor/Uptime_Robot/
sudo chown -R uptime-monitor:uptime-monitor /opt/uptime-monitor

# Відновити БД
sudo systemctl stop uptime-monitor uptime-monitor-worker
sudo cp /backup/uptime-monitor/sites.pre-update.*.db /var/lib/uptime-monitor/sites.db
sudo chown uptime-monitor:uptime-monitor /var/lib/uptime-monitor/sites.db
sudo systemctl start uptime-monitor uptime-monitor-worker
```

### Спосіб 3: Повне відновлення з бекапу системи

```bash
# Знайти бекап
sudo /opt/uptime-monitor/scripts/backup-system.sh --list

# Відновити
sudo /opt/uptime-monitor/scripts/restore-system.sh \
  --from /backup/uptime-monitor/on-change/backup-YYYYMMDD-HHMMSS.tar.gz \
  --force
```

---

## 🔄 Rollback з міграцією БД

> **Коли використовувати:** Якщо оновлення змінило схему БД (нові таблиці/колонки), і простий `git reset` не допоможе — старому коду може не підходити нова схема.

```bash
# 1. Відкотити код
cd /opt/uptime-monitor
sudo git reset --hard HEAD@{1}
sudo chown -R uptime-monitor:uptime-monitor .

# 2. Відновити БД з бекапу (обов'язково!)
sudo systemctl stop uptime-monitor uptime-monitor-worker
sudo cp /backup/uptime-monitor/sites.pre-update.*.db /var/lib/uptime-monitor/sites.db
sudo chown uptime-monitor:uptime-monitor /var/lib/uptime-monitor/sites.db

# 3. Запустити
sudo systemctl start uptime-monitor uptime-monitor-worker

# 4. Перевірити
sudo systemctl status uptime-monitor uptime-monitor-worker --no-pager
curl -s http://localhost:8080/health
```

> **Попередження:** Якщо не відновити БД, старий код може працювати некоректно з новою схемою. Завжди відновлюйте і код, і БД разом.

---

## ✅ Post-Update Verification

### Smoke Tests

```bash
# 1. Служби живі
sudo systemctl is-active uptime-monitor uptime-monitor-worker

# 2. Health endpoint
curl -s http://localhost:8080/health | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='healthy'; print('OK')"

# 3. API працює
curl -s http://localhost:8080/api/sites | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Sites in DB: {len(d)}')"

# 4. Логи без помилок
sudo journalctl -u uptime-monitor -n 100 --no-pager | grep -ci "error\|traceback\|exception" || echo "0 errors"

# 5. Версія коду збігається
cd /opt/uptime-monitor && git log -1 --oneline

# 6. SSL сертифікати (якщо використовуються)
curl -s http://localhost:8080/api/ssl-certificates | python3 -m json.tool | head -10
```

---

## 🐛 Усунення несправностей

### Служба не запускається

```bash
sudo journalctl -u uptime-monitor -n 100 --no-pager
sudo -u uptime-monitor /opt/uptime-monitor/venv/bin/python -m py_compile /opt/uptime-monitor/Uptime_Robot/*.py
```

### Worker не працює

```bash
sudo journalctl -u uptime-monitor-worker -n 100 --no-pager
sudo -u uptime-monitor /opt/uptime-monitor/venv/bin/python -c "import monitoring; import models; print('OK')"
```

### Помилки після оновлення

```bash
# 1. Логи
sudo journalctl -u uptime-monitor -n 100 --no-pager

# 2. Rollback
sudo /opt/uptime-monitor/deploy_update.sh --rollback
```

---

## 🔒 Security Notes (v2.0.0)

Починаючи з v2.0.0, проект включає:

| Фіча | Опис |
|------|------|
| **CORS** | Налаштовується через `cors.allow_origins` в `config.json` |
| **SSL Verification** | `verify_ssl: true/false` в `alert_policy` |
| **Rate Limiting** | `/login` — 5 спроб за 15 хв на IP |
| **Encryption at Rest** | `email_password` шифрується через Fernet |
| **Password Policy** | Мін. 12 символів, upper+lower+digit |
| **Random Admin Password** | Генерується при першому запуску |
| **Security Headers** | X-Content-Type-Options, X-Frame-Options, X-XSS-Protection |

### Config Changes (v2.0.0)

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

---

## 📊 Параметри моніторингу (v2.0.0)

| Параметр | Значення | Опис |
|----------|----------|------|
| `check_interval` | 60 сек | Періодичність перевірки |
| `down_failures_threshold` | 1 | Помилок для статусу DOWN |
| `up_success_threshold` | 1 | Успіхів для статусу UP |
| `still_down_repeat_seconds` | 300 сек | Повтор сповіщення |
| `ssl_notification_days` | 14 днів | Попередження про SSL |
| `request_timeout_seconds` | 60 сек | Таймаут HTTP |
| `verify_ssl` | true | Перевіряти SSL сертифікати |

---

## 📝 Чекліст оновлення

- [ ] Прочитано CHANGELOG.md
- [ ] Зроблено бекап (`backup-system.sh --verify`)
- [ ] Збережено конфіг та БД окремо
- [ ] Служби зупинено
- [ ] Код оновлено (Git/ZIP)
- [ ] Залежності оновлено (pip install -r)
- [ ] Міграцію БД виконано (якщо потрібно)
- [ ] Права встановлено (chown)
- [ ] Служби запущено
- [ ] Health check passed
- [ ] API працює (sites, users)
- [ ] Логи без помилок
- [ ] Rollback протестовано (якщо є змога)
