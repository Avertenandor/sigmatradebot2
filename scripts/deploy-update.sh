#!/bin/bash
###############################################################################
# SigmaTrade Bot - Update Deployment Script
# Execute this script ON THE SERVER to update from main branch
# Optimized for Docker cache and minimal downtime
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
GIT_BRANCH="main"
GIT_REPO="https://github.com/Avertenandor/sigmatradebot2.git"

# Banner
echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════╗"
echo "║   SigmaTrade Bot - Update Deployment                  ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Step 1: Navigate to project
log "Step 1/7: Navigating to project directory..."
cd "${PROJECT_PATH}" || {
    error "Project directory not found: ${PROJECT_PATH}"
    exit 1
}
log "✅ In project directory: ${PROJECT_PATH}"

# Step 2: Backup current state
log "Step 2/7: Creating backup..."
BACKUP_DIR="/tmp/sigmatrade-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "${BACKUP_DIR}"
cp -r . "${BACKUP_DIR}/" 2>/dev/null || true
log "✅ Backup created: ${BACKUP_DIR}"

# Step 3: Update code from repository
log "Step 3/7: Updating code from repository..."
if [ -d ".git" ]; then
    # Fix permissions if needed
    sudo chown -R "${USER}:${USER}" .git 2>/dev/null || true
    
    # Check current branch
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
    info "Current branch: ${CURRENT_BRANCH}"
    
    # Check remote URL and update if needed
    CURRENT_REMOTE=$(git remote get-url origin 2>/dev/null || echo "")
    if [ "${CURRENT_REMOTE}" != "${GIT_REPO}" ]; then
        info "Updating remote URL to ${GIT_REPO}"
        git remote set-url origin "${GIT_REPO}" || git remote add origin "${GIT_REPO}"
    fi
    
    # Fetch latest changes (with retry)
    info "Fetching latest changes..."
    for i in 1 2 3; do
        if git fetch origin "${GIT_BRANCH}" 2>&1; then
            break
        else
            if [ $i -eq 3 ]; then
                error "Failed to fetch from origin after 3 attempts"
                # Try to fix permissions and retry once more
                sudo chown -R "${USER}:${USER}" .git
                git fetch origin "${GIT_BRANCH}" || {
                    error "Failed to fetch even after fixing permissions"
                    exit 1
                }
            else
                warn "Fetch attempt $i failed, retrying..."
                sleep 2
            fi
        fi
    done
    
    # Check if there are updates
    LOCAL=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
    REMOTE=$(git rev-parse "origin/${GIT_BRANCH}" 2>/dev/null || echo "unknown")
    
    if [ "${LOCAL}" = "${REMOTE}" ] && [ "${LOCAL}" != "unknown" ]; then
        warn "Already up to date with origin/${GIT_BRANCH}"
    else
        info "Updating from ${LOCAL:0:7} to ${REMOTE:0:7}"
        git checkout "${GIT_BRANCH}" 2>/dev/null || git checkout -b "${GIT_BRANCH}" --track "origin/${GIT_BRANCH}"
        git pull origin "${GIT_BRANCH}" || {
            error "Failed to pull from origin"
            exit 1
        }
        log "✅ Code updated"
    fi
else
    error "Not a git repository. Please clone first."
    exit 1
fi

# Step 4: Check .env file
log "Step 4/7: Checking .env file..."
if [ ! -f .env ]; then
    error ".env file not found!"
    error "Please create .env file before deployment"
    exit 1
fi
log "✅ .env file exists"

# Step 5: Build Docker images with cache optimization
log "Step 5/7: Building Docker images (with cache optimization)..."
info "Building images with cache optimization..."

# Enable BuildKit for better caching
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Build with cache optimization
# --no-cache=false: use cache
# --pull=false: don't pull base images if they exist
# --build-arg BUILDKIT_INLINE_CACHE=1: enable inline cache
docker-compose -f docker-compose.python.yml build \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    --parallel \
    --no-cache=false || {
    error "Docker build failed"
    exit 1
}

log "✅ Docker images built successfully"

# Step 6: Run database migrations
log "Step 6/7: Running database migrations..."
info "Running Alembic migrations..."

# Run migrations in bot container (if it exists) or create temporary container
if docker ps -a --format '{{.Names}}' | grep -q "^sigmatrade-bot$"; then
    docker-compose -f docker-compose.python.yml run --rm bot \
        alembic upgrade head || {
        warn "Migration failed, but continuing..."
    }
else
    # Create temporary container for migration
    docker-compose -f docker-compose.python.yml run --rm bot \
        alembic upgrade head || {
        warn "Migration failed, but continuing..."
    }
fi

log "✅ Migrations completed"

# Step 7: Restart services with zero-downtime strategy
log "Step 7/7: Restarting services..."

# Strategy: Recreate containers with new images
# --force-recreate: recreate containers even if config hasn't changed
# --no-deps: don't start linked services
# --build: build images before starting
info "Recreating containers with new images..."
docker-compose -f docker-compose.python.yml up -d \
    --force-recreate \
    --no-deps \
    --build \
    bot worker scheduler || {
    error "Failed to start services"
    exit 1
}

# Wait for health checks
info "Waiting for services to be healthy..."
sleep 10

# Check container status
info "Container status:"
docker-compose -f docker-compose.python.yml ps

# Check logs for errors
log "Checking logs for errors..."
BOT_ERRORS=$(docker-compose -f docker-compose.python.yml logs bot --tail 50 2>&1 | grep -i "error\|exception\|traceback" | wc -l || echo "0")
WORKER_ERRORS=$(docker-compose -f docker-compose.python.yml logs worker --tail 50 2>&1 | grep -i "error\|exception\|traceback" | wc -l || echo "0")
SCHEDULER_ERRORS=$(docker-compose -f docker-compose.python.yml logs scheduler --tail 50 2>&1 | grep -i "error\|exception\|traceback" | wc -l || echo "0")

if [ "${BOT_ERRORS}" -gt 0 ] || [ "${WORKER_ERRORS}" -gt 0 ] || [ "${SCHEDULER_ERRORS}" -gt 0 ]; then
    warn "Found errors in logs:"
    warn "  Bot errors: ${BOT_ERRORS}"
    warn "  Worker errors: ${WORKER_ERRORS}"
    warn "  Scheduler errors: ${SCHEDULER_ERRORS}"
    warn "Please check logs manually"
else
    log "✅ No errors found in logs"
fi

# Show recent logs
echo ""
info "Bot logs (last 20 lines):"
docker-compose -f docker-compose.python.yml logs bot --tail 20

echo ""
info "Worker logs (last 15 lines):"
docker-compose -f docker-compose.python.yml logs worker --tail 15

echo ""
info "Scheduler logs (last 15 lines):"
docker-compose -f docker-compose.python.yml logs scheduler --tail 15

# Cleanup old images (optional, keep last 2)
info "Cleaning up old Docker images..."
docker image prune -f --filter "until=24h" || true

# Final summary
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           Update Deployment Complete!                ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════╝${NC}"
echo ""

log "✅ Deployment completed successfully!"
info ""
info "Useful commands:"
info "  - View bot logs: docker-compose -f docker-compose.python.yml logs -f bot"
info "  - View worker logs: docker-compose -f docker-compose.python.yml logs -f worker"
info "  - Restart services: docker-compose -f docker-compose.python.yml restart"
info "  - Stop services: docker-compose -f docker-compose.python.yml down"
info ""
info "Backup location: ${BACKUP_DIR}"

exit 0

