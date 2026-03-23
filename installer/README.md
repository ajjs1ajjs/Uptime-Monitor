# WiX Installer for Uptime Monitor

Ця папка містить файли для створення Windows MSI інсталятора.

## 📦 Що це таке?

WiX (Windows Installer XML) — професійний інструмент від Microsoft для створення .msi інсталяторів.

## 🚀 Швидкий старт

### Вимоги

1. **Windows 10/11**
2. **Python 3.8+** встановлено та додано в PATH
3. **WiX Toolset 3.14+**

### Встановлення WiX Toolset

**Спосіб 1: Chocolatey (рекомендовано)**
```powershell
choco install wixtoolset
```

**Спосіб 2: Завантажити з офіційного сайту**
1. Перейдіть на https://wixtoolset.org/docs/getting-started/
2. Завантажте інсталятор
3. Встановіть

### Створення MSI інсталятора

1. Відкрийте командний рядок **від імені адміністратора**
2. Перейдіть у цю папку:
   ```cmd
   cd D:\PROJECT\Uptime-Monitor\installer
   ```
3. Запустіть:
   ```cmd
   build_msi.bat
   ```

4. Після завершення ви отримаєте:
   ```
   UptimeMonitor-2.0.0.msi
   ```

## 📋 Використання MSI інсталятора

### Звичайне встановлення

```
Двічі клацніть на UptimeMonitor-2.0.0.msi
```

### Тихе встановлення (для адміністраторів)

```cmd
msiexec /i UptimeMonitor-2.0.0.msi /quiet
```

### Встановлення з логами

```cmd
msiexec /i UptimeMonitor-2.0.0.msi /l*v install.log
```

### Видалення

```cmd
msiexec /x UptimeMonitor-2.0.0.msi
```

### Тихе видалення

```cmd
msiexec /x UptimeMonitor-2.0.0.msi /quiet
```

## 📁 Структура файлів

```
installer/
├── product.wxs          # WiX конфігурація (XML)
├── build_msi.bat        # Скрипт збірки
├── README.md            # Цей файл
└── UptimeMonitor-2.0.0.msi  # Результат збірки
```

## ⚙️ Що встановлюється?

### Програма
```
C:\Program Files\Uptime Monitor\
├── main.py
├── main_service.py
├── config_manager.py
├── config_manager.py
├── monitoring.py
├── notifications.py
├── ... (інші модулі)
├── requirements.txt
└── install_service.bat
```

### Дані користувача
```
C:\ProgramData\UptimeMonitor\
├── sites.db           # База даних (зберігається при видаленні!)
├── config.json        # Конфігурація (зберігається при видаленні!)
└── uptime_monitor.log
```

### Меню Пуск
- Uptime Monitor (відкрити веб-інтерфейс)
- Uninstall Uptime Monitor

### Служба Windows
- **Назва:** UptimeMonitor
- **Тип запуску:** Автоматично
- **Порт:** 8080 (можна змінити під час встановлення)

## 🔧 Налаштування

### Зміна порту

Під час встановлення інсталятор запитає порт. За замовчуванням: **8080**

Якщо потрібно змінити після встановлення:

1. Відредагуйте `C:\ProgramData\UptimeMonitor\config.json`:
   ```json
   {
     "server": {
       "port": 9090
     }
   }
   ```

2. Перезапустіть службу:
   ```cmd
   net stop UptimeMonitor
   net start UptimeMonitor
   ```

## 🆚 Порівняння з іншими способами встановлення

| Спосіб | Переваги | Недоліки |
|--------|----------|----------|
| **MSI (WiX)** | Професійний, підтримка Group Policy, тихе встановлення | Потрібен WiX для збірки |
| **ZIP + install.bat** | Простий, не потрібні додаткові інструменти | Ручне оновлення |
| **Git clone** | Для розробників, легко оновлювати | Потрібен Git |

## 🛠️ Вирішення проблем

### Помилка: "WiX Toolset not found"

**Рішення:** Встановіть WiX Toolset:
```powershell
choco install wixtoolset
```

Або додайте до PATH:
```cmd
setx PATH "%PATH%;C:\Program Files (x86)\WiX Toolset v3.14\bin"
```

### Помилка: "Python is not installed"

**Рішення:** Встановіть Python 3.8+ з https://python.org

Під час встановлення обов'язково відмітьте:
- ✅ Add Python to PATH

### Помилка: "Service installation failed"

**Рішення:** Запустіть інсталятор від імені адміністратора.

### Помилка: "Port already in use"

**Рішення:** Виберіть інший порт під час встановлення (наприклад, 9090).

## 📝 Примітки

- **База даних `sites.db` НЕ видаляється при деінсталяції** — це захищає ваші дані
- Для повного видалення даних вручну видаліть `C:\ProgramData\UptimeMonitor\`
- Інсталятор автоматично встановлює Python залежності з `requirements.txt`
- Служба запускається автоматично після встановлення

## 🔗 Корисні посилання

- [WiX Toolset Documentation](https://wixtoolset.org/docs/)
- [WiX Toolset GitHub](https://github.com/wixtoolset/wix3)
- [MSI Command Line Options](https://docs.microsoft.com/en-us/windows/win32/msi/standard-installer-command-line-options)

## 📞 Підтримка

Якщо виникли проблеми:
1. Перевірте логи встановлення: `%TEMP%\msi*.log`
2. Відкрийте issue на GitHub: https://github.com/ajjs1ajjs/Uptime-Monitor/issues
