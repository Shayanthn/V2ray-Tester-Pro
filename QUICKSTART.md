# 🚀 Quick Start Guide

## Prerequisites
- Python 3.11 or higher
- 4GB RAM (8GB recommended)
- Internet connection

## Installation

### Windows (PowerShell)
```powershell
# Run setup script
.\setup.ps1

# Or manually:
pip install -r requirements.txt
# Download xray.exe from https://github.com/XTLS/Xray-core/releases
```

### Linux / macOS
```bash
# Run setup script
chmod +x setup.sh
./setup.sh

# Or manually:
pip3 install -r requirements.txt
# Download xray from https://github.com/XTLS/Xray-core/releases
```

## Configuration

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your settings (optional):
   - Telegram bot token (if you want bot integration)
   - Custom test URLs
   - Concurrency settings

## Usage

### GUI Mode (Default)
```bash
python "v2raytesterpro source.py"
```

### CLI Mode
```bash
python "v2raytesterpro source.py" --cli
```

### Docker
```bash
docker-compose up -d
```

## Directory Structure
```
V2ray-Tester-Pro/
├── v2raytesterpro source.py  # Main application
├── subscription_manager.py   # Subscription generator
├── requirements.txt          # Python dependencies
├── .env.example             # Configuration template
├── Dockerfile               # Docker image
├── docker-compose.yml       # Docker orchestration
├── subscriptions/           # Generated subscriptions (auto-created)
├── logs/                    # Log files (auto-created)
└── README.md               # Full documentation
```

## Output Files

After testing, you'll find:
- `subscriptions/subscription.txt` - Base64 subscription
- `subscriptions/clash.yaml` - Clash configuration
- `subscriptions/configs.json` - Raw V2Ray configs
- `subscriptions/singbox.json` - SingBox configuration
- `results.json` - Test results database

## Import to Clients

### v2rayN / v2rayNG
1. Copy the Base64 subscription URL
2. In the app: Subscription > Subscription Settings > Add
3. Paste the URL and save

### Clash
1. Copy the Clash YAML URL
2. In the app: Profiles > Import > From URL
3. Paste the URL

## Troubleshooting

### Xray not found
Download from https://github.com/XTLS/Xray-core/releases and place in the same directory.

### Import errors
Install missing packages:
```bash
pip install -r requirements.txt
```

### No results
- Check your internet connection
- Adjust `MAX_CONCURRENT_TESTS` in `.env` (try lower value like 20)
- Check firewall settings

## Need Help?

- Full documentation: [README.md](README.md)
- Developer guide: [ROADMAP.md](ROADMAP.md)
- Report issues: https://github.com/YOUR_USERNAME/V2ray-Tester-Pro/issues

---

**Made with ❤️ by Shayan Taherkhani**
