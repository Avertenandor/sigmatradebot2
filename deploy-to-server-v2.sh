#!/bin/bash

# 🚀 Скрипт адекватного деплоя с очисткой Docker кеша (v2 - для Docker Compose v2)
# Дата: 2025-01-16

set -e  # Остановка при ошибке

echo "========================================="
echo "🚀 Деплой SigmaTrade Bot с очисткой кеша"
echo "========================================="
echo ""

# Переходим в директорию проекта
cd /opt/sigmatradebot || exit 1
echo "✅ Перешли в /opt/sigmatradebot"

# Pull последних изменений из GitHub
echo ""
echo "📥 Получаем обновления из GitHub..."
git fetch origin main
git reset --hard origin/main
echo "✅ Код обновлен до последней версии"

# Останавливаем контейнеры (Docker Compose v2)
echo ""
echo "🛑 Останавливаем текущие контейнеры..."
docker compose -f docker-compose.python.yml down --remove-orphans || true
echo "✅ Контейнеры остановлены"

# Удаляем старые образы sigmatradebot
echo ""
echo "🗑️  Удаляем старые образы..."
docker images | grep sigmatradebot | awk '{print $3}' | xargs -r docker rmi -f || true
echo "✅ Старые образы удалены"

# Очищаем неиспользуемые образы и контейнеры
echo ""
echo "🧹 Очищаем неиспользуемые ресурсы Docker..."
docker system prune -f || true
echo "✅ Неиспользуемые ресурсы очищены"

# Очищаем build cache Docker
echo ""
echo "🧹 Очищаем Docker build cache..."
docker builder prune -af || true
echo "✅ Build cache очищен"

# Пересобираем образы с нуля (--no-cache) - Docker Compose v2
echo ""
echo "🔨 Пересобираем образы (--no-cache)..."
docker compose -f docker-compose.python.yml build --no-cache --pull
echo "✅ Образы пересобраны с нуля"

# Запускаем контейнеры - Docker Compose v2
echo ""
echo "🚀 Запускаем контейнеры..."
docker compose -f docker-compose.python.yml up -d
echo "✅ Контейнеры запущены"

# Ждем 10 секунд для инициализации
echo ""
echo "⏳ Ждем 10 секунд для инициализации..."
sleep 10

# Показываем статус контейнеров
echo ""
echo "📊 Статус контейнеров:"
docker compose -f docker-compose.python.yml ps
echo ""

# Показываем последние логи всех сервисов
echo ""
echo "📝 Последние логи bot (15 строк):"
docker compose -f docker-compose.python.yml logs --tail=15 bot
echo ""

echo ""
echo "📝 Последние логи worker (15 строк):"
docker compose -f docker-compose.python.yml logs --tail=15 worker
echo ""

echo ""
echo "📝 Последние логи scheduler (15 строк):"
docker compose -f docker-compose.python.yml logs --tail=15 scheduler
echo ""

echo "========================================="
echo "✅ Деплой успешно завершен!"
echo "========================================="
echo ""
echo "Для просмотра логов в реальном времени:"
echo "  docker compose -f docker-compose.python.yml logs -f bot"
echo "  docker compose -f docker-compose.python.yml logs -f worker"
echo "  docker compose -f docker-compose.python.yml logs -f scheduler"
echo ""
echo "Для проверки статуса:"
echo "  docker compose -f docker-compose.python.yml ps"
echo ""
echo "Для просмотра использования ресурсов:"
echo "  docker stats"
echo ""

