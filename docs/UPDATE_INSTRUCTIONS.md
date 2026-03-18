# Оновлення Uptime Monitor на продакшені

Цей документ описує **безпечний порядок оновлення** з обов’язковим бекапом перед змінами, перевіркою після оновлення та rollback-планом.

Підтримуються 2 сценарії:
1. інсталяція з `.git` (git clone)
2. інсталяція без `.git` (archive/zip)

---

## TL;DR (рекомендований порядок)

1. Перевірити поточний стан сервісу  
2. Зробити **повний pre-update backup** (`backup-system.sh --verify`)  
3. Зупинити сервіс  
4. Оновити код (git або zip)  
5. Запустити сервіс  
6. Перевірити статус/логи/HTTP  
7. При проблемі — **rollback** через `restore-system.sh`

---

## Крок 0: Перевірити тип інсталяції

```bash
cd /opt/uptime-monitor
if [ -d .git ]; then
  echo "git installation"
else
  echo "non-git installation"
fi
```

---

## Крок 1: Підготовка змінних (опційно, зручно)

```bash
SERVICE=uptime-monitor
APP_DIR=/opt/uptime-monitor
BACKUP_ROOT=/backup/uptime-monitor
TS=$(date +%Y%m%d-%H%M%S)
```

---

## Крок 2: Перевірити стан перед оновленням

```bash
sudo systemctl status $SERVICE --no-pager
sudo journalctl -u $SERVICE -n 30 --no-pager
```

---

## Крок 3: Обов’язковий pre-update backup (рекомендовано як стандарт)

> Це основний захист перед оновленням.  
> Скрипт зберігає БД, конфіг, SSL, логи, systemd unit (якщо є).

```bash
sudo mkdir -p "$BACKUP_ROOT"
sudo $APP_DIR/scripts/backup-system.sh \
  --dest "$BACKUP_ROOT" \
  --type on-change \
  --comment "pre-update-$TS" \
  --verify

sudo $APP_DIR/scripts/backup-system.sh --status
```

### Додатково (швидка копія ключових файлів)

```bash
sudo cp /etc/uptime-monitor/config.json "/backup/config.pre-update.$TS.json"
sudo cp /etc/systemd/system/uptime-monitor.service "/backup/uptime-monitor.service.pre-update.$TS" 2>/dev/null || true
```

---

## Крок 4: Зупинити сервіс

```bash
sudo systemctl stop $SERVICE
sudo systemctl is-active $SERVICE || true
```

---

## Варіант 1: Оновлення через Git (якщо є `.git`)

```bash
cd /opt/uptime-monitor
sudo git fetch --all --prune
sudo git checkout main
sudo git pull --ff-only origin main
```

---

## Варіант 2: Оновлення через ZIP/wget (якщо немає `.git`)

```bash
# Перевірити/встановити unzip
if ! command -v unzip &> /dev/null; then
  sudo apt update && sudo apt install -y unzip
fi

cd /tmp
wget https://github.com/ajjs1ajjs/Uptime-Monitor/archive/refs/heads/main.zip -O uptime_update.zip

# КРИТИЧНО: Видалити стару папку з sudo
sudo rm -rf /tmp/Uptime-Monitor-main

# КРИТИЧНО: Розпакувати з sudo
sudo unzip -o uptime_update.zip

# Скопіювати файли
sudo cp -r Uptime-Monitor-main/Uptime_Robot/* /opt/uptime-monitor/

# Прибрати тимчасові файли
sudo rm -rf uptime_update.zip Uptime-Monitor-main
```

---

## Крок 5: Запуск після оновлення

```bash
sudo systemctl daemon-reload
sudo systemctl start $SERVICE
sleep 3
sudo systemctl status $SERVICE --no-pager
```

---

## Крок 6: Перевірка після оновлення (обов’язково)

```bash
# Логи сервісу
sudo journalctl -u $SERVICE -n 80 --no-pager

# Перевірка HTTP (порт змініть якщо у вас не 8080)
curl -fsS http://localhost:8080 >/dev/null && echo "HTTP OK" || echo "HTTP FAIL"
```

---

## Точкова перевірка, що оновлення застосувалось

