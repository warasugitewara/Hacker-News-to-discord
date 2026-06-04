# Hacker News to Discord

Fetches top articles from Hacker News, translates and summarizes them using Gemini API, saves to local Archive, and notifies via Discord webhook.

## Setup

### 1. Create Virtual Environment and Install Dependencies

```bash
python3 -m venv venv
venv/bin/pip install --no-user -r requirements.txt
```

Or for Bash users:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file or set these environment variables:

```bash
export GEMINI_API_KEY="your-gemini-api-key"
export DISCORD_WEBHOOK_URL="your-discord-webhook-url"
```

### 3. Make Scripts Executable

```bash
chmod +x run.sh main.py
```

## Manual Execution

Run the script manually:

```bash
./run.sh
```

## Automated Scheduling with systemd

### 1. Set Up Environment File

Create `/home/waras/.hacker-news-env`:

```bash
GEMINI_API_KEY=your-gemini-api-key
DISCORD_WEBHOOK_URL=your-discord-webhook-url
```

Make it readable only by the user:

```bash
chmod 600 /home/waras/.hacker-news-env
```

### 2. Install systemd Service File

Copy the service file (requires sudo):

```bash
sudo cp hacker-news.service /etc/systemd/system/
sudo cp hacker-news.timer /etc/systemd/system/
```

Or use `sudo tee`:

```bash
sudo tee /etc/systemd/system/hacker-news.service > /dev/null <<EOF
[Unit]
Description=Hacker News to Discord Integration
After=network.target

[Service]
Type=oneshot
User=waras
WorkingDirectory=/home/waras/Hacker-news-to-Discord
EnvironmentFile=/home/waras/.hacker-news-env
ExecStart=/home/waras/Hacker-news-to-Discord/run.sh
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/hacker-news.timer > /dev/null <<EOF
[Unit]
Description=Daily Hacker News to Discord at 07:00 JST
Requires=hacker-news.service

[Timer]
OnCalendar=*-*-* 07:00:00 JST
Persistent=true

[Install]
WantedBy=timers.target
EOF
```

### 3. Enable and Start the Timer

```bash
sudo systemctl daemon-reload
sudo systemctl enable hacker-news.timer
sudo systemctl start hacker-news.timer
```

### 4. Verify Status

```bash
sudo systemctl status hacker-news.timer
sudo systemctl list-timers
sudo journalctl -u hacker-news.service -n 50
```

## File Structure

```
Hacker-news-to-Discord/
├── main.py           # Main Python script
├── run.sh            # Execution script with Git automation
├── requirements.txt  # Python dependencies
├── README.md         # This file
├── Archive/          # Directory for archived digests (auto-created)
│   └── YYYY-MM-DD.md # Daily digest markdown files
└── .gitignore        # Git ignore patterns
```

## Features

- ✓ Fetches top Hacker News articles from the past 24 hours
- ✓ Translates and summarizes using Gemini 1.5 Flash
- ✓ Respects API rate limits
- ✓ Saves digests to Archive directory
- ✓ Sends translations to Discord via webhook
- ✓ Automatically pushes to GitHub
- ✓ Scheduled daily execution at 07:00 JST

## Error Handling

- Graceful handling of API failures
- Detailed logging via systemd journal
- Non-blocking Discord notification (continues even if webhook fails)
- Git push failures are reported but don't block execution

## Notes

- Uses Gemini 1.5 Flash (free tier compatible)
- Discord messages are split if they exceed 2000 characters
- Archives are stored in Markdown format with timestamps
- Requires active internet connection for API calls
