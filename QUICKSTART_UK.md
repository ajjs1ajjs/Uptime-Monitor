# Uptime Monitor вЂ” РЁРІРёРґРєРёР№ СЃС‚Р°СЂС‚

## рџ“¦ Р’СЃС‚Р°РЅРѕРІР»РµРЅРЅСЏ (Linux)

### РЎРїРѕСЃС–Р± 1: Git (СЂРµРєРѕРјРµРЅРґРѕРІР°РЅРѕ)

```bash
# 1. РљР»РѕРЅСѓР№С‚Рµ СЂРµРїРѕР·РёС‚РѕСЂС–Р№
cd /opt
sudo git clone https://github.com/ajjs1ajjs/Uptime-Monitor.git
cd Uptime-Monitor

# 2. РЎС‚РІРѕСЂС–С‚СЊ РєРѕСЂРёСЃС‚СѓРІР°С‡Р°
sudo useradd -r -s /bin/false uptime-monitor

# 3. Р’СЃС‚Р°РЅРѕРІС–С‚СЊ Р·Р°Р»РµР¶РЅРѕСЃС‚С–
sudo apt update && sudo apt install -y python3 python3-pip python3-venv
sudo -u uptime-monitor python3 -m venv venv
sudo -u uptime-monitor venv/bin/pip install -r Uptime_Robot/requirements.txt

# 4. РЎС‚РІРѕСЂС–С‚СЊ Р»РѕРі-С„Р°Р№Р»
sudo touch uptime_monitor.log
sudo chown uptime-monitor:uptime-monitor uptime_monitor.log

# 5. РЎС‚РІРѕСЂС–С‚СЊ symlink
sudo ln -sf Uptime_Robot/main.py main.py
sudo ln -sf Uptime_Robot/ui_templates.py ui_templates.py

# 6. РќР°Р»Р°С€С‚СѓР№С‚Рµ systemd
sudo nano /etc/systemd/system/uptime-monitor.service
```

**Р’РјС–СЃС‚ СЃРµСЂРІС–СЃСѓ:**
```ini
[Unit]
Description=Uptime Monitor Service
After=network.target

[Service]
Type=simple
User=uptime-monitor
Group=uptime-monitor
WorkingDirectory=/opt/Uptime-Monitor
ExecStart=/opt/Uptime-Monitor/venv/bin/python /opt/Uptime-Monitor/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# 7. Р—Р°РїСѓСЃС‚С–С‚СЊ
sudo systemctl daemon-reload
sudo systemctl enable uptime-monitor
sudo systemctl start uptime-monitor
sudo systemctl status uptime-monitor
```

### РЎРїРѕСЃС–Р± 2: Docker

```bash
docker run -d \
  -p 8080:8080 \
  -v uptime-data:/data \
  --name uptime-monitor \
  ghcr.io/ajjs1ajjs/uptime-monitor:latest
```

---

## рџ”„ РћРЅРѕРІР»РµРЅРЅСЏ (РѕРґРЅР° РєРѕРјР°РЅРґР°)

```bash
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash
```

РЎРєСЂРёРїС‚ Р°РІС‚РѕРјР°С‚РёС‡РЅРѕ:
- Р’РёСЏРІР»СЏС” С–СЃРЅСѓСЋС‡Рµ РІСЃС‚Р°РЅРѕРІР»РµРЅРЅСЏ
- Р РѕР±РёС‚СЊ Р±РµРєР°Рї Р‘Р” С‚Р° РєРѕРЅС„С–РіСѓ
- РћРЅРѕРІР»СЋС” РєРѕРґ
- РџРµСЂРµР·Р°РїСѓСЃРєР°С” СЃРµСЂРІС–СЃРё
- Р’РёРІРѕРґРёС‚СЊ С–РЅСЃС‚СЂСѓРєС†С–СЋ Р· РІС–РґРєР°С‚Сѓ, СЏРєС‰Рѕ С‰РѕСЃСЊ РїС–С€Р»Рѕ РЅРµ С‚Р°Рє

---

## рџ› пёЏ РљРѕРјР°РЅРґРё

### РљРµСЂСѓРІР°РЅРЅСЏ СЃРµСЂРІС–СЃРѕРј

