# 🔧 Оновлення Uptime Monitor - Повна інструкція

## ⚠️ КРИТИЧНО ВАЖЛИВО

**Проблема з якою зіткнулися:** При розпакуванні ZIP без `sudo` файли створюються з правами користувача, потім неможливо скопіювати в `/opt/uptime-monitor/`.

**Рішення:** **ЗАВЖДИ** використовуйте `sudo` для всіх операцій з ZIP!

---

## 📋 Повна інструкція з оновлення (ZIP метод)

### Крок 1: Зупинити службу

```bash
sudo systemctl stop uptime-monitor
```

### Крок 2: Зробити бекап (ОБОВ'ЯЗКОВО!)

```bash
sudo /opt/uptime-monitor/scripts/backup-system.sh \
    --dest /backup/uptime-monitor/ \
    --type on-change \
    --comment "pre-update-$(date +%Y%m%d-%H%M%S)" \
    --verify
```

### Крок 3: Завантажити ZIP

```bash
cd /tmp
wget https://github.com/ajjs1ajjs/Uptime-Monitor/archive/refs/heads/main.zip -O uptime_update.zip
```

### Крок 4: **Видалити стару папку** (якщо є)

```bash
# КРИТИЧНО: Видалити З СУДОМ!
sudo rm -rf /tmp/Uptime-Monitor-main
```

### Крок 5: Розпакувати З СУДОМ

```bash
# КРИТИЧНО: Розпакувати З СУДОМ!
sudo unzip -o uptime_update.zip
```

### Крок 6: Скопіювати файли

```bash
sudo cp -r /tmp/Uptime-Monitor-main/Uptime_Robot/* /opt/uptime-monitor/
```

### Крок 7: Прибрати тимчасові файли

```bash
# КРИТИЧНО: Прибрати З СУДОМ!
sudo rm -rf uptime_update.zip /tmp/Uptime-Monitor-main
```

### Крок 8: Запустити службу

```bash
sudo systemctl start uptime-monitor
```

### Крок 9: Перевірити

```bash
# Статус
sudo systemctl status uptime-monitor

# HTTP перевірка
curl -fsS http://localhost:8080 && echo "HTTP OK" || echo "HTTP FAIL"

# Логи
sudo journalctl -u uptime-monitor -n 30 --no-pager
```

---

## 🚀 Все в одному (copy-paste)

```bash
# Зупинити, бекап, завантажити, розпакувати, скопіювати, запустити
sudo systemctl stop uptime-monitor && \
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/ --type on-change --verify && \
cd /tmp && \
sudo rm -rf /tmp/Uptime-Monitor-main && \
wget https://github.com/ajjs1ajjs/Uptime-Monitor/archive/refs/heads/main.zip -O uptime_update.zip && \
sudo unzip -o uptime_update.zip && \
sudo cp -r /tmp/Uptime-Monitor-main/Uptime_Robot/* /opt/uptime-monitor/ && \
sudo rm -rf uptime_update.zip /tmp/Uptime-Monitor-main && \
sudo systemctl start uptime-monitor && \
sudo systemctl status uptime-monitor && \
curl -fsS http://localhost:8080 && echo "HTTP OK" || echo "HTTP FAIL"
```

---

## 🔄 Git метод (якщо встановлено через git clone)

```bash
cd /opt/uptime-monitor

# Перевірити чи є .git
if [ -d .git ]; then
    echo "Git installation"
    
    # Бекап
    sudo /opt/uptime-monitor/scripts/backup-system.sh \
        --dest /backup/uptime-monitor/ \
        --type on-change
    
    # Оновлення
    sudo git fetch --all --prune
    sudo git checkout main
    sudo git pull --ff-only origin main
    
    # Перезапуск
    sudo systemctl restart uptime-monitor
    
    # Перевірка
    sudo systemctl status uptime-monitor
    curl -fsS http://localhost:8080 && echo "HTTP OK" || echo "HTTP FAIL"
else
    echo "Not a git installation. Use ZIP method."
fi
```

---

## 🆘 Вирішення проблем

### Проблема: `Permission denied` при розпакуванні

**Причина:** Попередній `unzip` без `sudo` створив файли з правами користувача.

**Рішення:**

```bash
# Видалити стару папку З СУДОМ
sudo rm -rf /tmp/Uptime-Monitor-main

# Розпакувати З СУДОМ
sudo unzip -o uptime_update.zip

# Скопіювати З СУДОМ
sudo cp -r /tmp/Uptime-Monitor-main/Uptime_Robot/* /opt/uptime-monitor/

# Прибрати З СУДОМ
sudo rm -rf uptime_update.zip /tmp/Uptime-Monitor-main
```

