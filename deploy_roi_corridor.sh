#!/bin/bash
# Deploy ROI corridor system to server

set -e

echo "🚀 Deploying ROI corridor system..."

# Pull latest changes
echo "📥 Pulling latest code..."
git pull origin main

# Run migration
echo "🗄️ Running database migration..."
docker compose exec -T bot alembic upgrade head

# Rebuild and restart bot
echo "🔄 Rebuilding and restarting bot..."
docker compose up -d --build bot

# Check status
echo "✅ Deployment complete! Checking status..."
docker compose ps bot

echo "📊 Recent logs:"
docker compose logs --tail=50 bot

echo ""
echo "✅ ROI corridor system deployed successfully!"
echo ""
echo "📝 Next steps:"
echo "1. Verify migration applied: docker compose exec bot alembic current"
echo "2. Check logs: docker compose logs -f bot"
echo "3. Test admin interface: /start -> Админ-панель -> Управление депозитами -> Коридоры доходности"

