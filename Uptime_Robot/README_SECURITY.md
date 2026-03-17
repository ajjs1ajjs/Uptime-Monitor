# Uptime Monitor v2.0 - Покращення безпеки та архітектури

## 🚀 Що змінилось

Проект був повністю реструктуризований з фокусом на **безпеку**, **продуктивність** та **підтримуваність**.

---

## 🔒 Безпека (Критичні виправлення)

### 1. Хешування паролів (bcrypt)
- **Проблема:** SHA-256 без salt — вразливий до атак
- **Рішення:** Перехід на bcrypt з автоматичним salt
- **Файл:** `auth_module.py`

```python
# Було (НЕБЕЗПЕЧНО):
hashlib.sha256(password.encode()).hexdigest()

# Стало (БЕЗПЕЧНО):
bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
```

### 2. SSL-верифікація
- **Проблема:** `ssl=False` в aiohttp — вразливий до MITM
- **Рішення:** Видалено відключення верифікації
- **Файли:** `main.py`, `main_service.py`

### 3. SQL Injection Protection
- **Проблема:** Динамічна конструкція SQL запитів
- **Рішення:** Валідація дозволених колонок
- **Файли:** `main.py`, `main_service.py`

### 4. Захист Cookies
- **Проблема:** Відсутні security headers
- **Рішення:** Додано `samesite='lax'`, `secure`, `httponly`
- **Файл:** `main.py`

### 5. .gitignore
- Додано правила для `.env`, бази даних, логів

---

## 🏗️ Архітектура (Рефакторинг)

### Нова структура проекту
```
Uptime_Robot/
├── auth_module.py          # Авторизація з bcrypt + Jinja2
├── config.py               # Конфігурація Pydantic
├── database.py             # Пул з'єднань SQLite
├── logger.py               # Логування з ротацією
├── models.py               # ORM моделі БД (НОВЕ!)
├── notifications.py        # Сервіс сповіщень (НОВЕ!)
├── monitoring.py           # Моніторинг сайтів (НОВЕ!)
├── ssl_checker.py          # Перевірка SSL
├── main.py                 # Основний додаток
├── main_service.py         # Windows Service
├── requirements.txt        # Закріплені версії
├── .gitignore
├── templates/              # Jinja2 шаблони
│   ├── login.html
│   └── change_password.html
└── tests.py                # Unit тести
```

### Нові модулі

#### 1. `models.py` — Робота з БД
- Централізована робота з базою даних
- Контекстні менеджери для автоматичного закриття з'єднань
- Функції: `get_all_sites()`, `add_site()`, `update_site()`, etc.

#### 2. `notifications.py` — Сповіщення
- Клас `NotificationService`
- Підтримка: Telegram, Teams, Discord, Slack, Email, SMS
- Асинхронна відправка
- Логування помилок

#### 3. `monitoring.py` — Моніторинг
- `SiteMonitor` — перевірка сайтів
- `SSLMonitor` — перевірка SSL сертифікатів
- Автоматичне очищення старих записів (30 днів)

---

## 📊 Покращення продуктивності

### 1. Логування
- **Було:** `print()`
- **Стало:** Модуль `logging` з ротацією файлів
- **Розмір:** 10 МБ, 5 резервних копій

### 2. Пул з'єднань до БД
- Контекстні менеджери (`with` statement)
- Автоматичне закриття з'єднань
- Запобігання витокам пам'яті

### 3. Очищення старих даних
- Автоматичне видалення `status_history` старше 30 днів
- Запобігання розростанню бази даних

---

## ✅ Валідація даних

### Підантичні валідатори
```python
class SiteCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., min_length=5, max_length=500)
    check_interval: int = Field(60, ge=10, le=3600)
    
    @validator('url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v
```

---

## 🎨 Шаблони Jinja2

### Шаблони винесено з Python коду:
- `templates/login.html`
- `templates/change_password.html`

### Переваги:
- Чистий код Python
- Легше редагувати HTML
- Можливість розширення

---

## 🧪 Тести

### Запуск тестів:
```bash
python tests.py
```

### Покриття:
- Хешування паролів (bcrypt)
- Робота з базою даних
- Валідація URL та назв
- Сервіс сповіщень

---

## 📦 Залежності (requirements.txt)

```
fastapi==0.104.1
uvicorn==0.24.0
aiohttp==3.9.1
pydantic==2.5.0
pywin32==306
python-multipart==0.0.6
bcrypt==5.0.0
jinja2==3.1.6
```

---

## ⚠️ Важливі зміни для користувачів

### 1. Паролі
**База даних НЕСУМІСНА зі старою версією!**

**Дії:**
1. Видаліть `sites.db` (якщо є старі дані)
2. Або оновіть пароль адміна через БД

**Стандартний логін:**
- Username: `admin`
- Password: `admin`
- **Важливо:** Змініть пароль при першому вході!

### 2. Перевірка HTTPS
Тепер HTTPS з'єднання перевіряються (без `ssl=False`). Самопідписані сертифікати можуть викликати помилки.

### 3. Валідація URL
Тепер приймаються тільки URL, що починаються з `http://` або `https://`

---

## 🚀 Встановлення та запуск

### 1. Встановлення залежностей:
```bash
pip install -r requirements.txt
```

### 2. Запуск додатку:
```bash
python main.py
```

### 3. Запуск на іншому порту:
```bash
python main.py 8080
```

---

## 🔧 Конфігурація

### Налаштування сповіщень через API:
```bash
POST /api/notify-settings
{
    "telegram": {
        "enabled": true,
        "token": "YOUR_BOT_TOKEN",
        "chat_id": "YOUR_CHAT_ID"
    }
}
```

### Додавання сайту:
```bash
POST /api/sites
{
    "name": "My Website",
    "url": "https://example.com",
    "check_interval": 60,
    "notify_methods": ["telegram", "email"]
}
```

---

## 📈 Логи

Логи зберігаються в `uptime_monitor.log` з автоматичною ротацією:
- Максимальний розмір: 10 МБ
- Кількість резервних копій: 5

---

## 🔐 Рекомендації з безпеки

1. **Змініть стандартний пароль** при першому вході
2. **Використовуйте HTTPS** для production
3. **Обмежте доступ** до порту файєволом
4. **Регулярно оновлюйте** залежності
5. **Робіть backup** бази даних

---

## 🐛 Відомі проблеми

### LSP Попередження
Деякі попередження LSP (language server) про типізацію — це помилки аналізатора, код працює коректно.

---

## 📞 Підтримка

При виникненні проблем:
1. Перевірте логи в `uptime_monitor.log`
2. Перевірте права доступу до файлів
3. Перевірте залежності: `pip list`

---

## 📝 Ліцензія

МОЯ ліцензія

---

**Версія:** 2.0  
**Дата:** 2024  
**Автор:** Uptime Monitor Team
