# Deployment Guide - Phase 1-7 Refactoring

## Quick Start

**Estimated Deployment Time:** 25-30 minutes
**Estimated Downtime:** 20-25 minutes
**Rollback Time:** 10 minutes (if needed)

---

## Pre-Deployment Requirements

### System Requirements
- Node.js 20+
- PostgreSQL 15+
- Redis 7+
- 2GB RAM minimum
- 10GB disk space

### Access Requirements
- [ ] SSH access to production server
- [ ] Database admin credentials
- [ ] Redis access
- [ ] Git repository access
- [ ] Telegram Bot Token

---

## Phase 1: Pre-Deployment Preparation (15 minutes)

### 1.1 Create Backup

```bash
# 1. SSH into production server
ssh user@production-server

# 2. Navigate to project directory
cd /path/to/sigmatradebot

# 3. Create backup directory
mkdir -p backups/$(date +%Y%m%d_%H%M%S)
cd backups/$(date +%Y%m%d_%H%M%S)

# 4. Backup database
pg_dump -h $DB_HOST -U $DB_USERNAME -d $DB_DATABASE -F c -b -v \
  -f "database_$(date +%Y%m%d_%H%M%S).dump"

# 5. Backup current code
cd /path/to/sigmatradebot
tar -czf backups/$(date +%Y%m%d_%H%M%S)/code_backup.tar.gz \
  --exclude=node_modules \
  --exclude=.git \
  --exclude=backups \
  --exclude=logs \
  .

# 6. Backup Redis (optional)
redis-cli --rdb backups/$(date +%Y%m%d_%H%M%S)/redis_dump.rdb

# 7. Verify backups
ls -lh backups/$(date +%Y%m%d_%H%M%S)/
```

**Expected Output:**
```
-rw-r--r-- 1 user user 150M database_20240101_120000.dump
-rw-r--r-- 1 user user  50M code_backup.tar.gz
-rw-r--r-- 1 user user  10M redis_dump.rdb
```

### 1.2 Test on Staging/Copy (Required)

```bash
# 1. Create test database
createdb -h $DB_HOST -U $DB_USERNAME ${DB_DATABASE}_test

# 2. Restore backup to test database
pg_restore -h $DB_HOST -U $DB_USERNAME -d ${DB_DATABASE}_test \
  backups/*/database_*.dump

# 3. Create test environment file
cp .env .env.test
sed -i 's/DB_DATABASE=.*/DB_DATABASE='${DB_DATABASE}'_test/' .env.test

# 4. Run migrations on test database
NODE_ENV=test npm run migration:run

# 5. Verify migrations
NODE_ENV=test npm run migration:show

# 6. Start bot in test mode
NODE_ENV=test npm start &
TEST_BOT_PID=$!

# 7. Wait 30 seconds
sleep 30

# 8. Check logs
tail -100 logs/app.log | grep -E "ERROR|Migration"

# 9. Stop test bot
kill $TEST_BOT_PID

# 10. Drop test database
dropdb -h $DB_HOST -U $DB_USERNAME ${DB_DATABASE}_test
```

**Expected Output:**
```
✅ All migrations applied successfully
✅ Bot started without errors
✅ Background jobs running
```

### 1.3 Verify Environment Variables

```bash
# Check all required environment variables
cat <<'EOF' > check_env.sh
#!/bin/bash

required_vars=(
  "TELEGRAM_BOT_TOKEN"
  "DB_HOST"
  "DB_PORT"
  "DB_USERNAME"
  "DB_PASSWORD"
  "DB_DATABASE"
  "REDIS_HOST"
  "REDIS_PORT"
  "QUICKNODE_HTTPS_URL"
  "QUICKNODE_WSS_URL"
  "SYSTEM_WALLET_ADDRESS"
  "PAYOUT_WALLET_ADDRESS"
)

missing=()
for var in "${required_vars[@]}"; do
  if [ -z "${!var}" ]; then
    missing+=("$var")
  fi
done

if [ ${#missing[@]} -eq 0 ]; then
  echo "✅ All required environment variables are set"
  exit 0
else
  echo "❌ Missing environment variables:"
  printf '  - %s\n' "${missing[@]}"
  exit 1
fi
EOF

chmod +x check_env.sh
source .env && ./check_env.sh
```

### 1.4 Health Check

