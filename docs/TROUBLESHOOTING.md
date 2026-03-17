# 🛠️ Посібник з усунення несправностей

Вирішення проблем з Uptime Monitor

---

## 📋 Зміст

1. [Служба не запускається](#служба-не-запускається)
2. [Проблеми з бекапом](#проблеми-з-бекапом)
3. [NFS проблеми](#nfs-проблеми)
4. [Samba проблеми](#samba-проблеми)
5. [Відновлення не працює](#відновлення-не-працює)
6. [SSL проблеми](#ssl-проблеми)
7. [Конфігурація](#конфігурація)
8. [Мережа](#мережа)

---

## Служба не запускається

### Перевірка статусу

```bash
sudo systemctl status uptime-monitor
```

### Перегляд логів

```bash
# Останні помилки
sudo journalctl -u uptime-monitor -n 50

# Логи в реальному часі
sudo journalctl -u uptime-monitor -f

# Логи з часом
sudo journalctl -u uptime-monitor --since "1 hour ago"
```

### Перевірка прав

```bash
# Перевірити власника файлів
ls -la /opt/uptime-monitor/
ls -la /etc/uptime-monitor/
ls -la /var/lib/uptime-monitor/

# Виправити права
sudo chown -R uptime-monitor:uptime-monitor /opt/uptime-monitor/
sudo chown -R uptime-monitor:uptime-monitor /var/lib/uptime-monitor/
sudo chown -R root:root /etc/uptime-monitor/
sudo chmod 600 /etc/uptime-monitor/config.json
```

### Помилка Permission denied на uptime_monitor.log

```bash
# Створити файл і виправити права
sudo touch /opt/uptime-monitor/uptime_monitor.log
sudo chown uptime-monitor:uptime-monitor /opt/uptime-monitor/uptime_monitor.log

# Перезапустити
sudo systemctl restart uptime-monitor
```

### Перевірка Python

```bash
# Версія Python
python3 --version

# Перевірити venv
ls -la /opt/uptime-monitor/venv/

# Перевстановити venv (якщо пошкоджено)
cd /opt/uptime-monitor
sudo rm -rf venv
sudo python3 -m venv venv
sudo ./venv/bin/pip install -r requirements.txt
```

### Порт зайнятий

```bash
# Знайти процес
sudo lsof -i :8080
sudo netstat -tulpn | grep :8080

# Зупинити процес
sudo kill -9 <PID>

# Або змінити порт
sudo nano /etc/uptime-monitor/config.json
# Змінити: "server.port": 9090
sudo systemctl restart uptime-monitor
```

---

## Проблеми з бекапом

### Бекап не створюється (Permission denied)

**Симптом:**
```
Error: Cannot create backup
Permission denied
```

**Рішення:**
```bash
# Перевірити права
sudo ls -la /backup/

# Створити директорію
sudo mkdir -p /backup/uptime-monitor

# Виправити права
sudo chown -R root:root /backup/uptime-monitor/
sudo chmod 755 /backup/uptime-monitor/

# Перевірити ще раз
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/
```

### Немає місця на диску

**Симптом:**
```
No space left on device
```

**Рішення:**
```bash
# Перевірити місце
df -h

# Розмір бекапів
sudo du -sh /backup/uptime-monitor/*

# Видалити старі бекапи
sudo /opt/uptime-monitor/scripts/backup-rotation.sh --keep 3

# Або перенести на зовнішній диск/NFS
sudo /opt/uptime-monitor/scripts/mount-backup.sh --type nfs ...
```

### Автоматичні бекапи не запускаються

**Симптом:**
Бекапи не створюються за розкладом

**Рішення:**
```bash
# Перевірити cron
sudo systemctl status cron

# Перевірити cron jobs
sudo cat /etc/cron.d/uptime-monitor-backup

# Перевірити логи cron
sudo grep CRON /var/log/syslog | tail -20

# Перевірити чи встановлено
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --status

# Перевстановити
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --remove
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install --dest /backup/uptime-monitor/

# Тест
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --test
```

---

## Проблеми з NFS

### NFS не монтується

**Симптом:**
```
mount.nfs: Connection refused
```

**Рішення:**
```bash
# Встановити клієнт
sudo apt-get update
sudo apt-get install -y nfs-common

# Перевірити доступність сервера
ping 192.168.1.10
showmount -e 192.168.1.10

# Перевірити firewall
sudo ufw status
sudo iptables -L | grep 2049

# Ручне монтування для тесту
sudo mkdir -p /mnt/test-nfs
sudo mount -t nfs -o vers=4 192.168.1.10:/exports/backups /mnt/test-nfs

# Якщо vers=4 не працює, спробувати vers=3
sudo mount -t nfs -o vers=3 192.168.1.10:/exports/backups /mnt/test-nfs

# Перевірити
mount | grep nfs
df -h | grep nfs
```

### NFS відмонтовується

**Симптом:**
NFS відключається після перезавантаження

**Рішення:**
```bash
# Перевірити fstab
cat /etc/fstab | grep nfs

# Додати _netdev для автомонтування
echo "192.168.1.10:/exports/backups /mnt/nfs-backup nfs vers=4,_netdev 0 0" | sudo tee -a /etc/fstab

# Перевірити
sudo mount -a
```

### Повільна робота NFS

**Рішення:**
```bash
# Додати опції продуктивності
sudo mount -t nfs -o vers=4,soft,intr,rsize=8192,wsize=8192 192.168.1.10:/exports/backups /mnt/nfs-backup
```

---

## Проблеми з Samba

### Samba не монтується

**Симптом:**
```
mount error(13): Permission denied
```

**Рішення:**
```bash
# Встановити клієнт
sudo apt-get update
sudo apt-get install -y cifs-utils

# Створити credentials файл
sudo mkdir -p /root/.backup-creds
sudo tee /root/.backup-creds/smb-credentials << EOF
username=backupuser
password=yourpassword
domain=WORKGROUP
EOF
sudo chmod 600 /root/.backup-creds/smb-credentials

# Тест ручного монтування
sudo mkdir -p /mnt/test-smb
sudo mount -t cifs //192.168.1.11/backups /mnt/test-smb \
    -o credentials=/root/.backup-creds/smb-credentials

# Перевірити
mount | grep cifs
df -h | grep cifs
```

### Неправильні символи в іменах файлів

**Рішення:**
```bash
# Додати iocharset
sudo mount -t cifs //192.168.1.11/backups /mnt/smb-backup \
    -o credentials=/root/.backup-creds/smb-credentials,iocharset=utf8
```

---

## Відновлення не працює

### Бекап пошкоджений

**Симптом:**
```
Error: Backup verification failed
```

**Рішення:**
```bash
# Перевірити цілісність
tar -tzf /path/to/backup.tar.gz > /dev/null

# Спробувати відновити з іншого бекапу
sudo /opt/uptime-monitor/scripts/restore-system.sh --list
sudo /opt/uptime-monitor/scripts/restore-system.sh --from /backup/uptime-monitor/daily/backup-OLDER.tar.gz
```

### Служба не запускається після відновлення

**Симптом:**
Відновлення успішне, але служба не стартує

**Рішення:**
```bash
# Перевірити статус
sudo systemctl status uptime-monitor

# Перевірити логи
sudo journalctl -u uptime-monitor -n 50

# Перевірити права
sudo ls -la /opt/uptime-monitor/
sudo ls -la /etc/uptime-monitor/

# Виправити права
sudo chown -R uptime-monitor:uptime-monitor /opt/uptime-monitor/
sudo chmod 644 /opt/uptime-monitor/sites.db

# Перезапустити
sudo systemctl restart uptime-monitor

# Якщо не допомогло - відновити з safety backup
ls -la /tmp/uptime-pre-restore-*/
sudo cp -r /tmp/uptime-pre-restore-*/sites.db /opt/uptime-monitor/
sudo systemctl restart uptime-monitor
```

---

## SSL проблеми

### Сертифікат не працює

**Симптом:**
Браузер показує помилку сертифікату

**Рішення:**
```bash
# Перевірити сертифікати
sudo ls -la /etc/uptime-monitor/ssl/

# Перевірити права
sudo chmod 600 /etc/uptime-monitor/ssl/*.pem

# Перевірити вміст
openssl x509 -in /etc/uptime-monitor/ssl/cert.pem -text -noout

# Перевірити чи підходить ключ до сертифіката
openssl x509 -noout -modulus -in /etc/uptime-monitor/ssl/cert.pem | openssl md5
openssl rsa -noout -modulus -in /etc/uptime-monitor/ssl/key.pem | openssl md5

# Мають бути однакові!
```

### Самопідписаний сертифікат

**Створення:**
```bash
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/uptime-monitor/ssl/key.pem \
    -out /etc/uptime-monitor/ssl/cert.pem \
    -subj "/CN=localhost"

sudo chmod 600 /etc/uptime-monitor/ssl/*.pem
sudo systemctl restart uptime-monitor
```

---

## Конфігурація

### JSON помилка

**Симптом:**
```
Error: Invalid JSON
```

**Рішення:**
```bash
# Перевірити синтаксис
python3 -m json.tool /etc/uptime-monitor/config.json

# Якщо помилка - відкат до попередньої версії
sudo /opt/uptime-monitor/scripts/config-rollback.sh --previous

# Або виправити вручну
sudo nano /etc/uptime-monitor/config.json
# Виправити помилку (зазвичай зайва кома або дужка)
```

### Неправильний порт

**Симптом:**
```
Address already in use
```

**Рішення:**
```bash
# Знайти зайнятий порт
sudo lsof -i :8080

# Змінити порт
sudo nano /etc/uptime-monitor/config.json
# Змінити: "server.port": 9090

# Перезапустити
sudo systemctl restart uptime-monitor

# Оновити firewall
sudo ufw allow 9090/tcp
```

---

## Мережа

### Немає доступу до веб-інтерфейсу

**Перевірка:**
```bash
# Перевірити чи слухає порт
sudo netstat -tulpn | grep 8080
sudo ss -tulpn | grep 8080

# Перевірити локально
curl http://localhost:8080

# Перевірити ззовні (з іншої машини)
curl http://$(hostname -I | awk '{print $1}'):8080

# Перевірити firewall
sudo ufw status
sudo iptables -L | grep 8080

# Відкрити порт
sudo ufw allow 8080/tcp
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload
```

### Немає доступу з інтернету

**Перевірка:**
```bash
# Перевірити IP
hostname -I

# Перевірити роутер/NAT
# Треба налаштувати port forwarding на роутері

# Перевірити зовнішній доступ
curl http://ifconfig.me
```

---

## Загальні команди діагностики

```bash
# Повна інформація про систему
sudo systemctl status uptime-monitor
sudo journalctl -u uptime-monitor --no-pager -n 100

# Перевірка файлів
sudo ls -laR /opt/uptime-monitor/
sudo ls -laR /etc/uptime-monitor/
sudo ls -laR /var/lib/uptime-monitor/

# Перевірка процесів
ps aux | grep uptime
sudo lsof -p $(pgrep -f "uptime-monitor")

# Перевірка мережі
sudo netstat -tulpn | grep uptime
sudo ss -tulpn | grep uptime

# Перевірка диска
df -h
du -sh /opt/uptime-monitor/
du -sh /var/lib/uptime-monitor/
du -sh /backup/uptime-monitor/ 2>/dev/null

# Перевірка пам'яті
free -h
top -p $(pgrep -f "uptime-monitor")
```

---

## Контакти та підтримка

Якщо проблема не вирішена:

1. Перевірте [INSTALL.md](../INSTALL.md)
2. Перевірте [COMMANDS.md](COMMANDS.md)
3. Перевірте [BACKUP.md](BACKUP.md)
4. Створіть issue на GitHub

**Корисні посилання:**
- Веб-інтерфейс: `http://$(hostname -I | awk '{print $1}'):8080`
- Логи: `sudo journalctl -u uptime-monitor -f`
- Конфіг: `sudo nano /etc/uptime-monitor/config.json`
