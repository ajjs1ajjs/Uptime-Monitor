# 🚀 Швидке оновлення на Production

## ⚡ Спосіб 1: Оновлення лише файлів конфігурації (НАЙШВИДШИЙ)

Якщо потрібно оновити лише налаштування моніторингу без повного оновлення системи:

```bash
# 1. Завантажте оновлені файли
cd /opt/Uptime-Monitor
sudo git pull origin main

# 2. Перевірте зміни (опціонально)
git diff HEAD~1 Uptime_Robot/config_manager.py Uptime_Robot/monitoring.py

# 3. Перезапустіть сервіс
sudo systemctl restart uptime-monitor

# 4. Переконайтеся що сервіс працює
sudo systemctl status uptime-monitor
```

**Час виконання:** ~30 секунд  
**Ризики:** Мінімальні (лише зміна налаштувань)

---

## ⚡ Спосіб 2: Оновлення через git pull (РЕКОМЕНДОВАНО)

Повне оновлення з репозиторію:

```bash
# 1. Перейдіть у директорію
cd /opt/Uptime-Monitor

# 2. Зробіть резервну копію поточної версії
sudo cp -r Uptime_Robot Uptime_Robot.backup.$(date +%Y%m%d-%H%M%S)

# 3. Оновіть код
sudo git pull origin main

# 4. Перезапустіть сервіс
sudo systemctl restart uptime-monitor

# 5. Перевірте логи
sudo journalctl -u uptime-monitor -n 50 --no-pager
```

**Час виконання:** ~1-2 хвилини  
**Ризики:** Низькі

---

## ⚡ Спосіб 3: Оновлення з перевіркою (БЕЗПЕЧНИЙ)

Для критичних середовищ:

```bash
# 1. Створіть повну резервну копію
sudo /opt/Uptime-Monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/

# 2. Оновіть код
cd /opt/Uptime-Monitor
sudo git stash  # зберегти локальні зміни якщо є
sudo git pull origin main

# 3. Перевірте синтаксис Python
sudo -u uptime-monitor /opt/Uptime-Monitor/venv/bin/python -m py_compile Uptime_Robot/config_manager.py
sudo -u uptime-monitor /opt/Uptime-Monitor/venv/bin/python -m py_compile Uptime_Robot/monitoring.py

# 4. Перезапустіть сервіс
sudo systemctl restart uptime-monitor

# 5. Моніторьте логи 1 хвилину
sudo journalctl -u uptime-monitor -f
```

**Час виконання:** ~3-5 хвилин  
**Ризики:** Дуже низькі

---

## 🔄 Відкат змін (Rollback)

Якщо після оновлення виникли проблеми:

```bash
# Спосіб 1: Git rollback
cd /opt/Uptime-Monitor
sudo git reset --hard HEAD~1
sudo systemctl restart uptime-monitor

# Спосіб 2: Відновлення з бекапу
sudo cp -r Uptime_Robot.backup.* Uptime_Robot
sudo systemctl restart uptime-monitor

# Спосіб 3: Відновлення конфігурації
sudo cp /backup/uptime-monitor/config.json /etc/uptime-monitor/config.json
sudo systemctl restart uptime-monitor
```

---

## 📋 Поточні налаштування моніторингу

Після оновлення будуть застосовані такі значення:

| Параметр | Значення | Опис |
|----------|----------|------|
| `check_interval` | 60 сек | Періодичність перевірки сайтів |
| `down_failures_threshold` | 1 | Помилка для статусу DOWN |
| `up_success_threshold` | 1 | Успіх для статусу UP |
| `still_down_repeat_seconds` | 300 сек | Повтор сповіщення (5 хв) |
| `ssl_notification_days` | 14 днів | Попередження про SSL |
| `ssl_notification_cooldown` | 21600 сек | Пауза між SSL-сповіщеннями (6 год) |
| `request_timeout_seconds` | 60 сек | Таймаут HTTP-запиту |
| `treat_4xx_as_down` | true | Вважати 4xx помилкою |

---

## 🔍 Перевірка після оновлення

```bash
# 1. Статус сервісу
sudo systemctl status uptime-monitor

# 2. Останні логи
sudo tail -f /var/log/uptime-monitor/uptime_monitor.log

# 3. Перевірка портів
sudo netstat -tlnp | grep :8080

# 4. Тест API
curl -s http://localhost:8080/api/sites | head -c 200

# 5. Перевірка версії
cd /opt/Uptime-Monitor && git log -1 --oneline
```

---

## 🆘 Усунення несправностей

### Сервіс не запускається
```bash
sudo journalctl -u uptime-monitor --since "5 minutes ago"
sudo -u uptime-monitor /opt/Uptime-Monitor/venv/bin/python /opt/Uptime-Monitor/Uptime_Robot/main.py
```

### Помилки в логах
```bash
# Перевірте синтаксис
sudo -u uptime-monitor /opt/Uptime-Monitor/venv/bin/python -m py_compile Uptime_Robot/*.py

# Відновіть бекап
sudo /opt/Uptime-Monitor/scripts/restore-backup.sh
```

### Конфлікти при git pull
```bash
cd /opt/Uptime-Monitor
sudo git stash  # зберегти локальні зміни
sudo git pull origin main
sudo git stash pop  # застосувати зміни
```

---

## 📞 Контакти для підтримки

- **GitHub Issues:** https://github.com/ajjs1ajjs/Uptime-Monitor/issues
- **Логи:** `/var/log/uptime-monitor/`
- **База даних:** `/var/lib/uptime-monitor/sites.db`
