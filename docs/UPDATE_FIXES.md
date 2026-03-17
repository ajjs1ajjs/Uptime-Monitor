# 🔧 Виправлення поширених проблем при оновленні

## Проблема: `Permission denied` при розпакуванні/копіюванні

### Причина
Перший `unzip` виконано **без `sudo`**, тому файли створилися з правами користувача `sa`.  
Потім `sudo unzip` не може видалити/перезаписати ці файли.

### Рішення

```bash
# 1. Видалити стару папку З СУДОМ
sudo rm -rf /tmp/Uptime-Monitor-APP-main

# 2. Завантажити ZIP заново (якщо видалений)
cd /tmp
wget https://github.com/ajjs1ajjs/Uptime-Monitor-APP/archive/refs/heads/main.zip -O uptime_update.zip

# 3. Розпакувати З СУДОМ
sudo unzip -o uptime_update.zip

# 4. Скопіювати файли
sudo cp -r /tmp/Uptime-Monitor-APP-main/Uptime_Robot/* /opt/uptime-monitor/

# 5. Прибрати тимчасові файли З СУДОМ
sudo rm -rf uptime_update.zip /tmp/Uptime-Monitor-APP-main

# 6. Запустити службу
sudo systemctl start uptime-monitor

# 7. Перевірити
sudo systemctl status uptime-monitor
curl -fsS http://localhost:8080 && echo "HTTP OK" || echo "HTTP FAIL"
```

---

## Проблема: `Command 'unzip' not found`

### Причина
Скрипт оновлення через ZIP вимагає утиліту `unzip`, яка не встановлена за замовчуванням у деяких мінімальних інсталяціях Linux.

### Рішення

#### 1. Встановити unzip

```bash
sudo apt update
sudo apt install -y unzip
```

#### 2. Перевірити встановлення

```bash
unzip -v
```

Якщо побачили версію - все ок:
```
UnZip 6.00 of 20 April 2009, by Debian.
```

#### 3. Повторити оновлення

Тепер можна виконати оновлення:

```bash
cd /tmp
wget https://github.com/ajjs1ajjs/Uptime-Monitor-APP/archive/refs/heads/main.zip -O uptime_update.zip

# КРИТИЧНО: Використовуйте sudo для всіх операцій!
sudo rm -rf /tmp/Uptime-Monitor-APP-main
sudo unzip -o uptime_update.zip
sudo cp -r /tmp/Uptime-Monitor-APP-main/Uptime_Robot/* /opt/uptime-monitor/
sudo rm -rf uptime_update.zip /tmp/Uptime-Monitor-APP-main
sudo systemctl restart uptime-monitor
```

---

## 📋 Повне безпечне оновлення (з виправленням)

```bash
# 1. Встановити unzip (якщо немає)
sudo apt update && sudo apt install -y unzip

# 2. Зупинити службу
sudo systemctl stop uptime-monitor

# 3. ЗРОБИТИ БЕКАП (критично!)
sudo /opt/uptime-monitor/scripts/backup-system.sh \
    --dest /backup/uptime-monitor/ \
    --type on-change \
    --comment "pre-update-$(date +%Y%m%d-%H%M%S)" \
    --verify

# 4. Перевірити бекап
sudo /opt/uptime-monitor/scripts/backup-system.sh --status

# 5. Завантажити оновлення
cd /tmp
wget https://github.com/ajjs1ajjs/Uptime-Monitor-APP/archive/refs/heads/main.zip -O uptime_update.zip

# 6. Розпакувати З СУДОМ
sudo rm -rf /tmp/Uptime-Monitor-APP-main
sudo unzip -o uptime_update.zip

# 7. Скопіювати файли
sudo cp -r /tmp/Uptime-Monitor-APP-main/Uptime_Robot/* /opt/uptime-monitor/

# 8. Прибрати тимчасові файли З СУДОМ
sudo rm -rf uptime_update.zip /tmp/Uptime-Monitor-APP-main

# 9. Запустити службу
sudo systemctl daemon-reload
sudo systemctl start uptime-monitor
sleep 3

# 10. Перевірити
sudo systemctl status uptime-monitor
sudo journalctl -u uptime-monitor -n 30 --no-pager

# 11. Перевірити HTTP
curl -fsS http://localhost:8080 && echo "HTTP OK" || echo "HTTP FAIL"
```

