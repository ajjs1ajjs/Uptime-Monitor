# Uptime Monitor - Посібник із встановлення

## 🚀 Швидкий старт (5 хвилин)

Запустіть Uptime Monitor із захистом резервного копіювання за 5 хвилин:

### 1. Встановити
```bash
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash
```

### 2. Доступ до веб-інтерфейсу
- **URL**: http://{SERVER_IP}:8080 (IP-адреса визначається автоматично)
- **Вхід**: адмін
- **Пароль**: admin

### 3. Створіть першу резервну копію ⚠️ ВАЖЛИВО
```bash
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/
```

### 4. Налаштуйте автоматичне резервне копіювання
```bash
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install --dest /backup/uptime-monitor/
```

### 5. Змініть пароль за умовчанням
1. Відкрийте http://{SERVER_IP}:8080 у браузері
2. Увійдіть за допомогою admin/admin
3. Негайно змініть пароль!

---

## 📋 Контрольний список після інсталяції

Після встановлення виконайте наведені нижче дії.

- [ ] **Змінити пароль за умовчанням** (admin/admin) - КРИТИЧНО!
- [ ] **Створіть першу резервну копію** - Захистіть свої дані
- [ ] **Налаштувати автоматичне резервне копіювання** - Щоденне резервне копіювання о 2:00 ночі
- [ ] **Налаштувати зовнішнє резервне копіювання** (NFS/Samba) – Необов’язково, але рекомендовано
- [ ] **Налаштувати домен і SSL** - Коли буде готово до виробництва
- [ ] **Додайте сайти моніторингу** - Почніть моніторинг своїх послуг
- [ ] **Налаштувати сповіщення** - Електронна пошта, Telegram тощо.

---

## ✨ Що нового

### 🔄 Система резервного копіювання (НОВИНКА!)
Повне рішення для резервного копіювання та відновлення:
- **Автоматичне резервне копіювання**: щодня, щотижня, щомісяця, щороку
- **Резервне копіювання при змінах**: автоматичне резервне копіювання, коли ви змінюєте конфігурацію
- **Кілька місць призначення**: локальний диск, NFS, спільні ресурси Samba
- **Відновлення однією командою**: відновлюйте все за допомогою однієї команди
- **Перевірка резервної копії**: перевірте цілісність ваших резервних копій
- **Політика збереження**: автоматичне очищення старих резервних копій

### ⚙️ Керування конфігурацією (НОВИНКА!)
- **Конфігурація JSON**: легко читати та редагувати
- **Автоматичне визначення IP-адреси**: IP-адреса сервера визначається автоматично
- **Просте налаштування домену**: просто відредагуйте config.json
- **Відкат конфігурації**: повернення до попередніх конфігурацій
- **Реєстрація змін**: відстежуйте всі зміни конфігурації

### 🔒 SSL/HTTPS (НОВИНКА!)
- **Користувацькі сертифікати**: використовуйте власні сертифікати SSL
- **Автоперенаправлення**: HTTP → HTTPS автоматично
- **Заголовки HSTS**: покращений захист

---

## 📝 Шпаргалка команд

### Команди резервного копіювання
```bash
# Create backup now
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/

# Check backup status
sudo /opt/uptime-monitor/scripts/backup-system.sh --status

# List all backups
sudo /opt/uptime-monitor/scripts/restore-system.sh --list

# Restore from latest backup
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto

# Restore specific backup
sudo /opt/uptime-monitor/scripts/restore-system.sh --from /backup/uptime-monitor/daily/backup-20260218-020000.tar.gz
```

### Керування послугами
```bash
# Start/Stop/Restart
sudo systemctl start uptime-monitor
sudo systemctl stop uptime-monitor
sudo systemctl restart uptime-monitor

# View logs in real-time
sudo journalctl -u uptime-monitor -f

# Check service status
sudo systemctl status uptime-monitor

# View last 50 log lines
sudo journalctl -u uptime-monitor -n 50
```

### Команди конфігурації
```bash
# Edit configuration
sudo nano /etc/uptime-monitor/config.json

# Rollback to previous configuration
sudo /opt/uptime-monitor/scripts/config-rollback.sh --previous

# List configuration backups
sudo /opt/uptime-monitor/scripts/config-rollback.sh --list

# Restart after changes
sudo systemctl restart uptime-monitor
```

### Управління резервним копіюванням
```bash
# Schedule automatic backups
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install --dest /backup/uptime-monitor/

# Check backup schedule status
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --status

# Verify all backups
sudo /opt/uptime-monitor/scripts/verify-backup.sh --all

# Mount NFS for backups
sudo /opt/uptime-monitor/scripts/mount-backup.sh --type nfs --server 192.168.1.10 --path /exports/backups --mount-point /mnt/nfs-backup --persist

# Mount Samba for backups
sudo /opt/uptime-monitor/scripts/mount-backup.sh --type smb --server 192.168.1.11 --share backups --mount-point /mnt/smb-backup --persist
```

