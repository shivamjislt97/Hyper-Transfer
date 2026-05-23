# 🚀 Hyper-Transfer

![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

A Telegram bot that downloads files from **MEGA** and uploads them directly to **Google Drive** — with animated progress bars, cancel support, and workspace management.

---

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
- [Docker Setup](#-docker-setup)
- [Backup System](#-backup-system)
- [Restore Guide](#-restore-guide)
- [Environment Variables](#-environment-variables)
- [Folder Structure](#-folder-structure)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Features

- 📥 Download files from MEGA links (megatools + MegaBasterd fallback for quota)
- ☁️ Upload directly to Google Drive via rclone
- 📊 Animated progress bar with speed, ETA, and percentage
- ❌ Cancel any transfer mid-way with one button tap
- 🔁 Reupload workspace files to GDrive without re-downloading
- 🗂️ Workspace manager — list, delete, or clear downloaded files
- 🔒 User allowlist — restrict bot to specific Telegram user IDs
- 🐳 Fully Dockerized with named volumes for persistent data
- 💾 Automated daily backup to Google Drive with 7-day retention

---

## 🏗️ Architecture

```
Telegram User
     │
     ▼
aiogram Bot (Python 3.12)
     │
     ├── megatools / MegaBasterd  ──→  /downloads (workspace volume)
     │                                        │
     └── rclone ──────────────────────────────┘──→  Google Drive
```

Data persisted in two Docker named volumes:
- `hyper-transfer-data` — rclone config, GDrive token, bot logs
- `hyper-transfer-downloads` — active download workspace

---

## 📦 Prerequisites

- Docker & Docker Compose v2
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- A Google account (for GDrive uploads)
- rclone (for backup system — installed automatically in Docker)

---

## ⚡ Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/shivamjislt97/Hyper-Transfer.git
cd Hyper-Transfer

# 2. Create your .env file
cp .env.example .env
# Edit .env and set BOT_TOKEN and ALLOWED_USER_IDS

# 3. Build and start
docker compose up -d --build

# 4. Check logs
docker compose logs -f
```

Open Telegram, find your bot, and send `/start`.

---

## 🐳 Docker Setup

### Build the image

```bash
docker compose build
```

### Start the bot

```bash
docker compose up -d
```

### Stop the bot

```bash
docker compose down
```

### View logs

```bash
docker compose logs -f bot
```

### Set GDrive token inside the bot

Send `/start` → tap **🔑 Change GDrive Token** → paste your OAuth JSON token.

---

## 💾 Backup System

### Configure rclone first

See [`docker-backup/rclone-setup.md`](docker-backup/rclone-setup.md) for a complete step-by-step guide.

### Run a manual backup

```bash
bash docker-backup/backup.sh
```

### Set up automatic daily backup (2:00 AM)

```bash
bash docker-backup/cron-setup.sh install
```

### Remove the cron job

```bash
bash docker-backup/cron-setup.sh remove
```

### Backup folder structure on Google Drive

```
Google Drive/
└── Docker-Backups/
    └── Hyper-Transfer/
        └── 2024-01-15/
            ├── images/
            │   └── hyper-transfer__latest_2024-01-15_02-00-00.tar.gz
            ├── containers/
            │   ├── hyper-transfer-bot_2024-01-15_02-00-00.tar.gz
            │   └── hyper-transfer-bot_2024-01-15_02-00-00.inspect.json
            └── volumes/
                ├── hyper-transfer-data_2024-01-15_02-00-00.tar.gz
                └── hyper-transfer-downloads_2024-01-15_02-00-00.tar.gz
```

Local backups older than 7 days are deleted automatically.

---

## 🔄 Restore Guide

### List available backups

```bash
bash docker-backup/restore.sh list
```

### Restore a specific backup

```bash
bash docker-backup/restore.sh restore 2024-01-15
```

This will:
1. Download the backup from Google Drive
2. Load Docker images via `docker load`
3. Restore named volumes from `.tar.gz` archives
4. Clean up temporary files

After restore, start the bot:

```bash
docker compose up -d
```

---

## 🔧 Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `BOT_TOKEN` | ✅ | — | Telegram bot token from @BotFather |
| `ALLOWED_USER_IDS` | ❌ | (all) | Comma-separated Telegram user IDs |
| `GDRIVE_FOLDER` | ❌ | `mega_transfers` | GDrive destination folder name |
| `RCLONE_REMOTE_NAME` | ❌ | `gdrive` | rclone remote name (must match rclone.conf) |
| `WORKSPACE_PATH` | ❌ | `/app/downloads` | Download workspace path inside container |
| `MAX_WORKSPACE_GB` | ❌ | `50` | Workspace size warning threshold (GB) |
| `MEGABASTERD_JAR_PATH` | ❌ | `/opt/megabasterd/MegaBasterd.jar` | Path to MegaBasterd JAR |
| `PROGRESS_UPDATE_INTERVAL` | ❌ | `2` | Progress bar update interval (seconds) |

---

## 📁 Folder Structure

```
Hyper-Transfer/
├── Dockerfile                  # Multi-stage production image
├── docker-compose.yml          # Services + named volumes
├── .dockerignore
├── .env.example                # Environment variable template
├── README.md
├── main.py                     # Bot entry point
├── config.py                   # Config loader
├── requirements.txt
├── startup.sh                  # Lightning.ai auto-start script
├── handlers/
│   ├── start_handler.py        # /start + main menu
│   ├── mega_handler.py         # MEGA download + upload flow
│   ├── reupload_handler.py     # Reupload workspace files
│   ├── workspace_handler.py    # Workspace manager
│   └── token_handler.py        # GDrive token setup
├── services/
│   └── megabasterd_runner.py   # MegaBasterd quota fallback
├── utils/
│   ├── downloader.py           # megatools wrapper
│   ├── uploader.py             # rclone wrapper
│   ├── size_monitor.py         # Disk-based progress monitor
│   ├── progress_bar.py         # Telegram progress bar renderer
│   ├── workspace_manager.py    # File listing + deletion
│   └── rclone_setup.py         # rclone config writer
├── data/                       # Runtime data (gitignored)
│   ├── rclone.conf
│   ├── token.json
│   └── bot.log
├── docker-backup/
│   ├── backup.sh               # Full backup script
│   ├── restore.sh              # Restore from GDrive
│   ├── cron-setup.sh           # Install/remove cron job
│   └── rclone-setup.md         # rclone configuration guide
└── logs/
    └── .gitkeep
```

---

## 🛠️ Troubleshooting

**Bot not responding after `/start`**
```bash
docker compose logs -f bot
# Check for BOT_TOKEN errors or import errors
```

**`megatools not found` error**
```bash
docker compose build --no-cache
# megatools is installed during image build
```

**rclone upload fails**
```bash
# Test rclone config inside container
docker compose exec bot rclone lsd gdrive:
# If it fails, re-set your GDrive token via the bot's Change GDrive Token button
```

**Progress bar stuck at 0%**
- This is fixed — the bot uses disk file size monitoring, not subprocess output parsing.
- If it still happens, check that the download workspace volume is writable.

**`TelegramConflictError` — two bot instances running**
```bash
docker compose down
docker compose up -d
# Only one instance should run at a time
```

**Backup script: `No project images found`**
```bash
# Make sure the container is running before backup
docker compose up -d
docker ps | grep hyper-transfer
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'Add my feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
