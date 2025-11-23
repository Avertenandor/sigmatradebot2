#!/bin/bash
###############################################################################
# Database Backup Script for SigmaTrade Bot
# Performs backup of critical tables and commits to git repository
###############################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration from environment or defaults
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USERNAME="${DB_USERNAME:-botuser}"
DB_PASSWORD="${DB_PASSWORD:-}"
DB_DATABASE="${DB_DATABASE:-sigmatrade}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-90}"
GCS_BACKUP_BUCKET="${GCS_BACKUP_BUCKET:-}"

# Generate timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE_ONLY=$(date +%Y%m%d)
BACKUP_FILE="db_backup_${TIMESTAMP}.sql"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILE}"

# Log function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" >&2
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

log "Starting database backup..."

# Export password for pg_dump
export PGPASSWORD="${DB_PASSWORD}"

# Backup critical tables (stored forever)
CRITICAL_TABLES=(
    "users"
    "deposits"
    "transactions"
    "referrals"
    "referral_earnings"
    "admins"
)

log "Backing up critical tables: ${CRITICAL_TABLES[*]}"

# Build table arguments for pg_dump
TABLE_ARGS=""
for table in "${CRITICAL_TABLES[@]}"; do
    TABLE_ARGS="${TABLE_ARGS} -t ${table}"
done

# Perform backup
if pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USERNAME}" \
    -d "${DB_DATABASE}" \
    ${TABLE_ARGS} \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    > "${BACKUP_PATH}"; then
    log "Database dump created: ${BACKUP_FILE}"
else
    error "Failed to create database dump"
    exit 1
fi

# Unset password
unset PGPASSWORD

# Get file size
BACKUP_SIZE=$(du -h "${BACKUP_PATH}" | cut -f1)
log "Backup size: ${BACKUP_SIZE}"

# Compress backup
log "Compressing backup..."
if gzip -f "${BACKUP_PATH}"; then
    BACKUP_PATH="${BACKUP_PATH}.gz"
    COMPRESSED_SIZE=$(du -h "${BACKUP_PATH}" | cut -f1)
    log "Compressed size: ${COMPRESSED_SIZE}"
else
    warn "Failed to compress backup, continuing with uncompressed file"
fi

# Commit to git repository
log "Committing backup to git..."
cd "${BACKUP_DIR}" || exit 1

# Check if git repo is initialized
if [ ! -d .git ]; then
    warn "Git repository not initialized in ${BACKUP_DIR}"
    warn "Initializing git repository..."
    git init
    git config user.name "SigmaTrade Backup Bot"
    git config user.email "backup@sigmatrade.org"
fi

# Add backup file
git add "$(basename "${BACKUP_PATH}")"

# Create commit
if git commit -m "Backup ${TIMESTAMP} (${COMPRESSED_SIZE:-$BACKUP_SIZE})"; then
    log "Backup committed to local git repository"

    # Push to remote if configured
    if git remote get-url origin &>/dev/null; then
        log "Pushing to remote repository..."
        if git push origin main; then
            log "Backup pushed to remote repository"
        else
            warn "Failed to push to remote repository"
        fi
    else
        warn "No remote repository configured, skipping push"
    fi
else
    warn "Nothing to commit (no changes)"
fi

cd - > /dev/null

# Upload to Google Cloud Storage (if configured)
if [ -n "${GCS_BACKUP_BUCKET}" ]; then
    log "Uploading to Google Cloud Storage..."
    if command -v gsutil &> /dev/null; then
        GCS_PATH="gs://${GCS_BACKUP_BUCKET}/daily/$(basename "${BACKUP_PATH}")"
        if gsutil cp "${BACKUP_PATH}" "${GCS_PATH}"; then
            log "Backup uploaded to ${GCS_PATH}"
        else
            warn "Failed to upload to GCS"
        fi
    else
        warn "gsutil not found, skipping GCS upload"
    fi
fi

# Cleanup old backups (keep retention period)
log "Cleaning up old backups (keeping last ${BACKUP_RETENTION_DAYS} days)..."
find "${BACKUP_DIR}" -name "db_backup_*.sql.gz" -mtime +${BACKUP_RETENTION_DAYS} -delete
find "${BACKUP_DIR}" -name "db_backup_*.sql" -mtime +${BACKUP_RETENTION_DAYS} -delete

REMAINING_BACKUPS=$(find "${BACKUP_DIR}" -name "db_backup_*.sql.gz" -o -name "db_backup_*.sql" | wc -l)
log "Remaining backups: ${REMAINING_BACKUPS}"

# Summary
log "Backup completed successfully!"
log "Backup file: ${BACKUP_PATH}"
log "Timestamp: ${TIMESTAMP}"

# Send notification (optional)
if [ -n "${ALERT_TELEGRAM_CHAT_ID:-}" ] && [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
    MESSAGE="✅ Database backup completed successfully%0A%0ATimestamp: ${TIMESTAMP}%0ASize: ${COMPRESSED_SIZE:-$BACKUP_SIZE}%0AFile: $(basename "${BACKUP_PATH}")"
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${ALERT_TELEGRAM_CHAT_ID}" \
        -d "text=${MESSAGE}" \
        -d "parse_mode=HTML" > /dev/null || warn "Failed to send Telegram notification"
fi

exit 0
