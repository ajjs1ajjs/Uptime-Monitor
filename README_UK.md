# Uptime Monitor

[![Р’РµСЂСЃС–СЏ](https://img.shields.io/badge/РІРµСЂСЃС–СЏ-2.1.0-blue.svg)](https://github.com/ajjs1ajjs/Uptime-Monitor/releases)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![РџР»Р°С‚С„РѕСЂРјР°](https://img.shields.io/badge/РїР»Р°С‚С„РѕСЂРјР°-Linux%20%7C%20Windows-lightgrey.svg)]()

**РњРѕРЅС–С‚РѕСЂРёРЅРі РґРѕСЃС‚СѓРїРЅРѕСЃС‚С– Р· Р°РІС‚РѕРјР°С‚РёС‡РЅРёРј СЂРµР·РµСЂРІРЅРёРј РєРѕРїС–СЋРІР°РЅРЅСЏРј, SSL СЃРµСЂС‚РёС„С–РєР°С‚Р°РјРё С‚Р° СЃРїРѕРІС–С‰РµРЅРЅСЏРјРё.**

<p align="center">
  <img src="https://img.shields.io/badge/uptime-24/7-green" alt="24/7 Uptime">
  <img src="https://img.shields.io/badge/SSL-РјРѕРЅС–С‚РѕСЂРёРЅРі-orange" alt="SSL Monitoring">
  <img src="https://img.shields.io/badge/СЃРїРѕРІС–С‰РµРЅРЅСЏ-Telegram%20%7C%20Email%20%7C%20Teams-blue" alt="РЎРїРѕРІС–С‰РµРЅРЅСЏ">
</p>

---

## рџљЂ РЁРІРёРґРєРёР№ СЃС‚Р°СЂС‚

### Р’СЃС‚Р°РЅРѕРІР»РµРЅРЅСЏ (Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash

# Р”РѕСЃС‚СѓРї РґРѕ РїР°РЅРµР»С–
http://YOUR_SERVER_IP:8080
# Р›РѕРіС–РЅ: admin / РџР°СЂРѕР»СЊ: auto-generated
```

### Windows

**Option A вЂ” Windows Service (recommended):**
```powershell
# Run as Administrator in Uptime_Robot folder
.\install_service.bat
# Access: http://localhost:8080
```

**Option B вЂ” PowerShell quick install:**
```powershell
# Run as Administrator
& {
    if (!(Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Host "Installing Python..."; winget install Python.Python.3.12 --silent
    }
    iwr https://github.com/ajjs1ajjs/Uptime-Monitor/archive/refs/heads/main.zip -OutFile uptime.zip
    Expand-Archive uptime.zip -DestinationPath . -Force; Remove-Item uptime.zip
    cd Uptime-Monitor-main/Uptime_Robot
    .\install.bat /y
}
```

> рџ’Ў Р—Р°РїСѓСЃС‚С–С‚СЊ С‚Сѓ Р¶ РєРѕРјР°РЅРґСѓ РїРѕРІС‚РѕСЂРЅРѕ РґР»СЏ РѕРЅРѕРІР»РµРЅРЅСЏ (Р°РІС‚РѕРјР°С‚РёС‡РЅРѕ РІРёСЏРІР»СЏС” С–СЃРЅСѓСЋС‡Рµ РІСЃС‚Р°РЅРѕРІР»РµРЅРЅСЏ, СЃС‚РІРѕСЂСЋС” СЂРµР·РµСЂРІРЅСѓ РєРѕРїС–СЋ РєРѕРЅС„С–РіСѓСЂР°С†С–С—, РїРµСЂРµР·Р°РїСѓСЃРєР°С” СЃР»СѓР¶Р±Сѓ).

**Option C вЂ” Python directly (no service):**
```powershell
python -m Uptime_Robot.main --host 0.0.0.0 --port 8080
# Access: http://localhost:8080
```

> **Windows Password (v2.0.0+):** Generated randomly on first run. Check the console output or run:
> ```powershell
> python -c "from Uptime_Robot.auth_module import hash_password; print('Check install output for password')"
> ```

---

## рџ“љ Р”РѕРєСѓРјРµРЅС‚Р°С†С–СЏ

| Р”РѕРєСѓРјРµРЅС‚ | РћРїРёСЃ |
|----------|------|
| **[INSTALL.md](INSTALL.md)** | РџРѕРІРЅР° С–РЅСЃС‚СЂСѓРєС†С–СЏ Р· РІСЃС‚Р°РЅРѕРІР»РµРЅРЅСЏ |
| **[QUICKSTART_UK.md](QUICKSTART_UK.md)** | РЁРІРёРґРєРёР№ СЃС‚Р°СЂС‚ Р·Р° 5 С…РІРёР»РёРЅ |
| **[docs/API.md](docs/API.md)** | API РґРѕРєСѓРјРµРЅС‚Р°С†С–СЏ |
| **[docs/BACKUP.md](docs/BACKUP.md)** | РЎРёСЃС‚РµРјР° СЂРµР·РµСЂРІРЅРѕРіРѕ РєРѕРїС–СЋРІР°РЅРЅСЏ |
| **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** | РЈСЃСѓРЅРµРЅРЅСЏ РЅРµСЃРїСЂР°РІРЅРѕСЃС‚РµР№ |
| **[docs/COMMANDS.md](docs/COMMANDS.md)** | Р”РѕРІС–РґРЅРёРє РєРѕРјР°РЅРґ |
| **[UPDATE_PRODUCTION.md](UPDATE_PRODUCTION.md)** | РћРЅРѕРІР»РµРЅРЅСЏ Production |
| **[NOTIFICATION_TROUBLESHOOTING_UK.md](NOTIFICATION_TROUBLESHOOTING_UK.md)** | Р”С–Р°РіРЅРѕСЃС‚РёРєР° СЃРїРѕРІС–С‰РµРЅСЊ |
| **[MIGRATION_GUIDE_UK.md](MIGRATION_GUIDE_UK.md)** | РњС–РіСЂР°С†С–СЏ Р· С–РЅС€РёС… СЃРёСЃС‚РµРј |

---

## рџЊџ РњРѕР¶Р»РёРІРѕСЃС‚С–

### РњРѕРЅС–С‚РѕСЂРёРЅРі
- вњ… HTTP/HTTPS РїРµСЂРµРІС–СЂРєРё
- вњ… SSL СЃРµСЂС‚РёС„С–РєР°С‚Рё (С‚РµСЂРјС–РЅ РґС–С—)
- вњ… Р§Р°СЃ РІС–РґРїРѕРІС–РґС–
- вњ… Р†РЅС‚РµСЂРІР°Р» РїРµСЂРµРІС–СЂРєРё: 60 СЃРµРєСѓРЅРґ

### РЎРїРѕРІС–С‰РµРЅРЅСЏ
- рџ“± Telegram
- рџ“§ Email (SMTP)
- рџ’¬ Slack
- рџЋ® Discord
- рџЏў Microsoft Teams
- рџ“ћ SMS (Twilio)

### Р РµР·РµСЂРІРЅРµ РєРѕРїС–СЋРІР°РЅРЅСЏ
- рџ”„ РђРІС‚РѕРјР°С‚РёС‡РЅС– Р±РµРєР°РїРё (С‰РѕРґРЅСЏ/С‰РѕС‚РёР¶РЅСЏ/С‰РѕРјС–СЃСЏС†СЏ)
- рџ’ѕ NFS/Samba РїС–РґС‚СЂРёРјРєР°
- рџ”§ Р’С–РґРЅРѕРІР»РµРЅРЅСЏ РѕРґРЅС–С”СЋ РєРѕРјР°РЅРґРѕСЋ
- рџ“¦ Р—Р±РµСЂРµР¶РµРЅРЅСЏ: Р‘Р”, РєРѕРЅС„С–РіСѓСЂР°С†С–С—, SSL, Р»РѕРіРё

### Р‘РµР·РїРµРєР°
- рџ”’ HTTPS/SSL РїС–РґС‚СЂРёРјРєР°
- рџ‘Ґ Р РѕР»С– РєРѕСЂРёСЃС‚СѓРІР°С‡С–РІ (admin/viewer)
- рџ”ђ РЈРїСЂР°РІР»С–РЅРЅСЏ СЃРµСЃС–СЏРјРё
- рџ›ЎпёЏ HSTS Р·Р°РіРѕР»РѕРІРєРё

---

## рџ“Љ Р¤СѓРЅРєС†С–РѕРЅР°Р»

- **Р’РµР±-РїР°РЅРµР»СЊ** вЂ” СЂРµР°Р»СЊРЅРёР№ С‡Р°СЃ, REST API
- **РџСѓР±Р»С–С‡РЅР° СЃС‚РѕСЂС–РЅРєР° СЃС‚Р°С‚СѓСЃСѓ** вЂ” РґР»СЏ РєР»С–С”РЅС‚С–РІ
- **Р†СЃС‚РѕСЂС–СЏ СЃС‚Р°С‚СѓСЃС–РІ** вЂ” 30 РґРЅС–РІ
- **Uptime СЃС‚Р°С‚РёСЃС‚РёРєР°** вЂ” РІС–РґСЃРѕС‚РєРё РґРѕСЃС‚СѓРїРЅРѕСЃС‚С–
- **SSL РґР°С€Р±РѕСЂРґ** вЂ” С‚РµСЂРјС–РЅ РґС–С— СЃРµСЂС‚РёС„С–РєР°С‚С–РІ

---

## вљ™пёЏ РќР°Р»Р°С€С‚СѓРІР°РЅРЅСЏ Р·Р° Р·Р°РјРѕРІС‡СѓРІР°РЅРЅСЏРј

| РџР°СЂР°РјРµС‚СЂ | Р—РЅР°С‡РµРЅРЅСЏ |
|-----------|-------|
| **РџРѕСЂС‚** | 8080 |
| **Р†РЅС‚РµСЂРІР°Р» РїРµСЂРµРІС–СЂРєРё** | 60 СЃРµРєСѓРЅРґ |
| **SSL РїРµСЂРµРІС–СЂРєР°** | РљРѕР¶РЅС– 6 РіРѕРґРёРЅ |
| **SSL СЃРїРѕРІС–С‰РµРЅРЅСЏ** | в‰¤14 РґРЅС–РІ РґРѕ Р·Р°РєС–РЅС‡РµРЅРЅСЏ |
| **Down РїРѕСЂС–Рі** | 1 РЅРµРІРґР°С‡Р° |
| **Up РїРѕСЂС–Рі** | 1 СѓСЃРїС–С… |

---

## рџ› пёЏ РўРµС…РЅРѕР»РѕРіС–С—

- **Backend**: Python 3.9+, FastAPI
- **Database**: SQLite
- **Frontend**: HTML/CSS/JavaScript
- **Monitoring**: aiohttp (async)
- **Notifications**: SMTP, Telegram API, Webhooks

---

## рџ“¦ РњРµС‚РѕРґРё РІСЃС‚Р°РЅРѕРІР»РµРЅРЅСЏ

| РњРµС‚РѕРґ | РџР»Р°С‚С„РѕСЂРјР° | РљРѕРјР°РЅРґР° |
|--------|----------|---------|
| **Git** | Linux | `git clone && cd Uptime-Monitor` |
| **Curl** | Linux | `curl ... \| sudo bash` |
| **Docker** | Р‘СѓРґСЊ-СЏРєР° | `docker run -p 8080:8080 ...` |
| **MSI** | Windows | Р—Р°РІР°РЅС‚Р°Р¶РёС‚Рё Р· Releases |
| **APT** | Debian/Ubuntu | `apt install uptime-monitor` |

---

## рџ”§ РћСЃРЅРѕРІРЅС– РєРѕРјР°РЅРґРё

```bash
# РЈРїСЂР°РІР»С–РЅРЅСЏ СЃР»СѓР¶Р±Р°РјРё
sudo systemctl start|stop|restart|status uptime-monitor
sudo systemctl start|stop|restart|status uptime-monitor-worker

# Р РµР·РµСЂРІРЅРµ РєРѕРїС–СЋРІР°РЅРЅСЏ
sudo /opt/uptime-monitor/scripts/backup-system.sh --dest /backup/

# Р’С–РґРЅРѕРІР»РµРЅРЅСЏ
sudo /opt/uptime-monitor/scripts/restore-system.sh --from /backup/...

# РџРµСЂРµРіР»СЏРґ Р»РѕРіС–РІ
sudo journalctl -u uptime-monitor -f
sudo journalctl -u uptime-monitor-worker -f

# Р”С–Р°РіРЅРѕСЃС‚РёРєР°
sudo /opt/uptime-monitor/check-notifications.sh
```

---

## рџ”Њ API РџСЂРёРєР»Р°РґРё

### Python

```python
import requests

# Р›РѕРіС–РЅ
session = requests.Session()
session.post('http://localhost:8080/login',
             data={'username': 'admin', 'password': 'admin'})

# РћС‚СЂРёРјР°С‚Рё СЃР°Р№С‚Рё
resp = session.get('http://localhost:8080/api/sites')
sites = resp.json()

# Р”РѕРґР°С‚Рё СЃР°Р№С‚
session.post('http://localhost:8080/api/sites', json={
    'name': 'РњС–Р№ РЎР°Р№С‚',
    'url': 'https://mysite.com',
    'check_interval': 60
})
```

### cURL

```bash
# Р›РѕРіС–РЅ
curl -X POST http://localhost:8080/login \
  -d "username=admin&password=admin" -c cookies.txt

# РћС‚СЂРёРјР°С‚Рё СЃР°Р№С‚Рё
curl -X GET http://localhost:8080/api/sites -b cookies.txt
```

Р‘С–Р»СЊС€Рµ РїСЂРёРєР»Р°РґС–РІ: [examples/api_examples.py](examples/api_examples.py)

---

## рџ† РЈСЃСѓРЅРµРЅРЅСЏ РЅРµСЃРїСЂР°РІРЅРѕСЃС‚РµР№

### РЎР»СѓР¶Р±Р° РЅРµ Р·Р°РїСѓСЃРєР°С”С‚СЊСЃСЏ

```bash
# РџРµСЂРµРІС–СЂРёС‚Рё СЃС‚Р°С‚СѓСЃ
sudo systemctl status uptime-monitor

# РџРµСЂРµРіР»СЏРЅСѓС‚Рё Р»РѕРіРё
sudo journalctl -u uptime-monitor -n 50

# РџРµСЂРµР·Р°РїСѓСЃС‚РёС‚Рё
sudo systemctl restart uptime-monitor
```

### РЎРїРѕРІС–С‰РµРЅРЅСЏ РЅРµ РїСЂР°С†СЋСЋС‚СЊ

```bash
# Р—Р°РїСѓСЃС‚РёС‚Рё РґС–Р°РіРЅРѕСЃС‚РёРєСѓ
sudo /opt/uptime-monitor/check-notifications.sh

# РџРµСЂРµРІС–СЂРёС‚Рё РЅР°Р»Р°С€С‚СѓРІР°РЅРЅСЏ РІ Р‘Р”
sudo sqlite3 /var/lib/uptime-monitor/sites.db \
  "SELECT config FROM notify_config WHERE id = 1;" | python3 -m json.tool
```

### РџСЂРѕР±Р»РµРјРё Р· Р±РµРєР°РїРѕРј

Р”РёРІС–С‚СЊСЃСЏ: [docs/BACKUP.md](docs/BACKUP.md)

---

## рџ“€ РџРѕСЂС–РІРЅСЏРЅРЅСЏ

| Р¤СѓРЅРєС†С–СЏ | Uptime Monitor | Uptime.com | Pingdom |
|---------|---------------|------------|---------|
| **Self-hosted** | вњ… РўР°Рє | вќЊ РќС– | вќЊ РќС– |
| **Р‘РµР·РєРѕС€С‚РѕРІРЅРѕ** | вњ… Open-source | вќЊ РџР»Р°С‚РЅРѕ | вќЊ РџР»Р°С‚РЅРѕ |
| **Р‘РµРєР°РїРё** | вњ… Р’Р±СѓРґРѕРІР°РЅС– | вљ пёЏ РћР±РјРµР¶РµРЅРѕ | вљ пёЏ РћР±РјРµР¶РµРЅРѕ |
| **SSL РјРѕРЅС–С‚РѕСЂРёРЅРі** | вњ… РўР°Рє | вњ… РўР°Рє | вњ… РўР°Рє |
| **РЎРїРѕРІС–С‰РµРЅСЊ** | вњ… 6+ РєР°РЅР°Р»С–РІ | вњ… РўР°Рє | вњ… РўР°Рє |
| **РљР°СЃС‚РѕРјС–Р·Р°С†С–СЏ** | вњ… РџРѕРІРЅР° | вќЊ РћР±РјРµР¶РµРЅРѕ | вќЊ РћР±РјРµР¶РµРЅРѕ |

---

## рџ¤ќ Р’РЅРµСЃРѕРє Сѓ РїСЂРѕРµРєС‚

1. Fork СЂРµРїРѕР·РёС‚РѕСЂС–Р№
2. РЎС‚РІРѕСЂС–С‚СЊ РіС–Р»РєСѓ (`git checkout -b feature/amazing`)
3. Р—СЂРѕР±С–С‚СЊ РєРѕРјС–С‚ (`git commit -m 'Р”РѕРґР°РЅРѕ amazing С„СѓРЅРєС†С–СЋ'`)
4. Push (`git push origin feature/amazing`)
5. Р’С–РґРєСЂРёР№С‚Рµ Pull Request

---

## рџ“ќ Р›С–С†РµРЅР·С–СЏ

MIT License вЂ” РґРёРІС–С‚СЊСЃСЏ С„Р°Р№Р» [LICENSE](LICENSE).

---

## рџ‘Ґ РџС–РґС‚СЂРёРјРєР°

- **Issues**: https://github.com/ajjs1ajjs/Uptime-Monitor/issues
- **Discussions**: https://github.com/ajjs1ajjs/Uptime-Monitor/discussions
- **Email**: support@example.com

---

## рџЋЇ Roadmap

### v2.1.0 (Q2 2026)
- [ ] WebSocket РѕРЅРѕРІР»РµРЅРЅСЏ РІ СЂРµР°Р»СЊРЅРѕРјСѓ С‡Р°СЃС–
- [ ] РўРµРјРЅР°/РЎРІС–С‚Р»Р° С‚РµРјР°
- [ ] Р•РєСЃРїРѕСЂС‚ Р·РІС–С‚С–РІ (CSV/PDF)

### v2.2.0 (Q3 2026)
- [ ] РўРµС…РЅС–С‡РЅС– РІС–РєРЅР° РѕР±СЃР»СѓРіРѕРІСѓРІР°РЅРЅСЏ
- [ ] Р‘Р°РіР°С‚РѕРјРѕРІРЅС–СЃС‚СЊ (i18n)
- [ ] РђСѓРґРёС‚ Р»РѕРіС–РІ

### v3.0.0 (Q4 2026)
- [ ] PostgreSQL РїС–РґС‚СЂРёРјРєР°
- [ ] РљР»Р°СЃС‚РµСЂРёР·Р°С†С–СЏ/HA
- [ ] РњРѕР±С–Р»СЊРЅРёР№ РґРѕРґР°С‚РѕРє

---

**в­ђ Р”РѕРґР°Р№С‚Рµ Р·С–СЂРєСѓ СЏРєС‰Рѕ РїСЂРѕРµРєС‚ РєРѕСЂРёСЃРЅРёР№!**

**рџ“ў РџРёС‚Р°РЅРЅСЏ? Р’С–РґРєСЂРёР№С‚Рµ issue Р°Р±Рѕ РїСЂРёС”РґРЅСѓР№С‚РµСЃСЊ РґРѕ РѕР±РіРѕРІРѕСЂРµРЅРЅСЏ!**
