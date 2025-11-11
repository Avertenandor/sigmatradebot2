#!/bin/bash

################################################################################
# Database Restore Script
#
# This script restores a PostgreSQL database from a backup file with:
# - Multiple restore modes (full, schema-only, data-only)
# - Pre-restore validation
# - Automatic backup before restore (safety)
# - Detailed logging
# - Rollback capability
# - Dry-run mode for testing
#
# Usage:
#   ./scripts/restore-from-backup.sh <backup_file> [options]
#
# Options:
#   --mode MODE           Restore mode: full, schema-only, or data-only (default: full)
#   --target-db NAME      Target database name (default: from env DB_DATABASE)
#   --no-safety-backup    Skip creating safety backup before restore
#   --dry-run             Validate backup without actually restoring
#   --clean               Drop existing database objects before restore
#   --force               Skip all confirmation prompts (DANGEROUS!)
#
# Examples:
#   # Full restore with safety backup
#   ./scripts/restore-from-backup.sh backups/daily/sigmatrade_20250110_120000.sql.gz
#
#   # Dry run to test backup validity
#   ./scripts/restore-from-backup.sh backups/daily/sigmatrade_20250110_120000.sql.gz --dry-run
#
#   # Schema-only restore (for testing)
#   ./scripts/restore-from-backup.sh backups/daily/sigmatrade_20250110_120000.sql.gz --mode schema-only
#
# Environment Variables Required:
#   DB_HOST, DB_PORT, DB_USERNAME, DB_PASSWORD, DB_DATABASE
################################################################################

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ==================== CONFIGURATION ====================

# Load environment variables
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# Backup directory
BACKUP_DIR="${BACKUP_DIR:-./backups}"
LOG_DIR="${BACKUP_DIR}/logs"

# Timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Log file
LOG_FILE="${LOG_DIR}/restore_${TIMESTAMP}.log"

# Parse command line arguments
BACKUP_FILE=""
RESTORE_MODE="full"
TARGET_DB="${DB_DATABASE}"
SAFETY_BACKUP=true
DRY_RUN=false
CLEAN_BEFORE_RESTORE=false
FORCE=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --mode)
      RESTORE_MODE="$2"
      shift 2
      ;;
    --target-db)
      TARGET_DB="$2"
      shift 2
      ;;
    --no-safety-backup)
      SAFETY_BACKUP=false
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --clean)
      CLEAN_BEFORE_RESTORE=true
      shift
      ;;
    --force)
      FORCE=true
      shift
      ;;
    -*)
      echo "Unknown option: $1"
      echo "Usage: $0 <backup_file> [options]"
      exit 1
      ;;
    *)
      BACKUP_FILE="$1"
      shift
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

log_warn() {
  log "WARN" "$@"
}

# ==================== ERROR HANDLING ====================

handle_error() {
  local line_no=$1
  log_error "Restore script failed at line ${line_no}"
  log_error "Check log file: ${LOG_FILE}"
  exit 1
}

trap 'handle_error ${LINENO}' ERR

# ==================== VALIDATION ====================

log_info "Starting database restore process..."

# Check if backup file is provided
if [ -z "${BACKUP_FILE}" ]; then
  log_error "No backup file specified"
  echo "Usage: $0 <backup_file> [options]"
  exit 1
fi

# Check if backup file exists
if [ ! -f "${BACKUP_FILE}" ]; then
  log_error "Backup file not found: ${BACKUP_FILE}"
  exit 1
fi

# Check required environment variables
if [ -z "${DB_HOST:-}" ] || [ -z "${DB_PORT:-}" ] || [ -z "${DB_USERNAME:-}" ] || [ -z "${TARGET_DB:-}" ]; then
  log_error "Missing required environment variables (DB_HOST, DB_PORT, DB_USERNAME, DB_DATABASE or --target-db)"
  exit 1
fi

# Validate restore mode
if [[ ! "${RESTORE_MODE}" =~ ^(full|schema-only|data-only)$ ]]; then
  log_error "Invalid restore mode: ${RESTORE_MODE}"
  log_error "Valid modes: full, schema-only, data-only"
  exit 1
fi

# Check if PostgreSQL tools are available
if ! command -v pg_restore &> /dev/null; then
  log_error "pg_restore command not found. Install PostgreSQL client tools."
  exit 1
fi

if ! command -v psql &> /dev/null; then
  log_error "psql command not found. Install PostgreSQL client tools."
  exit 1
fi

