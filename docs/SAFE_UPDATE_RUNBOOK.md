# 🔐 SAFE UPDATE RUNBOOK (Production)

Цей документ — покроковий **безпечний сценарій оновлення** Uptime Monitor на продакшені:
- спочатку повне збереження стану,
- потім оновлення,
- перевірка,
- і швидкий rollback при проблемах.

---

## 🎯 Мета

Зменшити ризик втрати даних/даунтайму під час апдейту:
1. зробити перевірений pre-update backup,
2. оновити код контрольовано,
3. підтвердити працездатність,
4. мати rollback за 1-2 команди.

---

## ✅ Передумови

- Linux host з `systemd`
- встановлений сервіс: `uptime-monitor`
- скрипти доступні в `/opt/uptime-monitor/scripts/`
- доступ sudo
- бажано мати вільне місце в `/backup`
- **встановлено `unzip`** (для ZIP-методу: `sudo apt install -y unzip`)

---

## 1) Підготувати змінні

```bash
SERVICE=uptime-monitor
APP_DIR=/opt/uptime-monitor
BACKUP_ROOT=/backup/uptime-monitor
TS=$(date +%Y%m%d-%H%M%S)
```

---

## 2) Перевірити поточний стан (до апдейту)

```bash
sudo systemctl status $SERVICE --no-pager
sudo journalctl -u $SERVICE -n 50 --no-pager
```

---

## 3) Зробити обов’язковий pre-update backup

> Це **критичний** крок. Не пропускати.

```bash
sudo mkdir -p "$BACKUP_ROOT"
sudo $APP_DIR/scripts/backup-system.sh \
  --dest "$BACKUP_ROOT" \
  --type on-change \
  --comment "pre-update-$TS" \
  --verify
```

Переконатися, що backup створено:

```bash
sudo $APP_DIR/scripts/backup-system.sh --status
```

Додатково зберегти ключові файли:

```bash
sudo cp /etc/uptime-monitor/config.json "/backup/config.pre-update.$TS.json"
sudo cp /etc/systemd/system/uptime-monitor.service "/backup/uptime-monitor.service.pre-update.$TS" 2>/dev/null || true
```

---

## 4) Зупинити сервіс перед оновленням

```bash
sudo systemctl stop $SERVICE
sudo systemctl is-active $SERVICE || true
```

---

## 5) Оновити код

### Варіант A: Git-інсталяція (є `.git`)

```bash
cd /opt/uptime-monitor
if [ -d .git ]; then
  sudo git fetch --all --prune
  sudo git checkout main
  sudo git pull --ff-only origin main
else
  echo "No .git found. Use ZIP flow."
fi
```

### Варіант B: ZIP-інсталяція (немає `.git`)

```bash
# Перевірити/встановити unzip (якщо немає)
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

## 6) Запустити сервіс після оновлення

```bash
sudo systemctl daemon-reload
sudo systemctl start $SERVICE
sleep 3
sudo systemctl status $SERVICE --no-pager
```

---

## 7) Перевірка після оновлення (обов’язково)

```bash
sudo journalctl -u $SERVICE -n 100 --no-pager
curl -fsS http://localhost:8080 >/dev/null && echo "HTTP OK" || echo "HTTP FAIL"
```

> Якщо порт не `8080`, використай свій порт з `config.json`.

---

## 8) Rollback, якщо щось не так

### Швидкий rollback з останнього backup

```bash
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto --force
```

### Rollback з конкретного backup

```bash
sudo /opt/uptime-monitor/scripts/restore-system.sh \
  --from /backup/uptime-monitor/on-change/backup-YYYYMMDD-HHMMSS.tar.gz \
  --force
```

Після rollback перевірити:

```bash
sudo systemctl status uptime-monitor --no-pager
sudo journalctl -u uptime-monitor -n 100 --no-pager
```

---

## 9) Повний runbook одним блоком (copy/paste)

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
sudo journalctl -u $SERVICE -n 50 --no-pager

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
sudo journalctl -u $SERVICE -n 100 --no-pager
curl -fsS http://localhost:8080 >/dev/null && echo "HTTP OK" || echo "HTTP FAIL"
```

---

## 🧭 Best Practices

- Завжди роби backup **до** апдейту.
- На критичних змінах завжди використовуй `--verify`.
- Тримай backup і локально, і на мережевому сховищі (NFS/SMB), якщо можливо.
- Перевіряй не тільки `systemctl status`, а і реальну доступність HTTP.
- Зберігай `config.pre-update.*` для швидкого порівняння налаштувань після апдейту.