---

## ⬆️ Оновлення з попередньої версії

Якщо у вас встановлено старішу версію:

### Оновлення Linux

#### 1. Резервне копіювання поточної інсталяції
```bash
# Create backup before upgrade
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/ --type on-change --comment "Pre-upgrade backup"

# Or manual backup - IMPORTANT: sites.db contains ALL your monitors and settings!
sudo cp /opt/uptime-monitor/sites.db /backup/sites.db.backup
```

#### 2. Оновити код
```bash
cd /opt/uptime-monitor
sudo git fetch --all --prune
sudo git checkout main
sudo git pull --ff-only origin main
```

#### 3. Перезапустіть службу
```bash
sudo systemctl restart uptime-monitor
```

#### 4. Перевірте систему резервного копіювання
```bash
# Check backup system status
sudo /opt/uptime-monitor/scripts/backup-system.sh --status

# Create test backup
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/ --type on-change --comment "Post-upgrade test"

# Verify backup
sudo /opt/uptime-monitor/scripts/verify-backup.sh --all
```

#### 5. Налаштуйте автоматичне резервне копіювання (якщо ще не налаштовано)
```bash
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install --dest /backup/uptime-monitor/
```

### Оновлення Windows

#### 1. Резервне копіювання поточних даних
```powershell
Copy-Item "$env:USERPROFILE\UptimeMonitor\sites.db" "$env:USERPROFILE\UptimeMonitor\sites.db.backup.$(Get-Date -Format yyyyMMdd-HHmmss)"
Copy-Item "$env:USERPROFILE\UptimeMonitor\config.json" "$env:USERPROFILE\UptimeMonitor\config.json.backup.$(Get-Date -Format yyyyMMdd-HHmmss)"
```

#### 2. Оновити файли

**Якщо встановлено з git clone:**
```powershell
cd D:\path\to\Uptime-Monitor
git pull --ff-only origin main
```

