#!/bin/bash
# Скрипт автоматического деплоя свежей версии бота на сервер
# Использование: ./deploy-latest.sh

set -e  # Прервать при любой ошибке

echo "🚀 Starting deployment of sigmatradebot..."
echo "================================================"

# 1. Переход в директорию проекта
cd /opt/sigmatradebot || exit 1
echo "✓ Changed to project directory"

# 2. Переключение origin на новый репозиторий (если ещё не сделано)
CURRENT_REMOTE=$(git remote get-url origin 2>/dev/null || echo "")
if [[ "$CURRENT_REMOTE" != *"sigmatradebot2"* ]]; then
    echo "📡 Updating remote URL to sigmatradebot2..."
    git remote set-url origin https://github.com/Avertenandor/sigmatradebot2.git
    echo "✓ Remote updated"
else
    echo "✓ Remote already set to sigmatradebot2"
fi

# 3. Остановка текущих контейнеров
echo "🛑 Stopping current containers..."
docker compose -f docker-compose.python.yml down || true
echo "✓ Containers stopped"

# 4. Получение последней версии из main
echo "📥 Fetching latest code from main..."
git fetch origin
git checkout main
git reset --hard origin/main
echo "✓ Code updated to latest main"

# 5. Пересборка и запуск контейнеров
echo "🔨 Building and starting containers..."
docker compose -f docker-compose.python.yml up -d --build
echo "✓ Containers built and started"

# 6. Проверка статуса
echo ""
echo "📊 Container status:"
docker compose -f docker-compose.python.yml ps

echo ""
echo "================================================"
echo "✅ Deployment completed successfully!"
echo ""
echo "To view logs, run:"
echo "  docker compose -f docker-compose.python.yml logs -f bot"
echo ""
