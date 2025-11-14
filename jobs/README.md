# Background Jobs

Dramatiq-based background task processing with APScheduler for periodic tasks.

## Architecture

```
jobs/
├── broker.py          # Redis broker configuration
├── scheduler.py       # APScheduler periodic task scheduling
├── worker.py          # Dramatiq worker entry point
└── tasks/             # Task definitions
    ├── payment_retry.py          # PART5: Payment retry with exponential backoff
    ├── notification_retry.py     # PART5: Notification retry
    ├── daily_rewards.py          # Daily reward distribution
    └── deposit_monitoring.py     # Blockchain deposit confirmation
```

## Tasks

### PART5 Critical Tasks

**1. Payment Retry** (`payment_retry.py`)
- **Schedule**: Every 1 minute
- **Purpose**: Process failed payments with exponential backoff (1min → 16min)
- **DLQ**: Moves to Dead Letter Queue after 5 attempts
- **Timeout**: 5 minutes

**2. Notification Retry** (`notification_retry.py`)
- **Schedule**: Every 1 minute
- **Purpose**: Retry failed Telegram notifications
- **Backoff**: 1min, 5min, 15min, 1h, 2h (up to 5 attempts)
- **Timeout**: 5 minutes

### Regular Tasks

**3. Deposit Monitoring** (`deposit_monitoring.py`)
- **Schedule**: Every 1 minute
- **Purpose**: Check blockchain for deposit confirmations
- **Confirmations**: 12 blocks on BSC
- **Timeout**: 5 minutes

**4. Daily Rewards** (`daily_rewards.py`)
- **Schedule**: Daily at 00:00 UTC
- **Purpose**: Calculate and distribute daily rewards
- **ROI Cap**: Respects 500% cap for level 1 deposits
- **Timeout**: 10 minutes

## Running

### Start Worker

```bash
# Single process
dramatiq jobs.worker

# Multiple processes (recommended for production)
dramatiq jobs.worker -p 4 -t 4

# With logging
dramatiq jobs.worker -p 4 -t 4 --verbose
```

### Start Scheduler

```bash
python -m jobs.scheduler
```

### Docker Compose

```bash
# Start all services (bot, worker, scheduler, redis, postgres)
docker-compose up -d

# View logs
docker-compose logs -f worker
docker-compose logs -f scheduler
```

## Configuration

Environment variables (see `.env.python.example`):

```env
# Redis (Dramatiq broker)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_token_here

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/dbname

# Blockchain
BSC_RPC_URL=https://bsc-dataseed.binance.org/
USDT_CONTRACT_ADDRESS=0x...
```

## Monitoring

### Dramatiq Dashboard

Install dashboard:
```bash
pip install dramatiq-dashboard
```

Run:
```bash
dramatiq-dashboard --broker jobs.broker:broker
```

Access: http://localhost:7000

### Task Stats

Check task statistics:
```python
from jobs.broker import broker
stats = broker.get_stats()
```

## Error Handling

- All tasks have automatic retry (max 3 attempts)
- Failed tasks are logged with full traceback
- PART5 critical tasks have additional DLQ mechanism
- Scheduler automatically restarts failed jobs

## Testing

Run individual tasks:
```python
from jobs.tasks.payment_retry import process_payment_retries

# Execute immediately
result = process_payment_retries()
print(result)
```

## Production Checklist

- [ ] Set appropriate `DRAMATIQ_PROCESSES` and `DRAMATIQ_THREADS`
- [ ] Configure Redis persistence (AOF or RDB)
- [ ] Set up monitoring/alerting for failed tasks
- [ ] Configure log rotation
- [ ] Set up DLQ monitoring for PART5 critical tasks
- [ ] Test scheduler restart behavior
- [ ] Monitor memory usage of workers
