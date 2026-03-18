# 🚀 Швидка інструкція: Створення MSI інсталятора

## Вимоги

- Windows 10/11
- Python 3.8+
- WiX Toolset 3.14+

## Встановлення WiX (якщо ще немає)

```powershell
choco install wixtoolset
```

## Створення MSI

```cmd
cd D:\PROJECT\Uptime-Monitor\installer
build_msi.bat
```

## Результат

```
UptimeMonitor-2.0.0.msi
```

## Використання

### Встановлення
```cmd
msiexec /i UptimeMonitor-2.0.0.msi
```

### Тихе встановлення
```cmd
msiexec /i UptimeMonitor-2.0.0.msi /quiet
```

### Видалення
```cmd
msiexec /x UptimeMonitor-2.0.0.msi
```

## Перевірка

```cmd
# Служба
sc query UptimeMonitor

# Порт
netstat -ano | findstr :8080

# Файли
dir "C:\Program Files\Uptime Monitor"
```

## Доступ до веб-інтерфейсу

```
http://localhost:8080
Login: admin
Password: admin
```

---

**Детальна інструкція:** [docs/WIX_INSTALLER_GUIDE.md](docs/WIX_INSTALLER_GUIDE.md)
