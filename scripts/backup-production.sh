#!/bin/bash

################################################################################
# Production Database Backup Script
#
# This script creates a full backup of the PostgreSQL database with:
# - Timestamped backup files
# - Compression (gzip)
# - Backup verification
# - Automatic rotation (keeps last 30 days + monthly archives)
# - Email notifications on failure
# - Detailed logging
#
# Usage:
#   ./scripts/backup-production.sh [options]
#
# Options:
#   --no-rotation    Skip automatic backup rotation
#   --verify-only    Only verify existing backups, don't create new one
#   --keep-days N    Keep backups for N days (default: 30)
#
# Environment Variables Required:
#   DB_HOST, DB_PORT, DB_USERNAME, DB_PASSWORD, DB_DATABASE
#   BACKUP_DIR (optional, default: ./backups)
#   ADMIN_EMAIL (optional, for failure notifications)
################################################################################

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ==================== CONFIGURATION ====================

# Load environment variables
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# Backup directory
BACKUP_DIR="${BACKUP_DIR:-./backups}"
BACKUP_DAILY_DIR="${BACKUP_DIR}/daily"
BACKUP_MONTHLY_DIR="${BACKUP_DIR}/monthly"

# Backup retention
KEEP_DAYS="${BACKUP_KEEP_DAYS:-30}"  # Keep daily backups for 30 days
KEEP_MONTHLY="${BACKUP_KEEP_MONTHLY:-12}"  # Keep monthly backups for 12 months

# Timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE_MONTHLY=$(date +%Y%m)  # For monthly backups (e.g., 202501)

# Backup filename
BACKUP_FILE="sigmatrade_${TIMESTAMP}.sql.gz"
BACKUP_PATH="${BACKUP_DAILY_DIR}/${BACKUP_FILE}"

# Log file
LOG_DIR="${BACKUP_DIR}/logs"
LOG_FILE="${LOG_DIR}/backup_${TIMESTAMP}.log"

# Parse command line arguments
NO_ROTATION=false
VERIFY_ONLY=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --no-rotation)
      NO_ROTATION=true
      shift
      ;;
    --verify-only)
      VERIFY_ONLY=true
      shift
      ;;
    --keep-days)
      KEEP_DAYS="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--no-rotation] [--verify-only] [--keep-days N]"
      exit 1
      ;;
  esac
done

# ==================== LOGGING ====================

# Create log directory
mkdir -p "${LOG_DIR}"

log() {
  local level="$1"
  shift
  local message="$*"
  local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
  echo "[${timestamp}] [${level}] ${message}" | tee -a "${LOG_FILE}"
}

log_info() {
  log "INFO" "$@"
}

log_error() {
  log "ERROR" "$@"
}

log_success() {
  log "SUCCESS" "$@"
}

# ==================== ERROR HANDLING ====================

send_alert() {
  local subject="$1"
  local message="$2"

  log_error "${message}"

  # Send email if admin email is configured
  if [ -n "${ADMIN_EMAIL:-}" ]; then
    echo "${message}" | mail -s "${subject}" "${ADMIN_EMAIL}" 2>/dev/null || true
  fi

  # TODO: Send Telegram notification to admin
  # Integrate with NotificationService when available
}

handle_error() {
  local line_no=$1
  send_alert "Database Backup Failed" "Backup script failed at line ${line_no}. Check log: ${LOG_FILE}"
  exit 1
}

trap 'handle_error ${LINENO}' ERR

# ==================== VALIDATION ====================

log_info "Starting database backup process..."

# Check required environment variables
if [ -z "${DB_HOST:-}" ] || [ -z "${DB_PORT:-}" ] || [ -z "${DB_USERNAME:-}" ] || [ -z "${DB_DATABASE:-}" ]; then
  send_alert "Database Backup Failed" "Missing required environment variables (DB_HOST, DB_PORT, DB_USERNAME, DB_DATABASE)"
  exit 1
