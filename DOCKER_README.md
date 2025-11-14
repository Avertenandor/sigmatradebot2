# Docker Deployment Guide

Complete Docker setup for SigmaTrade Bot (Python Migration).

## Architecture

```
┌─────────────────────────────────────────────────┐
│                 Docker Compose                  │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │
│  │   Bot    │  │  Worker  │  │  Scheduler   │ │
│  │(aiogram) │  │(Dramatiq)│  │(APScheduler) │ │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘ │
│       │             │                │         │
│       └─────────────┴────────────────┘         │
│                     │                          │
│         ┌───────────┴───────────┐              │
│         │                       │              │
│    ┌────▼─────┐          ┌─────▼────┐         │
│    │PostgreSQL│          │  Redis   │         │
│    │(Database)│          │ (Queue)  │         │
│    └──────────┘          └──────────┘         │
│                                                 │
└─────────────────────────────────────────────────┘
```

## Services

### 1. **postgres** - PostgreSQL 15
- Database for all persistent data
- Volume: `postgres_data`
- Port: 5432 (configurable)
- Healthcheck enabled

### 2. **redis** - Redis 7
- Message broker for Dramatiq
- AOF persistence enabled
- Volume: `redis_data`
- Port: 6379 (configurable)
- Healthcheck enabled

### 3. **bot** - Telegram Bot
- aiogram 3.x bot
- Runs migrations on startup
- Auto-restart enabled
- Logs to `./logs/`

### 4. **worker** - Dramatiq Worker
- 4 processes × 4 threads
- Processes background tasks
- Auto-restart enabled
- Logs to `./logs/`

### 5. **scheduler** - APScheduler
- Periodic task scheduling
- Runs PART5 critical tasks every minute
- Daily rewards at 00:00 UTC
- Auto-restart enabled

## Quick Start

### 1. Prerequisites

```bash
# Install Docker and Docker Compose
sudo apt-get update
sudo apt-get install docker.io docker-compose

# Or on Mac
brew install docker docker-compose
```

### 2. Configuration

Copy environment file:
```bash
cp .env.python.example .env
```

Edit `.env` with your settings:
```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Database (will be set by docker-compose)
DATABASE_URL=postgresql+asyncpg://sigmatrade:changeme@postgres:5432/sigmatrade

# Redis (will be set by docker-compose)
REDIS_HOST=redis
REDIS_PORT=6379

# Blockchain
BSC_RPC_URL=https://bsc-dataseed.binance.org/
USDT_CONTRACT_ADDRESS=0x55d398326f99059fF775485246999027B3197955
WALLET_PRIVATE_KEY=your_private_key_here

# Security
SECRET_KEY=your_secret_key_here
```

### 3. Build and Run

Using Makefile (recommended):
```bash
# Build images
make build

# Start all services
make up

# View logs
make logs

# View specific service logs
make logs-bot
make logs-worker
```

Or using docker-compose directly:
```bash
# Build
docker-compose -f docker-compose.python.yml build

# Start
docker-compose -f docker-compose.python.yml up -d

# Logs
docker-compose -f docker-compose.python.yml logs -f
```

### 4. Verify

Check that all services are running:
```bash
make ps
```

Should show:
```
sigmatrade-bot        Up (healthy)
sigmatrade-worker     Up
sigmatrade-scheduler  Up
sigmatrade-postgres   Up (healthy)
sigmatrade-redis      Up (healthy)
```

## Management

### View Logs

```bash
# All services
make logs

# Bot only
make logs-bot

# Worker only
make logs-worker

# Scheduler only
make logs-scheduler

# Follow last 100 lines
docker-compose -f docker-compose.python.yml logs -f --tail=100
```

### Database Operations

```bash
# Run migrations
make migrate

# Create new migration
make migration

# Open PostgreSQL shell
make shell-db

# Backup database
docker-compose -f docker-compose.python.yml exec postgres \
  pg_dump -U sigmatrade sigmatrade > backup.sql

# Restore database
cat backup.sql | docker-compose -f docker-compose.python.yml exec -T postgres \
  psql -U sigmatrade sigmatrade
```

### Container Management

