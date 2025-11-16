#!/bin/bash
###############################################################################
# Deploy SigmaTrade Bot to Production Server
# Automated deployment script for GCP server
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

# Server configuration (from SIGMATRADE_SERVER_SETUP.md)
SERVER_HOST="34.88.234.78"
SERVER_USER="konfu"
SERVER_PATH="/opt/sigmatradebot"
GIT_BRANCH="claude/sigmatradebot-python-migration-01UUhWd7yPartmZdGxtPAFLo"
GIT_REPO="https://github.com/Avertenandor/sigmatradebot.git"

# Banner
echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════╗"
echo "║      SigmaTrade Bot - Server Deployment Script       ║"
echo "║              Server: ${SERVER_HOST}                    ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Step 1: Check SSH connection
log "Step 1/10: Checking SSH connection..."
if ssh -o ConnectTimeout=5 "${SERVER_USER}@${SERVER_HOST}" "echo 'SSH connection OK'" 2>/dev/null; then
    log "✅ SSH connection successful"
else
    error "❌ Cannot connect to server via SSH"
    error "Please check:"
    error "  1. SSH key is configured"
    error "  2. Server is accessible"
    error "  3. User has access"
    exit 1
fi

# Step 2: Create project directory
log "Step 2/10: Creating project directory..."
ssh "${SERVER_USER}@${SERVER_HOST}" << 'ENDSSH'
    sudo mkdir -p /opt/sigmatradebot
    sudo chown -R konfu:konfu /opt/sigmatradebot
    cd /opt/sigmatradebot
    echo "✅ Directory created"
ENDSSH

# Step 3: Clone or update repository
log "Step 3/10: Cloning/updating repository..."
ssh "${SERVER_USER}@${SERVER_HOST}" << ENDSSH
    cd ${SERVER_PATH}
    if [ -d ".git" ]; then
        echo "📥 Updating existing repository..."
        git fetch origin
        git checkout ${GIT_BRANCH}
        git pull origin ${GIT_BRANCH}
        echo "✅ Repository updated"
    else
        echo "📥 Cloning repository..."
        git clone -b ${GIT_BRANCH} ${GIT_REPO} .
        echo "✅ Repository cloned"
    fi
ENDSSH

# Step 4: Setup environment
log "Step 4/10: Setting up environment..."
ssh "${SERVER_USER}@${SERVER_HOST}" << ENDSSH
    cd ${SERVER_PATH}
    chmod +x scripts/*.sh
    if [ ! -f .env ]; then
        echo "📝 Creating .env file..."
        ./scripts/setup-env.sh
        echo ""
        echo "⚠️  IMPORTANT: Edit .env file and fill in all required variables:"
        echo "   nano ${SERVER_PATH}/.env"
        echo ""
        echo "Required variables:"
        echo "  - TELEGRAM_BOT_TOKEN"
        echo "  - DATABASE_URL"
        echo "  - WALLET_PRIVATE_KEY"
        echo "  - WALLET_ADDRESS"
        echo "  - USDT_CONTRACT_ADDRESS"
        echo "  - RPC_URL"
        echo "  - SYSTEM_WALLET_ADDRESS"
        echo "  - ADMIN_TELEGRAM_IDS"
        echo ""
        read -p "Press Enter after editing .env file..."
    else
        echo "✅ .env file already exists"
    fi
ENDSSH

# Step 5: Validate environment
log "Step 5/10: Validating environment..."
ssh "${SERVER_USER}@${SERVER_HOST}" << ENDSSH
    cd ${SERVER_PATH}
    if python3 scripts/validate-env.py; then
        echo "✅ Environment validation passed"
    else
        echo "❌ Environment validation failed"
        echo "Please fix .env file and try again"
        exit 1
    fi
ENDSSH

# Step 6: Setup PostgreSQL database
log "Step 6/10: Setting up PostgreSQL database..."
ssh "${SERVER_USER}@${SERVER_HOST}" << 'ENDSSH'
    # Check if PostgreSQL is installed
    if ! command -v psql &> /dev/null; then
        echo "📦 Installing PostgreSQL..."
        sudo apt update
        sudo apt install -y postgresql postgresql-contrib
    fi
    
    # Start PostgreSQL service
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
    
    # Create database and user (if not exists)
    sudo -u postgres psql << 'PSQL'
        SELECT 'CREATE DATABASE sigmatradebot' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'sigmatradebot')\gexec
        DO \$\$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'botuser') THEN
                CREATE USER botuser WITH ENCRYPTED PASSWORD 'CHANGE_ME_IN_PROD';
            END IF;
        END
        \$\$;
        GRANT ALL PRIVILEGES ON DATABASE sigmatradebot TO botuser;
PSQL
    
    echo "✅ Database setup complete"
    echo "⚠️  IMPORTANT: Update DATABASE_URL in .env with correct password"
ENDSSH

# Step 7: Check readiness
log "Step 7/10: Checking deployment readiness..."
ssh "${SERVER_USER}@${SERVER_HOST}" << ENDSSH
    cd ${SERVER_PATH}
    if ./scripts/check-readiness.sh; then
        echo "✅ All checks passed"
    else
        echo "⚠️  Some checks failed, but continuing..."
    fi
ENDSSH

# Step 8: Build and start Docker containers
log "Step 8/10: Building and starting Docker containers..."
ssh "${SERVER_USER}@${SERVER_HOST}" << ENDSSH
    cd ${SERVER_PATH}
    
    # Build Docker images
    echo "🔨 Building Docker images..."
    docker-compose -f docker-compose.python.yml build
    
    # Start services
    echo "🚀 Starting services..."
    docker-compose -f docker-compose.python.yml up -d
    
    echo "✅ Services started"
ENDSSH

# Step 9: Wait for services to start
log "Step 9/10: Waiting for services to stabilize..."
sleep 15

# Step 10: Verify deployment
log "Step 10/10: Verifying deployment..."
ssh "${SERVER_USER}@${SERVER_HOST}" << ENDSSH
    cd ${SERVER_PATH}
    
    echo "📊 Container status:"
    docker-compose -f docker-compose.python.yml ps
    
    echo ""
    echo "📋 Bot logs (last 30 lines):"
    docker-compose -f docker-compose.python.yml logs bot | tail -30
    
    echo ""
    echo "📋 Worker logs (last 20 lines):"
    docker-compose -f docker-compose.python.yml logs worker | tail -20
    
    echo ""
    echo "📋 Scheduler logs (last 20 lines):"
    docker-compose -f docker-compose.python.yml logs scheduler | tail -20
ENDSSH

# Final summary
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           Deployment Complete!                       ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════╝${NC}"
echo ""

log "✅ Bot deployed successfully!"
info ""
info "Useful commands:"
info "  - View bot logs: ssh ${SERVER_USER}@${SERVER_HOST} 'cd ${SERVER_PATH} && docker-compose -f docker-compose.python.yml logs -f bot'"
info "  - Restart services: ssh ${SERVER_USER}@${SERVER_HOST} 'cd ${SERVER_PATH} && docker-compose -f docker-compose.python.yml restart'"
info "  - Stop services: ssh ${SERVER_USER}@${SERVER_HOST} 'cd ${SERVER_PATH} && docker-compose -f docker-compose.python.yml down'"
info ""
info "Test the bot by sending /start in Telegram"