**Якщо встановлено з архіву ZIP:**
1. Завантажте новий Windows ZIP із [Релізи](https://github.com/ajjs1ajjs/Uptime-Monitor/releases)
2. Розпакуйте/замініть файли у папці встановлення

#### 3. Перевстановіть службу з оновленими файлами
```powershell
cd D:\path\to\Uptime-Monitor\Uptime_Robot
python main_service.py stop
python main_service.py remove
.\install.bat
```

#### 4. Перевірити
```powershell
sc.exe queryex UptimeMonitor
netstat -ano | findstr :8080
```

---

## Встановлення Linux через CURL

### Встановити останню версію
```bash
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash
```

### Встановити за допомогою спеціального порту
```bash
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash -s -- --port 9090
```

### Встановити конкретну версію
```bash
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash -s -- --version v1.0.0
```

**Примітка.** Після встановлення сервер буде доступний за адресою `http://{SERVER_IP}:8080`, де автоматично визначається `{SERVER_IP}`.

## Встановлення Linux через APT

### Додати репозиторій
```bash
curl -fsSL https://ajjs1ajjs.github.io/Uptime-Monitor/KEY.gpg | sudo gpg --dearmor -o /usr/share/keyrings/uptime-monitor.gpg
echo "deb [signed-by=/usr/share/keyrings/uptime-monitor.gpg] https://ajjs1ajjs.github.io/Uptime-Monitor stable main" | sudo tee /etc/apt/sources.list.d/uptime-monitor.list
```

### Встановити
```bash
sudo apt update && sudo apt install uptime-monitor
```

### Запустити службу
```bash
sudo systemctl start uptime-monitor
```

## Встановлення Windows

### Спосіб 1: Проста інсталяція (рекомендовано)
1. Завантажте `uptime-monitor-v2.0.0-windows.zip` з [Releases](https://github.com/ajjs1ajjs/Uptime-Monitor/releases)
2. Витягніть у потрібне місце (наприклад, `C:\UptimeMonitor`)
3. Відкрийте папку `Uptime_Robot`
4. Запустіть `install.bat` від імені адміністратора
5. Введіть порт (натисніть Enter для порту за замовчуванням 8080)
6. Відкрийте `http://localhost:8080` у браузері

### Спосіб 2: Встановлення вручну
```cmd
cd C:\path\to\Uptime-Monitor\Uptime_Robot
python -m pip install -r requirements.txt
python -c "import config_manager as c; c.init_paths(); cfg=c.load_config(); cfg.setdefault('server', {})['port']=8080; c.save_config(cfg)"
python main_service.py install
net start UptimeMonitor
```

### Спосіб 3: Встановлення з Git (для розробки)
```cmd
git clone https://github.com/ajjs1ajjs/Uptime-Monitor.git
cd Uptime-Monitor\Uptime_Robot
python -m pip install -r requirements.txt
python main_service.py install
net start UptimeMonitor
```

### Windows - Резервне копіювання

**Важливо:** Зберігайте `sites.db` та `config.json` перед оновленням!

```powershell
# Резервне копіювання даних
Copy-Item "$env:USERPROFILE\UptimeMonitor\sites.db" "$env:USERPROFILE\UptimeMonitor\sites.db.backup.$(Get-Date -Format yyyyMMdd-HHmmss)"
Copy-Item "$env:USERPROFILE\UptimeMonitor\config.json" "$env:USERPROFILE\UptimeMonitor\config.json.backup.$(Get-Date -Format yyyyMMdd-HHmmss)"

# Відновлення з бекапу
Copy-Item "$env:USERPROFILE\UptimeMonitor\sites.db.backup.20260305-120000" "$env:USERPROFILE\UptimeMonitor\sites.db"
Copy-Item "$env:USERPROFILE\UptimeMonitor\config.json.backup.20260305-120000" "$env:USERPROFILE\UptimeMonitor\config.json"
```

### Windows - Усунення несправностей

```cmd
# Перевірка статусу служби
sc query UptimeMonitor

# Перевірка порту
netstat -ano | findstr :8080

# Перегляд логів
type "%USERPROFILE%\UptimeMonitor\uptime_monitor.log"

# Якщо служба не запускається - спробуйте вручну
cd C:\UptimeMonitor\Uptime_Robot
python main.py

# Перевстановка служби
net stop UptimeMonitor
python main_service.py remove
python main_service.py install
net start UptimeMonitor
```

### Windows - Конфігурація

**Розташування:** `%USERPROFILE%\UptimeMonitor\config.json`

```json
{
  "server": {
    "port": 8080,
    "host": "auto"
  },
  "check_interval": 60,
  "alert_policy": {
    "ssl_check_interval_hours": 6,
    "ssl_notification_days": 7
  }
}
```

**Зміна порту:**
```powershell
# Редагувати config.json
notepad "$env:USERPROFILE\UptimeMonitor\config.json"

# Або через PowerShell
$cfg = Get-Content "$env:USERPROFILE\UptimeMonitor\config.json" | ConvertFrom-Json
$cfg.server.port = 9090
$cfg | ConvertTo-Json -Depth 10 | Set-Content "$env:USERPROFILE\UptimeMonitor\config.json"
```

## Встановлення Docker

```bash
docker run -d -p 8080:8080 -v uptime-data:/var/lib/uptime-monitor ghcr.io/ajjs1ajjs/uptime-monitor:latest
```

## Облікові дані за замовчуванням

- **Ім'я користувача:** `admin`
- **Пароль:** `admin`

**Змініть пароль після першого входу!**

## Команди керування

### Linux (systemd)

```bash
# Check status
sudo systemctl status uptime-monitor

# Start service
sudo systemctl start uptime-monitor

# Stop service
sudo systemctl stop uptime-monitor

# Restart service
sudo systemctl restart uptime-monitor

# Enable on boot
sudo systemctl enable uptime-monitor

# Disable on boot
sudo systemctl disable uptime-monitor

# View logs
sudo journalctl -u uptime-monitor -f

# View last 50 lines
sudo journalctl -u uptime-monitor -n 50
```

### Windows (служба)

```cmd
# Check status
sc query UptimeMonitor

# Start service
net start UptimeMonitor

# Stop service
net stop UptimeMonitor

# Restart service
net stop UptimeMonitor && net start UptimeMonitor

# Disable on boot
sc config UptimeMonitor start= disabled

# Enable on boot
sc config UptimeMonitor start= auto
```

## Видалення

### Linux (через install.sh)

```bash
# Stop service
sudo systemctl stop uptime-monitor

# Disable service
sudo systemctl disable uptime-monitor

# Remove systemd service file
sudo rm /etc/systemd/system/uptime-monitor.service

# Reload systemd
sudo systemctl daemon-reload

# Remove application files
sudo rm -rf /opt/uptime-monitor

# Remove user (optional)
sudo userdel uptime-monitor
```

### Linux (через APT)

```bash
# Stop service
sudo systemctl stop uptime-monitor

# Disable service
sudo systemctl disable uptime-monitor

# Uninstall package
sudo apt remove --purge uptime-monitor

# Remove repository
sudo rm /etc/apt/sources.list.d/uptime-monitor.list
sudo rm /usr/share/keyrings/uptime-monitor.gpg

# Update package list
sudo apt update
```

### Windows (через інсталятор)

1. Відкрийте «Налаштування» -> «Програми» -> «Встановлені програми»
2. Знайдіть «Монітор безвідмовної роботи»
3. Натисніть «Видалити»

### Windows (вручну)

```cmd
# Stop service
net stop UptimeMonitor

# Delete service
sc delete UptimeMonitor

# Remove application files
rd /s /q "C:\Program Files\UptimeMonitor"
rd /s /q "%USERPROFILE%\UptimeMonitor"
```

## Усунення несправностей

### Порт уже використовується

**Linux:**
```bash
# Find process using port
sudo lsof -i :8080

# Kill process
sudo kill -9 <PID>
```

**Windows:**
```cmd
# Find process using port
netstat -ano | findstr :8080

# Kill process
taskkill /PID <PID> /F
```

### Служба не запускається

**Linux:**
```bash
# Check logs
sudo journalctl -u uptime-monitor -n 50

# Check permissions
ls -la /opt/uptime-monitor

# Check Python version
python3 --version
```

**Windows:**
```cmd
# Check logs
type "%USERPROFILE%\UptimeMonitor\uptime_monitor.log"

# Check if running as admin
whoami /priv
```

### Сповіщення не працюють

1. Перевірте, чи ввімкнено сповіщення у веб-інтерфейсі
2. Переконайтеся, що ключі API правильні
3. Перевірте журнали на наявність помилок:
```bash
   sudo journalctl -u uptime-monitor -f
   ```
    ```cmd
    type "%USERPROFILE%\UptimeMonitor\uptime_monitor.log"
    ```

### Проблеми резервного копіювання

**Помилка резервного копіювання через помилку дозволу:**
```bash
# Check backup directory permissions
sudo ls -la /backup/
sudo ls -la /backup/uptime-monitor/

# Fix permissions
sudo mkdir -p /backup/uptime-monitor
sudo chown -R root:root /backup/uptime-monitor/
sudo chmod 755 /backup/uptime-monitor/

# Retry backup
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/
```

**Помилка монтування NFS:**
```bash
# Install NFS client
sudo apt-get update
sudo apt-get install -y nfs-common

# Check NFS server availability
showmount -e 192.168.1.10

# Test manual mount
sudo mkdir -p /mnt/nfs-backup
sudo mount -t nfs 192.168.1.10:/exports/backups /mnt/nfs-backup

# Check mount
mount | grep nfs

# If successful, use the mount-backup script
sudo /opt/uptime-monitor/scripts/mount-backup.sh --type nfs --server 192.168.1.10 --path /exports/backups --mount-point /mnt/nfs-backup --persist
```

**Помилка монтування Samba (SMB):**
```bash
# Install Samba client
sudo apt-get update
sudo apt-get install -y cifs-utils

# Create credentials file
sudo mkdir -p /root/.backup-creds
sudo tee /root/.backup-creds/smb-credentials << EOF
username=backupuser
password=yourpassword
domain=WORKGROUP
EOF
sudo chmod 600 /root/.backup-creds/smb-credentials

# Test manual mount
sudo mkdir -p /mnt/smb-backup
sudo mount -t cifs //192.168.1.11/backups /mnt/smb-backup -o credentials=/root/.backup-creds/smb-credentials

# Use the mount-backup script
sudo /opt/uptime-monitor/scripts/mount-backup.sh --type smb --server 192.168.1.11 --share backups --mount-point /mnt/smb-backup --credentials /root/.backup-creds/smb-credentials --persist
```

**Помилка відновлення або служба не запускається після відновлення:**
```bash
# Check backup integrity
sudo /opt/uptime-monitor/scripts/verify-backup.sh /path/to/backup.tar.gz

# Check service status
sudo systemctl status uptime-monitor

# View restore logs
sudo tail -f /var/log/uptime-monitor/backup.log

# View service logs
sudo journalctl -u uptime-monitor -n 50

# Manual restore safety backup (created during restore)
ls -la /tmp/uptime-pre-restore-*/

# Restore from safety backup if needed
sudo cp -r /tmp/uptime-pre-restore-*/sites.db /var/lib/uptime-monitor/
sudo cp /tmp/uptime-pre-restore-*/config.json /etc/uptime-monitor/
sudo systemctl restart uptime-monitor
```

**Заплановане резервне копіювання не виконується:**
```bash
# Check if cron service is running
sudo systemctl status cron

# Check cron jobs
sudo cat /etc/cron.d/uptime-monitor-backup

# Check cron logs
sudo grep CRON /var/log/syslog | tail -20

# Test backup manually
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/ --type daily

# Reinstall schedule
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --remove
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install --dest /backup/uptime-monitor/
```

**Занадто велика резервна копія/проблеми з дисковим простором:**
```bash
# Check backup sizes
sudo du -sh /backup/uptime-monitor/*

# Clean old backups manually
sudo /opt/uptime-monitor/scripts/backup-rotation.sh --keep 3

# Check available space
df -h /backup

# Move backups to external storage
sudo /opt/uptime-monitor/scripts/mount-backup.sh --type nfs --server <IP> --path /exports/backups --mount-point /mnt/nfs-backup --persist
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install --dest /mnt/nfs-backup/uptime-monitor/
```

## Конфігурація

### Файл конфігурації Linux

Розташування: `/etc/uptime-monitor/config.json`

```json
{
    "server": {
        "port": 8080,
        "host": "0.0.0.0",
        "domain": "auto"
    },
    "ssl": {
        "enabled": false,
        "type": "custom",
        "cert_path": "/etc/uptime-monitor/ssl/cert.pem",
        "key_path": "/etc/uptime-monitor/ssl/key.pem",
        "redirect_http": true,
        "hsts": true,
        "hsts_max_age": 31536000
    },
    "data_dir": "/var/lib/uptime-monitor",
    "log_dir": "/var/log/uptime-monitor",
    "check_interval": 60,
    "notifications": {
        "email_enabled": false,
        "email_smtp_server": "",
        "email_smtp_port": 587,
        "email_username": "",
        "email_password": "",
        "email_to": ""
    },
    "backup": {
        "enabled": true,
        "max_backups": 10,
        "backup_dir": "/etc/uptime-monitor/config.backups"
    }
}
```

**Параметри конфігурації:**

- `server.port` - номер порту (за замовчуванням: 8080)
- `server.host` - Адреса прив'язки (за замовчуванням: 0.0.0.0 - усі інтерфейси)
- `server.domain` - Домен або IP-адреса сервера (за замовчуванням: "авто" - автоматичне визначення IP-адреси)
- `ssl.enabled` - Увімкнути HTTPS (за замовчуванням: false)
- `ssl.type` - Тип сертифіката: "custom", "selfsigned", "letsencrypt"
- `ssl.cert_path` - Шлях до сертифіката SSL
- `ssl.key_path` - Шлях до закритого ключа SSL
- `backup.enabled` - Увімкнути автоматичне резервне копіювання (за замовчуванням: true)
- `backup.max_backups` - Кількість резервних копій для збереження (за замовчуванням: 10)

### Файл конфігурації Windows

Розташування: `%USERPROFILE%\UptimeMonitor\config.json`

## Керування конфігурацією

### Редагування конфігурації

**Linux:**
```bash
# Edit configuration
sudo nano /etc/uptime-monitor/config.json

# Restart service to apply changes
sudo systemctl restart uptime-monitor

# Check status
sudo systemctl status uptime-monitor
```

### Відкат конфігурації

Перед кожною зміною конфігурації створюються автоматичні резервні копії.

**Список доступних резервних копій:**
```bash
sudo /opt/uptime-monitor/scripts/config-rollback.sh --list
```

**Повернення до попередньої конфігурації:**
```bash
sudo /opt/uptime-monitor/scripts/config-rollback.sh --previous
```

**Відкат до певної резервної копії:**
```bash
sudo /opt/uptime-monitor/scripts/config-rollback.sh --to config.20260218-120000.json
```

**Подивитися відмінності:**
```bash
sudo /opt/uptime-monitor/scripts/config-rollback.sh --diff config.latest.json
```

## Система резервного копіювання

Uptime Monitor включає комплексну систему резервного копіювання, яка підтримує локальне сховище, NFS і спільні ресурси Samba.

### Швидкий старт

**Створіть першу резервну копію:**
```bash
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/ --type daily
```

**Перевірити статус резервного копіювання:**
```bash
sudo /opt/uptime-monitor/scripts/backup-system.sh --status
```

**Список доступних резервних копій:**
```bash
sudo /opt/uptime-monitor/scripts/restore-system.sh --list
```

**Відновити з останньої резервної копії:**
```bash
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto
```

### Що створюється резервна копія

- **База даних**: база даних SQLite з усіма сайтами та даними моніторингу
- **Конфігурація**: config.json і історія конфігурацій
- **SSL-сертифікати**: ваші SSL-сертифікати та ключі
- **Журнали**: файли останніх журналів (останні 7 днів)
- **Systemd Service**: файл конфігурації служби

### Типи резервних копій

| Тип | Коли | Збереження |
|------|------|-----------|
| на зміну | Після зміни конфігурації | 10 резервних копій |
| щодня | Щодня о 2:00 | 7 днів |
| щотижня | Кожної неділі о 3:00 | Все (зберігається до місячних) |
| щомісяця | 1-го числа місяця о 4:00 | Все (зберігається до року) |
| щорічно | 1 січня о 5:00 | Назавжди |

### Резервне копіювання вручну

**Створити негайну резервну копію:**
```bash
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/
```

**Створити резервну копію з коментарем:**
```bash
sudo /opt/uptime-monitor/scripts/backup-system.sh \
    --dest /backup/uptime-monitor/ \
    --type on-change \
    --comment "Before major config change"
```

**Перевірте цілісність резервної копії:**
```bash
sudo /opt/uptime-monitor/scripts/backup-system.sh --verify --dest /backup/uptime-monitor/
```

### Резервне копіювання за розкладом (автоматично)

**Встановлюйте щоденні резервні копії:**
```bash
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install \
    --daily "0 2 * * *" \
    --dest /backup/uptime-monitor/
```

**Встановити за повним графіком:**
```bash
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install \
    --daily "0 2 * * *" \
    --weekly "0 3 * * 0" \
    --monthly "0 4 1 * *" \
    --dest /backup/uptime-monitor/
```

**Перевірити статус розкладу:**
```bash
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --status
```

**Видалити всі розклади:**
```bash
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --remove
```

**Тестова система резервного копіювання:**
```bash
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --test
```

### Налаштування резервного копіювання NFS

**1. Встановити клієнт NFS:**
```bash
sudo apt-get update
sudo apt-get install -y nfs-common
```

**2. Підключити ресурс NFS:**
```bash
sudo /opt/uptime-monitor/scripts/mount-backup.sh \
    --type nfs \
    --server 192.168.1.10 \
    --path /exports/backups \
    --mount-point /mnt/nfs-backup \
    --persist
```

**3. Створіть резервну копію в NFS:**
```bash
sudo /opt/uptime-monitor/scripts/backup-system.sh \
    --dest /mnt/nfs-backup/uptime-monitor/ \
    --type daily
```

**4. Заплануйте автоматичне резервне копіювання NFS:**
```bash
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install \
    --daily "0 2 * * *" \
    --dest /mnt/nfs-backup/uptime-monitor/
```

**Ручне монтування NFS (альтернатива):**
```bash
# Create mount point
sudo mkdir -p /mnt/nfs-backup

# Mount
sudo mount -t nfs 192.168.1.10:/exports/backups /mnt/nfs-backup

# Add to /etc/fstab for persistence
echo "192.168.1.10:/exports/backups /mnt/nfs-backup nfs defaults 0 0" | sudo tee -a /etc/fstab
```

### Налаштування резервного копіювання Samba (SMB).

**1. Встановити клієнт Samba:**
```bash
sudo apt-get update
sudo apt-get install -y cifs-utils
```

**2. Створіть файл облікових даних:**
```bash
sudo mkdir -p /root/.backup-creds
sudo tee /root/.backup-creds/smb-credentials << EOF
username=backupuser
password=yourpassword
domain=WORKGROUP
EOF
sudo chmod 600 /root/.backup-creds/smb-credentials
```

**3. Частка гори Самба:**
```bash
sudo /opt/uptime-monitor/scripts/mount-backup.sh \
    --type smb \
    --server 192.168.1.11 \
    --share backups \
    --mount-point /mnt/smb-backup \
    --credentials /root/.backup-creds/smb-credentials \
    --persist
```

**4. Створити резервну копію на Samba:**
```bash
sudo /opt/uptime-monitor/scripts/backup-system.sh \
    --dest /mnt/smb-backup/uptime-monitor/ \
    --type daily
```

**Ручне кріплення Samba (альтернатива):**
```bash
# Create mount point
sudo mkdir -p /mnt/smb-backup

# Mount
sudo mount -t cifs //192.168.1.11/backups /mnt/smb-backup \
    -o credentials=/root/.backup-creds/smb-credentials

# Add to /etc/fstab
echo "//192.168.1.11/backups /mnt/smb-backup cifs credentials=/root/.backup-creds/smb-credentials,_netdev 0 0" | sudo tee -a /etc/fstab
```

### Використання NFS і Samba

Ви можете використовувати кілька місць призначення резервних копій одночасно:

```bash
# Install schedule for both
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install \
    --daily "0 2 * * *" \
    --dest /backup/uptime-monitor/ \
    --enable-nfs

# This will backup to:
# 1. /backup/uptime-monitor/ (local)
# 2. /mnt/nfs-backup/uptime-monitor/ (NFS)
```

### Відновити з резервної копії

**Список доступних резервних копій:**
```bash
sudo /opt/uptime-monitor/scripts/restore-system.sh --list
```

**Відновити з останньої резервної копії:**
```bash
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto
```

**Відновити з певної резервної копії:**
```bash
sudo /opt/uptime-monitor/scripts/restore-system.sh \
    --from /backup/uptime-monitor/daily/backup-20260218-020000.tar.gz
```

**Відновити лише базу даних:**
```bash
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto --only database
```

**Відновити лише конфігурацію:**
```bash
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto --only config
```

**Сухий хід (подивитися, що буде відновлено):**
```bash
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto --dry-run
```

### Ротація резервного копіювання

Автоматична ротація запускається після кожного резервного копіювання. Щоб запустити вручну:

```bash
# Check what would be deleted (dry run)
sudo /opt/uptime-monitor/scripts/backup-rotation.sh --dry-run

# Run rotation
sudo /opt/uptime-monitor/scripts/backup-rotation.sh

# Keep only last 5 backups of each type
sudo /opt/uptime-monitor/scripts/backup-rotation.sh --keep 5
```

### Перевірте резервні копії

**Перевірте конкретну резервну копію:**
```bash
sudo /opt/uptime-monitor/scripts/verify-backup.sh \
    /backup/uptime-monitor/daily/backup-20260218-020000.tar.gz
```

**Перевірте всі резервні копії:**
```bash
sudo /opt/uptime-monitor/scripts/verify-backup.sh --all
```

**Показати статистику резервного копіювання:**
```bash
sudo /opt/uptime-monitor/scripts/verify-backup.sh --list
```

### Резервна конфігурація

Редагувати `/etc/uptime-monitor/config.json`:

```json
{
    "backup": {
        "enabled": true,
        "on_change_backup": true,
        "retention": {
            "on_change": 10,
            "daily": 7,
            "weekly": "all",
            "monthly": "all",
            "yearly": "all"
        }
    }
}
```

### Відключити резервне сховище

**Відключити NFS:**
```bash
sudo /opt/uptime-monitor/scripts/mount-backup.sh \
    --unmount \
    --mount-point /mnt/nfs-backup
```

**Відключіть Samba:**
```bash
sudo /opt/uptime-monitor/scripts/mount-backup.sh \
    --unmount \
    --mount-point /mnt/smb-backup
```

## Налаштування SSL/HTTPS

### Варіант 1: використання власних сертифікатів (рекомендовано)

**Крок 1:** Скопіюйте свої сертифікати в каталог SSL:
```bash
sudo mkdir -p /etc/uptime-monitor/ssl
sudo cp /path/to/your/certificate.pem /etc/uptime-monitor/ssl/cert.pem
sudo cp /path/to/your/private.key /etc/uptime-monitor/ssl/key.pem
sudo chmod 600 /etc/uptime-monitor/ssl/*.pem
```

**Крок 2:** Оновіть конфігурацію:
```bash
sudo nano /etc/uptime-monitor/config.json
```

Змініть такі налаштування:
```json
{
    "server": {
        "port": 443,
        "domain": "your-domain.com"
    },
    "ssl": {
        "enabled": true,
        "type": "custom",
        "cert_path": "/etc/uptime-monitor/ssl/cert.pem",
        "key_path": "/etc/uptime-monitor/ssl/key.pem"
    }
}
```

**Крок 3:** Перезапустіть службу:
```bash
sudo systemctl restart uptime-monitor
```

### Варіант 2: Самопідписаний сертифікат (тільки для тестування)

```bash
# Generate self-signed certificate
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/uptime-monitor/ssl/key.pem \
  -out /etc/uptime-monitor/ssl/cert.pem \
  -subj "/CN=localhost"

# Update config and restart
sudo nano /etc/uptime-monitor/config.json
sudo systemctl restart uptime-monitor
```

**Попередження:** веб-переглядачі відображатимуть попередження безпеки з самопідписаними сертифікатами.

## Конфігурація домену та IP

### Автоматичне визначення IP

За замовчуванням сервер автоматично визначає IP-адресу сервера:
```json
{
    "server": {
        "domain": "auto"
    }
}
```

### Використання конкретного IP

```bash
# Get your server IP
hostname -I

# Edit config
sudo nano /etc/uptime-monitor/config.json
```

Встановіть домен на свій IP:
```json
{
    "server": {
        "domain": "192.168.1.100"
    }
}
```

### Використання доменного імені

**Крок 1:** Налаштуйте DNS-запис A, який вказує на IP-адресу вашого сервера

**Крок 2:** Оновіть конфігурацію:
```json
{
    "server": {
        "domain": "monitor.yourdomain.com"
    }
}
```

**Крок 3:** Перезапустіть службу:
```bash
sudo systemctl restart uptime-monitor
```

## Кінцеві точки API

- `GET /` - Веб-інтерфейс
- `GET /api/sites` - Список усіх сайтів
- `POST /api/sites` - Додати сайт
- `PUT /api/sites/{id}` - Оновити сайт
- `DELETE /api/sites/{id}` - Видалити сайт
- `POST /api/sites/{id}/check` - Перевірити сайт вручну
- `POST /api/notify-settings` - Зберегти налаштування сповіщень

## Доступ до веб-інтерфейсу

**Початкове налаштування (після встановлення):**
- **Linux:** `http://<server-ip>:8080` (IP автоматично визначається під час встановлення)
- **Windows:** `http://localhost:8080` або `http://<your-ip>:8080`

**Після налаштування SSL:**
- **HTTPS:** `https://your-domain.com` (порт 443)

**Щоб перевірити IP-адресу вашого сервера:**
```bash
hostname -I
```

## Технічні деталі

- **Framework:** FastAPI
- **База даних:** SQLite
- **HTTP-клієнт:** aiohttp
- **Сервіс Windows:** pywin32
- **Linux Service:** systemd
- **Порт за замовчуванням:** 8080 (Linux і Windows)
- **Підтримка SSL:** Так (спеціальні сертифікати, самопідписані, Let's Encrypt готові)
- **Конфігурація:** на основі JSON з автоматичним резервним копіюванням/відкатом
- **Інтервал перевірки:** 60 секунд (глобальний), кожен сайт може мати власний інтервал (10с - 3600с)
- **Файл конфігурації:** `/etc/uptime-monitor/config.json` (Linux)
- **Каталог резервного копіювання:** `/etc/uptime-monitor/config.backups` (Linux)

---

## 🗑️ Повне видалення (Linux)

Якщо потрібно видалити Uptime Monitor і встановити з нуля:

### Швидке видалення (одна команда)

```bash
sudo systemctl stop uptime-monitor && \
sudo systemctl disable uptime-monitor && \
sudo rm /etc/systemd/system/uptime-monitor.service && \
sudo systemctl daemon-reload && \
sudo systemctl reset-failed && \
sudo rm -rf /opt/uptime-monitor /etc/uptime-monitor /var/lib/uptime-monitor /var/log/uptime-monitor /backup/uptime-monitor && \
sudo userdel uptime-monitor 2>/dev/null || true && \
echo "✅ Видалення завершено!"
```

### Покрокове видалення

**Крок 1: Зупинити службу**
```bash
sudo systemctl stop uptime-monitor
sudo systemctl disable uptime-monitor
```

**Крок 2: Видалити службу systemd**
```bash
sudo rm /etc/systemd/system/uptime-monitor.service
sudo systemctl daemon-reload
sudo systemctl reset-failed
```

**Крок 3: Видалити директорії**
```bash
# Директорія додатку
sudo rm -rf /opt/uptime-monitor

# Конфігурація
sudo rm -rf /etc/uptime-monitor

# Дані (база даних)
sudo rm -rf /var/lib/uptime-monitor

# Логи
sudo rm -rf /var/log/uptime-monitor

# Резервні копії (за бажанням)
sudo rm -rf /backup/uptime-monitor
```

**Крок 4: Видалити користувача**
```bash
sudo userdel uptime-monitor 2>/dev/null || echo "User already deleted"
```

**Крок 5: Видалити правила фаєрволу (якщо є)**
```bash
# Для UFW
sudo ufw delete allow 8080/tcp 2>/dev/null || true

# Для firewalld
sudo firewall-cmd --permanent --remove-port=8080/tcp 2>/dev/null || true
sudo firewall-cmd --reload 2>/dev/null || true
```

**Крок 6: Перевірити чи все видалено**
```bash
# Перевірка служби
systemctl status uptime-monitor  # Має бути "Unit not found"

# Перевірка процесів
ps aux | grep uptime-monitor  # Має бути пусто

# Перевірка порту
netstat -tlnp | grep 8080  # Має бути пусто
```

### 💾 Збереження даних перед видаленням

Якщо плануєте встановити з нуля і зберегти дані:

```bash
# Зберегти базу даних
sudo cp /var/lib/uptime-monitor/sites.db ~/sites.db.backup

# Зберегти конфігурацію
sudo cp /etc/uptime-monitor/config.json ~/config.json.backup

# Зберегти логи (опціонально)
sudo tar -czf ~/uptime-logs.tar.gz /var/log/uptime-monitor/
```

Після встановлення з нуля відновіть:
```bash
sudo systemctl stop uptime-monitor
sudo cp ~/sites.db.backup /var/lib/uptime-monitor/sites.db
sudo cp ~/config.json.backup /etc/uptime-monitor/config.json
sudo chown uptime-monitor:uptime-monitor /var/lib/uptime-monitor/sites.db
sudo chown uptime-monitor:uptime-monitor /etc/uptime-monitor/config.json
sudo systemctl start uptime-monitor
```

### 🔄 Чиста встановлення з нуля

Після повного видалення:

```bash
# 1. Встановити залежності
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv python3-full sqlite3 curl git

# 2. Встановити Uptime Monitor
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash

# 3. Перевірити статус
sudo systemctl status uptime-monitor

# 4. Відкрити у браузері
http://YOUR_SERVER_IP:8080
# Login: admin / Password: admin

# 5. Змінити пароль за замовчуванням!
```

---

## Підтримка

Якщо виникли проблеми та запитання, будь ласка, відкрийте випуск на GitHub:
https://github.com/ajjs1ajjs/Uptime-Monitor/issues


