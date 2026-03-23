# 🚀 Короткий посібник

Швидкий старт Uptime Monitor за 5 хвилин

## 1. Встановлення (1 хвилина)

```bash
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash
```

## 2. Перевірка статусу (30 секунд)

```bash
sudo systemctl status uptime-monitor uptime-monitor-worker
```

## 3. Створення першого бекапу ⚠️ ОБОВ'ЯЗКОВО

```bash
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/uptime-monitor/
```

## 4. Налаштування автоматичних бекапів

```bash
sudo /opt/uptime-monitor/scripts/schedule-backup.sh --install --dest /backup/uptime-monitor/
```

## 5. Доступ до веб-інтерфейсу

- **URL**: `http://$(hostname -I | awk '{print $1}'):8080`
- **Вхід**: `admin`
- **Пароль**: `admin`

## 6. Зміна пароля

1. Відкрити URL в браузері
2. Увійти з admin/admin
3. Система автоматично перенаправить на зміну пароля
4. **Обов'язково змініть пароль!**

---

## ✅ Контрольний список після інсталяції

- [ ] Змінити пароль за замовчуванням
- [ ] Створити перший бекап
- [ ] Налаштувати автоматичні бекапи
- [ ] Додати сайти для моніторингу
- [ ] Налаштувати сповіщення (опціонально)
- [ ] Налаштувати SSL (опціонально)

---

## 🆘 Якщо щось пішло не так

Дивіться:
- [UPDATE_INSTRUCTIONS.md](UPDATE_INSTRUCTIONS.md) - безпечний pre-update backup + rollback runbook
- [COMMANDS.md](COMMANDS.md) - всі команди
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - вирішення проблем
- [BACKUP.md](BACKUP.md) - інструкції по бекапу
