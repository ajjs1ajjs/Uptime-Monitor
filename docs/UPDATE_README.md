# 📚 Документація з оновлення Uptime Monitor

Цей каталог містить повну документацію для безпечного оновлення Uptime Monitor.

---

## 🚨 КРИТИЧНО ВАЖЛИВО

**Проблема:** При розпакуванні ZIP **без `sudo`** файли створюються з правами користувача, потім неможливо скопіювати в `/opt/uptime-monitor/`.

**Рішення:** **ЗАВЖДИ** використовуйте `sudo` для всіх операцій з ZIP!

```bash
sudo rm -rf /tmp/Uptime-Monitor-main    # Видалити стару папку
sudo unzip -o uptime_update.zip             # Розпакувати
sudo cp -r ...                              # Скопіювати
sudo rm -rf ...                             # Прибрати
```

**Детальніше:** [UPDATE_COMPLETE_GUIDE.md](UPDATE_COMPLETE_GUIDE.md)

---

## 🚀 Швидкий вибір

| Документ | Призначення | Час |
|----------|-------------|-----|
| **[UPDATE_COMPLETE_GUIDE.md](UPDATE_COMPLETE_GUIDE.md)** | 🆕 Повна інструкція (почніть тут!) | 5 хв |
| **[UPDATE_QUICKSTART.md](UPDATE_QUICKSTART.md)** | ⚡ Швидка інструкція | 1 хв |
| **[UPDATE_FIXES.md](UPDATE_FIXES.md)** | 🔧 Виправлення проблем (unzip, permissions) | 2 хв |
| **[SAFE_UPDATE_RUNBOOK.md](SAFE_UPDATE_RUNBOOK.md)** | 📋 Production runbook | 5 хв |
| **[UPDATE_INSTRUCTIONS.md](UPDATE_INSTRUCTIONS.md)** | 📖 Детальні інструкції | 10 хв |
| **[COMMANDS.md](COMMANDS.md)** | 📝 Всі команди | - |
| **[BACKUP.md](BACKUP.md)** | 💾 Система бекапів | - |

---

## 🔥 Якщо отримали помилку `unzip not found`

**Це найпоширеніша проблема!** Вирішення:

```bash
# Встановити unzip
sudo apt update && sudo apt install -y unzip

# Продовжити оновлення
```

**Детальніше:** [UPDATE_FIXES.md](UPDATE_FIXES.md)

---

## 📋 Готові скрипти

### Production (з повним бекапом)

```bash
cd /tmp
wget https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/docs/UPDATE_SCRIPT_SAFE.sh
chmod +x UPDATE_SCRIPT_SAFE.sh
sudo ./UPDATE_SCRIPT_SAFE.sh
```

**Що робить:**
- ✅ Перевіряє стан сервісу
- ✅ Створює бекап з перевіркою
- ✅ Зупиняє сервіс
- ✅ Оновлює код (git або ZIP)
- ✅ Запускає сервіс
- ✅ Перевіряє після оновлення
- ✅ Надає команди для rollback

### Test (швидке, без бекапу)

```bash
cd /tmp
wget https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/docs/UPDATE_SCRIPT_FAST.sh
chmod +x UPDATE_SCRIPT_FAST.sh
sudo ./UPDATE_SCRIPT_FAST.sh
```

**⚠️ Увага:** Не створює бекап! Використовуйте тільки на тестових середовищах.

---

## 🎯 Рекомендації для різних сценаріїв

### Production сервер

1. **Обов'язково** зробіть бекап
2. Використовуйте `UPDATE_SCRIPT_SAFE.sh`
3. Заплануйте даунтайм
4. Майте план rollback

**Документація:** [SAFE_UPDATE_RUNBOOK.md](SAFE_UPDATE_RUNBOOK.md)

### Test/Dev середовище

1. Можна використати `UPDATE_SCRIPT_FAST.sh`
2. Або ручне оновлення

**Документація:** [UPDATE_QUICKSTART.md](UPDATE_QUICKSTART.md)

### Якщо встановлено через Git

```bash
cd /opt/uptime-monitor
sudo git fetch --all --prune
sudo git checkout main
sudo git pull --ff-only origin main
sudo systemctl restart uptime-monitor
```