```bash
# Restart all services
make restart

# Restart specific service
docker-compose -f docker-compose.python.yml restart bot

# Stop all services
make down

# Stop and remove volumes
make clean

# Open shell in bot container
make shell-bot

# Execute command in container
docker-compose -f docker-compose.python.yml exec bot python -c "print('Hello')"
```

### Monitoring

```bash
# Container stats (CPU, memory)
docker stats

# Service health
docker-compose -f docker-compose.python.yml ps

# View logs with timestamps
docker-compose -f docker-compose.python.yml logs -f -t
```

## Production Deployment

### 1. Security

Update passwords in `.env`:
```env
POSTGRES_PASSWORD=strong_random_password_here
SECRET_KEY=another_strong_random_key
```

### 2. Persistent Storage

Volumes are automatically created:
- `postgres_data` - Database
- `redis_data` - Redis persistence

Backup regularly:
```bash
# Backup volumes
docker run --rm -v postgres_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/postgres_backup.tar.gz -C /data .
```

### 3. Resource Limits

Edit `docker-compose.python.yml` to add resource limits:
```yaml
services:
  bot:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
```

### 4. Logging

Logs are automatically rotated (max 10MB × 3 files).

For centralized logging, add:
```yaml
logging:
  driver: "syslog"
  options:
    syslog-address: "tcp://your-syslog-server:514"
```

### 5. Monitoring

Install monitoring tools:
```bash
# Prometheus + Grafana
docker-compose -f docker-compose.monitoring.yml up -d
```

### 6. Updates

```bash
# Pull latest code
git pull

# Rebuild and restart
make build
make restart

# Or zero-downtime rolling update
docker-compose -f docker-compose.python.yml up -d --no-deps --build bot
```

## Troubleshooting

### Bot not starting

```bash
# Check logs
make logs-bot

# Check if database is ready
make shell-db

# Check migrations
make migrate

# Restart
docker-compose -f docker-compose.python.yml restart bot
```

### Worker not processing tasks

```bash
# Check logs
make logs-worker

# Check Redis connection
docker-compose -f docker-compose.python.yml exec redis redis-cli ping

# Check queue
docker-compose -f docker-compose.python.yml exec redis redis-cli keys "*"

# Restart worker
docker-compose -f docker-compose.python.yml restart worker
```

### Database connection errors

```bash
# Check postgres health
docker-compose -f docker-compose.python.yml ps postgres

# Check connection from bot
docker-compose -f docker-compose.python.yml exec bot \
  python -c "from app.config.database import engine; import asyncio; asyncio.run(engine.connect())"

# Check DATABASE_URL in .env
cat .env | grep DATABASE_URL
```

### High memory usage

```bash
# Check stats
docker stats

# Restart services
make restart

# Reduce worker threads in docker-compose.python.yml:
command: worker -p 2 -t 2  # Instead of -p 4 -t 4
```

## Development

### Run without Docker

```bash
# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Redis
docker-compose -f docker-compose.python.yml up -d postgres redis

# Run migrations
alembic upgrade head

# Start bot
python -m bot.main

# Start worker (separate terminal)
dramatiq jobs.worker -p 4 -t 4

# Start scheduler (separate terminal)
python -m jobs.scheduler
```

### Hot Reload

For development, mount source code:
```yaml
services:
  bot:
    volumes:
      - ./app:/app/app
      - ./bot:/app/bot
    command: python -m bot.main
```

## Maintenance

### Cleanup

```bash
# Remove old logs
find ./logs -name "*.log" -mtime +7 -delete

# Prune Docker system
docker system prune -a --volumes

# Remove unused images
docker image prune -a
```

### Health Checks

All services have health checks:
```bash
# Check health status
docker-compose -f docker-compose.python.yml ps

# Manual health check
curl -f http://localhost:8000/health || echo "Not healthy"
```

## Support

For issues, check:
1. Service logs: `make logs`
2. Container status: `make ps`
3. Database connection: `make shell-db`
4. Redis connection: `docker-compose exec redis redis-cli ping`

## Next Steps

1. Configure monitoring and alerting
2. Set up automated backups
3. Configure SSL/TLS for production
4. Set up CI/CD pipeline
5. Configure log aggregation (ELK, Loki, etc.)
