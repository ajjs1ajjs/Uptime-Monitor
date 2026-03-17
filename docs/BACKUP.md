# 💾 Посібник із системи резервного копіювання

Повна інструкція по системі резервного копіювання

---

## 📋 Зміст

1. [Швидкий старт](#швидкий-старт)
2. [Що бекапиться](#що-бекапиться)
3. [Типи бекапів](#типи-бекапів)
4. [Створення бекапу](#створення-бекапу)
5. [Автоматичні бекапи](#автоматичні-бекапи)
6. [NFS бекап](#nfs-бекап)
7. [Samba бекап](#samba-бекап)
8. [Відновлення](#відновлення)
9. [Ротація](#ротація)
10. [Перевірка](#перевірка)

---

## Швидкий старт

```bash
# 1. Створити бекап
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/

# 2. Перевірити статус
sudo /opt/uptime-monitor/scripts/backup-system.sh --status

# 3. Відновити
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto
```

---

## Що бекапиться

| Компонент | Опис | Розмір |
|-----------|------|--------|
| **Database** | SQLite база з усіма сайтами та історією | ~1-10 MB |
| **Config** | config.json та історія змін | ~10-50 KB |
| **SSL** | Сертифікати та ключі | ~10 KB |
| **Logs** | Логи за останні 7 днів | ~1-100 MB |
| **Service** | Файл systemd служби | ~1 KB |

---

## Типи бекапів

| Тип | Коли | Зберігання | Призначення |
|-----|------|------------|-------------|
| `on-change` | Після зміни конфігурації | 10 штук | Захист від помилок |
| `daily` | Щодня о 2:00 | 7 днів | Щоденний захист |
| `weekly` | Щонеділі о 3:00 | Всі | Довгостроковий захист |
| `monthly` | 1-го числа о 4:00 | Всі | Архів |
| `yearly` | 1 січня о 5:00 | Назавжди | Річний архів |

---

## Створення бекапу

### Базовий бекап

```bash
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/
```

### Бекап з коментарем

```bash
sudo /opt/uptime-monitor/scripts/backup-system.sh \
    --dest /backup/uptime-monitor/ \
    --type on-change \
    --comment "Перед зміною SSL"
```

### Бекап з перевіркою

```bash
sudo /opt/uptime-monitor/scripts/backup-system.sh \
    --dest /backup/uptime-monitor/ \
    --verify
```

### Статус бекапів

```bash
sudo /opt/uptime-monitor/scripts/backup-system.sh --status
```

Виведе:
- Розмір бекапів
- Кількість бекапів
- Найновіший бекап
- Статус NFS/Samba

---

## Автоматичні бекапи

### Встановлення розкладу

```bash
# Тільки щоденні
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install \
    --daily "0 2 * * *" \
    --dest /backup/uptime-monitor/

# Повний розклад
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install \
    --daily "0 2 * * *" \
    --weekly "0 3 * * 0" \
    --monthly "0 4 1 * *" \
    --dest /backup/uptime-monitor/
```

### Перевірка розкладу

```bash
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --status
```

### Тестування

```bash
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --test
```

### Видалення розкладу

```bash
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --remove
```

---

## Резервне копіювання NFS

### 1. Встановлення клієнта

```bash
sudo apt-get update
sudo apt-get install -y nfs-common
```

### 2. Перевірка сервера

```bash
showmount -e 192.168.1.10
```

### 3. Монтування

```bash
sudo /opt/uptime-monitor/scripts/mount-backup.sh \
    --type nfs \
    --server 192.168.1.10 \
    --path /exports/backups \
    --mount-point /mnt/nfs-backup \
    --persist
```

### 4. Тестування

```bash
sudo /opt/uptime-monitor/scripts/backup-system.sh \
    --dest /mnt/nfs-backup/uptime-monitor/ \
    --type on-change \
    --comment "NFS test"
```

### 5. Автоматичні бекапи на NFS

```bash
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install \
    --daily "0 2 * * *" \
    --dest /mnt/nfs-backup/uptime-monitor/
```

### Розмонтування

```bash
sudo /opt/uptime-monitor/scripts/mount-backup.sh \
    --unmount \
    --mount-point /mnt/nfs-backup
```

---

## Резервне копіювання Samba

### 1. Встановлення клієнта

```bash
sudo apt-get update
sudo apt-get install -y cifs-utils
```

### 2. Створення credentials

```bash
sudo mkdir -p /root/.backup-creds
sudo tee /root/.backup-creds/smb-credentials << EOF
username=backupuser
password=yourpassword
domain=WORKGROUP
EOF
sudo chmod 600 /root/.backup-creds/smb-credentials
```

### 3. Монтування

```bash
sudo /opt/uptime-monitor/scripts/mount-backup.sh \
    --type smb \
    --server 192.168.1.11 \
    --share backups \
    --mount-point /mnt/smb-backup \
    --credentials /root/.backup-creds/smb-credentials \
    --persist
```

### 4. Тестування

```bash
sudo /opt/uptime-monitor/scripts/backup-system.sh \
    --dest /mnt/smb-backup/uptime-monitor/ \
    --type on-change \
    --comment "Samba test"
```

### 5. Автоматичні бекапи на Samba

```bash
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install \
    --daily "0 2 * * *" \
    --dest /mnt/smb-backup/uptime-monitor/
```

### Розмонтування

```bash
sudo /opt/uptime-monitor/scripts/mount-backup.sh \
    --unmount \
    --mount-point /mnt/smb-backup
```

---

## Відновлення

### Список бекапів

```bash
sudo /opt/uptime-monitor/scripts/restore-system.sh --list
```

### Відновлення з останнього

```bash
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto
```

### Відновлення з конкретного

```bash
sudo /opt/uptime-monitor/scripts/restore-system.sh \
    --from /backup/uptime-monitor/daily/backup-20260218-020000.tar.gz
```

### Часткове відновлення

```bash
# Тільки база даних
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto --only database

# Тільки конфігурація
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto --only config

# Тільки SSL
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto --only ssl
```

### Тестовий запуск

```bash
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto --dry-run
```

### Після відновлення

1. Перевірте статус: `sudo systemctl status uptime-monitor`
2. Перевірте логи: `sudo journalctl -u uptime-monitor -n 50`
3. Перевірте доступність: `curl http://localhost:8080`

---

## Ротація

### Перевірка перед видаленням

```bash
sudo /opt/uptime-monitor/scripts/backup-rotation.sh --dry-run
```

### Виконання ротації

```bash
sudo /opt/uptime-monitor/scripts/backup-rotation.sh
```

### Залишити тільки N бекапів

```bash
sudo /opt/uptime-monitor/scripts/backup-rotation.sh --keep 5
```

### Ручне видалення

```bash
# Переглянути розміри
sudo du -sh /backup/uptime-monitor/*/*

# Видалити старі
sudo find /backup/uptime-monitor/daily -name "backup-*.tar.gz" -mtime +7 -delete
```

---

## Перевірка

### Перевірка конкретного бекапу

```bash
sudo /opt/uptime-monitor/scripts/verify-backup.sh \
    /backup/uptime-monitor/daily/backup-20260218-020000.tar.gz
```

### Перевірка всіх бекапів

```bash
sudo /opt/uptime-monitor/scripts/verify-backup.sh --all
```

### Статистика

```bash
sudo /opt/uptime-monitor/scripts/verify-backup.sh --list
```

---

## Структура бекапу

```
backup-YYYYMMDDHHMMSS.tar.gz
├── database/
│   └── sites.db              # SQLite база
├── config/
│   ├── config.json           # Конфігурація
│   └── config.backups/       # Історія змін
├── ssl/
│   ├── cert.pem              # SSL сертифікат
│   └── key.pem               # Приватний ключ
├── logs/                     # Логи (7 днів)
├── systemd/
│   └── uptime-monitor.service # Служба
├── metadata.json             # Інформація про бекап
└── restore.sh                # Скрипт відновлення
```

---

## Налаштування в config.json

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

---

## Проблеми та рішення

### Бекап не створюється

**Перевірка:**
```bash
# Перевірити права
sudo ls -la /backup/

# Виправити
sudo mkdir -p /backup/uptime-monitor
sudo chown root:root /backup/uptime-monitor
sudo chmod 755 /backup/uptime-monitor
```

### NFS не монтується

**Перевірка:**
```bash
# Перевірити доступність
ping 192.168.1.10
showmount -e 192.168.1.10

# Ручне монтування
sudo mount -t nfs 192.168.1.10:/exports/backups /mnt/nfs-backup
```

### Немає місця на диску

**Рішення:**
```bash
# Перевірити місце
df -h

# Очистити старі бекапи
sudo /opt/uptime-monitor/scripts/backup-rotation.sh --keep 3

# Перенести на NFS
sudo /opt/uptime-monitor/scripts/mount-backup.sh ...
```
