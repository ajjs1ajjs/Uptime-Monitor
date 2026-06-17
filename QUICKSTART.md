# Uptime Monitor вЂ” Quick Start Guide

## Quick Installation (Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash
```

Access: `http://YOUR_SERVER_IP:8080`
Login: `admin` / Password: `auto-generated`

## Docker

```bash
docker run -d -p 8080:8080 -v uptime-data:/data --name uptime-monitor ghcr.io/ajjs1ajjs/uptime-monitor:latest
```

## Windows

```powershell
# Run as Administrator in Uptime_Robot folder
.\install_service.bat
```

## Update (one command)

```bash
curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash
```

## Documentation

| Document | Description |
|----------|-------------|
| [README.md](README.md) | Main documentation |
| [README_UK.md](README_UK.md) | Ukrainian documentation |
| [docs/API.md](docs/API.md) | API reference |
| [INSTALL.md](INSTALL.md) | Installation guide |
