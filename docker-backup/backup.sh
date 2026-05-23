#!/usr/bin/env bash
# backup.sh — Docker backup for Hyper-Transfer project
# Backs up images, containers, and volumes, then uploads to Google Drive via rclone.
#
# Test run (dry-run, no upload):  SKIP_UPLOAD=1 bash backup.sh
# Manual run:                     bash backup.sh
# ─────────────────────────────────────────────────────────────

set -euo pipefail

# ── Config ────────────────────────────────────────────────────
PROJECT_NAME="hyper-transfer"
COMPOSE_FILE="$(cd "$(dirname "$0")/.." && pwd)/docker-compose.yml"
BACKUP_ROOT="/backups"
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive}"
RCLONE_DEST="${RCLONE_REMOTE}:Docker-Backups/Hyper-Transfer"
RETENTION_DAYS=7
LOG_FILE="${BACKUP_ROOT}/backup.log"
SKIP_UPLOAD="${SKIP_UPLOAD:-0}"

# ── Helpers ───────────────────────────────────────────────────
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
die() { log "ERROR: $*"; exit 1; }

# ── Setup dated backup directory ──────────────────────────────
DATE=$(date '+%Y-%m-%d')
TS=$(date '+%Y-%m-%d_%H-%M-%S')
BACKUP_DIR="${BACKUP_ROOT}/${DATE}"
mkdir -p "${BACKUP_DIR}/images" "${BACKUP_DIR}/containers" "${BACKUP_DIR}/volumes"
mkdir -p "$(dirname "$LOG_FILE")"

log "=========================================="
log "Backup started — project: ${PROJECT_NAME}"
log "Destination: ${BACKUP_DIR}"

# ── 1. Image backup ───────────────────────────────────────────
log "--- Backing up Docker images ---"
# Find images belonging to this project (by name prefix or compose label)
IMAGES=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep -E "^${PROJECT_NAME}" || true)
# Also grab images defined in compose file
if [ -f "$COMPOSE_FILE" ]; then
    COMPOSE_IMAGES=$(docker compose -f "$COMPOSE_FILE" images -q 2>/dev/null \
        | xargs -r docker inspect --format '{{.RepoTags}}' \
        | tr -d '[]' | tr ' ' '\n' | grep -v '^$' || true)
    IMAGES=$(printf "%s\n%s" "$IMAGES" "$COMPOSE_IMAGES" | sort -u | grep -v '^$' || true)
fi

if [ -z "$IMAGES" ]; then
    log "No project images found — skipping image backup."
else
    while IFS= read -r img; do
        safe_name=$(echo "$img" | tr '/:' '__')
        out="${BACKUP_DIR}/images/${safe_name}_${TS}.tar.gz"
        log "  Saving image: ${img} → $(basename "$out")"
        docker save "$img" | gzip > "$out"
        log "  Size: $(du -sh "$out" | cut -f1)"
    done <<< "$IMAGES"
fi

# ── 2. Container backup ───────────────────────────────────────
log "--- Backing up running containers ---"
CONTAINERS=$(docker ps --filter "name=${PROJECT_NAME}" --format '{{.Names}}' || true)

if [ -z "$CONTAINERS" ]; then
    log "No running project containers found — skipping container backup."
else
    while IFS= read -r cname; do
        out="${BACKUP_DIR}/containers/${cname}_${TS}.tar.gz"
        meta="${BACKUP_DIR}/containers/${cname}_${TS}.inspect.json"
        log "  Exporting container: ${cname}"
        docker export "$cname" | gzip > "$out"
        docker inspect "$cname" > "$meta"
        log "  Size: $(du -sh "$out" | cut -f1)"
    done <<< "$CONTAINERS"
fi

# ── 3. Volume backup ──────────────────────────────────────────
log "--- Backing up Docker volumes ---"
# Named volumes: hyper-transfer-data, hyper-transfer-downloads
VOLUMES=$(docker volume ls --format '{{.Name}}' | grep "^${PROJECT_NAME}" || true)

if [ -z "$VOLUMES" ]; then
    log "No project volumes found — skipping volume backup."
else
    while IFS= read -r vol; do
        out="${BACKUP_DIR}/volumes/${vol}_${TS}.tar.gz"
        log "  Backing up volume: ${vol}"
        docker run --rm \
            -v "${vol}:/data:ro" \
            -v "${BACKUP_DIR}/volumes:/backup" \
            alpine tar czf "/backup/$(basename "$out")" -C /data .
        log "  Size: $(du -sh "$out" | cut -f1)"
    done <<< "$VOLUMES"
fi

# ── 4. Upload to Google Drive ─────────────────────────────────
if [ "$SKIP_UPLOAD" = "1" ]; then
    log "SKIP_UPLOAD=1 — skipping Google Drive upload."
else
    log "--- Uploading to Google Drive ---"
    if ! command -v rclone &>/dev/null; then
        log "WARNING: rclone not found — skipping upload. Install rclone and configure it."
    else
        if rclone copy "${BACKUP_DIR}" "${RCLONE_DEST}/${DATE}" \
                --log-level INFO \
                --log-file "${LOG_FILE}" 2>&1; then
            log "Upload successful → ${RCLONE_DEST}/${DATE}"
            # Delete local backup after successful upload (keep log)
            rm -rf "${BACKUP_DIR}"
            log "Local backup deleted after successful upload."
        else
            log "WARNING: Upload failed — local backup kept at ${BACKUP_DIR}"
        fi
    fi
fi

# ── 5. Cleanup old local backups ──────────────────────────────
log "--- Cleaning up backups older than ${RETENTION_DAYS} days ---"
find "${BACKUP_ROOT}" -maxdepth 1 -type d -name "????-??-??" \
    -mtime "+${RETENTION_DAYS}" -exec rm -rf {} + 2>/dev/null || true

# ── 6. Summary ────────────────────────────────────────────────
log "=========================================="
log "Backup complete."
if [ -d "$BACKUP_DIR" ]; then
    log "Local backup size: $(du -sh "$BACKUP_DIR" | cut -f1)"
fi
log "Log: ${LOG_FILE}"