log_info "Configuration:"
log_info "  Backup file: ${BACKUP_FILE}"
log_info "  Target database: ${TARGET_DB}@${DB_HOST}:${DB_PORT}"
log_info "  Restore mode: ${RESTORE_MODE}"
log_info "  Safety backup: ${SAFETY_BACKUP}"
log_info "  Dry run: ${DRY_RUN}"
log_info "  Clean before restore: ${CLEAN_BEFORE_RESTORE}"

# ==================== VALIDATE BACKUP FILE ====================

log_info "Validating backup file..."

# Get backup file size
BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
log_info "Backup file size: ${BACKUP_SIZE}"

# Set password for PostgreSQL commands
export PGPASSWORD="${DB_PASSWORD:-}"

# Test backup file integrity
if ! pg_restore --list "${BACKUP_FILE}" > /dev/null 2>&1; then
  log_error "Backup file is corrupted or invalid: ${BACKUP_FILE}"
  exit 1
fi

log_success "Backup file is valid"

# Get backup metadata
log_info "Backup contents:"
BACKUP_METADATA=$(pg_restore --list "${BACKUP_FILE}" 2>/dev/null | head -20)
echo "${BACKUP_METADATA}" >> "${LOG_FILE}"

# ==================== DRY RUN MODE ====================

if [ "$DRY_RUN" = true ]; then
  log_info "Running in dry-run mode - no changes will be made"

  # List what would be restored
  log_info "Objects that would be restored:"
  pg_restore --list "${BACKUP_FILE}" 2>/dev/null | grep -E "TABLE|SEQUENCE|INDEX|CONSTRAINT" | head -30 | tee -a "${LOG_FILE}"

  log_success "Dry-run completed. Backup file is valid and ready for restore."
  log_info "To perform actual restore, run without --dry-run flag"
  exit 0
fi

# ==================== SAFETY CHECKS ====================

# Check if target database exists
log_info "Checking if target database exists..."
DB_EXISTS=$(psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USERNAME}" -tAc "SELECT 1 FROM pg_database WHERE datname='${TARGET_DB}'" postgres 2>/dev/null || echo "0")

if [ "$DB_EXISTS" = "1" ]; then
  log_warn "Target database '${TARGET_DB}' already exists"

  if [ "$FORCE" = false ]; then
    echo ""
    echo "⚠️  WARNING: This will overwrite the existing database!"
    echo ""
    echo "Database: ${TARGET_DB}"
    echo "Host: ${DB_HOST}:${DB_PORT}"
    echo "Mode: ${RESTORE_MODE}"
    echo ""
    read -p "Are you sure you want to continue? (yes/no): " CONFIRM

    if [ "$CONFIRM" != "yes" ]; then
      log_info "Restore cancelled by user"
      exit 0
    fi
  else
    log_warn "Force mode enabled - skipping confirmation"
  fi
else
  log_info "Target database does not exist - it will be created"
fi

# ==================== SAFETY BACKUP ====================

if [ "$SAFETY_BACKUP" = true ] && [ "$DB_EXISTS" = "1" ]; then
  log_info "Creating safety backup before restore..."

  SAFETY_BACKUP_FILE="${BACKUP_DIR}/safety/sigmatrade_pre_restore_${TIMESTAMP}.sql.gz"
  mkdir -p "${BACKUP_DIR}/safety"

  log_info "Safety backup: ${SAFETY_BACKUP_FILE}"

  # Create safety backup
  pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USERNAME}" \
    -d "${TARGET_DB}" \
    --format=custom \
    --blobs \
    --compress=9 \
    --file="${SAFETY_BACKUP_FILE}" \
    2>> "${LOG_FILE}"

  SAFETY_SIZE=$(du -h "${SAFETY_BACKUP_FILE}" | cut -f1)
  log_success "Safety backup created (size: ${SAFETY_SIZE})"
  log_info "You can restore from this backup if needed: ${SAFETY_BACKUP_FILE}"
fi

# ==================== PREPARE TARGET DATABASE ====================

if [ "$DB_EXISTS" = "1" ]; then
  if [ "$CLEAN_BEFORE_RESTORE" = true ]; then
    log_warn "Dropping and recreating database '${TARGET_DB}'..."

    # Terminate all connections to the database
    psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USERNAME}" -d postgres <<EOF 2>> "${LOG_FILE}"
SELECT pg_terminate_backend(pg_stat_activity.pid)
FROM pg_stat_activity
WHERE pg_stat_activity.datname = '${TARGET_DB}'
  AND pid <> pg_backend_pid();