fi

# Check if PostgreSQL tools are available
if ! command -v pg_dump &> /dev/null; then
  send_alert "Database Backup Failed" "pg_dump command not found. Install PostgreSQL client tools."
  exit 1
fi

# Create backup directories
mkdir -p "${BACKUP_DAILY_DIR}"
mkdir -p "${BACKUP_MONTHLY_DIR}"

log_info "Configuration:"
log_info "  Database: ${DB_DATABASE}@${DB_HOST}:${DB_PORT}"
log_info "  Backup directory: ${BACKUP_DIR}"
log_info "  Daily retention: ${KEEP_DAYS} days"
log_info "  Monthly retention: ${KEEP_MONTHLY} months"

# ==================== VERIFY ONLY MODE ====================

if [ "$VERIFY_ONLY" = true ]; then
  log_info "Running in verify-only mode..."

  # Find latest backup
  LATEST_BACKUP=$(find "${BACKUP_DAILY_DIR}" -name "sigmatrade_*.sql.gz" -type f -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)

  if [ -z "${LATEST_BACKUP}" ]; then
    log_error "No backups found to verify"
    exit 1
  fi

  log_info "Verifying latest backup: ${LATEST_BACKUP}"

  # Test decompression
  if gzip -t "${LATEST_BACKUP}" 2>/dev/null; then
    log_success "Backup file integrity verified"
  else
    send_alert "Backup Verification Failed" "Latest backup file is corrupted: ${LATEST_BACKUP}"
    exit 1
  fi

  # Test SQL validity (dry run)
  export PGPASSWORD="${DB_PASSWORD:-}"
  if gunzip -c "${LATEST_BACKUP}" | psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USERNAME}" --single-transaction --set ON_ERROR_STOP=on --dry-run 2>/dev/null; then
    log_success "Backup SQL structure verified"
  else
    log_error "Warning: Could not verify SQL structure (this may be normal if --dry-run is not supported)"
  fi

  log_success "Verification complete"
  exit 0
fi

# ==================== CREATE BACKUP ====================

log_info "Creating database backup..."
log_info "Backup file: ${BACKUP_PATH}"

# Set password for pg_dump
export PGPASSWORD="${DB_PASSWORD:-}"

# Perform backup with compression
# Options:
#   -h: host
#   -p: port
#   -U: username
#   -F c: custom format (for better compression and features)
#   -b: include large objects
#   -v: verbose
#   -f: output file
#   --compress=9: maximum compression

START_TIME=$(date +%s)

pg_dump \
  -h "${DB_HOST}" \
  -p "${DB_PORT}" \
  -U "${DB_USERNAME}" \
  -d "${DB_DATABASE}" \
  --format=custom \
  --blobs \
  --verbose \
  --compress=9 \
  --file="${BACKUP_PATH}.tmp" \
  2>> "${LOG_FILE}"

# Rename from .tmp to final name (atomic operation)
mv "${BACKUP_PATH}.tmp" "${BACKUP_PATH}"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Get backup size
BACKUP_SIZE=$(du -h "${BACKUP_PATH}" | cut -f1)

log_success "Backup created successfully in ${DURATION} seconds"
log_info "Backup size: ${BACKUP_SIZE}"

# Unset password
unset PGPASSWORD

# ==================== VERIFY BACKUP ====================

log_info "Verifying backup integrity..."

# Check if file exists and is not empty
if [ ! -s "${BACKUP_PATH}" ]; then
  send_alert "Database Backup Failed" "Backup file is empty or does not exist: ${BACKUP_PATH}"
  exit 1
fi

# Test backup file integrity using pg_restore
export PGPASSWORD="${DB_PASSWORD:-}"

if pg_restore --list "${BACKUP_PATH}" > /dev/null 2>&1; then
  log_success "Backup integrity verified"
else
  send_alert "Database Backup Failed" "Backup file integrity check failed: ${BACKUP_PATH}"
  exit 1