---

### Проблема: `unzip: command not found`

**Рішення:**

```bash
sudo apt update && sudo apt install -y unzip
```

---

### Проблема: `curl: Failed to connect to localhost port 8080`

**Причина:** Сервіс щойно запустився, потрібно зачекати 5-10 секунд.

**Рішення:**

```bash
# Зачекати і перевірити знову
sleep 5
curl -fsS http://localhost:8080 && echo "HTTP OK" || echo "HTTP FAIL"

# Перевірити чи слухає порт
sudo ss -tlnp | grep 8080

# Перевірити логи
sudo journalctl -u uptime-monitor -n 30 --no-pager
```

---

### Проблема: Сервіс не запускається після оновлення

**Рішення:**

```bash
# Перевірити статус
sudo systemctl status uptime-monitor

# Перевірити логи
sudo journalctl -u uptime-monitor -n 50 --no-pager

# Відновити з бекапу
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto --force

# Або конкретний бекап
sudo /opt/uptime-monitor/scripts/restore-system.sh \
    --from /backup/uptime-monitor/on-change/backup-YYYYMMDD-HHMMSS.tar.gz \
    --force
```

---

## ✅ Контрольний список після оновлення

```bash
# 1. Статус сервісу
sudo systemctl status uptime-monitor

# 2. HTTP перевірка
curl -fsS http://localhost:8080

# 3. Логи
sudo journalctl -u uptime-monitor -n 30

# 4. Порт
sudo ss -tlnp | grep 8080

# 5. Веб-інтерфейс
# Відкрити http://192.168.71.145:8080 у браузері
```

---

## 📊 Порівняння методів

| Метод | Переваги | Недоліки | Коли |
|-------|----------|----------|------|
| **Git** | Швидко, чисто | Потребує `.git` | Production |
| **ZIP (one-liner)** | Універсально | Потребує `unzip` | Будь-де |
| **UPDATE_SCRIPT_SAFE.sh** | Повний захист | Довше | Production |
| **UPDATE_SCRIPT_FAST.sh** | Дуже швидко | Без бекапу | Test/Dev |

---

## 🔗 Корисні команди

```bash
# Список бекапів
sudo /opt/uptime-monitor/scripts/restore-system.sh --list

# Відновити з останнього
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto --force

# Статус бекапів
sudo /opt/uptime-monitor/scripts/backup-system.sh --status

# Конфігурація
sudo nano /etc/uptime-monitor/config.json

# Перевірити JSON
python3 -m json.tool /etc/uptime-monitor/config.json
```

---

## 🎯 Рекомендації

### Production

1. **Завжди** робіть бекап перед оновленням
2. Використовуйте `UPDATE_SCRIPT_SAFE.sh` або повну інструкцію вище
3. Заплануйте даунтайм
4. Майте план rollback

### Test/Dev

1. Можна використати `UPDATE_SCRIPT_FAST.sh`
2. Або one-liner команду
3. Все одно бажано зробити бекап

---

## 📞 Швидка допомога

```bash
# Все в одному з бекапом
sudo systemctl stop uptime-monitor && \
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/ --type on-change --verify && \
cd /tmp && sudo rm -rf /tmp/Uptime-Monitor-main && \
wget https://github.com/ajjs1ajjs/Uptime-Monitor/archive/refs/heads/main.zip -O uptime_update.zip && \
sudo unzip -o uptime_update.zip && \
sudo cp -r /tmp/Uptime-Monitor-main/Uptime_Robot/* /opt/uptime-monitor/ && \
sudo rm -rf uptime_update.zip /tmp/Uptime-Monitor-main && \
sudo systemctl start uptime-monitor && \
sleep 5 && \
sudo systemctl status uptime-monitor && \
curl -fsS http://localhost:8080 && echo "HTTP OK" || echo "HTTP FAIL"
```

---

## 📚 Документація

- [UPDATE_QUICKSTART.md](UPDATE_QUICKSTART.md) - Швидка інструкція
- [UPDATE_FIXES.md](UPDATE_FIXES.md) - Виправлення проблем
- [SAFE_UPDATE_RUNBOOK.md](SAFE_UPDATE_RUNBOOK.md) - Production runbook
- [BACKUP.md](BACKUP.md) - Система бекапів
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Вирішення проблем

---

**Останнє оновлення:** 2026-03-04  
**Версія:** v2.0.0