EOF

    # Drop database
    psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USERNAME}" -d postgres -c "DROP DATABASE IF EXISTS ${TARGET_DB};" 2>> "${LOG_FILE}"
    log_info "Database dropped"

    # Create fresh database
    psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USERNAME}" -d postgres -c "CREATE DATABASE ${TARGET_DB};" 2>> "${LOG_FILE}"
    log_success "Fresh database created"
  else
    log_info "Using existing database (objects will be overwritten)"
  fi
else
  # Create database if it doesn't exist
  log_info "Creating database '${TARGET_DB}'..."
  psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USERNAME}" -d postgres -c "CREATE DATABASE ${TARGET_DB};" 2>> "${LOG_FILE}"
  log_success "Database created"
fi

# ==================== PERFORM RESTORE ====================

log_info "Starting restore operation..."
log_info "This may take several minutes depending on database size..."

START_TIME=$(date +%s)

# Build pg_restore command based on mode
RESTORE_OPTS=(
  -h "${DB_HOST}"
  -p "${DB_PORT}"
  -U "${DB_USERNAME}"
  -d "${TARGET_DB}"
  --verbose
  --no-owner
  --no-privileges
)

# Add mode-specific options
case "${RESTORE_MODE}" in
  schema-only)
    RESTORE_OPTS+=(--schema-only)
    log_info "Restoring schema only (no data)"
    ;;
  data-only)
    RESTORE_OPTS+=(--data-only)
    log_info "Restoring data only (no schema)"
    ;;
  full)
    log_info "Restoring full database (schema + data)"
    ;;
esac

# Perform restore
if pg_restore "${RESTORE_OPTS[@]}" "${BACKUP_FILE}" 2>> "${LOG_FILE}"; then
  END_TIME=$(date +%s)
  DURATION=$((END_TIME - START_TIME))

  log_success "Restore completed successfully in ${DURATION} seconds"
else
  log_error "Restore failed - check log file for details"

  if [ "$SAFETY_BACKUP" = true ] && [ -n "${SAFETY_BACKUP_FILE:-}" ]; then
    log_warn "You can restore from safety backup: ${SAFETY_BACKUP_FILE}"
    log_info "Run: $0 ${SAFETY_BACKUP_FILE} --target-db ${TARGET_DB} --no-safety-backup"
  fi

  exit 1
fi

# ==================== POST-RESTORE VERIFICATION ====================

log_info "Verifying restored database..."

# Check if database has tables
TABLE_COUNT=$(psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USERNAME}" -d "${TARGET_DB}" -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null)

log_info "Restored tables: ${TABLE_COUNT}"

if [ "$TABLE_COUNT" -eq 0 ]; then
  log_error "No tables found in restored database"
  exit 1
fi

# Get row counts for main tables
log_info "Sample row counts:"
for table in users deposits withdrawals transactions referrals; do
  if psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USERNAME}" -d "${TARGET_DB}" -tAc "SELECT 1 FROM information_schema.tables WHERE table_name = '${table}'" 2>/dev/null | grep -q 1; then
    ROW_COUNT=$(psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USERNAME}" -d "${TARGET_DB}" -tAc "SELECT COUNT(*) FROM ${table};" 2>/dev/null)
    log_info "  ${table}: ${ROW_COUNT} rows"
  fi
done

# ==================== CLEANUP ====================

# Clean up old safety backups (keep last 7 days)
log_info "Cleaning up old safety backups..."
if [ -d "${BACKUP_DIR}/safety" ]; then
  DELETED_COUNT=$(find "${BACKUP_DIR}/safety" -name "sigmatrade_pre_restore_*.sql.gz" -type f -mtime +7 -delete -print 2>/dev/null | wc -l)
  log_info "Deleted ${DELETED_COUNT} old safety backup(s)"
fi

# Unset password
unset PGPASSWORD

# ==================== SUMMARY ====================

log_success "============================================"
log_success "Database restore completed successfully!"
log_success "============================================"
log_info "Source backup: $(basename ${BACKUP_FILE})"
log_info "Target database: ${TARGET_DB}"
log_info "Restore mode: ${RESTORE_MODE}"
log_info "Duration: ${DURATION} seconds"
log_info "Tables restored: ${TABLE_COUNT}"
if [ "$SAFETY_BACKUP" = true ] && [ -n "${SAFETY_BACKUP_FILE:-}" ]; then
  log_info "Safety backup: ${SAFETY_BACKUP_FILE}"
fi
log_info "Log file: ${LOG_FILE}"
log_success "============================================"

log_warn "IMPORTANT: After restore, you should:"
log_warn "  1. Verify application functionality"
log_warn "  2. Check data integrity"
log_warn "  3. Update any configuration if needed"
log_warn "  4. Restart the application"

exit 0
