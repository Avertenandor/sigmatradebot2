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

# Execute command based on argument
case "$1" in
    bot)
        # Validate environment variables (non-blocking - warnings only)
        echo -e "${YELLOW}Validating environment variables...${NC}"
        if [ -f "scripts/validate-env.py" ]; then
            python3 scripts/validate-env.py || {
                VALIDATION_EXIT_CODE=$?
                echo -e "${YELLOW}Environment validation returned warnings (exit code $VALIDATION_EXIT_CODE)${NC}"
                echo -e "${YELLOW}Continuing anyway - settings.py will handle critical validation${NC}"
                # Don't exit - let bot start and handle validation in settings.py
            }
        else
            echo -e "${YELLOW}Environment validation script NOT FOUND (scripts/validate-env.py). Continuing...${NC}"
        fi
        
        # Run database migrations (only for bot service)
        echo -e "${YELLOW}Running database migrations...${NC}"
        if ! alembic upgrade head; then
            echo -e "${RED}Migration failed!${NC}"
            exit 1
        fi
        echo -e "${GREEN}Migrations complete!${NC}"
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
    alembic)
        # Allow direct alembic command execution
        shift
        exec alembic "$@"
        ;;
    python)
        # Allow direct python command execution
        shift
        exec python "$@"
        ;;
    dramatiq)
        # Allow direct dramatiq command execution
        shift
        exec dramatiq "$@"
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo "Usage: $0 {bot|worker|scheduler|alembic|python|dramatiq} [args...]"
        exit 1
        ;;
esac