```bash
# 1. Check database connectivity
psql -h $DB_HOST -U $DB_USERNAME -d $DB_DATABASE -c "SELECT version();"

# 2. Check Redis connectivity
redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD ping

# 3. Check bot status
ps aux | grep "node.*index" | grep -v grep

# 4. Check disk space
df -h | grep -E "Filesystem|/$"

# 5. Check memory
free -h
```

**Expected Output:**
```
PostgreSQL 15.x
PONG
node process running
Filesystem      Size  Used  Avail  Use%
/dev/sda1       50G   20G    28G   42%
              total        used        free
Mem:           2.0Gi       1.2Gi       800Mi
```

---

## Phase 2: Stop Current Bot (5 minutes)

### 2.1 Graceful Shutdown

```bash
# 1. Find bot process ID
BOT_PID=$(ps aux | grep "node.*index" | grep -v grep | awk '{print $2}')

if [ -z "$BOT_PID" ]; then
  echo "⚠️ Bot is not running"
else
  echo "🔄 Stopping bot (PID: $BOT_PID)..."

  # 2. Send SIGTERM for graceful shutdown
  kill -SIGTERM $BOT_PID

  # 3. Wait up to 30 seconds for graceful shutdown
  timeout 30 tail --pid=$BOT_PID -f /dev/null

  # 4. Check if process still running
  if ps -p $BOT_PID > /dev/null 2>&1; then
    echo "⚠️ Bot didn't stop gracefully, forcing..."
    kill -SIGKILL $BOT_PID
  fi

  echo "✅ Bot stopped"
fi

# 5. Verify bot is stopped
sleep 2
if ps aux | grep "node.*index" | grep -v grep > /dev/null; then
  echo "❌ Bot is still running!"
  exit 1
else
  echo "✅ Bot is stopped"
fi
```

### 2.2 Close Database Connections

```bash
# Terminate all connections to the database (careful!)
psql -h $DB_HOST -U $DB_USERNAME -d postgres -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '$DB_DATABASE'
  AND pid <> pg_backend_pid();
"
```

---

## Phase 3: Deploy Code (5 minutes)

### 3.1 Pull Latest Code

```bash
# 1. Stash any local changes (if needed)
git stash

# 2. Fetch latest changes
git fetch origin

# 3. Checkout deployment branch
git checkout claude/project-exploration-011CUzxPR2oSUcyCnUd4oR1Q

# 4. Pull latest commits
git pull origin claude/project-exploration-011CUzxPR2oSUcyCnUd4oR1Q

# 5. Verify current commit
git log -1 --oneline

# 6. Show changed files
git diff --name-only HEAD~10..HEAD
```

**Expected Output:**
```
5247301 Complete notification failure retry system (FIX #17 - Part 2)

Changed files:
src/services/blockchain/deposit-processor.ts
src/services/blockchain/event-monitor.ts
src/services/notification.service.ts
src/database/entities/FailedNotification.entity.ts
...
```

### 3.2 Install Dependencies

```bash
# 1. Install production dependencies (clean install)
npm ci --production

# 2. Verify critical packages
npm list --depth=0 | grep -E "telegraf|typeorm|redis|ethers|bull"
```

**Expected Output:**
```
├── telegraf@4.x.x
├── typeorm@0.3.x
├── ioredis@5.x.x
├── ethers@6.x.x
├── bull@4.x.x
```

### 3.3 Build TypeScript (if needed)

```bash
# Only if you compile TypeScript in production
npm run build
```

---

## Phase 4: Run Migrations (5-10 minutes)

### 4.1 Verify Migration Files

```bash
# List all migration files
ls -la src/database/migrations/

# Should show:
# 1699999999001-AddDepositConstraints.ts
# 1699999999002-AddTransactionDeduplication.ts
# 1699999999003-AddPaymentRetrySystem.ts
# 1699999999004-AddFailedNotifications.ts
```

### 4.2 Show Pending Migrations

```bash
npm run migration:show
```

**Expected Output:**
```
[X] AddDepositConstraints1699999999001
[X] AddTransactionDeduplication1699999999002
[X] AddPaymentRetrySystem1699999999003
[X] AddFailedNotifications1699999999004

4 migrations are pending
```

### 4.3 Run Migrations

```bash
# Run all pending migrations
npm run migration:run

# Alternative: Run migrations one by one (safer)
npm run migration:run -- -t 1  # Run only 1 migration
# Review results, then repeat for each migration
```