---

## 🔄 Альтернатива: Оновлення через Git (не потребує unzip)

Якщо у вас встановлено через `git clone`:

```bash
cd /opt/uptime-monitor

# Перевірити чи є .git
if [ -d .git ]; then
    echo "Git installation detected"
    
    # Зупинити службу
    sudo systemctl stop uptime-monitor
    
    # Бекап
    sudo /opt/uptime-monitor/scripts/backup-system.sh \
        --dest /backup/uptime-monitor/ \
        --type on-change \
        --comment "pre-update-git"
    
    # Оновлення
    sudo git fetch --all --prune
    sudo git checkout main
    sudo git pull --ff-only origin main
    
    # Запустити
    sudo systemctl start uptime-monitor
    
    # Перевірка
    sudo systemctl status uptime-monitor
else
    echo "Not a git installation. Use ZIP method with unzip installed."
fi
```

---

## 🚀 Використання готових скриптів

### Безпечне оновлення (production)

```bash
# Завантажити скрипт
cd /tmp
wget https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor-APP/main/docs/UPDATE_SCRIPT_SAFE.sh

# Зробити виконуваним
chmod +x UPDATE_SCRIPT_SAFE.sh

# Запустити
sudo ./UPDATE_SCRIPT_SAFE.sh
```

### Швидке оновлення (test only!)

```bash
# Завантажити скрипт
cd /tmp
wget https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor-APP/main/docs/UPDATE_SCRIPT_FAST.sh

# Зробити виконуваним
chmod +x UPDATE_SCRIPT_FAST.sh

# Запустити (встановить unzip якщо треба)
sudo ./UPDATE_SCRIPT_FAST.sh
```

---

## ❌ Якщо оновлення не вдалося

### 1. Перевірити логи

```bash
sudo journalctl -u uptime-monitor -n 100 --no-pager
```

### 2. Перевірити статус

```bash
sudo systemctl status uptime-monitor --no-pager
```

### 3. Rollback до бекапу

```bash
# Список бекапів
sudo /opt/uptime-monitor/scripts/restore-system.sh --list

# Відновити з останнього
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto --force

# Або конкретний
sudo /opt/uptime-monitor/scripts/restore-system.sh \
    --from /backup/uptime-monitor/on-change/backup-YYYYMMDD-HHMMSS.tar.gz \
    --force
```

### 4. Перевірити після rollback

```bash
sudo systemctl status uptime-monitor
sudo journalctl -u uptime-monitor -n 50
```

---

## 📝 Контрольний список перед оновленням

- [ ] Перевірено вільне місце (`df -h`)
- [ ] Встановлено `unzip` (якщо потрібно)
- [ ] Зроблено бекап (`backup-system.sh`)
- [ ] Перевірено бекап (`backup-system.sh --status`)
- [ ] Заплановано даунтайм (якщо production)
- [ ] Є доступ до сервера (SSH/консоль)
- [ ] Записано IP/домен для перевірки після оновлення

---

## 🎯 Рекомендації

| Середовище | Метод | Примітки |
|------------|-------|----------|
| **Production** | `UPDATE_SCRIPT_SAFE.sh` | Завжди з бекапом |
| **Staging** | `UPDATE_SCRIPT_FAST.sh` | Можна без бекапу |
| **Development** | Git або ZIP | Як зручніше |
| **Git installation** | `git pull` | Найкращий варіант |
| **ZIP installation** | Встановити `unzip` + ZIP | Потребує unzip |

---

## 📞 Швидка допомога

```bash
# Все в одному (production):
sudo apt install -y unzip && \
sudo systemctl stop uptime-monitor && \
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/ --type on-change --verify && \
cd /tmp && \
sudo rm -rf /tmp/Uptime-Monitor-APP-main && \
wget -q https://github.com/ajjs1ajjs/Uptime-Monitor-APP/archive/refs/heads/main.zip -O uptime_update.zip && \
sudo unzip -o uptime_update.zip && \
sudo cp -r /tmp/Uptime-Monitor-APP-main/Uptime_Robot/* /opt/uptime-monitor/ && \
sudo rm -rf uptime_update.zip /tmp/Uptime-Monitor-APP-main && \
sudo systemctl start uptime-monitor && \
sudo systemctl status uptime-monitor
```
