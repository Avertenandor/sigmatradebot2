#!/bin/bash
###############################################################################
# SigmaTrade Bot - Full Deployment Script with Cache Optimization
# Deploys from sigmatradebot2/main branch to GCP server
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

# Configuration from SERVER_ACCESS.md
PROJECT_PATH="/opt/sigmatradebot"
GIT_BRANCH="main"
GIT_REPO="https://github.com/Avertenandor/sigmatradebot2.git"
SERVER_HOST="34.88.234.78"
SERVER_USER="konfu"
INSTANCE_NAME="sigmatrade-20251108-210354"
ZONE="europe-north1-a"
PROJECT_ID="telegram-bot-444304"

# Banner
echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════╗"
echo "║   SigmaTrade Bot - Full Deployment Script             ║"
echo "║   Repository: ${GIT_REPO}  ║"
echo "║   Branch: ${GIT_BRANCH}                                    ║"
echo "║   Server: ${SERVER_HOST}                              ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Step 1: Check SSH connection
log "Step 1/10: Checking SSH connection..."
if ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no "${SERVER_USER}@${SERVER_HOST}" "echo 'SSH OK'" 2>/dev/null; then
    log "✅ SSH connection successful"
else
    error "❌ Cannot connect to server via SSH"
    error "Trying gcloud method..."
    
    # Try gcloud SSH
    if command -v gcloud &> /dev/null; then
        info "Using gcloud compute ssh..."
        GCLOUD_SSH="gcloud compute ssh ${INSTANCE_NAME} --zone=${ZONE} --project=${PROJECT_ID}"
    else
        error "gcloud not found. Please install gcloud CLI or configure SSH keys."
        exit 1
    fi
fi

# Step 2: Execute deployment on server
log "Step 2/10: Executing deployment on server..."

if [ -n "${GCLOUD_SSH:-}" ]; then
    # Use gcloud SSH
    ${GCLOUD_SSH} << 'ENDSSH'
        set -euo pipefail
        cd /opt/sigmatradebot || { echo "Creating directory..."; sudo mkdir -p /opt/sigmatradebot; sudo chown -R konfu:konfu /opt/sigmatradebot; cd /opt/sigmatradebot; }
        
        # Update or clone repository
        if [ -d ".git" ]; then
            echo "📥 Updating repository..."
            git fetch origin
            git checkout main || git checkout -b main --track origin/main
            git pull origin main || true
        else
            echo "📥 Cloning repository..."
            git clone -b main https://github.com/Avertenandor/sigmatradebot2.git .
        fi
        
        # Stop existing containers gracefully
        echo "🛑 Stopping existing containers..."
        docker-compose -f docker-compose.python.yml down || docker compose -f docker-compose.python.yml down || true
        
        # Check .env file
        if [ ! -f .env ]; then
            echo "⚠️  .env file not found! Please create it before deployment."
            exit 1
        fi
        
        # Enable BuildKit for cache optimization
        export DOCKER_BUILDKIT=1
        export COMPOSE_DOCKER_CLI_BUILD=1
        
        # Build Docker images with cache optimization
        echo "🔨 Building Docker images (with cache optimization)..."
        docker-compose -f docker-compose.python.yml build --parallel || \
        docker compose -f docker-compose.python.yml build --parallel
        
        # Run database migrations
        echo "🗄️  Running database migrations..."
        docker-compose -f docker-compose.python.yml run --rm bot alembic upgrade head || \
        docker compose -f docker-compose.python.yml run --rm bot alembic upgrade head || true
        
        # Start services
        echo "🚀 Starting services..."
        docker-compose -f docker-compose.python.yml up -d || \
        docker compose -f docker-compose.python.yml up -d
        
        # Wait for services to stabilize
        echo "⏳ Waiting for services to stabilize..."
        sleep 15
        
        # Show status
        echo "📊 Container status:"
        docker-compose -f docker-compose.python.yml ps || \
        docker compose -f docker-compose.python.yml ps
        
        echo ""
        echo "📋 Bot logs (last 30 lines):"
        docker-compose -f docker-compose.python.yml logs bot | tail -30 || \
        docker compose -f docker-compose.python.yml logs bot | tail -30 || true
ENDSSH
else
    # Use direct SSH
    ssh "${SERVER_USER}@${SERVER_HOST}" << ENDSSH
        set -euo pipefail
        cd ${PROJECT_PATH} || { echo "Creating directory..."; sudo mkdir -p ${PROJECT_PATH}; sudo chown -R ${SERVER_USER}:${SERVER_USER} ${PROJECT_PATH}; cd ${PROJECT_PATH}; }
        
        # Update or clone repository
        if [ -d ".git" ]; then
            echo "📥 Updating repository..."
            git fetch origin
            git checkout ${GIT_BRANCH} || git checkout -b ${GIT_BRANCH} --track origin/${GIT_BRANCH}
            git pull origin ${GIT_BRANCH} || true
        else
            echo "📥 Cloning repository..."
            git clone -b ${GIT_BRANCH} ${GIT_REPO} .
        fi
        
        # Stop existing containers gracefully
        echo "🛑 Stopping existing containers..."
        docker-compose -f docker-compose.python.yml down || docker compose -f docker-compose.python.yml down || true
        
        # Check .env file
        if [ ! -f .env ]; then
            echo "⚠️  .env file not found! Please create it before deployment."
            exit 1
        fi
        
        # Enable BuildKit for cache optimization
        export DOCKER_BUILDKIT=1
        export COMPOSE_DOCKER_CLI_BUILD=1
        
        # Build Docker images with cache optimization
        echo "🔨 Building Docker images (with cache optimization)..."
        docker-compose -f docker-compose.python.yml build --parallel || \
        docker compose -f docker-compose.python.yml build --parallel
        
        # Run database migrations
        echo "🗄️  Running database migrations..."
        docker-compose -f docker-compose.python.yml run --rm bot alembic upgrade head || \
        docker compose -f docker-compose.python.yml run --rm bot alembic upgrade head || true
        
        # Start services
        echo "🚀 Starting services..."
        docker-compose -f docker-compose.python.yml up -d || \
        docker compose -f docker-compose.python.yml up -d
        
        # Wait for services to stabilize
        echo "⏳ Waiting for services to stabilize..."
        sleep 15
        
        # Show status
        echo "📊 Container status:"
        docker-compose -f docker-compose.python.yml ps || \
        docker compose -f docker-compose.python.yml ps
        
        echo ""
        echo "📋 Bot logs (last 30 lines):"
        docker-compose -f docker-compose.python.yml logs bot | tail -30 || \
        docker compose -f docker-compose.python.yml logs bot | tail -30 || true
ENDSSH
fi

# Final summary
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           Deployment Complete!                       ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════╝${NC}"
echo ""

log "✅ Deployment completed successfully!"
info ""
info "Useful commands:"
info "  - View bot logs: ssh ${SERVER_USER}@${SERVER_HOST} 'cd ${PROJECT_PATH} && docker-compose -f docker-compose.python.yml logs -f bot'"
info "  - Restart: ssh ${SERVER_USER}@${SERVER_HOST} 'cd ${PROJECT_PATH} && docker-compose -f docker-compose.python.yml restart'"
info "  - Status: ssh ${SERVER_USER}@${SERVER_HOST} 'cd ${PROJECT_PATH} && docker-compose -f docker-compose.python.yml ps'"

