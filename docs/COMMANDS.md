# 📋 Довідник команд

Повний список команд Uptime Monitor

---

## 🔧 Service Management (Управління службою)

```bash
# Веб-панель
sudo systemctl start uptime-monitor
sudo systemctl stop uptime-monitor
sudo systemctl restart uptime-monitor
sudo systemctl status uptime-monitor

# Фоновий моніторинг (Worker)
sudo systemctl start uptime-monitor-worker
sudo systemctl stop uptime-monitor-worker
sudo systemctl restart uptime-monitor-worker
sudo systemctl status uptime-monitor-worker

# Керування обома (рекомендується)
sudo systemctl restart uptime-monitor uptime-monitor-worker
```

---

## 🔄 Update (Оновлення)

### Рекомендований спосіб (автоматичний скрипт)
```bash
# Повне оновлення з бекапом + перевіркою
sudo /opt/uptime-monitor/deploy_update.sh

# Якщо щось пішло не так — відкат
sudo /opt/uptime-monitor/deploy_update.sh --rollback

# Зробити тільки бекап (без оновлення)
sudo /opt/uptime-monitor/deploy_update.sh --backup
```

### Ручне оновлення
```bash
# 1. Зупинити служби
sudo systemctl stop uptime-monitor uptime-monitor-worker

# 2. Бекап БД + конфіг
sudo cp /var/lib/uptime-monitor/sites.db /backup/sites.pre-update.db
sudo cp /etc/uptime-monitor/config.json /backup/config.pre-update.json

# 3. Оновити код
cd /opt/uptime-monitor
sudo git fetch --all --prune
sudo git checkout main
sudo git pull --ff-only origin main
sudo chown -R uptime-monitor:uptime-monitor .

# 4. Перезапустити
sudo systemctl daemon-reload
sudo systemctl start uptime-monitor uptime-monitor-worker

# 5. Перевірка
curl -s http://localhost:8080/health
```

---

## 📊 Журнали

```bash
# Веб-панель
sudo journalctl -u uptime-monitor -f

# Worker (Моніторинг)
sudo journalctl -u uptime-monitor-worker -f

# Логи помилок у файлах
sudo tail -f /var/log/uptime-monitor/uptime-monitor.error.log
sudo tail -f /var/log/uptime-monitor/worker.error.log
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

### Варіант 1: Через веб-інтерфейс (потрібні права admin)
1. Увійдіть як admin
2. Перейдіть на `/forgot-password`
3. Введіть username користувача
4. Отримаєте тимчасовий пароль на екрані

### Варіант 2: Через CLI (Linux)

```bash
cd /opt/uptime-monitor

# Скинути пароль
sudo ./venv/bin/python auth_cli.py reset-password --user admin --password НОВИЙ_ПАРОЛЬ

# Перезапустити сервіс
sudo systemctl restart uptime-monitor
```

> **Note (v2.0.0+):** Пароль має бути ≥12 символів, з upper+lower+digit. При першому вході система вимагатиме змінити пароль.

### Список користувачів

```bash
sudo ./venv/bin/python /opt/uptime-monitor/auth_cli.py list-users
```

### Перший вхід (v2.0.0+)
- Логін: `admin`
- Пароль: генерується випадково при першому запуску
```bash
# Знайти пароль в логах
sudo journalctl -u uptime-monitor | grep "DEFAULT ADMIN"
```
- Система ВИМАГАТИМЕ змінити пароль при першому вході!

### Якщо забули пароль (v2.0.0+)
```bash
# Скинути через CLI
cd /opt/uptime-monitor
sudo ./venv/bin/python auth_cli.py reset-password --user admin --password НОВИЙ_ПАРОЛЬ
sudo systemctl restart uptime-monitor
```

### Шлях до бази даних
- Linux: `/etc/uptime-monitor/sites.db` (default; computed from `CONFIG_PATH`)
- Windows: `%USERPROFILE%\UptimeMonitor\data\sites.db`

---

## 🪟 Windows-Specific Commands

### Windows Service (рекомендовано)

```powershell
# Встановлення служби (від Адміністратора)
.\install_service.bat

# Або вручну:
python main_service.py install
sc config UptimeMonitor start= auto
net start UptimeMonitor

# Управління
net start UptimeMonitor
net stop UptimeMonitor
python main_service.py remove     # Видалити службу
python main_service.py console    # Запустити в консолі (тест)

# Прямий запуск Python
python -m Uptime_Robot.main --host 0.0.0.0 --port 8080
```

### Windows Scheduled Task

```powershell
# Інтерактивний (обере 1=Service, 2=Task)
powershell -ExecutionPolicy Bypass -File create_task_simple.ps1

# Або напряму як Task:
powershell -ExecutionPolicy Bypass -File create_task.ps1 -UsePython
```

### Windows: Build EXE

```powershell
.\build_exe.bat
```
Створює `UptimeMonitor_EXE\UptimeMonitor.exe`

### Windows: Усунення несправностей

```powershell
# Перевірити чи служба встановлена
sc query UptimeMonitor

# Логи помилок служби
type "C:\ProgramData\UptimeMonitor\service_error.log" 2>$null

# Перевірити порт
netstat -ano | findstr :8080

# Перевірити Python
python --version
python -c "import fastapi, uvicorn, bcrypt, cryptography; print('Dependencies OK')"
```

---

## 📍 Шляхи до файлів (Linux)

| Файл | Шлях |
|------|------|
| Конфігурація | `/etc/uptime-monitor/config.json` |
| База даних (монітори) | `/var/lib/uptime-monitor/sites.db` |
| Логи | `/var/log/uptime-monitor/` |
| Скрипти | `/opt/uptime-monitor/scripts/` |
| Бекапи | `/backup/uptime-monitor/` |
| Служба systemd | `/etc/systemd/system/uptime-monitor.service` |

### 📍 Шляхи до файлів (Windows)

| Файл | Шлях |
|------|------|
| Конфігурація | `%USERPROFILE%\UptimeMonitor\config.json` |
| База даних | `%USERPROFILE%\UptimeMonitor\data\sites.db` |
| Логи | `%USERPROFILE%\UptimeMonitor\logs\` |
| Проект | `C:\Uptime-Monitor\Uptime_Robot\` (або ваш шлях) |

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


