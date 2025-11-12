#!/bin/bash
###############################################################################
# Deployment Script for SigmaTrade Bot to Google Cloud
# Handles build, test, and deployment to production
###############################################################################

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENVIRONMENT="${1:-production}"
GCP_PROJECT_ID="${GCP_PROJECT_ID:-sigmatrade-bot}"
GCP_REGION="${GCP_REGION:-us-central1}"
GCP_ZONE="${GCP_ZONE:-us-central1-a}"
INSTANCE_NAME="${INSTANCE_NAME:-sigmatrade-bot-prod}"

log() { echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"; }
error() { echo -e "${RED}[$(date +'%H:%M:%S')] ERROR:${NC} $1" >&2; }
warn() { echo -e "${YELLOW}[$(date +'%H:%M:%S')] WARNING:${NC} $1"; }
info() { echo -e "${BLUE}[$(date +'%H:%M:%S')] INFO:${NC} $1"; }

# Banner
echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════╗"
echo "║         SigmaTrade Bot Deployment Script             ║"
echo "║              Environment: ${ENVIRONMENT}                    ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(development|staging|production)$ ]]; then
    error "Invalid environment: ${ENVIRONMENT}"
    error "Valid options: development, staging, production"
    exit 1
fi

# Check if running in CI/CD or manual
if [ -n "${CI:-}" ]; then
    info "Running in CI/CD mode"
    SKIP_PROMPTS=true
else
    info "Running in manual mode"
    SKIP_PROMPTS=false
fi

# Step 1: Pre-flight checks
log "Step 1/10: Running pre-flight checks..."

# Check required commands
REQUIRED_COMMANDS=("git" "docker" "gcloud" "node" "npm")
for cmd in "${REQUIRED_COMMANDS[@]}"; do
    if ! command -v "$cmd" &> /dev/null; then
        error "Required command not found: $cmd"
        exit 1
    fi
done

# Check if .env file exists (only required for development)
if [ "$ENVIRONMENT" = "development" ] && [ ! -f "${PROJECT_ROOT}/.env" ]; then
    error ".env file not found in development mode. Please create it from .env.example"
    exit 1
fi

# In production/staging, secrets should come from Secret Manager or CI/CD variables
if [ "$ENVIRONMENT" != "development" ]; then
    info "Production/Staging mode: Using Google Secret Manager for secrets"
    if [ -f "${PROJECT_ROOT}/.env" ]; then
        warn "⚠️  Local .env file detected in production deploy. Secrets should be in Secret Manager!"
        warn "⚠️  The .env file will NOT be included in the Docker image"
    fi
fi

# Check git status
cd "${PROJECT_ROOT}"
if [ -n "$(git status --porcelain)" ]; then
    warn "You have uncommitted changes:"
    git status --short
    if [ "$SKIP_PROMPTS" = false ]; then
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# Step 2: Install dependencies
log "Step 2/10: Installing dependencies..."
npm ci --production=false

# Step 3: Linting
log "Step 3/10: Running linter..."
if npm run lint; then
    log "Linting passed"
else
    error "Linting failed. Fix errors before deploying."
    exit 1
fi

# Step 4: Type checking
log "Step 4/10: Type checking..."
if npm run build; then
    log "Build successful"
else
    error "Build failed"
    exit 1
fi

# Step 5: Run tests
log "Step 5/10: Running tests..."
if [ "$ENVIRONMENT" = "production" ]; then
    if npm run test; then
        log "Tests passed"
    else
        error "Tests failed. Cannot deploy to production."
        exit 1
    fi
else
    warn "Skipping tests for non-production environment"
fi

# Step 6: Build Docker image
log "Step 6/10: Building Docker image..."
IMAGE_TAG="gcr.io/${GCP_PROJECT_ID}/sigmatrade-bot:${ENVIRONMENT}-$(date +%Y%m%d-%H%M%S)"
LATEST_TAG="gcr.io/${GCP_PROJECT_ID}/sigmatrade-bot:${ENVIRONMENT}-latest"

if docker build -t "${IMAGE_TAG}" -t "${LATEST_TAG}" .; then
    log "Docker image built: ${IMAGE_TAG}"
else
    error "Docker build failed"
    exit 1
fi

# Step 7: Push to Google Container Registry
log "Step 7/10: Pushing to Container Registry..."

# Configure gcloud
gcloud config set project "${GCP_PROJECT_ID}"

# Authenticate Docker with GCR
gcloud auth configure-docker

# Push images
if docker push "${IMAGE_TAG}" && docker push "${LATEST_TAG}"; then
    log "Images pushed to GCR"
else
    error "Failed to push images"
    exit 1
fi

# Step 8: Database migrations
if [ "$ENVIRONMENT" = "production" ]; then
    log "Step 8/10: Running database migrations..."
    warn "This will run migrations on production database!"

    if [ "$SKIP_PROMPTS" = false ]; then
        read -p "Continue with migrations? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            error "Deployment aborted"
            exit 1
        fi
    fi

    # Connect to Cloud SQL and run migrations
    # This requires Cloud SQL Proxy or direct connection
    if npm run migration:run; then
        log "Migrations completed"
    else
        error "Migrations failed!"
        exit 1
    fi
else
    log "Step 8/10: Skipping migrations (not production)"
fi

# Step 9: Deploy to Compute Engine
log "Step 9/10: Deploying to Compute Engine..."

# SSH into instance and update
DEPLOY_SCRIPT="
    set -e
    cd /home/bot/sigmatradebot || exit 1

    echo 'Pulling latest code...'
    git pull origin main

    echo 'Pulling Docker image...'
    docker pull ${LATEST_TAG}

    echo 'Stopping current container...'
    docker-compose stop app || true

    echo 'Starting new container...'
    docker-compose up -d app

    echo 'Cleaning up old images...'
    docker image prune -f

    echo 'Checking health...'
    sleep 10
    curl -f http://localhost:3000/health || exit 1

    echo 'Deployment successful!'
"

if gcloud compute ssh "${INSTANCE_NAME}" \
    --zone="${GCP_ZONE}" \
    --command="${DEPLOY_SCRIPT}"; then
    log "Deployment completed"
else
    error "Deployment failed"
    exit 1
fi

# Step 10: Post-deployment verification
log "Step 10/10: Verifying deployment..."

sleep 15

# Check if service is responding
INSTANCE_IP=$(gcloud compute instances describe "${INSTANCE_NAME}" \
    --zone="${GCP_ZONE}" \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

if curl -f -s "http://${INSTANCE_IP}/health" > /dev/null; then
    log "Health check passed"
else
    error "Health check failed!"
    exit 1
fi

# Success!
echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════════╗"
echo "║           Deployment Completed Successfully!         ║"
echo "║                                                       ║"
echo "║  Environment: ${ENVIRONMENT}                                ║"
echo "║  Image: ${IMAGE_TAG:0:40}...  ║"
echo "║  Instance IP: ${INSTANCE_IP}                          ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Send notification
if [ -n "${ALERT_TELEGRAM_CHAT_ID:-}" ] && [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
    MESSAGE="🚀 Deployment completed%0A%0AEnvironment: ${ENVIRONMENT}%0ATime: $(date '+%Y-%m-%d %H:%M:%S')%0AStatus: SUCCESS"
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${ALERT_TELEGRAM_CHAT_ID}" \
        -d "text=${MESSAGE}" > /dev/null || true
fi

log "All done! 🎉"
exit 0
