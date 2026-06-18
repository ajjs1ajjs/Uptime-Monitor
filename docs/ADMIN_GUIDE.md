# 🔐 Admin Guide — Password Management

## Перше встановлення

При першому запуску генерується **випадковий пароль адміністратора**.

Пароль показується **один раз** у консолі (stdout) під час створення та зберігається в:
- **Linux:** `/etc/uptime-monitor/credentials.txt` (права `600`)
- **Windows:** `<директорія проекту>/credentials.txt`

> ⚠️ **Безпека:** з міркувань безпеки пароль **не пишеться** в журнал застосунку
> (journald/Docker logs) і **не друкується повторно** при кожному перезапуску
> сервісу. Якщо ви його не зберегли — скористайтесь командою `show-password` нижче.

## Команди CLI

### Показати поточний пароль

```bash
# Linux
sudo /opt/uptime-monitor/venv/bin/python -m Uptime_Robot.auth_cli show-password

# Windows
python -m Uptime_Robot.auth_cli show-password
```

### Скинути пароль (новий випадковий)

```bash
sudo /opt/uptime-monitor/venv/bin/python -m Uptime_Robot.auth_cli reset-password
```

### Скинути пароль (свій)

```bash
sudo /opt/uptime-monitor/venv/bin/python -m Uptime_Robot.auth_cli reset-password --password "MyNewPass123!"
```

### Відновити пароль з бекапу

Якщо пароль було змінено через веб-інтерфейс і ви його забули — відновіть останній збережений:

```bash
sudo /opt/uptime-monitor/venv/bin/python -m Uptime_Robot.auth_cli restore-password
```

### Користувачі

```bash
# Список користувачів
python -m Uptime_Robot.auth_cli list-users

# Створити користувача
python -m Uptime_Robot.auth_cli create-user --username john --password "Pass123!@#" --role viewer

# Видалити користувача
python -m Uptime_Robot.auth_cli delete-user --username john
```

## Оновлення

При оновленні через `curl ... | sudo bash` пароль **НЕ змінюється** — використовується той самий, що й при попередній установці.

## Як це працює

1. При створенні користувача пароль хешується (bcrypt) і **додатково шифрується** (Fernet/AES-256) для можливості відновлення
2. Зашифрована копія зберігається в колонці `password_encrypted` таблиці `users`
3. При зміні пароля через веб-інтерфейс оновлюються обидва поля: `password_hash` і `password_encrypted`
4. Команда `show-password` дешифрує `password_encrypted` і показує пароль
5. Команда `restore-password` відновлює пароль з `password_encrypted` у `password_hash`
