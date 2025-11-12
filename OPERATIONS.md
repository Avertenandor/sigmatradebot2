# 🛠 Operations Runbook - SigmaTrade Bot

**Last Updated:** 2025-11-11
**Version:** 1.0
**Status:** Production Ready

---

## 📋 Table of Contents

1. [Daily Operations](#daily-operations)
2. [Health Monitoring](#health-monitoring)
3. [Common Tasks](#common-tasks)
4. [Backup & Restore](#backup--restore)
5. [Incident Response](#incident-response)
6. [DLQ Management](#dlq-management)
7. [User Support](#user-support)
8. [Database Maintenance](#database-maintenance)
9. [Redis Operations](#redis-operations)
10. [Blockchain Monitoring](#blockchain-monitoring)
11. [Performance Tuning](#performance-tuning)
12. [Emergency Procedures](#emergency-procedures)

---

## 📅 Daily Operations

### Morning Checklist (9:00 AM)

```bash
#!/bin/bash
# Daily morning health check

echo "=== SigmaTrade Bot Health Check ==="
echo "Date: $(date)"
echo ""

# 1. Check bot status
echo "1. Bot Status:"
pm2 status sigmatrade-bot

# 2. Check error count (last 24 hours)
echo -e "\n2. Error Count (last 24h):"
pm2 logs sigmatrade-bot --lines 1000 --nostream | grep -i error | wc -l

# 3. Database connection
echo -e "\n3. Database Status:"
psql -h localhost -U botuser -d sigmatrade -c "SELECT COUNT(*) as user_count FROM users;"

# 4. Redis connection
echo -e "\n4. Redis Status:"
redis-cli ping

# 5. Check DLQ items
echo -e "\n5. Dead Letter Queue:"
psql -h localhost -U botuser -d sigmatrade -c "SELECT COUNT(*) FROM payment_retry WHERE status = 'dlq';"

# 6. Pending deposits
echo -e "\n6. Pending Deposits:"
psql -h localhost -U botuser -d sigmatrade -c "SELECT COUNT(*) FROM deposits WHERE status = 'pending';"

# 7. Notification failures (last hour)
echo -e "\n7. Recent Notification Failures:"
psql -h localhost -U botuser -d sigmatrade -c "SELECT COUNT(*) FROM notification_failure WHERE created_at > NOW() - INTERVAL '1 hour';"

# 8. Blockchain sync status
echo -e "\n8. Blockchain Sync:"
redis-cli GET last_processed_block

echo -e "\n=== Health Check Complete ==="
```

**Save as:** `/home/bot/scripts/daily-check.sh`

**Alert Thresholds:**
- Errors > 50 in 24h: Investigate immediately
- DLQ items > 5: Review failed payments
- Pending deposits > 10 for >1h: Check blockchain monitor
- Notification failures > 20: Check Telegram API status

---

### Evening Checklist (6:00 PM)

```bash
#!/bin/bash
# Evening operations check

echo "=== Evening Operations Report ==="

# 1. Today's statistics
echo "1. Today's Activity:"
psql -h localhost -U botuser -d sigmatrade -c "
SELECT
  COUNT(DISTINCT user_id) as active_users,
  COUNT(*) as total_deposits,
  SUM(amount) as total_volume
FROM deposits
WHERE created_at >= CURRENT_DATE;
"

# 2. Referral rewards paid today
echo -e "\n2. Referral Rewards:"
psql -h localhost -U botuser -d sigmatrade -c "
SELECT
  COUNT(*) as rewards_count,
  SUM(amount) as total_rewards
FROM referral_earnings
WHERE created_at >= CURRENT_DATE;
"

# 3. System resource usage
echo -e "\n3. Resource Usage:"
echo "CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}')%"
echo "Memory: $(free -h | awk '/^Mem:/ {print $3 "/" $2}')"
echo "Disk: $(df -h / | awk 'NR==2 {print $3 "/" $2 " (" $5 " used)"}')"

# 4. Database size
echo -e "\n4. Database Size:"
psql -h localhost -U botuser -d sigmatrade -c "
SELECT
  pg_size_pretty(pg_database_size('sigmatrade')) as db_size;
"

echo -e "\n=== Report Complete ==="
```

**Save as:** `/home/bot/scripts/evening-report.sh`

---

## 🏥 Health Monitoring

### Real-time Health Dashboard

```bash
#!/bin/bash
# Continuous health monitoring (run in tmux/screen)

watch -n 10 '
echo "=== SigmaTrade Bot Live Status ==="
echo "Time: $(date)"
echo ""
echo "Bot Process:"
pm2 jlist | jq ".[] | {name, status, cpu, memory}"
echo ""
echo "Recent Errors (last 5 minutes):"
pm2 logs sigmatrade-bot --lines 100 --nostream | grep -i error | tail -5
echo ""
echo "Database Connections:"
psql -h localhost -U botuser -d sigmatrade -c "SELECT count(*) as active_connections FROM pg_stat_activity WHERE datname = \"sigmatrade\";"
echo ""
echo "Redis Memory:"
redis-cli INFO memory | grep used_memory_human
echo ""
echo "Last Processed Block:"
redis-cli GET last_processed_block
'
```

**Save as:** `/home/bot/scripts/health-dashboard.sh`

### Monitoring Queries

#### Active Users (Last Hour)
```sql
SELECT COUNT(DISTINCT user_id) as active_users
FROM user_actions
WHERE created_at > NOW() - INTERVAL '1 hour';
```

#### Deposit Processing Time
```sql
SELECT
  AVG(EXTRACT(EPOCH FROM (confirmed_at - created_at))) as avg_processing_seconds,
  MAX(EXTRACT(EPOCH FROM (confirmed_at - created_at))) as max_processing_seconds
FROM deposits
WHERE confirmed_at IS NOT NULL
  AND created_at > NOW() - INTERVAL '24 hours';
```

#### Failed Transactions (Last 24h)
```sql
SELECT
  type,
  COUNT(*) as count,
  AVG(amount) as avg_amount
FROM transactions
WHERE status = 'failed'
  AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY type;
```

#### Redis Cache Hit Rate
```bash
redis-cli INFO stats | grep keyspace_hits
redis-cli INFO stats | grep keyspace_misses
# Calculate: hits / (hits + misses) * 100%
```

---

## 🔧 Common Tasks

### Restart Bot

```bash
# Graceful restart (recommended)
pm2 reload sigmatrade-bot

# Hard restart (if graceful fails)
pm2 restart sigmatrade-bot

# Check logs after restart
pm2 logs sigmatrade-bot --lines 50
```

### View Logs

```bash
# Live logs
pm2 logs sigmatrade-bot

# Last 100 lines
pm2 logs sigmatrade-bot --lines 100 --nostream

# Error logs only
pm2 logs sigmatrade-bot --err

# Save logs to file
pm2 logs sigmatrade-bot --lines 1000 --nostream > bot-logs-$(date +%Y%m%d).txt
```

### Clear Redis Cache

```bash
# Clear all caches (CAUTION!)
redis-cli FLUSHDB

# Clear specific cache keys
redis-cli KEYS "user:*" | xargs redis-cli DEL
redis-cli KEYS "referral_chain:*" | xargs redis-cli DEL

# Clear expired keys only
redis-cli --scan --pattern "*" | while read key; do
  TTL=$(redis-cli TTL "$key")
  if [ "$TTL" -eq "-1" ]; then
    echo "Key without TTL: $key"
  fi
done
```

### Database Connection Check

```bash
# Test connection
psql -h localhost -U botuser -d sigmatrade -c "SELECT NOW();"

# Show active connections
psql -h localhost -U botuser -d sigmatrade -c "
SELECT
  pid,
  usename,
  application_name,
  client_addr,
  state,
  query_start,
  state_change
FROM pg_stat_activity
WHERE datname = 'sigmatrade';
"

# Kill idle connections (>30 minutes)
psql -h localhost -U botuser -d sigmatrade -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'sigmatrade'
  AND state = 'idle'
  AND state_change < NOW() - INTERVAL '30 minutes';
"
```

### Manual Blockchain Sync

```bash
# Get current block number
node -e "
const ethers = require('ethers');
const provider = new ethers.JsonRpcProvider(process.env.QUICKNODE_HTTPS_URL);
provider.getBlockNumber().then(block => console.log('Current block:', block));
"

# Update last processed block in Redis
redis-cli SET last_processed_block 12345678

# Trigger manual sync (requires bot restart)
pm2 restart sigmatrade-bot
```

---

## 💾 Backup & Restore

### Database Backup

#### Automated Daily Backup (cron)
```bash
# /etc/cron.d/sigmatrade-backup
0 3 * * * /home/bot/scripts/backup.sh >> /var/log/sigmatrade-backup.log 2>&1
```

#### Backup Script
```bash
#!/bin/bash
# /home/bot/scripts/backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/bot/sigmatradebot/backups"
DB_HOST="localhost"
DB_USER="botuser"
DB_NAME="sigmatrade"

echo "=== Starting backup at $(date) ==="

# Create backup directory
mkdir -p $BACKUP_DIR

# Full database backup
echo "Creating full database backup..."
pg_dump -h $DB_HOST -U $DB_USER $DB_NAME > $BACKUP_DIR/full_backup_$DATE.sql

# Critical tables only (faster)
echo "Creating critical tables backup..."
pg_dump -h $DB_HOST -U $DB_USER -t users -t deposits -t transactions \
  -t referrals -t payment_retry $DB_NAME > $BACKUP_DIR/critical_$DATE.sql

# Compress backups
echo "Compressing backups..."
gzip $BACKUP_DIR/full_backup_$DATE.sql
gzip $BACKUP_DIR/critical_$DATE.sql

# Upload to cloud storage (REQUIRED for production)
if [ -n "$GCS_BUCKET" ]; then
  echo "Uploading to Google Cloud Storage..."
  gsutil cp $BACKUP_DIR/full_backup_$DATE.sql.gz gs://$GCS_BUCKET/backups/
  gsutil cp $BACKUP_DIR/critical_$DATE.sql.gz gs://$GCS_BUCKET/backups/

  # Set lifecycle policy for automatic cleanup (90 days retention)
  # gsutil lifecycle set lifecycle.json gs://$GCS_BUCKET
else
  echo "WARNING: GCS_BUCKET not configured - backups stored only locally!"
  echo "Configure GCS_BACKUP_BUCKET in .env for production"
fi

# Cleanup old backups (keep 14 days locally)
echo "Cleaning up old backups..."
find $BACKUP_DIR -name "*.sql.gz" -mtime +14 -delete

echo "=== Backup completed at $(date) ==="
echo "Size: $(du -sh $BACKUP_DIR/full_backup_$DATE.sql.gz)"
```

### Restore from Backup

```bash
#!/bin/bash
# Restore database from backup

# CAUTION: This will overwrite existing data!

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: ./restore.sh <backup-file.sql.gz>"
  exit 1
fi

echo "WARNING: This will overwrite the current database!"
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
  echo "Restore cancelled."
  exit 0
fi

# Stop bot
echo "Stopping bot..."
pm2 stop sigmatrade-bot

# Decompress backup
echo "Decompressing backup..."
gunzip -c $BACKUP_FILE > /tmp/restore.sql

# Drop and recreate database
echo "Recreating database..."
psql -h localhost -U postgres -c "DROP DATABASE IF EXISTS sigmatrade;"
psql -h localhost -U postgres -c "CREATE DATABASE sigmatrade OWNER botuser;"

# Restore data
echo "Restoring data..."
psql -h localhost -U botuser -d sigmatrade < /tmp/restore.sql

# Clear Redis cache
echo "Clearing Redis cache..."
redis-cli FLUSHDB

# Restart bot
echo "Restarting bot..."
pm2 start sigmatrade-bot

# Cleanup
rm /tmp/restore.sql

echo "Restore completed successfully!"
```

---

## 🚨 Incident Response

### Severity Levels

| Level | Description | Response Time | Escalation |
|-------|-------------|---------------|------------|
| **P1 - Critical** | Bot down, money at risk | 15 minutes | Immediate on-call |
| **P2 - High** | Major feature broken | 1 hour | Notify team lead |
| **P3 - Medium** | Minor issue, workaround exists | 4 hours | Normal workflow |
| **P4 - Low** | Cosmetic, enhancement request | 24 hours | Backlog |

### Incident Response Checklist

#### P1 - Critical Incident
```markdown
1. [ ] Acknowledge incident in monitoring channel
2. [ ] Run health check script: `./scripts/daily-check.sh`
3. [ ] Check recent logs: `pm2 logs sigmatrade-bot --lines 200`
4. [ ] Identify root cause
5. [ ] Apply immediate fix or rollback
6. [ ] Verify fix with smoke tests
7. [ ] Document incident in postmortem template
8. [ ] Notify stakeholders of resolution
```

#### Common P1 Scenarios

**Bot Not Responding**
```bash
# 1. Check if process is running
pm2 status sigmatrade-bot

# 2. If not running, check why it stopped
pm2 logs sigmatrade-bot --err --lines 50

# 3. Restart bot
pm2 restart sigmatrade-bot

# 4. Monitor for errors
pm2 logs sigmatrade-bot --lines 100
```

**Database Connection Lost**
```bash
# 1. Check database status
pg_isready -h localhost -U botuser -d sigmatrade

# 2. Check active connections
psql -h localhost -U botuser -d sigmatrade -c "
  SELECT count(*) FROM pg_stat_activity;
"

# 3. If max connections reached, kill idle connections
psql -h localhost -U postgres -c "
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE datname = 'sigmatrade'
    AND state = 'idle'
    AND state_change < NOW() - INTERVAL '10 minutes';
"

# 4. Restart bot
pm2 restart sigmatrade-bot
```

**Blockchain Monitor Stuck**
```bash
# 1. Check last processed block
redis-cli GET last_processed_block

# 2. Compare with current block
node -e "
const ethers = require('ethers');
const provider = new ethers.JsonRpcProvider(process.env.QUICKNODE_HTTPS_URL);
provider.getBlockNumber().then(console.log);
"

# 3. If stuck, clear Redis tracking and restart
redis-cli DEL last_processed_block last_fetch_time
pm2 restart sigmatrade-bot

# 4. Monitor logs for successful sync
pm2 logs sigmatrade-bot | grep "Block processed"
```

**Out of Memory**
```bash
# 1. Check memory usage
free -h
pm2 monit

# 2. Identify memory leak
pm2 logs sigmatrade-bot --lines 500 | grep -i "memory"

# 3. Restart bot (temporary fix)
pm2 restart sigmatrade-bot

# 4. Enable heap snapshot for analysis
pm2 restart sigmatrade-bot --node-args="--max-old-space-size=2048"

# 5. Schedule code review to fix leak
```

---

## 📬 DLQ Management

### View DLQ Items

```sql
-- All DLQ items
SELECT
  id,
  user_id,
  amount,
  wallet_address,
  attempt_number,
  last_error,
  created_at
FROM payment_retry
WHERE status = 'dlq'
ORDER BY created_at DESC;
```

### Resolve DLQ Item Manually

```sql
-- After manually sending payment via blockchain explorer

BEGIN;

-- 1. Update retry record
UPDATE payment_retry
SET
  status = 'success',
  tx_hash = '0x...', -- Actual transaction hash
  resolved_by = 'admin_telegram_id',
  resolved_at = NOW(),
  admin_notes = 'Manually sent via BSCScan'
WHERE id = <dlq_item_id>;

-- 2. Verify user received funds (check blockchain)
-- 3. Notify user

COMMIT;
```

### Retry DLQ Item

```sql
-- Reset DLQ item for retry

UPDATE payment_retry
SET
  status = 'pending',
  attempt_number = 0,
  next_retry_at = NOW(),
  last_error = NULL
WHERE id = <dlq_item_id>;

-- Bot will pick it up on next retry job run
```

### DLQ Statistics

```sql
-- DLQ items by error type
SELECT
  SUBSTRING(last_error FROM 1 FOR 50) as error_type,
  COUNT(*) as count,
  SUM(amount) as total_amount
FROM payment_retry
WHERE status = 'dlq'
GROUP BY error_type
ORDER BY count DESC;

-- Average time to DLQ
SELECT
  AVG(EXTRACT(EPOCH FROM (
    (SELECT MAX(created_at) FROM payment_retry WHERE status = 'dlq')
    - created_at
  )) / 3600) as avg_hours_to_dlq
FROM payment_retry
WHERE status = 'dlq';
```

---

## 👥 User Support

### Common User Issues

#### 1. Deposit Not Showing
```sql
-- Check if transaction exists
SELECT * FROM deposits
WHERE user_id = (SELECT id FROM users WHERE telegram_id = '<user_telegram_id>')
ORDER BY created_at DESC
LIMIT 10;

-- If not found, check blockchain
-- Have user provide transaction hash
-- Verify on BSCScan: https://bscscan.com/tx/<tx_hash>

-- If valid, create expired deposit review
INSERT INTO expired_deposit_review (user_id, tx_hash, user_reported_at, blockchain_data)
VALUES (...);
```

#### 2. Referral Not Working
```sql
-- Check referral link
SELECT
  u.telegram_id,
  u.first_name,
  u.referrer_id,
  r.first_name as referrer_name
FROM users u
LEFT JOIN users r ON u.referrer_id = r.id
WHERE u.telegram_id = '<user_telegram_id>';

-- Check for circular referrals
WITH RECURSIVE ref_chain AS (
  SELECT id, referrer_id, 1 as depth
  FROM users WHERE telegram_id = '<user_telegram_id>'
  UNION ALL
  SELECT u.id, u.referrer_id, rc.depth + 1
  FROM users u
  JOIN ref_chain rc ON u.id = rc.referrer_id
  WHERE rc.depth < 10
)
SELECT * FROM ref_chain;
```

#### 3. Withdrawal Not Received
```sql
-- Check payment status
SELECT
  pr.id,
  pr.amount,
  pr.status,
  pr.attempt_number,
  pr.next_retry_at,
  pr.last_error,
  pr.tx_hash
FROM payment_retry pr
JOIN users u ON pr.user_id = u.id
WHERE u.telegram_id = '<user_telegram_id>'
ORDER BY pr.created_at DESC
LIMIT 5;

-- If in DLQ, follow DLQ resolution process
-- If successful but user claims not received, verify on blockchain
```

### User Management Commands

```sql
-- Block user
UPDATE users
SET is_banned = true, banned_at = NOW(), ban_reason = 'Reason here'
WHERE telegram_id = '<user_telegram_id>';

-- Unblock user
UPDATE users
SET is_banned = false, banned_at = NULL, ban_reason = NULL
WHERE telegram_id = '<user_telegram_id>';

-- Adjust balance (with admin approval)
UPDATE users
SET balance = balance + <amount>
WHERE telegram_id = '<user_telegram_id>';

-- Log admin action
INSERT INTO admin_actions (admin_id, action_type, target_user_id, details)
VALUES ('<admin_id>', 'balance_adjustment', '<user_id>', '{"amount": 10.5, "reason": "Compensation"}');
```

---

## 🗄 Database Maintenance

### Weekly Maintenance (Sunday 2 AM)

```bash
#!/bin/bash
# Weekly database maintenance script

echo "=== Starting weekly maintenance at $(date) ==="

# 1. Analyze tables for query optimization
echo "Analyzing tables..."
psql -h localhost -U botuser -d sigmatrade -c "ANALYZE VERBOSE;"

# 2. Vacuum to reclaim space
echo "Vacuuming database..."
psql -h localhost -U botuser -d sigmatrade -c "VACUUM VERBOSE;"

# 3. Reindex critical tables
echo "Reindexing critical tables..."
psql -h localhost -U botuser -d sigmatrade -c "REINDEX TABLE CONCURRENTLY users;"
psql -h localhost -U botuser -d sigmatrade -c "REINDEX TABLE CONCURRENTLY deposits;"
psql -h localhost -U botuser -d sigmatrade -c "REINDEX TABLE CONCURRENTLY transactions;"

# 4. Check for bloat
echo "Checking table bloat..."
psql -h localhost -U botuser -d sigmatrade -c "
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;
"

# 5. Delete old user_actions (>7 days)
echo "Cleaning up old user actions..."
psql -h localhost -U botuser -d sigmatrade -c "
DELETE FROM user_actions WHERE created_at < NOW() - INTERVAL '7 days';
"

# 6. Delete old rate_limit_log (>7 days)
echo "Cleaning up old rate limit logs..."
psql -h localhost -U botuser -d sigmatrade -c "
DELETE FROM rate_limit_log WHERE created_at < NOW() - INTERVAL '7 days';
"

echo "=== Maintenance completed at $(date) ==="
```

### Database Performance Queries

```sql
-- Slow queries
SELECT
  query,
  calls,
  total_time,
  mean_time,
  max_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- Table sizes
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
  pg_total_relation_size(schemaname||'.'||tablename) AS bytes
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY bytes DESC;

-- Index usage
SELECT
  schemaname,
  tablename,
  indexname,
  idx_scan,
  idx_tup_read,
  idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;

-- Unused indexes (consider dropping)
SELECT
  schemaname,
  tablename,
  indexname,
  idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexname NOT LIKE '%pkey';
```

---

## 🔴 Redis Operations

### Redis Maintenance

```bash
# Redis health check
redis-cli PING
redis-cli INFO server
redis-cli INFO memory

# Key count by pattern
redis-cli --scan --pattern "user:*" | wc -l
redis-cli --scan --pattern "ratelimit:*" | wc -l
redis-cli --scan --pattern "admin:session:*" | wc -l

# Memory usage by key type
redis-cli --bigkeys

# Clear expired keys
redis-cli --scan | while read key; do
  TTL=$(redis-cli TTL "$key")
  if [ "$TTL" -eq "-2" ]; then
    echo "Deleted expired key: $key"
    redis-cli DEL "$key"
  fi
done
```

### Redis Backup

```bash
# Create snapshot
redis-cli BGSAVE

# Check last save time
redis-cli LASTSAVE

# Copy RDB file
cp /var/lib/redis/dump.rdb /home/bot/backups/redis-$(date +%Y%m%d).rdb
```

---

## ⛓ Blockchain Monitoring

### Check Sync Status

```bash
#!/bin/bash
# Check blockchain sync status

echo "=== Blockchain Sync Status ==="

# Last processed block (our bot)
LAST_BLOCK=$(redis-cli GET last_processed_block)
echo "Last Processed Block: $LAST_BLOCK"

# Current blockchain block
CURRENT_BLOCK=$(node -e "
const ethers = require('ethers');
const provider = new ethers.JsonRpcProvider(process.env.QUICKNODE_HTTPS_URL);
provider.getBlockNumber().then(console.log);
" 2>/dev/null)
echo "Current Block: $CURRENT_BLOCK"

# Calculate lag
LAG=$((CURRENT_BLOCK - LAST_BLOCK))
echo "Lag: $LAG blocks"

if [ $LAG -gt 100 ]; then
  echo "⚠️  WARNING: Sync lag is high!"
elif [ $LAG -gt 10 ]; then
  echo "⚡ NOTICE: Minor sync lag"
else
  echo "✅ Sync is up to date"
fi

# Last fetch time
LAST_FETCH=$(redis-cli GET last_fetch_time)
if [ -n "$LAST_FETCH" ]; then
  LAST_FETCH_READABLE=$(date -d @$((LAST_FETCH / 1000)) '+%Y-%m-%d %H:%M:%S')
  echo "Last Fetch: $LAST_FETCH_READABLE"
fi
```

### Manual Transaction Verification

```bash
# Verify transaction on BSCScan
TX_HASH="0x..."
curl -s "https://api.bscscan.com/api?module=transaction&action=gettxreceiptstatus&txhash=$TX_HASH&apikey=$BSCSCAN_API_KEY"

# Check USDT transfer event
node -e "
const ethers = require('ethers');
const provider = new ethers.JsonRpcProvider(process.env.QUICKNODE_HTTPS_URL);
const txHash = '$TX_HASH';

provider.getTransactionReceipt(txHash).then(receipt => {
  console.log('Status:', receipt.status === 1 ? 'Success' : 'Failed');
  console.log('Block:', receipt.blockNumber);
  console.log('Gas Used:', receipt.gasUsed.toString());
  console.log('Logs:', receipt.logs.length);
});
"
```

---

## ⚡ Performance Tuning

### Database Connection Pool

```typescript
// config/database.config.ts
export const dataSourceOptions = {
  // ...
  extra: {
    max: 20,              // Maximum connections (increase if CPU allows)
    min: 5,               // Minimum connections
    acquireTimeout: 30000, // 30 seconds
    idleTimeout: 600000,  // 10 minutes
  }
};
```

### Redis Configuration

```bash
# /etc/redis/redis.conf

# Memory management
maxmemory 2gb
maxmemory-policy allkeys-lru

# Persistence (for admin sessions)
save 900 1
save 300 10
save 60 10000

# Performance
tcp-backlog 511
timeout 0
tcp-keepalive 300
```

---

## 🚑 Emergency Procedures

### Emergency Shutdown

```bash
#!/bin/bash
# Emergency shutdown procedure

echo "⚠️  EMERGENCY SHUTDOWN INITIATED"
echo "Time: $(date)"

# 1. Stop accepting new requests
pm2 stop sigmatrade-bot

# 2. Wait for pending transactions to complete
sleep 10

# 3. Create emergency backup
./scripts/backup.sh

# 4. Document reason
read -p "Reason for emergency shutdown: " reason
echo "$(date): EMERGENCY SHUTDOWN - $reason" >> /var/log/emergency.log

# 5. Notify team
# (Send alert via Telegram/Email)

echo "✅ Emergency shutdown complete"
```

### Emergency Rollback

```bash
#!/bin/bash
# Emergency rollback to previous version

# 1. Stop bot
pm2 stop sigmatrade-bot

# 2. Git rollback
cd /home/bot/sigmatradebot
git log --oneline -5  # Show recent commits
read -p "Enter commit hash to rollback to: " commit_hash
git reset --hard $commit_hash

# 3. Restore dependencies
npm install

# 4. Run migrations if needed
npm run migration:revert

# 5. Restart bot
pm2 start sigmatrade-bot

# 6. Monitor logs
pm2 logs sigmatrade-bot --lines 100
```

---

## 📊 Performance Metrics

### Key Performance Indicators (KPIs)

| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| Bot Uptime | >99.9% | <99.5% | <99% |
| Response Time | <200ms | >500ms | >1s |
| Deposit Processing | <30s | >60s | >120s |
| Database Queries | <50ms | >100ms | >200ms |
| Error Rate | <0.1% | >1% | >5% |
| DLQ Items | 0 | >3 | >10 |
| Memory Usage | <70% | >80% | >90% |
| CPU Usage | <60% | >75% | >85% |

---

## 📝 Maintenance Schedule

### Daily
- Morning health check (9 AM)
- Evening operations report (6 PM)
- Monitor DLQ items
- Review error logs

### Weekly (Sunday 2 AM)
- Database vacuum & analyze
- Clear old user_actions
- Clear old rate_limit_log
- Review Redis memory usage
- Check for slow queries

### Monthly (1st Sunday)
- Full database backup verification
- Review and rotate logs
- Update dependencies (security patches)
- Performance review meeting
- Incident postmortem review

### Quarterly
- Security audit
- Load testing
- Disaster recovery drill
- Documentation review
- Infrastructure cost optimization

---

## 📞 On-Call Contact

```yaml
Primary On-Call: [Name]
  - Telegram: @username
  - Phone: +1-XXX-XXX-XXXX
  - Email: oncall@example.com

Secondary On-Call: [Name]
  - Telegram: @username
  - Phone: +1-XXX-XXX-XXXX

Escalation: [Team Lead Name]
  - Available: 24/7
  - Phone: +1-XXX-XXX-XXXX
```

---

**Last Updated:** 2025-11-11
**Version:** 1.0
**Next Review:** 2025-12-11
