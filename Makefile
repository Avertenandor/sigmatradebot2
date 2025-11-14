.PHONY: help build up down restart logs ps clean migrate shell

# Default target
help:
	@echo "SigmaTrade Bot - Python Migration"
	@echo ""
	@echo "Available commands:"
	@echo "  make build      - Build Docker images"
	@echo "  make up         - Start all services"
	@echo "  make down       - Stop all services"
	@echo "  make restart    - Restart all services"
	@echo "  make logs       - View logs (all services)"
	@echo "  make logs-bot   - View bot logs"
	@echo "  make logs-worker - View worker logs"
	@echo "  make ps         - Show running containers"
	@echo "  make clean      - Stop and remove all containers/volumes"
	@echo "  make migrate    - Run database migrations"
	@echo "  make shell-bot  - Open shell in bot container"
	@echo "  make shell-db   - Open PostgreSQL shell"

# Build Docker images
build:
	docker-compose -f docker-compose.python.yml build

# Start all services
up:
	docker-compose -f docker-compose.python.yml up -d

# Stop all services
down:
	docker-compose -f docker-compose.python.yml down

# Restart all services
restart:
	docker-compose -f docker-compose.python.yml restart

# View logs
logs:
	docker-compose -f docker-compose.python.yml logs -f

# View bot logs
logs-bot:
	docker-compose -f docker-compose.python.yml logs -f bot

# View worker logs
logs-worker:
	docker-compose -f docker-compose.python.yml logs -f worker

# View scheduler logs
logs-scheduler:
	docker-compose -f docker-compose.python.yml logs -f scheduler

# Show running containers
ps:
	docker-compose -f docker-compose.python.yml ps

# Clean up (remove containers and volumes)
clean:
	docker-compose -f docker-compose.python.yml down -v
	docker system prune -f

# Run database migrations
migrate:
	docker-compose -f docker-compose.python.yml exec bot alembic upgrade head

# Open shell in bot container
shell-bot:
	docker-compose -f docker-compose.python.yml exec bot /bin/bash

# Open PostgreSQL shell
shell-db:
	docker-compose -f docker-compose.python.yml exec postgres psql -U sigmatrade -d sigmatrade

# Create new migration
migration:
	@read -p "Enter migration message: " msg; \
	docker-compose -f docker-compose.python.yml exec bot alembic revision --autogenerate -m "$$msg"
