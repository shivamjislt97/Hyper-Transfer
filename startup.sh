#!/bin/bash
# ─────────────────────────────────────────────────────────────
# startup.sh — Auto-start Mega → GDrive Bot on Lightning.ai
# Register this in: Plugins → On Start
# ─────────────────────────────────────────────────────────────

BOT_DIR="/teamspace/studios/this_studio/mega_gdrive_bot"
LOG_FILE="$BOT_DIR/data/startup.log"
PID_FILE="$BOT_DIR/data/bot.pid"

# Kill any previously running instance
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[startup] Stopping old bot instance (PID $OLD_PID)..." | tee -a "$LOG_FILE"
        kill "$OLD_PID"
        sleep 2
    fi
fi

# Install Python dependencies if needed
cd "$BOT_DIR"
if [ ! -f ".deps_installed" ]; then
    echo "[startup] Installing Python dependencies..." | tee -a "$LOG_FILE"
    pip install -q -r requirements.txt && touch .deps_installed
fi

# Install system tools if missing
if ! command -v megadl &>/dev/null; then
    echo "[startup] Installing megatools..." | tee -a "$LOG_FILE"
    apt-get install -y -q megatools 2>&1 | tail -3 | tee -a "$LOG_FILE"
fi

if ! command -v rclone &>/dev/null; then
    echo "[startup] Installing rclone..." | tee -a "$LOG_FILE"
    curl -s https://rclone.org/install.sh | bash 2>&1 | tail -3 | tee -a "$LOG_FILE"
fi

# Start the bot in background
echo "[startup] Starting Mega GDrive Bot..." | tee -a "$LOG_FILE"
nohup python "$BOT_DIR/main.py" >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"

echo "✅ Mega GDrive Bot Started! PID: $(cat $PID_FILE)" | tee -a "$LOG_FILE"
