# 🚀 Міграція Uptime Monitor в хмару (AWS/Azure)

**Повний посібник** з перенесення налаштувань та даних на новий сервер.

---

## 📋 Зміст

1. [Швидка міграція (3 кроки)](#швидка-міграція-3-кроки)
2. [Підготовка старого сервера](#підготовка-старого-сервера)
3. [Міграція на AWS EC2](#міграція-на-aws-ec2)
4. [Міграція на Azure VM](#міграція-на-azure-vm)
5. [Якщо немає SSH доступу](#якщо-немає-ssh-доступу)
6. [Автоматична міграція (скрипти)](#автоматична-міграція-скрипти)
7. [Перевірка після міграції](#перевірка-після-міграції)
8. [Поширені проблеми](#поширені-проблеми)

---

## 🎯 Швидка міграція (3 кроки)

### **Крок 1: Встановіть на новому сервері**

```bash
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor-APP/main/install.sh | sudo bash
```

### **Крок 2: Скопіюйте 3 файли**

```bash
# З нового сервера (замініть OLD_SERVER_IP на ваш старий IP)
scp user@OLD_SERVER_IP:/var/lib/uptime-monitor/sites.db /var/lib/uptime-monitor/
scp user@OLD_SERVER_IP:/etc/uptime-monitor/config.json /etc/uptime-monitor/
scp user@OLD_SERVER_IP:/opt/uptime-monitor/.env /opt/uptime-monitor/
```

### **Крок 3: Перезапустіть**

```bash
sudo systemctl restart uptime-monitor
```

**✅ Все!** Відкрийте `http://ВАШ_IP:8080`

---

## 📦 Підготовка старого сервера

### **Що потрібно скопіювати:**

| Файл | Шлях | Навіщо |
|------|------|--------|
| **sites.db** | `/var/lib/uptime-monitor/sites.db` | ВСІ сайти, історія, користувачі |
| **config.json** | `/etc/uptime-monitor/config.json` | Порт, SSL, сповіщення |
| **.env** | `/opt/uptime-monitor/.env` | Паролі, API ключі |
| **ssl/** | `/etc/uptime-monitor/ssl/` | HTTPS сертифікати (опціонально) |

### **Створіть бекап (рекомендовано):**

```bash
# На старому сервері
sudo tar -czvf /tmp/uptime-backup.tar.gz \
    /var/lib/uptime-monitor/sites.db \
    /etc/uptime-monitor/config.json \
    /opt/uptime-monitor/.env \
    /etc/uptime-monitor/ssl/

# Завантажте на комп'ютер
scp user@OLD_SERVER_IP:/tmp/uptime-backup.tar.gz ~/
```

---

## ☁️ Міграція на AWS EC2

### **Крок 1: Створіть EC2 інстанс**

1. Відкрийте [AWS Console](https://console.aws.amazon.com/ec2/)
2. **Launch Instance**
3. Оберіть:
   - **Name**: `uptime-monitor`
   - **AMI**: Ubuntu Server 22.04 LTS
   - **Instance type**: `t2.micro` (Free Tier)
   - **Key pair**: Створіть або оберіть існуючий
4. **Network settings**:
   - ☑️ Allow SSH traffic
   - ☑️ Allow HTTP/HTTPS traffic from internet
5. **Launch instance**

### **Крок 2: Дозвольте порт 8080**

1. У консолі EC2 оберіть ваш інстанс
2. Знизу: **Security** → **Security groups** → клік на ID
3. **Edit inbound rules** → **Add rule**:
   - **Type**: Custom TCP
   - **Port**: `8080`
   - **Source**: Anywhere (0.0.0.0/0)
4. **Save rules**

### **Крок 3: Підключіться та встановіть**

```bash
# Підключіться до EC2
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# Встановіть Uptime Monitor
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor-APP/main/install.sh | sudo bash
```

### **Крок 4: Скопіюйте дані**

```bash
# З EC2 інстанса (замініть OLD_SERVER_IP)
scp ubuntu@OLD_SERVER_IP:/var/lib/uptime-monitor/sites.db /var/lib/uptime-monitor/
scp ubuntu@OLD_SERVER_IP:/etc/uptime-monitor/config.json /etc/uptime-monitor/
scp ubuntu@OLD_SERVER_IP:/opt/uptime-monitor/.env /opt/uptime-monitor/

# Перезапустіть
sudo systemctl restart uptime-monitor
```

### **Крок 5: Відкрийте веб-інтерфейс**

```bash
# Дізнайтесь IP
hostname -I | awk '{print $1}'

# Відкрийте в браузері: http://YOUR_EC2_IP:8080
```

---

## ☁️ Міграція на Azure VM

### **Крок 1: Створіть Azure VM**

```bash
# Через Azure CLI (або створіть в консолі)
az vm create \
  --resource-group uptime-rg \
  --name uptime-monitor \
  --image Ubuntu2204 \
  --size Standard_B1s \
  --admin-username azureuser \
  --generate-ssh-keys \
  --location eastus
```

### **Крок 2: Дозвольте порт 8080**

```bash
az vm open-port \
  --resource-group uptime-rg \
  --name uptime-monitor \
  --port 8080
```

### **Крок 3: Підключіться та встановіть**

```bash
# Підключіться
ssh azureuser@YOUR_AZURE_IP

# Встановіть
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor-APP/main/install.sh | sudo bash
```

### **Крок 4: Скопіюйте дані**

```bash
scp azureuser@OLD_SERVER_IP:/var/lib/uptime-monitor/sites.db /var/lib/uptime-monitor/
scp azureuser@OLD_SERVER_IP:/etc/uptime-monitor/config.json /etc/uptime-monitor/
scp azureuser@OLD_SERVER_IP:/opt/uptime-monitor/.env /opt/uptime-monitor/

sudo systemctl restart uptime-monitor
```

---

## 🔐 Якщо немає SSH доступу до старого сервера

### **Варіант 1: Через бекап-файл**

```bash
# 1. На старому сервері створіть бекап
sudo tar -czvf /tmp/uptime-backup.tar.gz \
    /var/lib/uptime-monitor/sites.db \
    /etc/uptime-monitor/config.json \
    /opt/uptime-monitor/.env

# 2. Завантажте файл на комп'ютер
# (через FTP/SFTP або консоль хостингу)

# 3. Завантажте на новий сервер
scp /tmp/uptime-backup.tar.gz user@NEW_SERVER_IP:/tmp/

# 4. На новому сервері розпакуйте
ssh user@NEW_SERVER_IP
sudo tar -xzvf /tmp/uptime-backup.tar.gz -C /
sudo systemctl restart uptime-monitor
```

### **Варіант 2: Через панель керування (cPanel/Plesk)**

1. Відкрийте **File Manager**
2. Перейдіть до:
   - `/var/lib/uptime-monitor/sites.db`
   - `/etc/uptime-monitor/config.json`
   - `/opt/uptime-monitor/.env`
3. Завантажте файли на комп'ютер
4. Завантажте на новий сервер через SFTP (FileZilla/WinSCP)

### **Варіант 3: Через базу даних (якщо SQLite)**

```bash
# Експорт даних
sqlite3 /var/lib/uptime-monitor/sites.db ".dump" > sites-dump.sql

# На новому сервері імпорт
sqlite3 /var/lib/uptime-monitor/sites.db < sites-dump.sql
```

---

## 🤖 Автоматична міграція (скрипти)

### **Універсальний скрипт міграції**

Створіть файл `migrate.sh` на новому сервері:

```bash
#!/bin/bash
set -e

# ============================================
# Uptime Monitor Migration Script
# ============================================

OLD_SERVER_IP="${1:-}"
OLD_SERVER_USER="${2:-ubuntu}"

if [ -z "$OLD_SERVER_IP" ]; then
    echo "Використання: $0 <OLD_SERVER_IP> [OLD_SERVER_USER]"
    echo "Приклад: $0 192.168.1.100 ubuntu"
    exit 1
fi

echo "🚀 Міграція Uptime Monitor"
echo "=========================="
echo "Старий сервер: $OLD_SERVER_IP"
echo "Користувач: $OLD_SERVER_USER"
echo ""

# 1. Встановлення
echo "📦 Встановлення..."
if [ ! -d "/opt/uptime-monitor" ]; then
    curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor-APP/main/install.sh | sudo bash
else
    echo "✅ Вже встановлено"
fi

# 2. Зупинка служби
echo "⏹️  Зупинка служби..."
sudo systemctl stop uptime-monitor

# 3. Копіювання даних
echo "📥 Копіювання даних..."
mkdir -p /tmp/uptime-migration

scp -o StrictHostKeyChecking=no ${OLD_SERVER_USER}@${OLD_SERVER_IP}:/var/lib/uptime-monitor/sites.db /tmp/uptime-migration/ || echo "⚠️  Не вдалось скопіювати sites.db"
scp -o StrictHostKeyChecking=no ${OLD_SERVER_USER}@${OLD_SERVER_IP}:/etc/uptime-monitor/config.json /tmp/uptime-migration/ || echo "⚠️  Не вдалось скопіювати config.json"
scp -o StrictHostKeyChecking=no ${OLD_SERVER_USER}@${OLD_SERVER_IP}:/opt/uptime-monitor/.env /tmp/uptime-migration/ || echo "⚠️  Не вдалось скопіювати .env"
scp -o StrictHostKeyChecking=no -r ${OLD_SERVER_USER}@${OLD_SERVER_IP}:/etc/uptime-monitor/ssl/ /tmp/uptime-migration/ 2>/dev/null || echo "⚠️  SSL не знайдено"

# 4. Відновлення
echo "🔄 Відновлення даних..."
if [ -f "/tmp/uptime-migration/sites.db" ]; then
    sudo cp /tmp/uptime-migration/sites.db /var/lib/uptime-monitor/
    sudo cp /tmp/uptime-migration/config.json /etc/uptime-monitor/
    sudo cp /tmp/uptime-migration/.env /opt/uptime-monitor/
    
    if [ -d "/tmp/uptime-migration/ssl" ]; then
        sudo mkdir -p /etc/uptime-monitor/ssl
        sudo cp -r /tmp/uptime-migration/ssl/* /etc/uptime-monitor/ssl/
    fi
    
    sudo chown -R uptime-monitor:uptime-monitor /var/lib/uptime-monitor/sites.db
    sudo chown -R uptime-monitor:uptime-monitor /etc/uptime-monitor/config.json
    sudo chown -R uptime-monitor:uptime-monitor /opt/uptime-monitor/.env
    
    echo "✅ Дані відновлено"
else
    echo "❌ Файли не знайдено"
    exit 1
fi

# 5. Запуск
echo "▶️  Запуск служби..."
sudo systemctl start uptime-monitor
sudo systemctl enable uptime-monitor

# 6. Перевірка
echo "✅ Перевірка..."
sleep 3
sudo systemctl status uptime-monitor --no-pager -n 5

# 7. IP адреса
PUBLIC_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "=================================="
echo "✅ МІГРАЦІЯ ЗАВЕРШЕНА!"
echo "=================================="
echo ""
echo "🌐 Веб-інтерфейс: http://${PUBLIC_IP}:8080"
echo ""
echo "📝 Наступні кроки:"
echo "   1. Відкрийте http://${PUBLIC_IP}:8080"
echo "   2. Увійдіть (admin/admin або ваші дані)"
echo "   3. Перевірте сайти та сповіщення"
echo ""

# Очищення
rm -rf /tmp/uptime-migration
```

### **Використання скрипта:**

```bash
# Завантажте скрипт на новий сервер
scp migrate.sh user@NEW_SERVER_IP:/home/user/

# Підключіться
ssh user@NEW_SERVER_IP

# Запустіть (вкажіть старий IP та користувача)
chmod +x migrate.sh
./migrate.sh 192.168.1.100 ubuntu
```

---

## ✅ Перевірка після міграції

### **1. Перевірте службу:**

```bash
sudo systemctl status uptime-monitor
```

**Має бути:**
```
● uptime-monitor.service - Uptime Monitor Service
   Active: active (running)
```

### **2. Перевірте порт:**

```bash
sudo netstat -tlnp | grep 8080
```

**Має бути:**
```
tcp6  0  0 :::8080  :::*  LISTEN  1234/python3
```

### **3. Перевірте базу даних:**

```bash
# Кількість сайтів
sqlite3 /var/lib/uptime-monitor/sites.db "SELECT COUNT(*) FROM sites;"

# Список сайтів
sqlite3 /var/lib/uptime-monitor/sites.db "SELECT name, url FROM sites;"
```

### **4. Перевірте логи:**

```bash
sudo journalctl -u uptime-monitor -n 20
```

### **5. Відкрийте веб-інтерфейс:**

```bash
# Дізнайтесь IP
hostname -I | awk '{print $1}'

# Відкрийте в браузері: http://IP:8080
```

---

## ❌ Поширені проблеми

### **1. Помилка: "Permission denied" при копіюванні**

**Рішення:**
```bash
# На старому сервері дайте права
sudo chmod 644 /var/lib/uptime-monitor/sites.db
sudo chmod 644 /etc/uptime-monitor/config.json
sudo chmod 644 /opt/uptime-monitor/.env

# Або копіюйте через sudo
sudo scp user@OLD_IP:/var/lib/uptime-monitor/sites.db /var/lib/uptime-monitor/
```

### **2. Служба не запускається**

**Рішення:**
```bash
# Перевірте логи
sudo journalctl -u uptime-monitor -f

# Перевірте права
sudo chown -R uptime-monitor:uptime-monitor /var/lib/uptime-monitor/sites.db
sudo chown -R uptime-monitor:uptime-monitor /etc/uptime-monitor/config.json

# Перезапустіть
sudo systemctl restart uptime-monitor
```

### **3. Порт 8080 не доступний**

**Рішення:**

**AWS:**
- Security Groups → Add rule → Port 8080

**Azure:**
```bash
az vm open-port --resource-group uptime-rg --name uptime-monitor --port 8080
```

### **4. Веб-інтерфейс не відкривається**

**Рішення:**
```bash
# Перевірте firewall
sudo ufw status
sudo ufw allow 8080/tcp

# Перевірте службу
sudo systemctl status uptime-monitor

# Перевірте порт
sudo netstat -tlnp | grep 8080
```

### **5. Немає даних після міграції**

**Рішення:**
```bash
# Перевірте що файли скопіювались
ls -la /var/lib/uptime-monitor/sites.db
ls -la /etc/uptime-monitor/config.json

# Перевірте розмір (не має бути 0)
du -h /var/lib/uptime-monitor/sites.db

# Якщо файли порожні - скопіюйте ще раз
scp user@OLD_IP:/var/lib/uptime-monitor/sites.db /var/lib/uptime-monitor/
```

---

## 📊 Порівняння хмарних провайдерів

| Функція | AWS EC2 | Azure VM | DigitalOcean |
|---------|---------|----------|--------------|
| **Безкоштовний рівень** | 750 год/міс (t2.micro) | 750 год/міс (B1S) | Немає |
| **Мінімальна ціна** | $0 (Free Tier) | $0 (Free Tier) | $4/міс |
| **Порт за замовчуванням** | 8080 | 8080 | 8080 |
| **SSH ключ** | Обов'язково | Обов'язково | Обов'язково |
| **Security** | Security Groups | NSG | Firewall |

---

## 🎯 Шпаргалка команд

```bash
# Встановити
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor-APP/main/install.sh | sudo bash

# Зупинити службу
sudo systemctl stop uptime-monitor

# Скопіювати дані
scp user@OLD_IP:/var/lib/uptime-monitor/sites.db /var/lib/uptime-monitor/
scp user@OLD_IP:/etc/uptime-monitor/config.json /etc/uptime-monitor/
scp user@OLD_IP:/opt/uptime-monitor/.env /opt/uptime-monitor/

# Запустити службу
sudo systemctl start uptime-monitor

# Перевірити статус
sudo systemctl status uptime-monitor

# Подивитись логи
sudo journalctl -u uptime-monitor -f

# Дізнатись IP
hostname -I | awk '{print $1}'
```

---

## 📞 Підтримка

Якщо виникли проблеми:

1. Перевірте [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Перевірте логи: `sudo journalctl -u uptime-monitor -f`
3. Створіть issue на GitHub

---

**📅 Останнє оновлення:** Березень 2026  
**📝 Версія:** 1.0.0
