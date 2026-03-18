# APT Repository for Uptime Monitor

Ця гілка містить репозиторій APT для Uptime Monitor.

## Використання

```bash
# Add repository
curl -fsSL https://ajjs1ajjs.github.io/Uptime-Monitor/KEY.gpg | sudo gpg --dearmor -o /usr/share/keyrings/uptime-monitor.gpg
echo "deb [signed-by=/usr/share/keyrings/uptime-monitor.gpg] https://ajjs1ajjs.github.io/Uptime-Monitor stable main" | sudo tee /etc/apt/sources.list.d/uptime-monitor.list

# Install
sudo apt update
sudo apt install uptime-monitor
```

## Структура каталогу

```
apt-repo/
├── dists/
│   └── stable/
│       └── main/
│           └── binary-amd64/
│               ├── Packages
│               └── Packages.gz
├── pool/
│   └── main/
│       └── u/
│           └── uptime-monitor/
│               └── uptime-monitor_*.deb
└── README.md
```

## Оновлення

Цей репозиторій автоматично оновлюється GitHub Actions, коли створюється новий випуск.
