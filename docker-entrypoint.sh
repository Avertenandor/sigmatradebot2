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
        # Validate environment variables
        echo -e "${YELLOW}Validating environment variables...${NC}"
        if [ -f "scripts/validate-env.py" ]; then
            python3 scripts/validate-env.py
            VALIDATION_EXIT_CODE=$?
            if [ $VALIDATION_EXIT_CODE -ne 0 ]; then
                echo -e "${RED}Environment validation FAILED with exit code $VALIDATION_EXIT_CODE${NC}"
                exit $VALIDATION_EXIT_CODE
            else
                echo -e "${GREEN}Environment validation PASSED${NC}"
            fi
        else
            echo -e "${RED}Environment validation script NOT FOUND (scripts/validate-env.py). Failing.${NC}"
            exit 1
        fi
        
        # Run database migrations (only for bot service)
        echo -e "${YELLOW}Running database migrations...${NC}"
        if alembic upgrade head; then
            echo -e "${GREEN}Migrations complete!${NC}"
        else
            MIGRATION_EXIT_CODE=$?
            echo -e "${RED}Migration failed with exit code: ${MIGRATION_EXIT_CODE}${NC}"
            echo -e "${YELLOW}Checking migration status...${NC}"
            alembic current || true
            echo -e "${YELLOW}Attempting to continue anyway...${NC}"
            # In production, you might want to exit here:
            # exit ${MIGRATION_EXIT_CODE}
        fi
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
