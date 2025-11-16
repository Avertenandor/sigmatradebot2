#!/bin/bash
###############################################################################
# SigmaTrade Bot - Server Deployment Script
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
GIT_REPO="https://github.com/Avertenandor/sigmatradebot.git"

# Banner
echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════╗"
echo "║      SigmaTrade Bot - Server Deployment Script       ║"
echo "║              Execute this ON THE SERVER              ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Step 1: Create project directory
log "Step 1/9: Creating project directory..."
sudo mkdir -p "${PROJECT_PATH}"
sudo chown -R "${USER}:${USER}" "${PROJECT_PATH}"
cd "${PROJECT_PATH}"
log "✅ Directory created: ${PROJECT_PATH}"

# Step 2: Clone or update repository
log "Step 2/9: Cloning/updating repository..."
if [ -d ".git" ]; then
    info "Repository exists, updating..."
    git fetch origin
    git checkout "${GIT_BRANCH}"
    git pull origin "${GIT_BRANCH}"
    log "✅ Repository updated"
else
    info "Cloning repository..."
    git clone -b "${GIT_BRANCH}" "${GIT_REPO}" .
    log "✅ Repository cloned"
fi

# Step 3: Make scripts executable
log "Step 3/9: Making scripts executable..."
chmod +x scripts/*.sh
log "✅ Scripts are executable"

# Step 4: Setup environment
log "Step 4/9: Setting up environment..."
if [ ! -f .env ]; then
    info "Creating .env file..."
    ./scripts/setup-env.sh
    
    echo ""
    warn "⚠️  IMPORTANT: You need to edit .env file and fill in all required variables!"
    echo ""
    info "Required variables:"
    echo "  - TELEGRAM_BOT_TOKEN (from @BotFather)"
    echo "  - DATABASE_URL (PostgreSQL connection string)"
    echo "  - WALLET_PRIVATE_KEY (your wallet private key)"
    echo "  - WALLET_ADDRESS (your wallet address)"
    echo "  - USDT_CONTRACT_ADDRESS (BSC USDT contract)"
    echo "  - RPC_URL (BSC RPC endpoint)"
    echo "  - SYSTEM_WALLET_ADDRESS (system wallet for deposits)"
    echo "  - ADMIN_TELEGRAM_IDS (comma-separated admin IDs)"
    echo ""
    read -p "Press Enter to edit .env file (nano will open)..."
    nano .env
else
    warn ".env file already exists, skipping setup"
    read -p "Do you want to edit .env file? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        nano .env
    fi
fi

# Step 5: Validate environment
log "Step 5/9: Validating environment..."
if python3 scripts/validate-env.py; then
    log "✅ Environment validation passed"
else
    error "❌ Environment validation failed"
    error "Please fix .env file and run this script again"
    exit 1
fi

# Step 6: Setup PostgreSQL database
log "Step 6/9: Setting up PostgreSQL database..."

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    info "Installing PostgreSQL..."
    sudo apt update
    sudo apt install -y postgresql postgresql-contrib
fi

# Start PostgreSQL service
sudo systemctl start postgresql || true
sudo systemctl enable postgresql || true

# Extract database password from .env if available
DB_PASSWORD=$(grep "^DATABASE_URL=" .env | sed 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/' || echo "changeme")

# Create database and user
info "Creating database and user..."
sudo -u postgres psql << EOF
-- Create database if not exists
SELECT 'CREATE DATABASE sigmatradebot' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'sigmatradebot')\gexec

-- Create user if not exists
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'botuser') THEN
        CREATE USER botuser WITH ENCRYPTED PASSWORD '${DB_PASSWORD}';
    END IF;
END
\$\$;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE sigmatradebot TO botuser;
\q
EOF

log "✅ Database setup complete"
warn "⚠️  Make sure DATABASE_URL in .env matches the created database"

# Step 7: Check readiness
log "Step 7/9: Checking deployment readiness..."
if ./scripts/check-readiness.sh; then
    log "✅ All readiness checks passed"
else
    warn "⚠️  Some checks failed, but continuing..."
fi

# Step 8: Build and start Docker containers
log "Step 8/9: Building and starting Docker containers..."

# Check Docker
if ! command -v docker &> /dev/null; then
    error "Docker is not installed!"
    error "Install with: sudo apt install docker.io docker-compose"
    exit 1
fi

# Build images
info "Building Docker images (this may take a few minutes)..."
docker-compose -f docker-compose.python.yml build

# Start services
info "Starting services..."
docker-compose -f docker-compose.python.yml up -d

log "✅ Services started"

# Step 9: Wait and verify
log "Step 9/9: Waiting for services to stabilize..."
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
info "  - Status: docker-compose -f docker-compose.python.yml ps"
info ""
info "Test the bot by sending /start in Telegram"

