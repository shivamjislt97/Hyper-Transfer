#!/usr/bin/env bash
# restore.sh — Restore Hyper-Transfer Docker backup from Google Drive
#
# Usage:
#   bash restore.sh list              — list available backups on GDrive
#   bash restore.sh restore 2024-01-15 — restore a specific date's backup
# ─────────────────────────────────────────────────────────────

set -euo pipefail

RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive}"
RCLONE_SRC="${RCLONE_REMOTE}:Docker-Backups/Hyper-Transfer"
RESTORE_TMP="/tmp/hyper-transfer-restore"
LOG_FILE="/backups/restore.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
die() { log "ERROR: $*"; exit 1; }

mkdir -p "$(dirname "$LOG_FILE")"

# ── Subcommand: list ──────────────────────────────────────────
cmd_list() {
    echo ""
    echo "📦 Available backups on Google Drive:"
    echo "────────────────────────────────────"
    rclone lsd "${RCLONE_SRC}" --format "p" 2>/dev/null \
        | awk '{print NR". "$NF}' \
        || die "Could not list backups. Is rclone configured? Run: rclone config"
    echo ""
}

# ── Subcommand: restore <date> ────────────────────────────────
cmd_restore() {
    local date_str="${1:-}"
    [ -z "$date_str" ] && die "Usage: bash restore.sh restore YYYY-MM-DD"

    log "=========================================="
    log "Starting restore for date: ${date_str}"

    local src="${RCLONE_SRC}/${date_str}"
    local dest="${RESTORE_TMP}/${date_str}"

    # Check backup exists
    rclone lsd "$src" &>/dev/null || die "Backup not found on GDrive: ${src}"

    # Download backup
    log "Downloading backup from GDrive..."
    mkdir -p "$dest"
    rclone copy "$src" "$dest" --log-level INFO
    log "Download complete → ${dest}"

    # ── Restore images ────────────────────────────────────────
    if [ -d "${dest}/images" ] && [ -n "$(ls "${dest}/images/"*.tar.gz 2>/dev/null)" ]; then
        log "--- Restoring Docker images ---"
        for f in "${dest}/images/"*.tar.gz; do
            log "  Loading: $(basename "$f")"
            docker load < <(gzip -dc "$f")
        done
    else
        log "No image backups found — skipping."
    fi

    # ── Restore volumes ───────────────────────────────────────
    if [ -d "${dest}/volumes" ] && [ -n "$(ls "${dest}/volumes/"*.tar.gz 2>/dev/null)" ]; then
        log "--- Restoring Docker volumes ---"
        for f in "${dest}/volumes/"*.tar.gz; do
            # Extract volume name from filename: volname_YYYY-MM-DD_HH-MM-SS.tar.gz
            vol_name=$(basename "$f" | sed 's/_[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}_[0-9]\{2\}-[0-9]\{2\}-[0-9]\{2\}\.tar\.gz//')
            log "  Restoring volume: ${vol_name}"
            docker volume create "$vol_name" 2>/dev/null || true
            docker run --rm \
                -v "${vol_name}:/data" \
                -v "${dest}/volumes:/backup:ro" \
                alpine sh -c "cd /data && tar xzf /backup/$(basename "$f")"
            log "  Volume ${vol_name} restored."
        done
    else
        log "No volume backups found — skipping."
    fi

    # ── Cleanup temp ──────────────────────────────────────────
    rm -rf "$dest"

    log "=========================================="
    log "Restore complete for ${date_str}."
    echo ""
    echo "✅ Restore complete!"
    echo "   Run: docker compose up -d"
}

# ── Entry point ───────────────────────────────────────────────
CMD="${1:-help}"
case "$CMD" in
    list)    cmd_list ;;
    restore) cmd_restore "${2:-}" ;;
    *)
        echo "Usage:"
        echo "  bash restore.sh list                  — list available backups"
        echo "  bash restore.sh restore YYYY-MM-DD    — restore a specific backup"
        ;;
esac
