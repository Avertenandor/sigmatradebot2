#!/bin/bash
###############################################################################
# SigmaTrade Bot - Non-Interactive Server Deployment Script
# Execute this script ON THE SERVER (no user input required)
# Assumes .env is already configured
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
echo "║   SigmaTrade Bot - Non-Interactive Deployment        ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Step 1: Create project directory
log "Step 1/8: Creating project directory..."
sudo mkdir -p "${PROJECT_PATH}"
sudo chown -R "${USER}:${USER}" "${PROJECT_PATH}"
cd "${PROJECT_PATH}"
log "✅ Directory created: ${PROJECT_PATH}"

# Step 2: Clone or update repository
log "Step 2/8: Cloning/updating repository..."
if [ -d ".git" ]; then
    info "Repository exists, updating..."
    git fetch origin
    git checkout "${GIT_BRANCH}" || git checkout -b "${GIT_BRANCH}" --track "origin/${GIT_BRANCH}"
    git pull origin "${GIT_BRANCH}" || true
    log "✅ Repository updated"
else
    info "Cloning repository..."
    git clone -b "${GIT_BRANCH}" "${GIT_REPO}" .
    log "✅ Repository cloned"
fi

# Step 3: Make scripts executable
log "Step 3/8: Making scripts executable..."
chmod +x scripts/*.sh 2>/dev/null || true
log "✅ Scripts are executable"

# Step 4: Setup environment (non-interactive)
log "Step 4/8: Setting up environment..."
if [ ! -f .env ]; then
    info "Creating .env file..."
    cp .env.example .env
    chmod 600 .env
    
    # Generate secrets
    SECRET_KEY=$(openssl rand -hex 32)
    ENCRYPTION_KEY=$(openssl rand -hex 32)
    
    sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY}|" .env
    sed -i "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=${ENCRYPTION_KEY}|" .env
    
    log "✅ .env created with generated secrets"
    warn "⚠️  IMPORTANT: Edit .env file and fill in required variables before continuing!"
    warn "   Required: TELEGRAM_BOT_TOKEN, WALLET_PRIVATE_KEY, etc."
    exit 1
else
    log "✅ .env file exists"
fi

# Step 5: Validate environment
log "Step 5/8: Validating environment..."
if python3 scripts/validate-env.py 2>/dev/null; then
    log "✅ Environment validation passed"
else
    error "❌ Environment validation failed"
    error "Please fix .env file and run this script again"
    exit 1
fi

# Step 6: Setup PostgreSQL database
log "Step 6/8: Setting up PostgreSQL database..."

# Install PostgreSQL if needed
if ! command -v psql &> /dev/null; then
    info "Installing PostgreSQL..."
    sudo apt update -qq
    sudo apt install -y postgresql postgresql-contrib
fi

# Start PostgreSQL
sudo systemctl start postgresql || true
sudo systemctl enable postgresql || true

# Extract password from DATABASE_URL if available
DB_PASSWORD="changeme123"
if grep -q "^DATABASE_URL=" .env; then
    DB_PASSWORD=$(grep "^DATABASE_URL=" .env | sed 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/' || echo "changeme123")
fi

# Create database and user
info "Creating database and user..."
sudo -u postgres psql << EOF 2>/dev/null || true
SELECT 'CREATE DATABASE sigmatradebot' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'sigmatradebot')\gexec
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'botuser') THEN
        CREATE USER botuser WITH ENCRYPTED PASSWORD '${DB_PASSWORD}';
    ELSE
        ALTER USER botuser WITH PASSWORD '${DB_PASSWORD}';
    END IF;
END
\$\$;
GRANT ALL PRIVILEGES ON DATABASE sigmatradebot TO botuser;
\q
EOF

log "✅ Database setup complete"

# Step 7: Build and start Docker containers
log "Step 7/8: Building and starting Docker containers..."

# Check Docker
if ! command -v docker &> /dev/null; then
    error "Docker is not installed!"
    exit 1
fi

# Build images
info "Building Docker images (this may take a few minutes)..."
docker-compose -f docker-compose.python.yml build

# Start services
info "Starting services..."
docker-compose -f docker-compose.python.yml up -d

log "✅ Services started"

# Step 8: Wait and verify
log "Step 8/8: Waiting for services to stabilize..."
sleep 15

info "Container status:"
docker-compose -f docker-compose.python.yml ps

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
echo -e "${GREEN}║           Deployment Complete!                       ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════╝${NC}"
echo ""

log "✅ Bot deployed successfully!"
info ""
info "Useful commands:"
info "  - View bot logs: docker-compose -f docker-compose.python.yml logs -f bot"
info "  - Restart: docker-compose -f docker-compose.python.yml restart"
info "  - Stop: docker-compose -f docker-compose.python.yml down"
info ""
info "Test the bot by sending /start in Telegram"