**Expected Output:**
```
query: BEGIN TRANSACTION
query: SELECT * FROM "migrations" "migrations" ...
query: ALTER TABLE "deposits" ADD "processing_started_at" ...
query: CREATE INDEX "IDX_deposits_processing" ...
query: INSERT INTO "migrations" ...
query: COMMIT

Migration AddDepositConstraints1699999999001 has been executed successfully.

[Repeat for each migration]

All migrations completed successfully!
```

### 4.4 Verify Migrations

```bash
# 1. Check migration status
npm run migration:show

# 2. Verify database schema
psql -h $DB_HOST -U $DB_USERNAME -d $DB_DATABASE <<'EOF'
-- Check new columns exist
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'deposits'
  AND column_name IN ('processing_started_at', 'processed_by');

-- Check new tables exist
SELECT table_name, table_type
FROM information_schema.tables
WHERE table_name IN ('payment_retries', 'failed_notifications');

-- Check indexes exist
SELECT indexname, tablename
FROM pg_indexes
WHERE indexname LIKE 'IDX_payment_retries%'
   OR indexname LIKE 'IDX_failed_notifications%'
   OR indexname = 'IDX_deposits_processing'
   OR indexname = 'IDX_transactions_tx_hash_unique';
EOF
```

**Expected Output:**
```
[✅] All migrations applied
[✅] New columns exist in deposits table
[✅] New tables created (payment_retries, failed_notifications)
[✅] All indexes created successfully
```

---

## Phase 5: Start Bot (2 minutes)

### 5.1 Start Bot Service

```bash
# Option 1: Using PM2 (recommended)
pm2 start npm --name "sigmatradebot" -- start
pm2 save

# Option 2: Using systemd
sudo systemctl start sigmatradebot

# Option 3: Direct start (development)
npm start > logs/app.log 2>&1 &
echo $! > bot.pid
```

### 5.2 Monitor Startup

```bash
# Watch logs for 30 seconds
timeout 30 tail -f logs/app.log
```

**Expected Output (Key Messages):**
```
✅ Database connected
✅ Redis connected
✅ Bull queues initialized
✅ Blockchain monitoring started
✅ Payment retry processor started
✅ Notification retry processor started
✅ Bot started successfully
📡 Listening for deposits to: 0x...
```

### 5.3 Verify Bot is Running

```bash
# Check process
ps aux | grep "node.*index" | grep -v grep

# Check PM2 status (if using PM2)
pm2 status

# Check systemd status (if using systemd)
sudo systemctl status sigmatradebot
```

---

## Phase 6: Post-Deployment Verification (30 minutes)

### 6.1 Smoke Tests (5 minutes)

```bash
# Create smoke test script
cat <<'EOF' > smoke_tests.sh
#!/bin/bash

echo "🔍 Running smoke tests..."

# Test 1: Bot responds to /start
echo "Test 1: Send /start to bot and verify response"
# Manual: Send /start via Telegram

# Test 2: Check logs for errors
echo "Test 2: Check for errors in logs"
ERROR_COUNT=$(tail -1000 logs/app.log | grep -c "ERROR")
if [ $ERROR_COUNT -gt 0 ]; then
  echo "❌ Found $ERROR_COUNT errors in logs"
  tail -1000 logs/app.log | grep "ERROR"
else
  echo "✅ No errors in logs"
fi

# Test 3: Check database connections
echo "Test 3: Verify database connections"
ACTIVE_CONNECTIONS=$(psql -h $DB_HOST -U $DB_USERNAME -d $DB_DATABASE -t -c "
  SELECT count(*) FROM pg_stat_activity
  WHERE datname = '$DB_DATABASE' AND state = 'active';
")
echo "✅ Active database connections: $ACTIVE_CONNECTIONS"

# Test 4: Check Redis connections
echo "Test 4: Verify Redis connections"
redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD ping
if [ $? -eq 0 ]; then
  echo "✅ Redis connection OK"
else
  echo "❌ Redis connection failed"
fi

# Test 5: Check background jobs
echo "Test 5: Verify background jobs"
QUEUE_KEYS=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD KEYS "bull:*" | wc -l)
echo "✅ Found $QUEUE_KEYS queue keys in Redis"

# Test 6: Verify blockchain monitoring
echo "Test 6: Check blockchain WebSocket connection"
grep "Blockchain monitoring started" logs/app.log
if [ $? -eq 0 ]; then
  echo "✅ Blockchain monitoring active"
else
  echo "❌ Blockchain monitoring not started"
fi

echo "✅ Smoke tests complete"
EOF

chmod +x smoke_tests.sh
./smoke_tests.sh
```

### 6.2 Functional Tests (10 minutes)

