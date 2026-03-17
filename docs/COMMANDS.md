# 📋 Довідник команд

Повний список команд Uptime Monitor

---

## 🔧 Service Management (Управління службою)

```bash
# Запустити службу
sudo systemctl start uptime-monitor

# Зупинити службу
sudo systemctl stop uptime-monitor

# Перезапустити службу
sudo systemctl restart uptime-monitor

# Перевірити статус
sudo systemctl status uptime-monitor

# Увімкнути автозапуск
sudo systemctl enable uptime-monitor

# Вимкнути автозапуск
sudo systemctl disable uptime-monitor
```

---

## 🔄 Update (Оновлення)

```bash
# 1. Зупинити службу
sudo systemctl stop uptime-monitor

# 2. Бекап бази даних (ТУТ ВСІ МОНІТОРИ!)
DB_PATH=$(python3 - <<'PY'
import json, os
config='/etc/uptime-monitor/config.json'
if os.path.exists(config):
    try:
        with open(config,'r',encoding='utf-8') as f:
            data=json.load(f)
        print(os.path.join(os.path.dirname(config), 'sites.db'))
    except Exception:
        print('/etc/uptime-monitor/sites.db')
else:
    print('/etc/uptime-monitor/sites.db')
PY
)
sudo cp "$DB_PATH" /backup/sites.db.backup

# 3. Оновити код
cd /opt/uptime-monitor
if [ -d .git ]; then
    sudo git fetch --all --prune
    sudo git checkout main
    sudo git pull --ff-only origin main
else
    # Встановити unzip якщо немає
    if ! command -v unzip &> /dev/null; then
        sudo apt update && sudo apt install -y unzip
    fi

    cd /tmp
    wget https://github.com/ajjs1ajjs/Uptime-Monitor-APP/archive/refs/heads/main.zip -O uptime_update.zip
    
    # КРИТИЧНО: Видалити стару папку з sudo
    sudo rm -rf /tmp/Uptime-Monitor-APP-main
    
    # КРИТИЧНО: Розпакувати з sudo
    sudo unzip -o uptime_update.zip
    
    # Скопіювати файли
    sudo cp -r /tmp/Uptime-Monitor-APP-main/Uptime_Robot/* /opt/uptime-monitor/
    
    # Прибрати тимчасові файли
    sudo rm -rf uptime_update.zip /tmp/Uptime-Monitor-APP-main
fi

# 4. Start service
sudo systemctl start uptime-monitor

# 5. Verify
sudo systemctl status uptime-monitor
```

### Швидке оновлення (якщо вже все налаштовано)
```bash
cd /opt/uptime-monitor && if [ -d .git ]; then
    sudo git fetch --all --prune
    sudo git checkout main
    sudo git pull --ff-only origin main
else
    echo "No .git directory found. Use wget update flow from docs/UPDATE_INSTRUCTIONS.md"
fi && sudo systemctl restart uptime-monitor
```

---

## 📊 Журнали

```bash
# Дивитись логи в реальному часі
sudo journalctl -u uptime-monitor -f

# Показати останні 50 рядків
sudo journalctl -u uptime-monitor -n 50

# Показати логи за сьогодні
sudo journalctl -u uptime-monitor --since today

# Показати логи помилок
sudo tail -f /var/log/uptime-monitor/uptime-monitor.error.log
```

---

## ⚙️ Configuration (Конфігурація)

```bash
# Редагувати конфігурацію
sudo nano /etc/uptime-monitor/config.json

# Перевірити синтаксис JSON
python3 -m json.tool /etc/uptime-monitor/config.json

# Перезапустити після змін
sudo systemctl restart uptime-monitor
```

---

## 🔄 Configuration Rollback (Відкат конфігурації)

```bash
# Список доступних версій
sudo /opt/uptime-monitor/scripts/config-rollback.sh --list

# Відкат до попередньої версії
sudo /opt/uptime-monitor/scripts/config-rollback.sh --previous

# Відкат до конкретної версії
sudo /opt/uptime-monitor/scripts/config-rollback.sh --to config.20260218-120000.json

# Показати відмінності
sudo /opt/uptime-monitor/scripts/config-rollback.sh --diff config.latest.json
```

---

## 💾 Backup (Створення бекапів)

```bash
# Створити бекап зараз
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/

# Створити бекап з коментарем
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/ --type on-change --comment "Before SSL setup"

# Перевірити статус бекапів
sudo /opt/uptime-monitor/scripts/backup-system.sh --status

# Перевірити цілісність бекапу
sudo /opt/uptime-monitor/scripts/verify-backup.sh /backup/uptime-monitor/daily/backup-20260218-020000.tar.gz

# Перевірити всі бекапи
sudo /opt/uptime-monitor/scripts/verify-backup.sh --all
```

---

## 📅 Scheduled Backups (Заплановані бекапи)

```bash
# Встановити щоденні бекапи
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install --daily "0 2 * * *" --dest /backup/uptime-monitor/

# Встановити повний розклад
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install \
    --daily "0 2 * * *" \
    --weekly "0 3 * * 0" \
    --monthly "0 4 1 * *" \
    --dest /backup/uptime-monitor/

# Перевірити статус розкладу
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --status

# Видалити всі розклади
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --remove

# Тестувати систему бекапів
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --test
```

---

## 🗄️ Restore (Відновлення)

```bash
# Список доступних бекапів
sudo /opt/uptime-monitor/scripts/restore-system.sh --list

# Відновити з останнього бекапу
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto

# Відновити з конкретного бекапу
sudo /opt/uptime-monitor/scripts/restore-system.sh --from /backup/uptime-monitor/daily/backup-20260218-020000.tar.gz

# Відновити тільки базу даних
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto --only database

# Відновити тільки конфігурацію
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto --only config

# Тестовий запуск (без змін)
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto --dry-run
```