```bash
cd /opt/uptime-monitor
grep -n "_normalize_and_validate_url" main.py
grep -n "idx_ssl_certificates_site_id_unique" models.py
grep -n "UPDATE ssl_certificates SET" monitoring.py
grep -n "WHERE s.is_active = 1" models.py
```

---

## Rollback (якщо щось пішло не так)

### Швидкий rollback з останнього backup

```bash
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto --force
```

### Rollback з конкретного backup-файлу

```bash
sudo /opt/uptime-monitor/scripts/restore-system.sh \
  --from /backup/uptime-monitor/on-change/backup-YYYYMMDD-HHMMSS.tar.gz \
  --force
```

### Перевірка після rollback

```bash
sudo systemctl status uptime-monitor --no-pager
sudo journalctl -u uptime-monitor -n 80 --no-pager
```

---

## Повний runbook одним блоком (копіюй/виконуй по кроках)

```bash
SERVICE=uptime-monitor
APP_DIR=/opt/uptime-monitor
BACKUP_ROOT=/backup/uptime-monitor
TS=$(date +%Y%m%d-%H%M%S)

# Перевірити/встановити unzip
if ! command -v unzip &> /dev/null; then
  sudo apt update && sudo apt install -y unzip
fi

sudo systemctl status $SERVICE --no-pager
sudo journalctl -u $SERVICE -n 30 --no-pager

sudo mkdir -p "$BACKUP_ROOT"
sudo $APP_DIR/scripts/backup-system.sh --dest "$BACKUP_ROOT" --type on-change --comment "pre-update-$TS" --verify
sudo $APP_DIR/scripts/backup-system.sh --status
sudo cp /etc/uptime-monitor/config.json "/backup/config.pre-update.$TS.json"

sudo systemctl stop $SERVICE

cd /opt/uptime-monitor
if [ -d .git ]; then
  sudo git fetch --all --prune
  sudo git checkout main
  sudo git pull --ff-only origin main
else
  cd /tmp
  wget https://github.com/ajjs1ajjs/Uptime-Monitor/archive/refs/heads/main.zip -O uptime_update.zip
  
  # КРИТИЧНО: Видалити стару папку з sudo
  sudo rm -rf /tmp/Uptime-Monitor-main
  
  # КРИТИЧНО: Розпакувати з sudo
  sudo unzip -o uptime_update.zip
  
  # Скопіювати файли
  sudo cp -r /tmp/Uptime-Monitor-main/Uptime_Robot/* /opt/uptime-monitor/
  
  # Прибрати тимчасові файли
  sudo rm -rf uptime_update.zip /tmp/Uptime-Monitor-main
fi

sudo systemctl daemon-reload
sudo systemctl start $SERVICE
sleep 3

sudo systemctl status $SERVICE --no-pager
sudo journalctl -u $SERVICE -n 80 --no-pager
curl -fsS http://localhost:8080 >/dev/null && echo "HTTP OK" || echo "HTTP FAIL"
```

---

## Windows (окремий сценарій)

```powershell
# 1) Backup data
Copy-Item "$env:USERPROFILE\UptimeMonitor\sites.db" "$env:USERPROFILE\UptimeMonitor\sites.db.backup.$(Get-Date -Format yyyyMMdd-HHmmss)"
Copy-Item "$env:USERPROFILE\UptimeMonitor\config.json" "$env:USERPROFILE\UptimeMonitor\config.json.backup.$(Get-Date -Format yyyyMMdd-HHmmss)"

# 2) Update files
# If git clone:
cd D:\path\to\Uptime-Monitor
git pull --ff-only origin main

# If release ZIP:
# Download and extract latest Windows ZIP from:
# https://github.com/ajjs1ajjs/Uptime-Monitor/releases

# 3) Reinstall service from updated folder
cd D:\path\to\Uptime-Monitor\Uptime_Robot
python main_service.py stop
python main_service.py remove
.\install.bat

# 4) Verify service and port
sc.exe queryex UptimeMonitor
netstat -ano | findstr :8080
```

---

## Примітки безпеки

- Завжди робіть backup **до** `systemctl stop` + update.
- Не пропускайте `--verify` для критичних апдейтів.
- Для прод-середовища тримайте окремий каталог бекапів (локально + NFS/SMB за можливості).
- Після оновлення перевіряйте не лише `systemctl status`, а й фактичну доступність HTTP.