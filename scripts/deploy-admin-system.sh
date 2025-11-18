#!/bin/bash
###############################################################################
# Deploy Admin Management System Updates
# Execute this script ON THE SERVER after connecting via SSH
###############################################################################

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"; }
error() { echo -e "${RED}[$(date +'%H:%M:%S')] ERROR:${NC} $1" >&2; }
warn() { echo -e "${YELLOW}[$(date +'%H:%M:%S')] WARNING:${NC} $1"; }
info() { echo -e "${BLUE}[$(date +'%H:%M:%S')] INFO:${NC} $1"; }

# Configuration
PROJECT_PATH="/opt/sigmatradebot"
GIT_BRANCH="claude/sigmatradebot-python-migration-01UUhWd7yPartmZdGxtPAFLo"

# Banner
echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════╗"
echo "║    Deploy Admin Management System Updates           ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Step 1: Navigate to project
log "Step 1/6: Navigating to project directory..."
cd "${PROJECT_PATH}" || {
    error "Project directory not found: ${PROJECT_PATH}"
    exit 1
}
log "✅ In project directory: ${PROJECT_PATH}"

# Step 2: Update code from repository
log "Step 2/6: Updating code from repository..."
if [ -d ".git" ]; then
    info "Fetching latest changes..."
    git fetch origin
    
    info "Checking out branch: ${GIT_BRANCH}"
    git checkout "${GIT_BRANCH}" || warn "Already on branch ${GIT_BRANCH}"
    
    info "Pulling latest changes..."
    git pull origin "${GIT_BRANCH}"
    log "✅ Code updated"
else
    error "Not a git repository!"
    exit 1
fi

# Step 3: Check for new migration
log "Step 3/6: Checking for new migrations..."
MIGRATION_FILE="alembic/versions/20250113_000001_create_admin_actions_table.py"
if [ -f "${MIGRATION_FILE}" ]; then
    log "✅ Migration file found: ${MIGRATION_FILE}"
else
    error "Migration file not found: ${MIGRATION_FILE}"
    exit 1
fi

# Step 4: Apply database migration
log "Step 4/6: Applying database migration..."
warn "⚠️  This will run migrations on production database!"

# Check if running in Docker
if docker-compose -f docker-compose.python.yml ps bot > /dev/null 2>&1; then
    info "Running migration through Docker container..."
    docker-compose -f docker-compose.python.yml exec -T bot alembic upgrade head || {
        error "Migration failed!"
        exit 1
    }
else
    info "Running migration locally..."
    if command -v alembic &> /dev/null; then
        alembic upgrade head || {
            error "Migration failed!"
            exit 1
        }
    else
        error "Alembic not found! Cannot run migration."
        exit 1
    fi
fi

log "✅ Migration applied successfully"

# Step 5: Verify migration
log "Step 5/6: Verifying migration..."
if docker-compose -f docker-compose.python.yml ps bot > /dev/null 2>&1; then
    CURRENT_REV=$(docker-compose -f docker-compose.python.yml exec -T bot alembic current 2>/dev/null | head -1 | awk '{print $1}' || echo "")
else
    CURRENT_REV=$(alembic current 2>/dev/null | head -1 | awk '{print $1}' || echo "")
fi

if [[ "${CURRENT_REV}" == *"20250113_000001"* ]]; then
    log "✅ Migration verified: ${CURRENT_REV}"
else
    warn "⚠️  Could not verify migration, but continuing..."
fi

# Step 6: Rebuild and restart services
log "Step 6/6: Rebuilding and restarting services..."

info "Stopping services..."
docker-compose -f docker-compose.python.yml stop || warn "Some services may not have been running"

info "Building Docker images (this may take a few minutes)..."
docker-compose -f docker-compose.python.yml build --no-cache bot worker scheduler || {
    error "Docker build failed!"
    exit 1
}

info "Starting services..."
docker-compose -f docker-compose.python.yml up -d || {
    error "Failed to start services!"
    exit 1
}

log "✅ Services restarted"

# Wait for services to stabilize
info "Waiting for services to stabilize..."
sleep 15

# Show status
info "Container status:"
docker-compose -f docker-compose.python.yml ps

# Show logs
echo ""
info "Bot logs (last 30 lines):"
docker-compose -f docker-compose.python.yml logs bot | tail -30

echo ""
info "Worker logs (last 20 lines):"
docker-compose -f docker-compose.python.yml logs worker | tail -20

echo ""
info "Scheduler logs (last 20 lines):"
docker-compose -f docker-compose.python.yml logs scheduler | tail -20

# Final summary
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Admin Management System Deployed!                ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════╝${NC}"
echo ""

log "✅ Deployment complete!"
info ""
info "Next steps:"
info "  1. Test admin panel: Send /admin in Telegram"
info "  2. Check admin_actions table: SELECT * FROM admin_actions LIMIT 5;"
info "  3. Monitor logs: docker-compose -f docker-compose.python.yml logs -f bot"
info ""
warn "⚠️  IMPORTANT: All admins will need to enter master key on first login!"

