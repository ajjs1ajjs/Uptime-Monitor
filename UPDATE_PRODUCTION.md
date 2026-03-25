# 🔄 Оновлення Uptime Monitor на Production

**Останнє оновлення:** 2026-03-25  
**Версія:** 2.0.0

---

## 📋 Зміст

1. [Швидке оновлення (рекомендовано)](#швидке-оновлення-рекомендовано)
2. [Безпечне оновлення з бекапом](#безпечне-оновлення-з-бекапом)
3. [Оновлення через Git](#оновлення-через-git)
4. [Оновлення через ZIP](#оновлення-через-zip)
5. [Відновлення після оновлення (Rollback)](#відновлення-після-оновлення-rollback)
6. [Перевірка після оновлення](#перевірка-після-оновлення)
7. [Усунення несправностей](#усунення-несправностей)

---

## ⚡ Швидке оновлення (рекомендовано)

Для більшості випадків — оновлення через install.sh:

```bash
# 1. Завантажити та виконати інсталятор
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash

# 2. Перевірити статус
sudo systemctl status uptime-monitor uptime-monitor-worker

# 3. Перевірити логи
sudo journalctl -u uptime-monitor --since "5 minutes ago"
```

**Час:** ~2-3 хвилини  
**Ризики:** Низькі (інсталятор зберігає конфігурацію)

---

## 🛡️ Безпечне оновлення з бекапом

Для критичних середовищ — з повним бекапом:

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
```

### Крок 3: BECKAP (ОБОВ'ЯЗКОВО!)

```bash
# Створити бекап
sudo mkdir -p "$BACKUP_ROOT"
sudo $APP_DIR/scripts/backup-system.sh \
  --dest "$BACKUP_ROOT" \
  --type on-change \
  --comment "pre-update-$TS" \
  --verify

# Додатково зберегти конфігурацію
sudo cp /etc/uptime-monitor/config.json "/backup/config.pre-update.$TS.json"
sudo cp /etc/systemd/system/uptime-monitor.service "/backup/uptime-monitor.service.pre-update.$TS" 2>/dev/null || true
```

### Крок 4: Оновлення

```bash
# Зупинити служби
sudo systemctl stop $SERVICE
sudo systemctl stop ${SERVICE}-worker

# Оновити код (Git метод)
cd /opt/uptime-monitor
if [ -d .git ]; then
    sudo git fetch --all --prune
    sudo git checkout main
    sudo git pull --ff-only origin main
else
    # ZIP метод якщо немає .git
    cd /tmp
    sudo wget -q https://github.com/ajjs1ajjs/Uptime-Monitor/archive/refs/heads/main.zip -O uptime.zip
    sudo unzip -o uptime.zip
    sudo cp -r Uptime-Monitor-main/Uptime_Robot/* $APP_DIR/
    sudo rm -rf uptime.zip Uptime-Monitor-main
fi

# Встановити права
sudo chown -R uptime-monitor:uptime-monitor $APP_DIR

# Перезапустити служби
sudo systemctl daemon-reload
sudo systemctl start $SERVICE
sudo systemctl start ${SERVICE}-worker
```

### Крок 5: Перевірка

```bash
# Статус
sudo systemctl status $SERVICE --no-pager
sudo systemctl status ${SERVICE}-worker --no-pager

# API тест
curl -s http://localhost:8080/health

# Логи
sudo journalctl -u $SERVICE -f
```

**Час:** ~5-7 хвилин  
**Ризики:** Дуже низькі (є бекап)

---

## 📦 Оновлення через Git

Якщо встановлено через `git clone`:

```bash
cd /opt/uptime-monitor

# 1. Резервна копія
sudo cp -r Uptime_Robot Uptime_Robot.backup.$(date +%Y%m%d-%H%M%S)

# 2. Оновлення
sudo git pull origin main

# 3. Перезапуск
sudo systemctl restart uptime-monitor
sudo systemctl restart uptime-monitor-worker

# 4. Перевірка
sudo systemctl status uptime-monitor uptime-monitor-worker
```

---

## 📥 Оновлення через ZIP

Якщо немає Git:

```bash
# 1. Резервна копія
sudo cp -r /opt/uptime-monitor/Uptime_Robot \
  /opt/uptime-monitor/Uptime_Robot.backup.$(date +%Y%m%d-%H%M%S)

# 2. Завантажити нову версію
cd /tmp
wget -q https://github.com/ajjs1ajjs/Uptime-Monitor/archive/refs/heads/main.zip -O uptime.zip

# 3. Розпакувати
unzip -o uptime.zip

# 4. Оновити файли
sudo cp -r Uptime-Monitor-main/Uptime_Robot/* /opt/uptime-monitor/

# 5. Прибрати тимчасові файли
rm -rf uptime.zip Uptime-Monitor-main

# 6. Перезапустити
sudo systemctl restart uptime-monitor
sudo systemctl restart uptime-monitor-worker
```

---

## 🔄 Відновлення після оновлення (Rollback)

### Спосіб 1: Git rollback

```bash
cd /opt/uptime-monitor
sudo git reset --hard HEAD~1
sudo systemctl restart uptime-monitor
sudo systemctl restart uptime-monitor-worker
```

### Спосіб 2: Відновлення з бекапу файлів

```bash
# Знайти бекап
ls -la /opt/uptime-monitor/Uptime_Robot.backup.*

# Відновити
sudo cp -r /opt/uptime-monitor/Uptime_Robot.backup.*/ /opt/uptime-monitor/Uptime_Robot/
sudo chown -R uptime-monitor:uptime-monitor /opt/uptime-monitor/Uptime_Robot
sudo systemctl restart uptime-monitor
sudo systemctl restart uptime-monitor-worker
```

### Спосіб 3: Повне відновлення з бекапу системи

```bash
# Знайти бекап
sudo /opt/uptime-monitor/scripts/backup-system.sh --list

# Відновити
sudo /opt/uptime-monitor/scripts/restore-system.sh \
  --from /backup/uptime-monitor/on-change/backup-YYYYMMDD-HHMMSS.tar.gz
```

---

## ✅ Перевірка після оновлення

### Основні перевірки

```bash
# 1. Статус служб
sudo systemctl is-active uptime-monitor
sudo systemctl is-active uptime-monitor-worker

# 2. Перевірка портів
sudo ss -tlnp | grep 8080

# 3. API тест
curl -s http://localhost:8080/health

# 4. Отримати сайти
curl -s http://localhost:8080/api/sites | python3 -m json.tool | head -20

# 5. Версія коду
cd /opt/uptime-monitor && git log -1 --oneline
```

### Перевірка моніторингу

```bash
# Логи worker
sudo journalctl -u uptime-monitor-worker --since "10 minutes ago" | tail -30

# Статус сайтів
sudo sqlite3 /var/lib/uptime-monitor/sites.db \
  "SELECT name, status, last_down_alert FROM sites WHERE is_active = 1 LIMIT 10;"
```

### Перевірка сповіщень

```bash
# Діагностика
sudo /opt/uptime-monitor/check-notifications.sh

# Або вручну
sudo sqlite3 /var/lib/uptime-monitor/sites.db \
  "SELECT config FROM notify_config WHERE id = 1;" | python3 -m json.tool
```

---

## 🐛 Усунення несправностей

### Служба не запускається

```bash
# Переглянути логи
sudo journalctl -u uptime-monitor --since "5 minutes ago"

# Спробувати запустити вручну
sudo -u uptime-monitor /opt/uptime-monitor/venv/bin/python /opt/uptime-monitor/main.py

# Перевірити синтаксис
sudo -u uptime-monitor /opt/uptime-monitor/venv/bin/python -m py_compile \
  /opt/uptime-monitor/*.py
```

### Worker не працює

```bash
# Логи worker
sudo journalctl -u uptime-monitor-worker --since "5 minutes ago"

# Перевірити імпорти
sudo -u uptime-monitor /opt/uptime-monitor/venv/bin/python \
  -c "import monitoring; import models; print('OK')"

# Перезапустити
sudo systemctl restart uptime-monitor-worker
```

### Сповіщення не приходять

```bash
# Перевірити налаштування
sudo sqlite3 /var/lib/uptime-monitor/sites.db \
  "SELECT config FROM notify_config WHERE id = 1;" | python3 -m json.tool

# Запустити діагностику
sudo /opt/uptime-monitor/check-notifications.sh

# Перезапустити worker
sudo systemctl restart uptime-monitor-worker
```

### Конфлікти при Git pull

```bash
cd /opt/uptime-monitor

# Зберегти локальні зміни
sudo git stash

# Оновити
sudo git pull origin main

# Застосувати зміни (якщо потрібно)
sudo git stash pop
```

### Помилки після оновлення

```bash
# 1. Перевірити логи
sudo journalctl -u uptime-monitor -n 100 --no-pager

# 2. Відновити бекап
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto

# 3. Або відкотити Git
cd /opt/uptime-monitor
sudo git reset --hard HEAD~1
sudo systemctl restart uptime-monitor
```

---

## 📊 Поточні налаштування (v2.0.0)

| Параметр | Значення | Опис |
|----------|----------|------|
| `check_interval` | 60 сек | Періодичність перевірки сайтів |
| `down_failures_threshold` | 1 | Помилка для статусу DOWN |
| `up_success_threshold` | 1 | Успіх для статусу UP |
| `still_down_repeat_seconds` | 300 сек | Повтор сповіщення (5 хв) |
| `ssl_notification_days` | 14 днів | Попередження про SSL |
| `ssl_notification_cooldown` | 21600 сек | Пауза між SSL-сповіщеннями (6 год) |
| `ssl_check_interval_hours` | 6 годин | Періодичність SSL перевірки |
| `request_timeout_seconds` | 60 сек | Таймаут HTTP-запиту |
| `treat_4xx_as_down` | true | Вважати 4xx помилкою |

---

## 📞 Додаткові ресурси

- **GitHub Issues:** https://github.com/ajjs1ajjs/Uptime-Monitor/issues
- **Логи:** `/var/log/uptime-monitor/`
- **База даних:** `/var/lib/uptime-monitor/sites.db`
- **Конфігурація:** `/etc/uptime-monitor/config.json`

---

## 📝 Чекліст оновлення

- [ ] Зроблено бекап (`--type on-change --verify`)
- [ ] Збережено конфігурацію окремо
- [ ] Служби зупинено перед оновленням
- [ ] Код оновлено (Git або ZIP)
- [ ] Права встановлено (`chown uptime-monitor:uptime-monitor`)
- [ ] Служби перезапущено
- [ ] Перевірено статус служб
- [ ] Перевірено API (`/health`)
- [ ] Перевірено логи
- [ ] Перевірено сповіщення (опціонально)

---

**✅ Якщо всі перевірки пройшли — оновлення успішне!**
