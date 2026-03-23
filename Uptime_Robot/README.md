# Монітор безвідмовної роботи

[![Випуск GitHub](https://img.shields.io/github/release/ajjs1ajjs/Uptime-Monitor.svg)](https://github.com/ajjs1ajjs/Uptime-Monitor/releases)
[![Codecov](https://codecov.io/gh/ajjs1ajjs/Uptime-Monitor/branch/main/graph/badge.svg)](https://codecov.io/gh/ajjs1ajjs/Uptime-Monitor)
[![Docker](https://img.shields.io/badge/ghcr.io-ajjs1ajjs%2Fuptime--monitor-blue)](https://github.com/ajjs1ajjs/Uptime-Monitor/pkgs/container/Uptime-Monitor)
[![Ліцензія: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Служба моніторингу безвідмовної роботи веб-сайту з багатоканальними сповіщеннями та відстеженням сертифіката SSL.

**Особливості:**
- ✅ **НОВИНКА! Система резервного копіювання** - автоматичне резервне копіювання з можливістю відновлення
- ✅ **НОВИНКА! Керування конфігураціями** – конфігурація JSON із підтримкою відкату
- ✅ **НОВИНКА! SSL/HTTPS** - спеціальні сертифікати з автоматичним перенаправленням
- Моніторинг кількох веб-сайтів і кінцевих точок
- Відстеження терміну дії сертифіката SSL
- Багатоканальні сповіщення (Telegram, Email, Slack, Discord, Teams, SMS)
- Веб-панель інструментів
- REST API
- Кросплатформенність (Linux, Windows, Docker)

## 📚 Документація

Швидкі посилання на детальну документацію:

- **[Швидкий старт](../docs/QUICKSTART.md)** - Почніть працювати за 5 хвилин
- **[Довідка про команди](../docs/COMMANDS.md)** - Усі команди в одному місці
- **[Посібник із резервного копіювання](../docs/BACKUP.md)** - Повні інструкції з резервного копіювання
- **[Усунення несправностей](../docs/TROUBLESHOOTING.md)** - Вирішення проблем

## Швидкий старт

### Linux (CURL) – рекомендовано

```bash
# Install latest version
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash

# Install with custom port
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash -s -- --port 9090

# Install specific version
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash -s -- --version v1.0.0
```

### Linux (APT)

```bash
# Add repository
curl -fsSL https://ajjs1ajjs.github.io/Uptime-Monitor/KEY.gpg | sudo gpg --dearmor -o /usr/share/keyrings/uptime-monitor.gpg
echo "deb [signed-by=/usr/share/keyrings/uptime-monitor.gpg] https://ajjs1ajjs.github.io/Uptime-Monitor stable main" | sudo tee /etc/apt/sources.list.d/uptime-monitor.list

# Install
sudo apt update && sudo apt install uptime-monitor

# Start
sudo systemctl start uptime-monitor
```

### Докер

```bash
# Pull and run
docker run -d -p 8080:8080 -v uptime-data:/var/lib/uptime-monitor ghcr.io/ajjs1ajjs/uptime-monitor:latest
```

### Windows

1. Завантажте `uptime-monitor-vX.X.X-windows.zip` з [Релізи](https://github.com/ajjs1ajjs/Uptime-Monitor/releases)
2. Витягніть у потрібне місце
3. Запустіть `install.bat` від імені адміністратора

## ⚡ Швидкий початок резервного копіювання (ВАЖЛИВО!)

Після встановлення негайно налаштуйте резервні копії:

```bash
# 1. Create first backup
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/

# 2. Schedule automatic backups
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install --dest /backup/uptime-monitor/

# 3. Verify backup system
sudo /opt/uptime-monitor/scripts/backup-system.sh --status
```

## Облікові дані за замовчуванням

- **Ім'я користувача:** `admin`
- **Пароль:** `admin`

**⚠️ Змініть пароль після першого входу!**

## Структура проекту

```
Uptime_Robot/
├── main.py                 # Веб-панель (FastAPI)
├── worker.py               # Фоновий моніторинг (Окремий процес)
├── requirements.txt        # Залежності Python
├── routers/                # Модулі API та UI
├── templates/              # HTML шаблони
├── config_manager.py       # Керування конфігурацією
├── database.py             # Асинхронна робота з БД
└── sites.db               # База даних (створюється автоматично)
```

## Швидкий старт (Python)

### 1. Встановлення залежностей
```bash
pip install -r requirements.txt
```

### 2. Запуск Веб-панелі
```bash
python main.py [port]
```
За замовчуванням порт 8080.

### 3. Запуск Моніторингу (ОБОВ'ЯЗКОВО)
Щоб сайти перевірялися у фоні, запустіть окремий процес:
```bash
python worker.py
```
*(Або `python -m Uptime_Robot.worker`, якщо запускаєте з корінного каталогу проекту)*

### 3. Вхід в систему
Відкрийте браузер: http://localhost:8080 (або ваш порт)

**Обов'язкова авторизація:**
- **Логін:** `admin`
- **Пароль:** `admin`
- ⚠️ **Обов'язково змініть пароль після першого входу!**

Після входу система перенаправить на сторінку зміни пароля.

## Встановлення як Windows служба

### Спосіб 1: Простий (install.bat)
1. Запустіть `install.bat` від імені Адміністратора
2. Введіть порт
3. Служба буде встановлена та запущена

```cmd
install.bat
```

### Спосіб 2: Створення EXE + інсталятора

1. **Запустіть збірку:**
```bash
build_exe.bat
```Це створить:
- `UptimeMonitor.exe` - головний виконуваний файл
- Інсталятор з GUI для вибору порту
- Програма реєструється в "Programs and Features" для видалення

2. **Встановіть:**
- Запустіть згенерований інсталятор
- Введіть бажаний порт
- Програма встановиться в `C:\Program Files\UptimeMonitor`
- Служба автоматично запуститься

3. **Доступ:**
- Веб-інтерфейс: http://localhost:[port]
- Автоматичне визначення IP показується на головній сторінці

### Управління службою

```cmd
# Зупинити
net stop UptimeMonitor

# Запустити
net start UptimeMonitor

# Перезапустити
net stop UptimeMonitor && net start UptimeMonitor

# Видалити службу
sc delete UptimeMonitor
```

## Встановлення як Linux служба

### Спосіб 1: Через install.sh
```bash
sudo ./install.sh
```

### Спосіб 2: Вручну
```bash
# Встановити залежності
sudo apt update && sudo apt install python3-pip python3-venv sqlite3 curl

# Клонувати репозиторій
git clone https://github.com/ajjs1ajjs/Uptime-Monitor.git
cd Uptime-Monitor

# Створити віртуальне середовище
python3 -m venv venv
source venv/bin/activate

# Встановити залежності
pip install -r requirements.txt

# Запустити
python main.py --port 8080
```

### Створення системної служби (systemd)
```bash
# Створити файл служби
sudo nano /etc/systemd/system/uptime-monitor.service
```

Додайте наступне:
```ini
[Unit]
Description=Uptime Monitor Service
After=network.target

[Service]
Type=simple
User=uptime-monitor
WorkingDirectory=/opt/uptime-monitor
ExecStart=/opt/uptime-monitor/venv/bin/python /opt/uptime-monitor/main.py --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Запустити
sudo systemctl daemon-reload
sudo systemctl enable uptime-monitor
sudo systemctl start uptime-monitor
```

## Видалення програми

### Якщо встановлено через інсталятор (Windows):
1. Відкрийте "Settings" -> "Apps" -> "Installed apps"
2. Знайдіть "Uptime Monitor"
3. Натисніть "Uninstall"

### Якщо встановлено через install.sh (Linux):
```bash
sudo systemctl stop uptime-monitor
sudo systemctl disable uptime-monitor
sudo rm /etc/systemd/system/uptime-monitor.service
sudo systemctl daemon-reload
sudo rm -rf /opt/uptime-monitor
```

### Ручне видалення (Windows):
```cmd
net stop UptimeMonitor
sc delete UptimeMonitor
rd /s /q "C:\Program Files\UptimeMonitor"
```

## Налаштування сповіщень

### Доступні канали:
- 📱 **Telegram** - Bot Token + Chat ID
- 🏢 **MS Teams** - Incoming Webhook URL
- 🎮 **Discord** - Webhook URL
- 💬 **Slack** - Incoming Webhook URL
- 📧 **Email** - SMTP (Gmail, Outlook, тощо)
- 📱 **SMS** - Twilio API

### Налаштування в веб-інтерфейсі:
1. Увімкніть потрібні канали (toggle switches)
2. Заповніть дані для кожного каналу
3. Натисніть "Зберегти налаштування"

## Функціонал

### Моніторинг сайтів:
- ➕ Додавання сайтів з вибором каналів сповіщень
- ✏️ Редагування доданих сайтів
- 🗑️ Видалення сайтів
- 🔄 Ручна перевірка

### Статистика:
- Загальна кількість сайтів
- Кількість доступних/недоступних
- Uptime (відсоток доступності)
- Час відповіді
- HTTP статус код

### Автоматичні перевірки:
- Кожні 60 секунд
- Автоматичні сповіщення при падінні
- Антиспам: сповіщення не частіше ніж раз в 5 хвилин

## 🆕 Новий функціонал (Остання версія)

### 🔄 Система резервного копіювання

**Команди:**
```bash
# Створити резервну копію
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/

# Перевірити статус
sudo /opt/uptime-monitor/scripts/backup-system.sh --status

# Відновити з останньої копії
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto

# Запланувати автоматичні копії
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install --dest /backup/uptime-monitor/

# NFS монтування
sudo /opt/uptime-monitor/scripts/mount-backup.sh --type nfs --server 192.168.1.10 --path /exports/backups --mount-point /mnt/nfs-backup --persist

# Samba монтування
sudo /opt/uptime-monitor/scripts/mount-backup.sh --type smb --server 192.168.1.11 --share backups --mount-point /mnt/smb-backup --persist
```

**Що зберігається:**
- База даних SQLite (всі сайти та історія)
- Конфігурація (config.json)
- SSL сертифікати
- Логи (останні 7 днів)
- Systemd служба

**Типи бекапів:**
- `on-change` - Після зміни конфігурації (10 копій)
- `daily` - Щодня о 2:00 (7 днів)
- `weekly` - Щонеділі о 3:00 (всі)
- `monthly` - 1-го числа о 4:00 (всі)
- `yearly` - 1 січня о 5:00 (назавжди)

### ⚙️ Управління конфігурацією

**Файл конфігурації:** `/etc/uptime-monitor/config.json`

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
        "key_path": "/etc/uptime-monitor/ssl/key.pem"
    },
    "backup": {
        "enabled": true,
        "retention": {
            "daily": 7,
            "weekly": "all"
        }
    }
}
```

**Команди:**
```bash
# Редагувати конфіг
sudo nano /etc/uptime-monitor/config.json

# Відкат до попередньої версії
sudo /opt/uptime-monitor/scripts/config-rollback.sh --previous

# Список версій
sudo /opt/uptime-monitor/scripts/config-rollback.sh --list

# Перезапуск після змін
sudo systemctl restart uptime-monitor
```

### 🔒 SSL/HTTPS

**Налаштування:**
1. Додайте сертифікати:
```bash
sudo mkdir -p /etc/uptime-monitor/ssl
sudo cp cert.pem key.pem /etc/uptime-monitor/ssl/
sudo chmod 600 /etc/uptime-monitor/ssl/*.pem
```

2. Відредагуйте конфіг:
```bash
sudo nano /etc/uptime-monitor/config.json
# Змініть: "ssl.enabled": true, "server.port": 443
```

3. Перезапустіть:
```bash
sudo systemctl restart uptime-monitor
```

**Функції:**
- Автоматичний редирект HTTP → HTTPS
- HSTS заголовки
- Підтримка власних сертифікатів

## Кінцеві точки API

- `GET /` - Веб-інтерфейс
- `GET /api/sites` - Список всіх сайтів
- `POST /api/sites` - Додати сайт
- `PUT /api/sites/{id}` - Оновити сайт
- `DELETE /api/sites/{id}` - Видалити сайт
- `POST /api/sites/{id}/check` - Перевірити сайт вручну
- `POST /api/notify-settings` - Зберегти налаштування сповіщень

## Порт

За замовчуванням: **8080** (Windows і Linux)

Можна змінити:
- При запуску: `python main.py 8080`
- При встановленні через інсталятор
- В файлі `%USERPROFILE%\UptimeMonitor\config.json` (параметр `server.port`)

## Технічні деталі

- **Фреймворк:** FastAPI
- **База даних:** SQLite
- **HTTP клієнт:** aiohttp
- **Windows служба:** pywin32
- **Linux служба:** systemd
- **Порт:** Конфігурований (за замовч. 8080)
- **IP:** Автоматично визначається локальна IP адреса

## Проблеми та рішення

### Порт зайнятий
Змініть порт в `%USERPROFILE%\UptimeMonitor\config.json` або перевстановіть службу через `install.bat`.

### Служба не запускається
Перевірте чи є права адміністратора:
```cmd
sc query UptimeMonitor
```

### Не надходять сповіщення
Перевірте налаштування в веб-інтерфейсі та правильність API ключів.

## Ліцензія

МОЯ ліцензія


