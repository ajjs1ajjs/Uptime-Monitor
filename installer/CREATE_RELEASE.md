# 📦 Інструкція: Створення GitHub Release з MSI

## Спосіб 1: Через веб-інтерфейс (рекомендовано)

### Крок 1: Відкрийте GitHub Releases
Перейдіть за посиланням:
```
https://github.com/ajjs1ajjs/Uptime-Monitor/releases/new
```

### Крок 2: Виберіть тег
- **Tag version:** `v2.0.0` (вже створено!)
- **Target:** `master`

### Крок 3: Заповніть інформацію

**Release title:**
```
Uptime Monitor v2.0.0 - WiX MSI Installer
```

**Description:**
```markdown
## 🎉 Нова версія з WiX MSI інсталятором!

### ✨ Основні зміни

- 🆕 **WiX MSI інсталятор** - професійна установка для Windows
- 🔧 **Автоматична установка залежностей** - Python пакети встановлюються автоматично
- 🚀 **Автоматична установка служби** - служба Windows створюється під час інсталяції
- 💾 **Збереження даних** - база даних (sites.db) зберігається при видаленні
- 📚 **Повна документація** - детальні інструкції з встановлення

### 📦 Встановлення

#### MSI Інсталятор (рекомендовано)
1. Завантажте `UptimeMonitor-2.0.0.msi`
2. Двічі клацніть на файл
3. Слідуйте інструкціям майстра встановлення

#### ZIP Архів (альтернатива)
1. Завантажте `UptimeMonitor-2.0.0-windows.zip`
2. Розпакуйте в потрібне місце
3. Запустіть `install.bat` від імені адміністратора

### 📚 Документація

- [QUICKSTART_UK.md](QUICKSTART_UK.md) - Швидкий старт
- [INSTALL.md](INSTALL.md) - Повна інструкція з встановлення
- [docs/WIX_INSTALLER_GUIDE.md](docs/WIX_INSTALLER_GUIDE.md) - Створення MSI інсталятора

### 🔧 Технічні деталі

** MSI інсталятор:**
- Автоматично встановлює Python залежності
- Створює службу Windows
- Запускає службу після встановлення
- Зберігає дані користувача при видаленні

** Вимоги:**
- Windows 10/11
- Python 3.8+ (або встановлюється автоматично)
- Права адміністратора

### 🐛 Виправлення проблем

Якщо виникли проблеми:
1. Перевірте логи встановлення: `%TEMP%\msi*.log`
2. Відкрийте issue: https://github.com/ajjs1ajjs/Uptime-Monitor/issues

---

**📊 Зміни:** 8 файлів додано, 1034 рядки додано

**⭐ Дякуємо за використання Uptime Monitor!**
```

### Крок 4: Завантажте файли

Перетягніть файли в область **"Attach binaries by dropping them here or selecting them"**:

1. **`UptimeMonitor-2.0.0.msi.zip`** (160 KB) ⭐ **ОСНОВНИЙ ФАЙЛ**
   - Шлях: `D:\PROJECT\Uptime-Monitor\installer\UptimeMonitor-2.0.0.msi.zip`
   - Містить: `UptimeMonitor-2.0.0.msi`

2. **`UptimeMonitor-2.0.0-windows.zip`** (якщо є)
   - Старий ZIP для сумісності

### Крок 5: Натисніть "Publish release"

✅ **Готово!** Release опубліковано.

---

## Спосіб 2: Через GitHub CLI (якщо встановлено)

```powershell
# Встановити GitHub CLI (як адміністратор)
choco install gh -y

# Авторизуватися
gh auth login

# Створити реліз
gh release create v2.0.0 `
  --title "Uptime Monitor v2.0.0 - WiX MSI Installer" `
  --notes-file RELEASE_NOTES.md `
  installer/UptimeMonitor-2.0.0.msi
```

---

## ✅ Контрольний список

Після створення Release:

- [ ] Release опубліковано на https://github.com/ajjs1ajjs/Uptime-Monitor/releases
- [ ] Файл `UptimeMonitor-2.0.0.msi` завантажено
- [ ] Теґ `v2.0.0` прив'язано до релізу
- [ ] Опис релізу заповнено
- [ ] Посилання на документацію додано

---

## 🔗 Корисні посилання

- **Releases:** https://github.com/ajjs1ajjs/Uptime-Monitor/releases
- **Tags:** https://github.com/ajjs1ajjs/Uptime-Monitor/tags
- **GitHub Docs:** https://docs.github.com/en/repositories/releasing-projects-on-github