---

## 🔄 Backup Rotation (Ротація бекапів)

```bash
# Перевірити що буде видалено
sudo /opt/uptime-monitor/scripts/backup-rotation.sh --dry-run

# Виконати ротацію
sudo /opt/uptime-monitor/scripts/backup-rotation.sh

# Залишити тільки 5 останніх
sudo /opt/uptime-monitor/scripts/backup-rotation.sh --keep 5
```

---

## 🌐 NFS Mount (Монтування NFS)

```bash
# Встановити NFS клієнт
sudo apt-get install -y nfs-common

# Змонтувати NFS
sudo /opt/uptime-monitor/scripts/mount-backup.sh \
    --type nfs \
    --server 192.168.1.10 \
    --path /exports/backups \
    --mount-point /mnt/nfs-backup \
    --persist

# Розмонтувати
sudo /opt/uptime-monitor/scripts/mount-backup.sh --unmount --mount-point /mnt/nfs-backup

# Перевірити монтування
mount | grep nfs
```

---

## 🔗 Samba Mount (Монтування Samba)

```bash
# Встановити Samba клієнт
sudo apt-get install -y cifs-utils

# Змонтувати з паролем
sudo /opt/uptime-monitor/scripts/mount-backup.sh \
    --type smb \
    --server 192.168.1.11 \
    --share backups \
    --mount-point /mnt/smb-backup \
    --username backupuser \
    --password secret \
    --persist

# Змонтувати з credentials файлом
sudo /opt/uptime-monitor/scripts/mount-backup.sh \
    --type smb \
    --server nas.local \
    --share backups \
    --mount-point /mnt/smb-backup \
    --credentials /root/.smb-credentials \
    --persist

# Розмонтувати
sudo /opt/uptime-monitor/scripts/mount-backup.sh --unmount --mount-point /mnt/smb-backup
```

---

## 🔒 Налаштування SSL/HTTPS

```bash
# Створити директорію для сертифікатів
sudo mkdir -p /etc/uptime-monitor/ssl

# Скопіювати сертифікати
sudo cp /path/to/cert.pem /etc/uptime-monitor/ssl/
sudo cp /path/to/key.pem /etc/uptime-monitor/ssl/

# Встановити права
sudo chmod 600 /etc/uptime-monitor/ssl/*.pem

# Редагувати конфіг
sudo nano /etc/uptime-monitor/config.json
# Змінити:
#   "server.port": 443
#   "ssl.enabled": true

# Перезапустити
sudo systemctl restart uptime-monitor
```

---

## 🧹 Cleanup (Очищення)

```bash
# Перевірити розмір бекапів
sudo du -sh /backup/uptime-monitor/*

# Видалити старі бекапи
sudo /opt/uptime-monitor/scripts/backup-rotation.sh

# Видалити службу
sudo systemctl stop uptime-monitor
sudo systemctl disable uptime-monitor
sudo rm /etc/systemd/system/uptime-monitor.service
sudo systemctl daemon-reload

# Видалити програму
sudo rm -rf /opt/uptime-monitor
sudo rm -rf /etc/uptime-monitor
sudo rm -rf /var/lib/uptime-monitor
sudo userdel uptime-monitor
```

---

## 🔐 Password Reset (Скидання пароля)

### Варіант 1: Через веб-інтерфейс (найпростіший)
1. На сторінці логіну натисніть "Забули пароль?"
2. Введіть username (admin)
3. Отримаєте новий тимчасовий пароль
4. Увійдіть з новим паролем - система вимагатиме змінити його

### Варіант 2: Через CLI (Linux)

```bash
cd /opt/uptime-monitor

# Скинути пароль (з вимогою зміни при вході)
sudo ./venv/bin/python auth_cli.py reset-password --user admin --password НОВИЙ_ПАРОЛЬ

# АБО скинути БЕЗ вимоги зміни
sudo ./venv/bin/python auth_cli.py reset-password --user admin --password НОВИЙ_ПАРОЛЬ --no-force-change

# Перезапустити сервіс
sudo systemctl restart uptime-monitor
```

### Варіант 3: Через CLI (Windows)

```bat
cd D:\Project\Uptime_Robot
python auth_cli.py reset-password --user admin --password НОВИЙ_ПАРОЛЬ --no-force-change
```

### Список користувачів

```bash
sudo ./venv/bin/python /opt/uptime-monitor/auth_cli.py list-users
```

### Перший вхід
- Логін: `admin`
- Пароль: `admin`
- Система ВИМАГАТИМЕ змінити пароль при першому вході!

### Шлях до бази даних
- Linux: `/etc/uptime-monitor/sites.db` (default; computed from `CONFIG_PATH`)
- Windows: `%USERPROFILE%\UptimeMonitor\data\sites.db`

## 📍 Шляхи до файлів

| Файл | Шлях |
|------|------|
| Конфігурація | `/etc/uptime-monitor/config.json` |
| База даних (монітори) | `/etc/uptime-monitor/sites.db` |
| Логи | `/var/log/uptime-monitor/` |
| Скрипти | `/opt/uptime-monitor/scripts/` |
| Бекапи | `/backup/uptime-monitor/` |
| Служба systemd | `/etc/systemd/system/uptime-monitor.service` |

---

## 🔍 Корисні команди

```bash
# Перевірити порт
sudo lsof -i :8080

# Перевірити диск
sudo df -h

# Перевірити процеси
ps aux | grep uptime

# Перевірити IP
hostname -I

# Перевірити версію Python
python3 --version

# Перевірити права
ls -la /opt/uptime-monitor/
ls -la /etc/uptime-monitor/
ls -la /var/lib/uptime-monitor/
```