fi

unset PGPASSWORD

# ==================== MONTHLY BACKUP ====================

# On the first day of the month, create a monthly archive
DAY_OF_MONTH=$(date +%d)

if [ "$DAY_OF_MONTH" = "01" ]; then
  MONTHLY_BACKUP_FILE="sigmatrade_monthly_${DATE_MONTHLY}.sql.gz"
  MONTHLY_BACKUP_PATH="${BACKUP_MONTHLY_DIR}/${MONTHLY_BACKUP_FILE}"

  log_info "Creating monthly backup archive..."
  cp "${BACKUP_PATH}" "${MONTHLY_BACKUP_PATH}"
  log_success "Monthly backup created: ${MONTHLY_BACKUP_FILE}"
fi

# ==================== CLEANUP OLD BACKUPS ====================

if [ "$NO_ROTATION" = false ]; then
  log_info "Cleaning up old backups..."

  # Remove daily backups older than KEEP_DAYS
  log_info "Removing daily backups older than ${KEEP_DAYS} days..."
  DELETED_COUNT=$(find "${BACKUP_DAILY_DIR}" -name "sigmatrade_*.sql.gz" -type f -mtime +${KEEP_DAYS} -delete -print 2>/dev/null | wc -l)
  log_info "Deleted ${DELETED_COUNT} old daily backup(s)"

  # Remove monthly backups older than KEEP_MONTHLY months
  log_info "Removing monthly backups older than ${KEEP_MONTHLY} months..."
  MONTHS_AGO_DATE=$(date -d "${KEEP_MONTHLY} months ago" +%Y%m)
  DELETED_MONTHLY=0

  for file in "${BACKUP_MONTHLY_DIR}"/sigmatrade_monthly_*.sql.gz; do
    if [ -f "$file" ]; then
      # Extract date from filename (format: sigmatrade_monthly_YYYYMM.sql.gz)
      FILE_DATE=$(basename "$file" | sed 's/sigmatrade_monthly_\([0-9]\{6\}\).*/\1/')

      if [ "$FILE_DATE" -lt "$MONTHS_AGO_DATE" ]; then
        rm -f "$file"
        DELETED_MONTHLY=$((DELETED_MONTHLY + 1))
        log_info "Deleted old monthly backup: $(basename $file)"
      fi
    fi
  done

  log_info "Deleted ${DELETED_MONTHLY} old monthly backup(s)"

  # Clean up old log files (keep last 90 days)
  log_info "Cleaning up old log files..."
  DELETED_LOGS=$(find "${LOG_DIR}" -name "backup_*.log" -type f -mtime +90 -delete -print 2>/dev/null | wc -l)
  log_info "Deleted ${DELETED_LOGS} old log file(s)"
fi

# ==================== SUMMARY ====================

log_success "============================================"
log_success "Backup completed successfully!"
log_success "============================================"
log_info "Backup file: ${BACKUP_FILE}"
log_info "Backup size: ${BACKUP_SIZE}"
log_info "Duration: ${DURATION} seconds"
log_info "Log file: ${LOG_FILE}"

# Count current backups
DAILY_COUNT=$(find "${BACKUP_DAILY_DIR}" -name "sigmatrade_*.sql.gz" -type f 2>/dev/null | wc -l)
MONTHLY_COUNT=$(find "${BACKUP_MONTHLY_DIR}" -name "sigmatrade_monthly_*.sql.gz" -type f 2>/dev/null | wc -l)

log_info "Current backups:"
log_info "  Daily: ${DAILY_COUNT} backup(s)"
log_info "  Monthly: ${MONTHLY_COUNT} backup(s)"

# Calculate total backup size
TOTAL_SIZE=$(du -sh "${BACKUP_DIR}" | cut -f1)
log_info "Total backup size: ${TOTAL_SIZE}"

log_success "============================================"

exit 0
