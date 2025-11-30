#!/bin/bash
set -e

# Configuration
PROJECT_DIR="/opt/sigmatradebot"
COMPOSE_FILE="docker-compose.python.yml"
BACKUP_DIR="/opt/sigmatradebot/backups/pre_deploy_$(date +%Y%m%d_%H%M%S)"

echo "==================================================="
echo "🚀 STARTING PRODUCTION DEPLOY: $(date)"
echo "==================================================="

cd $PROJECT_DIR

# 1. Update Code
echo "📥 Fetching latest updates..."
git fetch origin main
git reset --hard origin/main

# 2. Cleanup & Stop
echo "🛑 Stopping current containers..."
docker-compose -f $COMPOSE_FILE down --remove-orphans

echo "🧹 Cleaning Docker artifacts..."
# Remove dangling images to free space
docker image prune -f

# 3. Build & Start
echo "🏗️ Rebuilding containers (No Cache)..."
# Using --no-cache to ensure fresh dependencies
docker-compose -f $COMPOSE_FILE up -d --build --no-cache --force-recreate

# 4. Wait for DB
echo "⏳ Waiting for Database to initialize..."
sleep 10

# 5. Migrations
echo "🗄️ Applying Database Migrations..."
docker-compose -f $COMPOSE_FILE exec -T bot alembic upgrade head

# 6. Verification
echo "✅ Checking container status..."
docker-compose -f $COMPOSE_FILE ps

echo "==================================================="
echo "🎉 DEPLOYMENT COMPLETED SUCCESSFULLY"
echo "==================================================="

