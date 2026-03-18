# ⚡ Швидка інструкція з оновлення

## 🚨 КРИТИЧНО ВАЖЛИВО

**Проблема:** При розпакуванні ZIP **без `sudo`** файли створюються з правами користувача, потім неможливо скопіювати в `/opt/uptime-monitor/`.

**Рішення:** **ЗАВЖДИ** використовуйте `sudo` для всіх операцій з ZIP!

```bash
sudo rm -rf /tmp/Uptime-Monitor-main    # Видалити стару папку
sudo unzip -o uptime_update.zip             # Розпакувати
sudo cp -r ...                              # Скопіювати
sudo rm -rf ...                             # Прибрати
```

---

## 🚨 Якщо отримали помилку `unzip not found`

```bash
# 1. Встановити unzip
sudo apt update && sudo apt install -y unzip

# 2. Продовжити оновлення
```

---

## 📋 Повне безпечне оновлення (5 хвилин)

```bash
# 0. Встановити unzip (якщо немає)
sudo apt install -y unzip

# 1. Зупинити службу
sudo systemctl stop uptime-monitor

# 2. ЗРОБИТИ БЕКАП (ОБОВ'ЯЗКОВО!)
sudo /opt/uptime-monitor/scripts/backup-system.sh \
    --dest /backup/uptime-monitor/ \
    --type on-change \
    --comment "pre-update" \
    --verify

# 3. Завантажити оновлення
cd /tmp
wget https://github.com/ajjs1ajjs/Uptime-Monitor/archive/refs/heads/main.zip -O uptime_update.zip

# 4. Розпакувати З СУДОМ
sudo rm -rf /tmp/Uptime-Monitor-main
sudo unzip -o uptime_update.zip

# 5. Скопіювати файли
sudo cp -r /tmp/Uptime-Monitor-main/Uptime_Robot/* /opt/uptime-monitor/

# 6. Прибрати тимчасові файли З СУДОМ
sudo rm -rf uptime_update.zip /tmp/Uptime-Monitor-main

# 7. Запустити
sudo systemctl daemon-reload
sudo systemctl start uptime-monitor
sleep 3

# 8. Перевірити
sudo systemctl status uptime-monitor
curl -fsS http://localhost:8080 && echo "HTTP OK" || echo "HTTP FAIL"
```

---

## 🔄 Якщо встановлено через Git (кращий варіант)

```bash
cd /opt/uptime-monitor

# 1. Бекап
sudo /opt/uptime-monitor/scripts/backup-system.sh \
    --dest /backup/uptime-monitor/ \
    --type on-change

# 2. Оновлення
sudo git fetch --all --prune
sudo git checkout main
sudo git pull --ff-only origin main

# 3. Перезапуск
sudo systemctl restart uptime-monitor

# 4. Перевірка
sudo systemctl status uptime-monitor
```

---

## 🎯 Готові скрипти

### Production (з бекапом)

```bash
cd /tmp
wget https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/docs/UPDATE_SCRIPT_SAFE.sh
chmod +x UPDATE_SCRIPT_SAFE.sh
sudo ./UPDATE_SCRIPT_SAFE.sh
```

### Test (швидке, без бекапу)

```bash
cd /tmp
wget https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/docs/UPDATE_SCRIPT_FAST.sh
chmod +x UPDATE_SCRIPT_FAST.sh
sudo ./UPDATE_SCRIPT_FAST.sh
```

---

## 🆘 Rollback (якщо щось не так)

```bash
# Список бекапів
sudo /opt/uptime-monitor/scripts/restore-system.sh --list

# Відновити з останнього
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto --force

# Конкретний бекап
sudo /opt/uptime-monitor/scripts/restore-system.sh \
    --from /backup/uptime-monitor/on-change/backup-YYYYMMDD-HHMMSS.tar.gz \
    --force
```

---

## ✅ Перевірка після оновлення

```bash
# Статус
sudo systemctl status uptime-monitor

# Логи
sudo journalctl -u uptime-monitor -n 50

# HTTP
curl -fsS http://localhost:8080

# Процес
ps aux | grep -E "(python.*main|uptime)" | grep -v grep
```

---

## 📊 Порівняння методів

| Метод | Переваги | Недоліки | Коли |
|-------|----------|----------|------|
| **Git** | Швидко, чисто | Потребує .git | Production |
| **ZIP** | Універсально | Потребує `unzip` | Якщо немає .git |
| **SAFE скрипт** | Повний захист | Довше | Production |
| **FAST скрипт** | Дуже швидко | Без бекапу | Test/Dev |

---

## 🔗 Детальна документація

- [SAFE_UPDATE_RUNBOOK.md](SAFE_UPDATE_RUNBOOK.md) - Повний production runbook
- [UPDATE_INSTRUCTIONS.md](UPDATE_INSTRUCTIONS.md) - Детальні інструкції
- [UPDATE_FIXES.md](UPDATE_FIXES.md) - Виправлення проблем
- [BACKUP.md](BACKUP.md) - Система бекапів
