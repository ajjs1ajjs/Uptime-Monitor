# Система ролей користувачів

## Огляд

Додано систему ролей для керування правами доступу користувачів.

## Ролі

### `admin` - Повний доступ
- ✅ Перегляд дашборду та статистики
- ✅ Додавання/редагування/видалення сайтів
- ✅ Зміна налаштувань сповіщень
- ✅ Управління користувачами
- ✅ Запуск ручних перевірок

### `viewer` - Тільки перегляд
- ✅ Перегляд дашборду
- ✅ Перегляд статистики та історії
- ✅ Перегляд сповіщень та інцидентів
- ✅ Перегляд SSL сертифікатів
- ❌ Додавання/редагування/видалення сайтів
- ❌ Зміна налаштувань сповіщень
- ❌ Управління користувачами

## CLI команди

### Ініціалізація бази даних
```bash
python auth_cli.py init
```

### Створення користувача
```bash
# Створити користувача з роллю viewer (за замовчуванням)
python auth_cli.py create-user --username john --password secret123

# Створити користувача з роллю admin
python auth_cli.py create-user --username admin2 --password secret123 --role admin
```

### Перегляд списку користувачів
```bash
python auth_cli.py list-users
```

Приклад виводу:
```
Users:
ID    Username        Role       Must Change  Last Login
--------------------------------------------------------------
1     admin           admin      No           2026-03-04 10:30:00
2     john            viewer     No           Never
```

### Зміна ролі користувача
```bash
# Підвищити до admin
python auth_cli.py set-role --username john --role admin

# Знизити до viewer
python auth_cli.py set-role --username admin2 --role viewer
```

### Видалення користувача
```bash
python auth_cli.py delete-user --username john
```

> ⚠️ **Увага**: Неможливо видалити останнього admin користувача

### Скидання пароля
```bash
python auth_cli.py reset-password --username john --password newpassword
```

## API ендпоінти

### Отримати поточного користувача
```
GET /api/user
```

Відповідь:
```json
{
  "username": "admin",
  "role": "admin",
  "is_admin": true
}
```

### Отримати всіх користувачів (тільки admin)
```
GET /api/users
```

### Створити користувача (тільки admin)
```
POST /api/users
Content-Type: application/json

{
  "username": "newuser",
  "password": "password123",
  "role": "viewer"
}
```

### Оновити користувача (тільки admin)
```
PUT /api/users/{username}
Content-Type: application/json

{
  "role": "admin",
  "password": "newpassword"  // optional
}
```

### Видалити користувача (тільки admin)
```
DELETE /api/users/{username}
```

## UI

### Сторінка управління користувачами

Доступна за адресою `/users` (тільки для admin)

Функціонал:
- Перегляд списку всіх користувачів
- Створення нових користувачів
- Редагування ролі та пароля
- Видалення користувачів (крім останнього admin)

## Міграція

При першому запуску після оновлення:
1. Всі користувачі з `is_admin=1` отримають роль `admin`
2. Всі користувачі з `is_admin=0` отримають роль `viewer`
3. Міграція виконується автоматично при ініціалізації бази даних

## Приклади використання

### Створення користувача тільки для перегляду

```bash
# Створити користувача для менеджера який тільки моніторить статус
python auth_cli.py create-user --username manager --password MonitorPass123 --role viewer
```

### Надання прав адміністратора

```bash
# Надати права адміністратора досвідченому користувачу
python auth_cli.py set-role --username experienced_user --role admin
```

### Ротація персоналу

```bash
# Видалити користувача який звільнився
python auth_cli.py delete-user --username former_employee

# Створити нового з потрібними правами
python auth_cli.py create-user --username new_employee --password SecurePass456 --role viewer
```

## Безпека

- Паролі зберігаються у хешованому вигляді (bcrypt)
- Сесії мають термін дії 7 днів
- Viewer не може отримати доступ до API адміністратора (отримає 403 Forbidden)
- Неможливо видалити останнього admin користувача