**Manual Testing Checklist:**

- [ ] **Test 1: Bot Basic Commands**
  - Send `/start` → Verify welcome message
  - Send `/help` → Verify help text
  - Send `/profile` → Verify profile display

- [ ] **Test 2: Registration Flow** (if not registered)
  - Send `/start` → Click "Register"
  - Enter wallet address (use test address)
  - Verify EIP-55 checksum warning (if needed)
  - Complete registration
  - Verify password shown

- [ ] **Test 3: Admin Functions** (if admin)
  - Send `/admin_login` → Login with master key
  - Send `/admin_panel` → Verify panel opens
  - Check statistics
  - Verify session persists after restart

- [ ] **Test 4: Deposit Processing** (observe)
  - Monitor logs for deposit events
  - Verify deposits are processed
  - Check for race condition errors (should be none)

### 6.3 Monitor Key Metrics (15 minutes)

```bash
# Create monitoring script
cat <<'EOF' > monitor.sh
#!/bin/bash

echo "📊 Monitoring system metrics..."

# Check database performance
echo "=== Database Stats ==="
psql -h $DB_HOST -U $DB_USERNAME -d $DB_DATABASE <<'SQL'
-- Index usage
SELECT
  schemaname,
  tablename,
  indexname,
  idx_scan AS scans,
  idx_tup_read AS tuples_read
FROM pg_stat_user_indexes
WHERE indexname LIKE 'IDX_%'
ORDER BY idx_scan DESC
LIMIT 10;

-- Table sizes
SELECT
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;

-- Active queries
SELECT count(*) as active_queries
FROM pg_stat_activity
WHERE state = 'active' AND datname = current_database();
SQL

# Check Redis keys
echo -e "\n=== Redis Stats ==="
redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD INFO stats | grep -E "total_commands_processed|instantaneous_ops_per_sec"
redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD DBSIZE

# Check Bull queues
echo -e "\n=== Bull Queue Stats ==="
for queue in blockchain-monitor payment-processor payment-retry notification-retry reward-calculator; do
  echo "Queue: $queue"
  redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD HGETALL "bull:$queue:counts"
done

# Check system resources
echo -e "\n=== System Resources ==="
echo "Memory:"
free -h | grep -E "Mem|Swap"
echo "Disk:"
df -h / | grep -E "Filesystem|/$"
echo "CPU Load:"
uptime

# Check recent errors
echo -e "\n=== Recent Errors ==="
tail -1000 logs/app.log | grep ERROR | tail -10

echo -e "\n✅ Monitoring complete"
EOF

chmod +x monitor.sh
./monitor.sh
```

**Expected Results:**
- Index scans > 0 for new indexes
- No active long-running queries
- Redis ops per second stable
- Queue counts reasonable
- Memory usage < 80%
- No recent errors

---

## Phase 7: Final Verification (5 minutes)

### 7.1 Success Criteria Checklist

- [ ] ✅ All migrations applied successfully
- [ ] ✅ Bot started without errors
- [ ] ✅ No errors in logs (last 30 minutes)
- [ ] ✅ Blockchain monitoring active (WebSocket connected)
- [ ] ✅ Background jobs running (payment-retry, notification-retry)
- [ ] ✅ Database indexes being used (idx_scan > 0)
- [ ] ✅ Redis connections stable
- [ ] ✅ Bot responds to commands
- [ ] ✅ Admin panel accessible
- [ ] ✅ Memory usage normal (< 80%)
- [ ] ✅ CPU load normal

### 7.2 Document Deployment

```bash
# Create deployment record
cat <<EOF > DEPLOYMENT_RECORD_$(date +%Y%m%d_%H%M%S).txt
Deployment Date: $(date)
Git Commit: $(git rev-parse HEAD)
Git Branch: $(git rev-parse --abbrev-ref HEAD)
Migrations Applied: 4
  - AddDepositConstraints (1699999999001)
  - AddTransactionDeduplication (1699999999002)
  - AddPaymentRetrySystem (1699999999003)
  - AddFailedNotifications (1699999999004)
Downtime: [INSERT ACTUAL DOWNTIME]
Issues: [INSERT ANY ISSUES]
Status: SUCCESS
EOF
```

---

## Rollback Procedure (Emergency Only)

**Use ONLY if critical issues detected:**

### Step 1: Stop Bot

