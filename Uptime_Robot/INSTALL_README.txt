UPTIME MONITOR - ВСТАНОВЛЕННЯ, РЕЗЕРВНЕ КОПІЮВАННЯ, ОНОВЛЕННЯ, ПОСІБНИК З УСУНЕННЯ НЕСПРАВНОСТЕЙ
===============================================================

Короткий оперативний посібник для Linux/WSL.

Основні документи:
- ../INSTALL.md
- ../docs/QUICKSTART.md
- ../docs/COMMANDS.md
- ../docs/TROUBLESHOOTING.md
- ../docs/BACKUP.md


1) Нова інсталяція (рекомендовано)
------------------------------

curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash

Підтвердити:
sudo systemctl status uptime-monitor --no-pager
sudo journalctl -u uptime-monitor -n 80 --no-pager

Доступ:
- URL: http://<SERVER_IP>:8080
- Логін: admin
- Пароль: admin

Важливо: змінити пароль після першого входу.


2) Чиста перевстановлення (видалення старої інсталяції)
--------------------------------------

Використовуйте це, коли старий інтерфейс/стара поведінка все ще з’являється.

sudo systemctl stop uptime-monitor 2>/dev/null || правда
sudo systemctl вимкнути uptime-monitor 2>/dev/null || правда
sudo rm -f /etc/systemd/system/uptime-monitor.service
sudo systemctl daemon-reload
sudo rm -rf /opt/uptime-monitor /etc/uptime-monitor /var/lib/uptime-monitor /var/log/uptime-monitor

curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash


3) Резервне копіювання (обов'язково)
---------------------

Створіть першу резервну копію:
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/

Розклад автоматичного резервного копіювання:
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install --dest /backup/uptime-monitor/

Перевірте резервну систему:
sudo /opt/uptime-monitor/scripts/backup-system.sh --status
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --status

Перевірте резервні копії:
sudo /opt/uptime-monitor/scripts/verify-backup.sh --all


4) Відновити
----------

Список резервних копій:
sudo /opt/uptime-monitor/scripts/restore-system.sh --list

Відновити останню резервну копію:
sudo /opt/uptime-monitor/scripts/restore-system.sh --auto

Відновити певну резервну копію:
sudo /opt/uptime-monitor/scripts/restore-system.sh --from /backup/uptime-monitor/daily/<backup-file>.tar.gz


5) Оновіть існуючу установку
------------------------------

5.1 Встановлення Git (.git існує)

cd /opt/uptime-monitor
sudo systemctl зупинити безперебійну роботу
sudo git fetch --all --prune
sudo git checkout main
sudo git pull --ff-only origin main
sudo systemctl запускає монітор безперебійної роботи

5.2 Встановлення без git (без .git)

cd /opt/uptime-monitor
sudo systemctl зупинити безперебійну роботу
sudo wget -O main.py "https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/Uptime_Robot/main.py"
sudo wget -O models.py "https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/Uptime_Robot/models.py"
sudo wget -O monitoring.py "https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/Uptime_Robot/monitoring.py"
sudo wget -O ui_templates.py "https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/Uptime_Robot/ui_templates.py"
sudo systemctl запускає монітор безперебійної роботи

Перевірити після оновлення:
sudo systemctl status uptime-monitor --no-pager
sudo journalctl -u uptime-monitor -n 80 --no-pager


6) Швидкі перевірки (UI + API + auth)
----------------------------------

Check new UI markers in installed code:
grep -n "Monitors Timeline (24h)" /opt/uptime-monitor/ui_templates.py
grep -n "Статус всіх моніторів" /opt/uptime-monitor/ui_templates.py
grep -n "Історія інцидентів" /opt/uptime-monitor/ui_templates.py
grep -n "Глобальні налаштування сповіщень" /opt/uptime-monitor/ui_templates.py

Основна перевірка HTTP:
curl -sS -o /dev/null -w "GET /login -> HTTP %{http_code}\n" http://127.0.0.1:8080/login

Якщо admin/admin не працює:
curl -X POST -d "ім'я користувача=адміністратор" http://127.0.0.1:8080/забули-пароль


7) Troubleshooting
------------------

Служба не запускається:
sudo journalctl -u uptime-monitor -n 200 --no-pager
sudo systemctl status uptime-monitor --no-pager

Неправильний/старий інтерфейс користувача після оновлення:
1. Запустіть чистий розділ перевстановлення.
2. Очистити кеш браузера (жорстке перезавантаження).
3. Ще раз перевірте маркери інтерфейсу користувача в /opt/uptime-monitor/ui_templates.py.

Не можу увійти:
1. Скиньте пароль адміністратора за допомогою кінцевої точки із забутим паролем.
2. Перевірте таблиці авторизації та файл БД у /etc/uptime-monitor/sites.db.
3. Перезапустіть службу.

Порт зайнятий:
sudo ss -ltnp | grep :8080 || правда


8) Корисні команди
------------------

Пуск/зупинка/перезапуск/статус:
sudo systemctl запускає монітор безперебійної роботи
sudo systemctl зупинити безперебійну роботу
sudo systemctl перезапустіть монітор безвідмовної роботи
sudo systemctl status uptime-monitor --no-pager

Журнали:
sudo journalctl -u uptime-monitor -f
sudo journalctl -u uptime-monitor -n 100 --no-pager

Конфігурація:
sudo nano /etc/uptime-monitor/config.json
sudo systemctl перезапустіть монітор безвідмовної роботи

