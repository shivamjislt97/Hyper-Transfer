#!/usr/bin/env bash
# cron-setup.sh — Install daily cron job for Hyper-Transfer backup
#
# Usage:
#   bash cron-setup.sh install    — install cron job (runs daily at 2:00 AM)
#   bash cron-setup.sh remove     — remove the cron job
#   bash cron-setup.sh run        — run backup manually right now
# ─────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_SCRIPT="${SCRIPT_DIR}/backup.sh"
CRON_MARKER="# hyper-transfer-backup"
CRON_SCHEDULE="0 2 * * *"   # daily at 2:00 AM

[ -f "$BACKUP_SCRIPT" ] || { echo "ERROR: backup.sh not found at ${BACKUP_SCRIPT}"; exit 1; }
chmod +x "$BACKUP_SCRIPT"

cmd_install() {
    # Remove any existing entry first
    crontab -l 2>/dev/null | grep -v "$CRON_MARKER" | crontab - 2>/dev/null || true

    # Add new cron entry
    (crontab -l 2>/dev/null; echo "${CRON_SCHEDULE} bash ${BACKUP_SCRIPT} ${CRON_MARKER}") | crontab -

    echo "✅ Cron job installed:"
    echo "   ${CRON_SCHEDULE} bash ${BACKUP_SCRIPT}"
    echo ""
    echo "   Backup will run automatically every day at 2:00 AM."
    echo "   To run manually: bash cron-setup.sh run"
}

cmd_remove() {
    crontab -l 2>/dev/null | grep -v "$CRON_MARKER" | crontab - 2>/dev/null || true
    echo "✅ Cron job removed."
}

cmd_run() {
    echo "▶ Running backup now..."
    bash "$BACKUP_SCRIPT"
}

CMD="${1:-help}"
case "$CMD" in
    install) cmd_install ;;
    remove)  cmd_remove ;;
    run)     cmd_run ;;
    *)
        echo "Usage:"
        echo "  bash cron-setup.sh install   — install daily 2AM cron job"
        echo "  bash cron-setup.sh remove    — remove cron job"
        echo "  bash cron-setup.sh run       — run backup manually now"
        ;;
esac
