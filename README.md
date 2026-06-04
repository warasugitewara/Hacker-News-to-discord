# Hacker News to Discord

Fetches top articles from Hacker News, translates and summarizes them using Gemini API, saves to local Archive, and notifies via Discord webhook.

## Features

- ✓ Fetches top Hacker News articles from the past 24 hours
- ✓ Translates and summarizes using Gemini 2.0 Flash (latest model)
- ✓ Respects API rate limits
- ✓ Graceful fallback to demo mode if API unavailable
- ✓ Saves digests to local Archive directory
- ✓ Sends translations to Discord via webhook
- ✓ Automatically commits and pushes to GitHub
- ✓ Scheduled daily execution at 07:00 JST via systemd

## Quick Start

### 1. Clone and Setup (First Time)

```bash
cd ~/Hacker-news-to-Discord

# Create virtual environment
python3 -m venv venv

# Install dependencies
venv/bin/pip install --no-user -r requirements.txt
```

### 2. Configure API Keys

```bash
# Create environment file with your API keys
cat > ~/.hacker-news-env << 'EOF'
GEMINI_API_KEY=your-api-key-here
DISCORD_WEBHOOK_URL=your-webhook-url-here
EOF

# Secure the file
chmod 600 ~/.hacker-news-env
```

**Get API Keys:**
- **Gemini API:** https://aistudio.google.com/app/api-keys
- **Discord Webhook:** Discord Server > Settings > Integrations > Webhooks

### 3. Quick Validation

```bash
./setup.sh
```

This will verify:
- ✓ Virtual environment exists
- ✓ API keys are configured
- ✓ Python dependencies are installed

### 4. Test Execution

```bash
./run.sh
```

## Systemd Automated Scheduling

### Install Service Files

```bash
# Copy systemd files (requires sudo)
sudo cp hacker-news.service /etc/systemd/system/
sudo cp hacker-news.timer /etc/systemd/system/

# Reload systemd daemon
sudo systemctl daemon-reload

# Enable and start the timer
sudo systemctl enable --now hacker-news.timer
```

### Verify Status

```bash
# Check timer status
sudo systemctl status hacker-news.timer

# View scheduled timers
sudo systemctl list-timers

# View recent execution logs
sudo journalctl -u hacker-news.service -n 50
```

## File Structure

```
Hacker-news-to-Discord/
├── main.py                  # Main Python script
├── run.sh                   # Execution script with Git automation
├── setup.sh                 # Setup validator and helper
├── requirements.txt         # Python dependencies
├── README.md                # This file
├── hacker-news.service      # systemd service unit
├── hacker-news.timer        # systemd timer unit
├── .env.example             # Example environment template
└── Archive/                 # Directory for daily digests (auto-created)
    └── YYYY-MM-DD.md        # Daily digest markdown files
```