**Найкращий варіант!** Не потребує `unzip`.

### Якщо встановлено через ZIP

1. Встановіть `unzip`: `sudo apt install -y unzip`
2. Використовуйте `UPDATE_SCRIPT_SAFE.sh`

**Детальніше:** [UPDATE_FIXES.md](UPDATE_FIXES.md)

---

## 📊 Порівняння методів оновлення

| Метод | Бекап | Час | Складність | Коли |
|-------|-------|-----|------------|------|
| **UPDATE_SCRIPT_SAFE.sh** | ✅ Так | 5 хв | Низька | Production |
| **UPDATE_SCRIPT_FAST.sh** | ❌ Ні | 2 хв | Низька | Test/Dev |
| **Git pull** | ❌ Ні | 1 хв | Низька | Git installation |
| **ZIP/wget** | ❌ Ні | 3 хв | Середня | ZIP installation |
| **Ручний (runbook)** | ✅ Так | 10 хв | Середня | Custom сценарії |

---

## 🆘 Rollback (відновлення)

Якщо оновлення не вдалося:

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

**Детальніше:** [BACKUP.md](BACKUP.md)

---

## ✅ Контрольний список після оновлення

```bash
# 1. Статус сервісу
sudo systemctl status uptime-monitor

# 2. Логи
sudo journalctl -u uptime-monitor -n 50

# 3. HTTP перевірка
curl -fsS http://localhost:8080

# 4. Процес
ps aux | grep -E "(python.*main|uptime)" | grep -v grep

# 5. Статус бекапів
sudo /opt/uptime-monitor/scripts/backup-system.sh --status
```

---

## 📞 Швидка допомога

### Все в одному (production)

```bash
sudo apt install -y unzip && \
sudo systemctl stop uptime-monitor && \
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/ --type on-change --verify && \
cd /tmp && \
sudo rm -rf /tmp/Uptime-Monitor-main && \
wget -q https://github.com/ajjs1ajjs/Uptime-Monitor/archive/refs/heads/main.zip -O uptime_update.zip && \
sudo unzip -o uptime_update.zip && \
sudo cp -r /tmp/Uptime-Monitor-main/Uptime_Robot/* /opt/uptime-monitor/ && \
sudo rm -rf uptime_update.zip /tmp/Uptime-Monitor-main && \
sudo systemctl start uptime-monitor && \
sudo systemctl status uptime-monitor
```

### Все в одному (git installation)

```bash
cd /opt/uptime-monitor && \
sudo systemctl stop uptime-monitor && \
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/ --type on-change && \
sudo git fetch --all --prune && \
sudo git checkout main && \
sudo git pull --ff-only origin main && \
sudo systemctl start uptime-monitor && \
sudo systemctl status uptime-monitor
```

---

## 📖 Зміст документації

### Основні документи

- **[UPDATE_QUICKSTART.md](UPDATE_QUICKSTART.md)** - Швидка інструкція з оновлення
- **[UPDATE_FIXES.md](UPDATE_FIXES.md)** - Виправлення поширених проблем
- **[SAFE_UPDATE_RUNBOOK.md](SAFE_UPDATE_RUNBOOK.md)** - Production runbook з бекапом
- **[UPDATE_INSTRUCTIONS.md](UPDATE_INSTRUCTIONS.md)** - Детальні інструкції
- **[COMMANDS.md](COMMANDS.md)** - Довідник всіх команд
- **[BACKUP.md](BACKUP.md)** - Система резервного копіювання

### Скрипти

- **[UPDATE_SCRIPT_SAFE.sh](UPDATE_SCRIPT_SAFE.sh)** - Безпечне оновлення (production)
- **[UPDATE_SCRIPT_FAST.sh](UPDATE_SCRIPT_FAST.sh)** - Швидке оновлення (test)

---

## 🔗 Корисні посилання

- [QUICKSTART.md](QUICKSTART.md) - Швидкий старт
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Вирішення проблем
- [README.md](../README.md) - Головна сторінка

---

**⭐ Поставте зірку, якщо документація допомогла!**