```bash
# Stop bot immediately
kill -SIGKILL $(ps aux | grep "node.*index" | grep -v grep | awk '{print $2}')

# Or using PM2
pm2 stop sigmatradebot

# Or using systemd
sudo systemctl stop sigmatradebot
```

### Step 2: Restore Database

```bash
# Drop current database
dropdb -h $DB_HOST -U $DB_USERNAME $DB_DATABASE

# Create new database
createdb -h $DB_HOST -U $DB_USERNAME $DB_DATABASE

# Restore from backup
pg_restore -h $DB_HOST -U $DB_USERNAME -d $DB_DATABASE \
  backups/YYYYMMDD_HHMMSS/database_*.dump

# Verify restore
psql -h $DB_HOST -U $DB_USERNAME -d $DB_DATABASE -c "SELECT COUNT(*) FROM users;"
```

### Step 3: Restore Code

```bash
# Checkout previous version
git checkout <previous-commit-hash>

# Install dependencies
npm ci --production

# Start bot
npm start
```

### Step 4: Verify Rollback

```bash
# Check bot is running
ps aux | grep "node.*index"

# Check logs
tail -f logs/app.log
```

**Rollback Time:** ~10 minutes

---

## Troubleshooting

### Issue: Migration Failed

**Symptoms:** Migration exits with error

**Solution:**
```bash
# 1. Check error message
tail -100 logs/app.log | grep -A 10 "Migration.*failed"

# 2. Check what was partially created
psql -h $DB_HOST -U $DB_USERNAME -d $DB_DATABASE -c "\dt"
psql -h $DB_HOST -U $DB_USERNAME -d $DB_DATABASE -c "\di"

# 3. Manually revert partial changes
psql -h $DB_HOST -U $DB_USERNAME -d $DB_DATABASE <<'EOF'
-- Example for migration 3
DROP TABLE IF EXISTS payment_retries CASCADE;
DELETE FROM migrations WHERE timestamp >= 1699999999003;
EOF

# 4. Fix migration code and retry
```

### Issue: Bot Won't Start

**Symptoms:** Bot process exits immediately

**Solution:**
```bash
# 1. Check logs
tail -100 logs/app.log

# 2. Check environment variables
source .env && ./check_env.sh

# 3. Check database connectivity
psql -h $DB_HOST -U $DB_USERNAME -d $DB_DATABASE -c "SELECT 1;"

# 4. Check Redis connectivity
redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD ping

# 5. Try starting with debug logs
DEBUG=* npm start
```

### Issue: High Memory Usage

**Symptoms:** Memory > 90%

**Solution:**
```bash
# 1. Check process memory
ps aux --sort=-%mem | head -10

# 2. Restart bot
pm2 restart sigmatradebot

# 3. Monitor memory
watch -n 5 free -h
```

### Issue: Slow Queries

**Symptoms:** Database queries taking > 1s

**Solution:**
```sql
-- Check slow queries
SELECT
  pid,
  now() - query_start AS duration,
  state,
  query
FROM pg_stat_activity
WHERE state != 'idle'
  AND query NOT LIKE '%pg_stat_activity%'
ORDER BY duration DESC;

-- Check missing indexes
SELECT
  schemaname,
  tablename,
  indexname,
  idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY schemaname, tablename;

-- Analyze tables
ANALYZE deposits;
ANALYZE transactions;
ANALYZE payment_retries;
ANALYZE failed_notifications;
```

---

## Support Contacts

**In case of emergency:**
1. Check logs: `tail -f logs/app.log`
2. Review [MIGRATIONS.md](./MIGRATIONS.md)
3. Review [CHANGELOG.md](./CHANGELOG.md)
4. Execute rollback procedure above

---

## Post-Deployment Monitoring (First 24 Hours)

### Hour 1: Intensive Monitoring

```bash
# Monitor logs continuously
tail -f logs/app.log | grep -E "ERROR|WARN|Critical"
```

### Hours 2-24: Periodic Checks

```bash
# Run monitoring script every hour
watch -n 3600 ./monitor.sh
```

### Key Metrics to Track

- Error rate (target: < 0.1%)
- Deposit confirmation rate (target: 99.9%+)
- Payment success rate (target: 99%+)
- Notification delivery rate (target: 99%+)
- Response time (target: < 500ms)
- Memory usage (target: < 80%)

---

## Deployment Complete! 🎉

If all verifications pass, deployment is successful.

**Next Steps:**
- Monitor system for 24 hours
- Review metrics daily for first week
- Schedule regular maintenance
- Plan next deployment cycle

**Congratulations on a successful deployment!**