```bash
# РЎС‚Р°С‚СѓСЃ
sudo systemctl status uptime-monitor

# РЎС‚Р°СЂС‚/РЎС‚РѕРї/Р РµСЃС‚Р°СЂС‚
sudo systemctl start uptime-monitor
sudo systemctl stop uptime-monitor
sudo systemctl restart uptime-monitor

# Р›РѕРіРё
sudo journalctl -u uptime-monitor -f
tail -f /opt/Uptime-Monitor/uptime_monitor.log

# РџРµСЂРµРІС–СЂРєР° API
curl http://localhost:8080/api/server-time
curl http://localhost:8080/api/sites
```

### РћРЅРѕРІР»РµРЅРЅСЏ

```bash
# РћРґРЅР° РєРѕРјР°РЅРґР° (curl)
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash
```

---

## рџ“Ѓ РЎС‚СЂСѓРєС‚СѓСЂР°

```
/opt/Uptime-Monitor/
в”њв”Ђв”Ђ main.py                    в†’ symlink в†’ Uptime_Robot/main.py
в”њв”Ђв”Ђ ui_templates.py            в†’ symlink в†’ Uptime_Robot/ui_templates.py
в”њв”Ђв”Ђ uptime_monitor.log         # Р›РѕРіРё
в”њв”Ђв”Ђ Uptime_Robot/
в”‚   в”њв”Ђв”Ђ main.py               # API С‚Р° РјР°СЂС€СЂСѓС‚Рё
в”‚   в”њв”Ђв”Ђ ui_templates.py       # HTML С€Р°Р±Р»РѕРЅРё
в”‚   в”њв”Ђв”Ђ monitoring.py         # РњРѕРЅС–С‚РѕСЂРёРЅРі
в”‚   в””в”Ђв”Ђ ...
в”њв”Ђв”Ђ venv/                     # Р’С–СЂС‚СѓР°Р»СЊРЅРµ СЃРµСЂРµРґРѕРІРёС‰Рµ
в””в”Ђв”Ђ docs/                     # Р”РѕРєСѓРјРµРЅС‚Р°С†С–СЏ
```

---

## рџЊђ Р”РѕСЃС‚СѓРї

```
http://YOUR_SERVER_IP:8080/

Login: admin
Password: auto-generated

вљ пёЏ Р—РјС–РЅС–С‚СЊ РїР°СЂРѕР»СЊ РїС–СЃР»СЏ РїРµСЂС€РѕРіРѕ РІС…РѕРґСѓ!
```

---

## рџ“љ Р”РѕРєСѓРјРµРЅС‚Р°С†С–СЏ

- [INSTALL_AND_UPDATE.md](docs/INSTALL_AND_UPDATE.md) вЂ” РџРѕРІРЅР° С–РЅСЃС‚СЂСѓРєС†С–СЏ
- [README.md](README.md) вЂ” Р—Р°РіР°Р»СЊРЅР° С–РЅС„РѕСЂРјР°С†С–СЏ
- [docs/](docs/) вЂ” Р†РЅС€С– РґРѕРєСѓРјРµРЅС‚Рё

---

## рџ† РџСЂРѕР±Р»РµРјРё?

### РЎРµСЂРІС–СЃ РЅРµ Р·Р°РїСѓСЃРєР°С”С‚СЊСЃСЏ

```bash
# РџРµСЂРµРІС–СЂС‚Рµ Р»РѕРіРё
sudo journalctl -u uptime-monitor -n 50 --no-pager

# РЎРїСЂРѕР±СѓР№С‚Рµ РІСЂСѓС‡РЅСѓ
cd /opt/Uptime-Monitor
sudo -u uptime-monitor venv/bin/python main.py
```

### РџРѕРјРёР»РєР° "Permission denied"

```bash
sudo chown -R uptime-monitor:uptime-monitor /opt/Uptime-Monitor
sudo systemctl restart uptime-monitor
```

### Р‘СЂР°СѓР·РµСЂ РїРѕРєР°Р·СѓС” СЃС‚Р°СЂСѓ РІРµСЂСЃС–СЋ

```
Ctrl + Shift + R  (РѕС‡РёСЃС‚РєР° РєРµС€Сѓ)
РђР±Рѕ Ctrl + Shift + N (СЂРµР¶РёРј С–РЅРєРѕРіРЅС–С‚Рѕ)
```

---

**GitHub:** https://github.com/ajjs1ajjs/Uptime-Monitor  
**РћСЃС‚Р°РЅРЅС” РѕРЅРѕРІР»РµРЅРЅСЏ:** 2026-03-17
