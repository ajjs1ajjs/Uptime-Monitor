# Uptime Monitor — Інструкція з оновлення

## 📋 Швидке оновлення (рекомендовано)

```bash
cd /opt/uptime-monitor

# Зупинити сервіс
sudo systemctl stop uptime-monitor

# Оновити з GitHub
sudo chown -R sa:sa .git/
git fetch origin
git reset --hard origin/main

# Видалити старі файли (якщо є)
rm -f ui_templates.py
rm -f page.html
rm -f Uptime_Robot/page.html

# Видалити кеш Python
find . -path ./venv -prune -o -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -path ./venv -prune -o -name "*.pyc" -delete 2>/dev/null

# Виправити права
sudo chown -R uptime-monitor:uptime-monitor main.py Uptime_Robot/main.py Uptime_Robot/ui_templates.py uptime_monitor.log

# Запустити сервіс
sudo systemctl start uptime-monitor
sudo systemctl status uptime-monitor
```

**В браузері:**
- Натисніть **Ctrl + Shift + R** (очистка кешу)
- Або відкрийте в режимі інкогніто: **Ctrl + Shift + N**

---

## 🔧 Автоматичне оновлення (deploy_update.sh)

Якщо встановлено скрипт `deploy_update.sh`:

```bash
cd /opt/uptime-monitor
sudo ./deploy_update.sh
```

**Інші команди:**
```bash
sudo ./deploy_update.sh --status    # Перевірити статус
sudo ./deploy_update.sh --logs      # Показати логи
sudo ./deploy_update.sh --rollback  # Відкат до попередньої версії
sudo ./deploy_update.sh --help      # Допомога
```

---

## 📝 Оновлення через wget (якщо git не працює)

```bash
cd /opt/uptime-monitor

# Зупинити сервіс
sudo systemctl stop uptime-monitor

# Завантажити оновлені файли
sudo wget -O main.py "https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/Uptime_Robot/main.py"
sudo wget -O Uptime_Robot/ui_templates.py "https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/Uptime_Robot/ui_templates.py"

# Видалити старі файли
rm -f ui_templates.py
rm -f page.html
rm -f Uptime_Robot/page.html

# Видалити кеш
find . -path ./venv -prune -o -name "__pycache__" -exec rm -rf {} + 2>/dev/null

# Виправити права
sudo chown uptime-monitor:uptime-monitor main.py Uptime_Robot/ui_templates.py

# Запустити сервіс
sudo systemctl start uptime-monitor
sudo systemctl status uptime-monitor
```

---

## ✅ Перевірка після оновлення

```bash
cd /opt/uptime-monitor

# Перевірити версію
git log --oneline -1

# Перевірити файл
grep -c "loadUptimeChart" Uptime_Robot/ui_templates.py  # Має бути 0

# Перевірити сервіс
sudo systemctl status uptime-monitor

# Перевірити API
curl -s http://localhost:8080/api/server-time
```

---

## 🚨 Якщо щось пішло не так

### Відкат до попередньої версії:
```bash
cd /opt/uptime-monitor
sudo ./deploy_update.sh --rollback
```

### Або вручну:
```bash
cd /opt/uptime-monitor
sudo git log --oneline -5  # Знайти попередній коміт
sudo git reset --hard <PREVIOUS_COMMIT>
sudo systemctl restart uptime-monitor
```

### Перевірка логів:
```bash
sudo journalctl -u uptime-monitor -n 50 --no-pager
sudo tail -50 /opt/uptime-monitor/uptime_monitor.log
```

---

## 📌 Важливі файли

| Файл | Призначення |
|------|-------------|
| `main.py` | Головний файл додатку |
| `Uptime_Robot/ui_templates.py` | HTML шаблони |
| `Uptime_Robot/main.py` | API та маршрути |
| `uptime_monitor.log` | Логи |
| `deploy_update.sh` | Скрипт оновлення |

---

## ⚠️ Увага!

1. **Завжди зупиняйте сервіс** перед оновленням
2. **Видаляйте кеш Python** (`__pycache__`, `*.pyc`)
3. **Видаляйте старі файли** (`ui_templates.py`, `page.html` в корені)
4. **Виправляйте права** після оновлення
5. **Очищайте кеш браузера** після оновлення (Ctrl + Shift + R)

---

## 🔄 Повний цикл оновлення

```bash
# 1. Зупинити
sudo systemctl stop uptime-monitor

# 2. Оновити код
cd /opt/uptime-monitor
sudo chown -R sa:sa .git/
git fetch origin
git reset --hard origin/main

# 3. Прибрати старе
rm -f ui_templates.py page.html Uptime_Robot/page.html
find . -path ./venv -prune -o -name "__pycache__" -exec rm -rf {} + 2>/dev/null

# 4. Виправити права
sudo chown -R uptime-monitor:uptime-monitor main.py Uptime_Robot/main.py Uptime_Robot/ui_templates.py uptime_monitor.log

# 5. Запустити
sudo systemctl start uptime-monitor

# 6. Перевірити
sudo systemctl status uptime-monitor
curl -s http://localhost:8080/api/server-time

# 7. В браузері: Ctrl + Shift + R
```

---

**Останнє оновлення:** 2026-03-17
**Версія:** main branch
**GitHub:** https://github.com/ajjs1ajjs/Uptime-Monitor
