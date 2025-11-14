#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting SigmaTrade Bot...${NC}"

# Wait for PostgreSQL
echo -e "${YELLOW}Waiting for PostgreSQL...${NC}"
while ! nc -z postgres 5432; do
  sleep 0.1
done
echo -e "${GREEN}PostgreSQL is ready!${NC}"

# Wait for Redis
echo -e "${YELLOW}Waiting for Redis...${NC}"
while ! nc -z redis 6379; do
  sleep 0.1
done
echo -e "${GREEN}Redis is ready!${NC}"

# Run database migrations (only for bot service)
if [ "$1" = "bot" ]; then
    echo -e "${YELLOW}Running database migrations...${NC}"
    alembic upgrade head
    echo -e "${GREEN}Migrations complete!${NC}"
fi

# Execute command based on argument
case "$1" in
    bot)
        echo -e "${GREEN}Starting Telegram Bot...${NC}"
        exec python -m bot.main
        ;;
    worker)
        echo -e "${GREEN}Starting Dramatiq Worker...${NC}"
        exec dramatiq jobs.worker -p 4 -t 4 --verbose
        ;;
    scheduler)
        echo -e "${GREEN}Starting Task Scheduler...${NC}"
        exec python -m jobs.scheduler
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo "Usage: $0 {bot|worker|scheduler}"
        exit 1
        ;;
esac
