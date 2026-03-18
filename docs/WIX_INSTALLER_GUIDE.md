# 📦 Створення MSI інсталятора для Windows

Ця інструкція описує процес створення професійного Windows MSI інсталятора для Uptime Monitor.

---

## 📋 Зміст

1. [Вимоги](#вимоги)
2. [Встановлення WiX Toolset](#встановлення-wix-toolset)
3. [Створення MSI](#створення-msi)
4. [Тестування інсталятора](#тестування-інсталятора)
5. [Публікація в Releases](#публікація-в-releases)
6. [Вирішення проблем](#вирішення-проблем)

---

## 🔧 Вимоги

### Обов'язково

- **Windows 10/11** (x64)
- **Python 3.8+** (встановлено та додано в PATH)
- **WiX Toolset 3.14+**
- **Права адміністратора** (для тестування)

### Бажано

- **Chocolatey** (для легкої установки WiX)
- **Віртуальна машина Windows** (для безпечного тестування)

---

## 📥 Встановлення WiX Toolset

### Спосіб 1: Chocolatey (найпростіший)

```powershell
# Встановити Chocolatey якщо немає
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Встановити WiX Toolset
choco install wixtoolset
```

### Спосіб 2: Ручне встановлення

1. Перейдіть на https://wixtoolset.org/docs/getting-started/
2. Завантажте **WiX Toolset v3.14.x**
3. Запустіть інсталятор
4. Додайте до PATH вручну:
   ```cmd
   setx PATH "%PATH%;C:\Program Files (x86)\WiX Toolset v3.14\bin"
   ```

### Перевірка встановлення

```cmd
heat.exe -?
candle.exe -?
light.exe -?
```

Якщо бачите довідку — встановлено правильно! ✅

---

## 🏗️ Створення MSI

### Крок 1: Підготовка файлів

Переконайтеся, що всі файли на місці:

```cmd
cd D:\PROJECT\Uptime-Monitor\installer

# Перевірка файлів
dir ..\Uptime_Robot\main.py
dir ..\Uptime_Robot\requirements.txt
dir ..\Uptime_Robot\icon.ico
```

### Крок 2: Запуск збірки

```cmd
# Відкрийте Command Prompt від імені адміністратора
cd D:\PROJECT\Uptime-Monitor\installer

# Запустіть скрипт збірки
build_msi.bat
```

### Крок 3: Очікування завершення

Скрипт автоматично:
1. ✅ Перевірить WiX Toolset
2. ✅ Згенерує унікальні GUID
3. ✅ Оновить версію в product.wxs
4. ✅ Скомпілює .wxs → .wixobj
5. ✅ Створить .msi файл

### Крок 4: Результат

Після завершення ви отримаєте:

```
installer\
└── UptimeMonitor-2.0.0.mi
```

**Розмір:** ~15-25 MB (залежить від включених файлів)

---

## 🧪 Тестування інсталятора

### ⚠️ ВАЖЛИВО: Тестуйте на віртуальній машині!

Не тестуйте новий інсталятор на production-машині!

### Крок 1: Створіть чисту VM

1. Встановіть VirtualBox або VMware
2. Створіть VM з Windows 10/11
3. Встановіть Python (якщо потрібно для тесту)

### Крок 2: Скопіюйте MSI на VM

```cmd
# На хост-машині
copy UptimeMonitor-2.0.0.msi \\vmware-host\Shared Folders\
```

### Крок 3: Встановлення

```cmd
# Звичайне встановлення
msiexec /i UptimeMonitor-2.0.0.msi

# Тихе встановлення (для автоматизації)
msiexec /i UptimeMonitor-2.0.0.msi /quiet

# Встановлення з логами
msiexec /i UptimeMonitor-2.0.0.msi /l*v install.log
```

### Крок 4: Перевірка

```cmd
# Перевірка служби
sc query UptimeMonitor

# Перевірка порту
netstat -ano | findstr :8080

# Перевірка файлів
dir "C:\Program Files\Uptime Monitor"

# Перевірка даних
dir "C:\ProgramData\UptimeMonitor"
```

### Крок 5: Тест веб-інтерфейсу

Відкрийте браузер:
```
http://localhost:8080
```

Логін: `admin`  
Пароль: `admin`

### Крок 6: Тест видалення

```cmd
# Видалення
msiexec /x UptimeMonitor-2.0.0.msi

# Тихе видалення
msiexec /x UptimeMonitor-2.0.0.msi /quiet

# Перевірка що служба видалена
sc query UptimeMonitor
```

**Важливо:** Файли `sites.db` та `config.json` мають **залишитися** в `C:\ProgramData\UptimeMonitor\`

---

## 📤 Публікація в Releases

### Крок 1: Створіть GitHub Release

1. Перейдіть на https://github.com/ajjs1ajjs/Uptime-Monitor/releases
2. Натисніть **Draft a new release**
3. Введіть тег: `v2.0.0`
4. Введіть назву: `Uptime Monitor v2.0.0`
5. Опишіть зміни

### Крок 2: Завантажте файли

Перетягніть файли в Release:

```
✅ UptimeMonitor-2.0.0.msi          # MSI інсталятор
✅ UptimeMonitor-2.0.0-windows.zip  # ZIP архів (існуючий)
```

### Крок 3: Оновіть README

Додайте посилання на MSI в README.md:

```markdown
### Windows

#### Спосіб 1: MSI інсталятор (рекомендовано)
Завантажте [UptimeMonitor-2.0.0.msi](https://github.com/ajjs1ajjs/Uptime-Monitor/releases/download/v2.0.0/UptimeMonitor-2.0.0.msi)

#### Спосіб 2: ZIP архів
Завантажте [UptimeMonitor-2.0.0-windows.zip](...)
```

### Крок 4: Опублікуйте

Натисніть **Publish release**

---

## 🛠️ Вирішення проблем

### Помилка: "WiX Toolset not found"

**Причина:** WiX не встановлено або не в PATH

**Рішення:**
```cmd
# Перевірка
where heat.exe

# Якщо не знайдено - додати до PATH
setx PATH "%PATH%;C:\Program Files (x86)\WiX Toolset v3.14\bin"

# Або перевстановити через Chocolatey
choco install wixtoolset --force
```

### Помилка: "Invalid GUID"

**Причина:** Некоректний GUID в product.wxs

**Рішення:** Запустіть `build_msi.bat` — він автоматично згенерує нові GUID

### Помилка: "Service installation failed"

**Причина:** Немає прав адміністратора

**Рішення:** Запустіть інсталятор від імені адміністратора

### Помилка: "Python is not installed"

**Причина:** Python не знайдено в PATH

**Рішення:**
1. Перевстановіть Python
2. Відмітьте галочку "Add Python to PATH"
3. Перезапустіть командний рядок

### Помилка компіляції: "File not found"

**Причина:** product.wxs посилається на неіснуючі файли

**Рішення:**
```cmd
# Перевірка шляхів
dir ..\Uptime_Robot\main.py
dir ..\Uptime_Robot\icon.ico

# Якщо файлів немає - оновіть шляхи в product.wxs
```

### MSI занадто великий

**Причина:** Включено зайві файли

**Рішення:** Відредагуйте product.wxs, видаліть непотрібні `<Component>`

### Інсталятор не запускає службу

**Причина:** Проблема з Custom Actions

**Рішення:** Перевірте логи:
```cmd
# Перегляд логів встановлення
type %TEMP%\msi*.log
```

---

## 📊 Контрольний список перед релізом

### Перед збіркою

- [ ] WiX Toolset встановлено
- [ ] Всі файли в `Uptime_Robot\` на місці
- [ ] Версія в README.md оновлена
- [ ] CHANGELOG.md оновлено

### Після збірки

- [ ] MSI створено без помилок
- [ ] Розмір файлу адекватний (<50 MB)
- [ ] Іконка відображається

### Тестування

- [ ] Встановлення на чистій VM працює
- [ ] Служба запускається автоматично
- [ ] Веб-інтерфейс доступний
- [ ] Видалення працює коректно
- [ ] Дані зберігаються після видалення

### Публікація

- [ ] GitHub Release створено
- [ ] MSI завантажено в Release
- [ ] README оновлено
- [ ] CHANGELOG оновлено

---

## 📞 Додаткова допомога

### Корисні команди

```cmd
# Перегляд встановлених MSI продуктів
wmic product where "name like '%Uptime%'" get name,version

# Примусове видалення
msiexec /x {PRODUCT-CODE} /quiet

# Відновлення
msiexec /f UptimeMonitor-2.0.0.msi
```

### Логи

- **Встановлення:** `%TEMP%\msi*.log`
- **Служба:** `C:\ProgramData\UptimeMonitor\uptime_monitor.log`
- **WiX компіляція:** Виводиться в консоль під час `build_msi.bat`

### Ресурси

- [WiX Toolset Documentation](https://wixtoolset.org/docs/)
- [MSI Command Line Options](https://docs.microsoft.com/en-us/windows/win32/msi/standard-installer-command-line-options)
- [Windows Installer SDK](https://docs.microsoft.com/en-us/windows/win32/msi/windows-installer-portal)

---

## ✅ Підсумок

Після виконання цієї інструкції ви матимете:

1. ✅ Професійний MSI інсталятор
2. ✅ Протестований на чистій системі
3. ✅ Опублікований в GitHub Releases
4. ✅ Готовий для використання користувачами

**Час виконання:** ~30-60 хвилин (включаючи тестування)
