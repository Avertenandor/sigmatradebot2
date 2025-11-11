# 🔧 Troubleshooting Guide - SigmaTrade Bot

**Last Updated:** 2025-11-11
**Version:** 1.0
**Status:** Production Ready

---

## 📋 Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [Bot Issues](#bot-issues)
3. [Database Issues](#database-issues)
4. [Redis Issues](#redis-issues)
5. [Blockchain Issues](#blockchain-issues)
6. [Deposit Problems](#deposit-problems)
7. [Payment & Withdrawal Issues](#payment--withdrawal-issues)
8. [Notification Issues](#notification-issues)
9. [Performance Issues](#performance-issues)
10. [User-Reported Issues](#user-reported-issues)

---

## 🚀 Quick Diagnostics

### First Response Checklist

```bash
#!/bin/bash
# Quick diagnostics script

echo "=== SigmaTrade Bot Quick Diagnostics ==="
echo "Time: $(date)"
echo ""

# 1. Bot status
echo "1. Bot Process:"
if pm2 status sigmatrade-bot | grep -q "online"; then
  echo "✅ Bot is running"
else
  echo "❌ Bot is NOT running"
fi

# 2. Database
echo -e "\n2. Database:"
if pg_isready -h localhost -U botuser -d sigmatrade &>/dev/null; then
  echo "✅ Database is accessible"
else
  echo "❌ Database is NOT accessible"
fi

# 3. Redis
echo -e "\n3. Redis:"
if redis-cli ping &>/dev/null; then
  echo "✅ Redis is running"
else
  echo "❌ Redis is NOT running"
fi

# 4. Recent errors
echo -e "\n4. Recent Errors (last 5):"
pm2 logs sigmatrade-bot --err --lines 5 --nostream 2>/dev/null || echo "No recent errors"

# 5. System resources
echo -e "\n5. System Resources:"
echo "Memory: $(free -h | awk '/^Mem:/ {print $3 "/" $2}')"
echo "CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}')%"
echo "Disk: $(df -h / | awk 'NR==2 {print $5}')"

echo -e "\n=== Diagnostics Complete ==="
```

**Save as:** `/home/bot/scripts/quick-diag.sh`

---

## 🤖 Bot Issues

### Issue: Bot Not Responding

**Symptoms:**
- Users report bot not responding to commands
- `/start` command doesn't work
- Bot shows as offline

**Diagnosis:**
```bash
# Check bot process
pm2 status sigmatrade-bot

# Check recent errors
pm2 logs sigmatrade-bot --err --lines 50

# Check if bot API is reachable
curl https://api.telegram.org/bot$BOT_TOKEN/getMe
```

**Solutions:**

#### Solution 1: Restart Bot
```bash
# Graceful restart
pm2 reload sigmatrade-bot

# If graceful restart fails
pm2 restart sigmatrade-bot --force

# Monitor logs
pm2 logs sigmatrade-bot --lines 100
```

#### Solution 2: Check Bot Token
```bash
# Verify bot token is valid
curl https://api.telegram.org/bot$BOT_TOKEN/getMe

# If invalid, update .env and restart
nano /home/bot/sigmatradebot/.env
pm2 restart sigmatrade-bot
```

#### Solution 3: Check Telegram API Status
```bash
# Check if Telegram API is down
curl -I https://api.telegram.org

# If down, wait for Telegram to restore service
# Monitor: https://status.telegram.org/
```

---

### Issue: Bot Crashes on Startup

**Symptoms:**
- Bot starts and immediately crashes
- Error in PM2 logs
- Status shows "errored"

**Diagnosis:**
```bash
# Check startup errors
pm2 logs sigmatrade-bot --err --lines 100

# Check environment variables
pm2 env sigmatrade-bot

# Try running directly (not via PM2)
cd /home/bot/sigmatradebot
node dist/index.js
```

**Common Causes & Solutions:**

#### Cause 1: Missing Environment Variables
```bash
# Check .env file
cat /home/bot/sigmatradebot/.env

# Verify all required variables are set
# Required: BOT_TOKEN, DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, REDIS_HOST, QUICKNODE_HTTPS_URL

# Fix: Add missing variables
nano /home/bot/sigmatradebot/.env
pm2 restart sigmatrade-bot
```

#### Cause 2: Database Connection Failed
```bash
# Test database connection
psql -h localhost -U botuser -d sigmatrade -c "SELECT 1;"

# If fails, check PostgreSQL is running
sudo systemctl status postgresql

# If not running, start it
sudo systemctl start postgresql

# Verify credentials
psql -h localhost -U postgres -c "SELECT usename FROM pg_user WHERE usename = 'botuser';"
```

#### Cause 3: Redis Connection Failed
```bash
# Test Redis connection
redis-cli ping

# If fails, check Redis is running
sudo systemctl status redis

# If not running, start it
sudo systemctl start redis

# Check Redis configuration
redis-cli CONFIG GET bind
redis-cli CONFIG GET port
```

#### Cause 4: TypeScript Compilation Errors
```bash
# Rebuild TypeScript
cd /home/bot/sigmatradebot
npm run build

# If build fails, check for syntax errors
npm run lint

# Fix errors and rebuild
npm run build
pm2 restart sigmatrade-bot
```

---

### Issue: High Memory Usage / Memory Leak

**Symptoms:**
- Memory usage continuously growing
- Bot becomes slow over time
- Eventually crashes with "Out of Memory"

**Diagnosis:**
```bash
# Check current memory usage
pm2 monit

# Check memory trend
pm2 logs sigmatrade-bot --lines 1000 | grep -i "memory"

# Get heap snapshot (requires heapdump module)
kill -USR2 $(pm2 pid sigmatrade-bot)
```

**Solutions:**

#### Solution 1: Increase Memory Limit
```bash
# Restart with higher memory limit
pm2 restart sigmatrade-bot --node-args="--max-old-space-size=2048"
```

#### Solution 2: Schedule Periodic Restarts
```bash
# Add to cron: restart bot daily at 4 AM
crontab -e
# Add line:
0 4 * * * pm2 restart sigmatrade-bot
```

#### Solution 3: Investigate Memory Leak
```bash
# Common sources:
# - Unclosed database connections
# - Event listener leaks
# - Large objects in global scope
# - Cached data not being cleared

# Check for:
# 1. Database connection pool exhaustion
psql -h localhost -U botuser -d sigmatrade -c "
  SELECT count(*) FROM pg_stat_activity WHERE datname = 'sigmatrade';
"

# 2. Redis key count growth
redis-cli DBSIZE

# 3. Clear caches
redis-cli FLUSHDB

pm2 restart sigmatrade-bot
```

---

## 🗄 Database Issues

### Issue: Database Connection Pool Exhausted

**Symptoms:**
- Error: "Connection pool exhausted"
- Error: "Too many connections"
- Bot slows down or stops responding

**Diagnosis:**
```sql
-- Check active connections
SELECT
  count(*),
  state,
  wait_event_type
FROM pg_stat_activity
WHERE datname = 'sigmatrade'
GROUP BY state, wait_event_type;

-- Check connection pool settings
SHOW max_connections;

-- Find long-running queries
SELECT
  pid,
  usename,
  state,
  query_start,
  NOW() - query_start as duration,
  query
FROM pg_stat_activity
WHERE datname = 'sigmatrade'
  AND state != 'idle'
ORDER BY duration DESC;
```

**Solutions:**

#### Solution 1: Kill Idle Connections
```sql
-- Kill idle connections (older than 30 minutes)
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'sigmatrade'
  AND state = 'idle'
  AND state_change < NOW() - INTERVAL '30 minutes';
```

#### Solution 2: Increase Connection Pool Size
```typescript
// src/config/database.config.ts
export const dataSourceOptions = {
  // ...
  extra: {
    max: 30,  // Increase from 20 to 30
    min: 5,
    acquireTimeout: 30000,
    idleTimeout: 600000,
  }
};
```

```bash
# Rebuild and restart
npm run build
pm2 restart sigmatrade-bot
```

#### Solution 3: Restart PostgreSQL
```bash
# Only as last resort!
sudo systemctl restart postgresql

# Wait for startup
sleep 5

# Restart bot
pm2 restart sigmatrade-bot
```

---

### Issue: Slow Database Queries

**Symptoms:**
- Bot responds slowly
- Timeouts on deposit processing
- Users experience delays

**Diagnosis:**
```sql
-- Find slow queries
SELECT
  query,
  calls,
  total_time,
  mean_time,
  max_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- Check for missing indexes
SELECT
  schemaname,
  tablename,
  attname,
  n_distinct,
  correlation
FROM pg_stats
WHERE schemaname = 'public'
  AND n_distinct > 100
  AND correlation < 0.1;

-- Check table bloat
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
  pg_total_relation_size(schemaname||'.'||tablename) AS bytes
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY bytes DESC;
```

**Solutions:**

#### Solution 1: Add Missing Indexes
```sql
-- Example: Add index on deposits.status
CREATE INDEX CONCURRENTLY idx_deposits_status
ON deposits(status)
WHERE status = 'pending';

-- Example: Add composite index
CREATE INDEX CONCURRENTLY idx_deposits_user_status
ON deposits(user_id, status);
```

#### Solution 2: Vacuum and Analyze
```sql
-- Analyze tables for query planner
ANALYZE VERBOSE;

-- Vacuum to reclaim space
VACUUM VERBOSE;

-- Full vacuum (requires downtime)
VACUUM FULL;
```

#### Solution 3: Optimize Query
```sql
-- Example: Optimize referral chain query
-- BEFORE (N+1 queries):
-- SELECT * FROM users WHERE id = 1;
-- SELECT * FROM users WHERE id = referrer_id; -- Repeated N times

-- AFTER (Single recursive CTE):
WITH RECURSIVE referral_chain AS (
  SELECT id, referrer_id, 1 as level
  FROM users WHERE id = 1
  UNION ALL
  SELECT u.id, u.referrer_id, rc.level + 1
  FROM users u
  JOIN referral_chain rc ON u.id = rc.referrer_id
  WHERE rc.level < 5
)
SELECT * FROM referral_chain;
```

---

### Issue: Database Deadlocks

**Symptoms:**
- Error: "deadlock detected"
- Transactions failing intermittently
- Race conditions on deposits/withdrawals

**Diagnosis:**
```sql
-- Check recent deadlocks
SELECT * FROM pg_stat_database_conflicts
WHERE datname = 'sigmatrade';

-- Enable deadlock logging
ALTER DATABASE sigmatrade SET deadlock_timeout = '1s';
ALTER DATABASE sigmatrade SET log_lock_waits = on;

-- Check locks
SELECT
  locktype,
  relation::regclass,
  mode,
  granted,
  pid
FROM pg_locks
WHERE NOT granted;
```

**Solutions:**

#### Solution 1: Use Pessimistic Locking
```typescript
// Ensure critical sections use pessimistic locking

await dataSource.transaction(async (manager) => {
  const deposit = await manager
    .createQueryBuilder(Deposit, 'deposit')
    .setLock('pessimistic_write')  // ✅ Prevents deadlocks
    .where('deposit.id = :id', { id: depositId })
    .getOne();

  // Process deposit...
  await manager.save(deposit);
});
```

#### Solution 2: Retry Logic for Deadlocks
```typescript
async function withDeadlockRetry<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3
): Promise<T> {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      if (error.code === '40P01' && attempt < maxRetries) {
        // Deadlock detected, retry
        await new Promise(resolve => setTimeout(resolve, 100 * attempt));
        continue;
      }
      throw error;
    }
  }
  throw new Error('Max retries exceeded');
}
```

---

## 🔴 Redis Issues

### Issue: Redis Memory Full

**Symptoms:**
- Error: "OOM command not allowed"
- Bot fails to cache data
- Rate limiting stops working

**Diagnosis:**
```bash
# Check memory usage
redis-cli INFO memory

# Check key count
redis-cli DBSIZE

# Check largest keys
redis-cli --bigkeys

# Check eviction statistics
redis-cli INFO stats | grep evicted
```

**Solutions:**

#### Solution 1: Clear Unnecessary Keys
```bash
# Delete old rate limit keys
redis-cli --scan --pattern "ratelimit:*" | while read key; do
  TTL=$(redis-cli TTL "$key")
  if [ "$TTL" -eq "-1" ]; then
    echo "Deleting key without TTL: $key"
    redis-cli DEL "$key"
  fi
done

# Clear old sessions
redis-cli --scan --pattern "session:*" | while read key; do
  TTL=$(redis-cli TTL "$key")
  if [ "$TTL" -le "0" ]; then
    redis-cli DEL "$key"
  fi
done
```

#### Solution 2: Increase Memory Limit
```bash
# Edit Redis config
sudo nano /etc/redis/redis.conf

# Change maxmemory
maxmemory 4gb  # Increase from 2gb to 4gb

# Restart Redis
sudo systemctl restart redis
```

#### Solution 3: Enable Eviction Policy
```bash
# Edit Redis config
sudo nano /etc/redis/redis.conf

# Set eviction policy
maxmemory-policy allkeys-lru

# Restart Redis
sudo systemctl restart redis
```

---

## ⛓ Blockchain Issues

### Issue: Blockchain Sync Stuck

**Symptoms:**
- Deposits not being detected
- Last processed block not updating
- Sync lag increasing

**Diagnosis:**
```bash
# Check last processed block
LAST_BLOCK=$(redis-cli GET last_processed_block)
echo "Last processed: $LAST_BLOCK"

# Check current blockchain height
CURRENT_BLOCK=$(node -e "
const ethers = require('ethers');
const provider = new ethers.JsonRpcProvider(process.env.QUICKNODE_HTTPS_URL);
provider.getBlockNumber().then(console.log);
" 2>/dev/null)
echo "Current block: $CURRENT_BLOCK"

# Calculate lag
echo "Lag: $((CURRENT_BLOCK - LAST_BLOCK)) blocks"

# Check bot logs for blockchain errors
pm2 logs sigmatrade-bot | grep -i blockchain
```

**Solutions:**

#### Solution 1: Reset Blockchain Sync
```bash
# Clear last processed block
redis-cli DEL last_processed_block
redis-cli DEL last_fetch_time

# Restart bot to trigger resync
pm2 restart sigmatrade-bot

# Monitor sync progress
watch -n 5 'redis-cli GET last_processed_block'
```

#### Solution 2: Check QuickNode Connection
```bash
# Test QuickNode endpoint
curl -X POST $QUICKNODE_HTTPS_URL \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# If fails, check QuickNode status
# Visit: https://dashboard.quicknode.com/

# If down, switch to backup RPC
# Edit .env:
QUICKNODE_HTTPS_URL=https://bsc-dataseed.binance.org/
pm2 restart sigmatrade-bot
```

#### Solution 3: Manual Sync Specific Block Range
```typescript
// scripts/manual-sync.ts
import { ethers } from 'ethers';

const provider = new ethers.JsonRpcProvider(process.env.QUICKNODE_HTTPS_URL);
const startBlock = 12345678;  // Replace with start block
const endBlock = 12345700;    // Replace with end block

async function manualSync() {
  for (let i = startBlock; i <= endBlock; i++) {
    const block = await provider.getBlock(i, true);
    console.log(`Processing block ${i}...`);

    // Process block transactions
    for (const tx of block.transactions) {
      // Your deposit detection logic here
    }
  }
}

manualSync();
```

---

## 💰 Deposit Problems

### Issue: Deposit Not Detected

**Symptoms:**
- User sent USDT but deposit not showing
- Transaction confirmed on BSCScan
- No record in database

**Diagnosis:**
```bash
# 1. Verify transaction on blockchain
TX_HASH="0x..."  # From user
curl "https://api.bscscan.com/api?module=transaction&action=gettxreceiptstatus&txhash=$TX_HASH&apikey=$BSCSCAN_API_KEY"

# 2. Check if transaction is in our system
psql -h localhost -U botuser -d sigmatrade -c "
  SELECT * FROM deposits WHERE tx_hash = '$TX_HASH';
"

# 3. Check user's wallet address
USER_TELEGRAM_ID="123456789"  # From user
psql -h localhost -U botuser -d sigmatrade -c "
  SELECT telegram_id, wallet_address FROM users WHERE telegram_id = '$USER_TELEGRAM_ID';
"

# 4. Verify transaction details on chain
node -e "
const ethers = require('ethers');
const provider = new ethers.JsonRpcProvider(process.env.QUICKNODE_HTTPS_URL);
const txHash = '$TX_HASH';

provider.getTransactionReceipt(txHash).then(receipt => {
  console.log('From:', receipt.from);
  console.log('To:', receipt.to);
  console.log('Status:', receipt.status);
  console.log('Block:', receipt.blockNumber);
});
"
```

**Solutions:**

#### Solution 1: Transaction Too Old (Expired)
```sql
-- Check if transaction is older than monitoring window
-- Add to expired_deposit_review table for admin approval

BEGIN;

INSERT INTO expired_deposit_review (
  user_id,
  tx_hash,
  user_reported_at,
  blockchain_data,
  status
)
SELECT
  u.id,
  '$TX_HASH',
  NOW(),
  '{"from": "0x...", "to": "0x...", "amount": "10.0", "blockNumber": 12345678}'::jsonb,
  'pending_review'
FROM users u
WHERE u.telegram_id = '$USER_TELEGRAM_ID';

COMMIT;

-- Notify admin for review
```

#### Solution 2: Wrong Recipient Address
```sql
-- If user sent to wrong address, no recovery possible
-- Document in support ticket

-- Check if transaction went to our system wallet
SELECT
  '$TX_HASH' as tx_hash,
  CASE
    WHEN to_address = '$SYSTEM_WALLET' THEN 'Correct address'
    ELSE 'Wrong address - no recovery'
  END as status
FROM transactions
WHERE tx_hash = '$TX_HASH';
```

#### Solution 3: Amount Mismatch (Out of Tolerance)
```sql
-- Check if amount is within tolerance (±0.01 USDT)
SELECT
  amount,
  CASE
    WHEN amount BETWEEN 9.99 AND 10.01 THEN 'Level 1 (valid)'
    WHEN amount BETWEEN 49.99 AND 50.01 THEN 'Level 2 (valid)'
    WHEN amount BETWEEN 99.99 AND 100.01 THEN 'Level 3 (valid)'
    WHEN amount BETWEEN 149.99 AND 150.01 THEN 'Level 4 (valid)'
    WHEN amount BETWEEN 299.99 AND 300.01 THEN 'Level 5 (valid)'
    ELSE 'Invalid amount - out of tolerance'
  END as validation
FROM deposits
WHERE tx_hash = '$TX_HASH';

-- If out of tolerance, may require manual review
```

---

## 💸 Payment & Withdrawal Issues

### Issue: Payment Stuck in DLQ

**Symptoms:**
- Withdrawal in Dead Letter Queue
- User not receiving funds
- Multiple retry attempts failed

**Diagnosis:**
```sql
-- Check DLQ item details
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
  AND user_id = (SELECT id FROM users WHERE telegram_id = '<user_telegram_id>');
```

**Solutions:**

#### Solution 1: Manual Payment via BSCScan
```bash
# 1. Verify user's wallet address
# 2. Use hot wallet to send USDT manually
# 3. Get transaction hash from BSCScan
# 4. Update database

psql -h localhost -U botuser -d sigmatrade << EOF
BEGIN;

UPDATE payment_retry
SET
  status = 'success',
  tx_hash = '0x...', -- Transaction hash from BSCScan
  resolved_by = '<admin_telegram_id>',
  resolved_at = NOW(),
  admin_notes = 'Manually sent via BSCScan due to DLQ'
WHERE id = <dlq_item_id>;

COMMIT;
EOF

# 5. Notify user
```

#### Solution 2: Retry with Different Gas Settings
```bash
# Reset DLQ item for retry with different settings
psql -h localhost -U botuser -d sigmatrade -c "
  UPDATE payment_retry
  SET
    status = 'pending',
    attempt_number = 0,
    next_retry_at = NOW(),
    last_error = NULL,
    metadata = jsonb_set(
      COALESCE(metadata, '{}'::jsonb),
      '{gas_multiplier}',
      '1.5'  -- Increase gas by 50%
    )
  WHERE id = <dlq_item_id>;
"

# Bot will retry on next job run
```

#### Solution 3: Cancel and Refund
```sql
-- If payment cannot be completed, refund to user balance

BEGIN;

-- Mark payment as cancelled
UPDATE payment_retry
SET status = 'cancelled'
WHERE id = <dlq_item_id>;

-- Refund to user balance
UPDATE users
SET balance = balance + (SELECT amount FROM payment_retry WHERE id = <dlq_item_id>)
WHERE id = (SELECT user_id FROM payment_retry WHERE id = <dlq_item_id>);

-- Log admin action
INSERT INTO admin_actions (admin_id, action_type, target_user_id, details)
VALUES ('<admin_id>', 'payment_refund', '<user_id>', '{"dlq_item_id": <dlq_item_id>, "reason": "Unable to process payment"}');

COMMIT;
```

---

## 📢 Notification Issues

### Issue: Users Not Receiving Notifications

**Symptoms:**
- Deposit confirmed but user not notified
- Bot commands work but no responses
- Notification failures in logs

**Diagnosis:**
```bash
# Check recent notification failures
pm2 logs sigmatrade-bot | grep -i "notification.*fail"

# Check notification_failure table
psql -h localhost -U botuser -d sigmatrade -c "
  SELECT
    nf.id,
    u.telegram_id,
    nf.notification_type,
    nf.attempt_count,
    nf.last_error,
    nf.created_at
  FROM notification_failure nf
  JOIN users u ON nf.user_id = u.id
  ORDER BY nf.created_at DESC
  LIMIT 10;
"

# Test bot can send messages
curl -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
  -d "chat_id=<admin_chat_id>" \
  -d "text=Test message"
```

**Solutions:**

#### Solution 1: User Blocked Bot
```bash
# Error: "Forbidden: bot was blocked by the user"

# Mark user as having blocked bot
psql -h localhost -U botuser -d sigmatrade -c "
  UPDATE users
  SET bot_blocked = true, bot_blocked_at = NOW()
  WHERE telegram_id = '<user_telegram_id>';
"

# Stop sending notifications to this user
# User must /start bot again to re-enable
```

#### Solution 2: Telegram API Rate Limit
```bash
# Error: "429 Too Many Requests"

# Slow down notification sending
# Implement delay between notifications

# Check rate limit in Redis
redis-cli GET "ratelimit:telegram_api:messages"

# Clear if stuck
redis-cli DEL "ratelimit:telegram_api:messages"

# Retry failed notifications
psql -h localhost -U botuser -d sigmatrade -c "
  UPDATE notification_failure
  SET
    attempt_count = 0,
    next_retry_at = NOW() + INTERVAL '5 minutes'
  WHERE last_error LIKE '%429%'
    AND attempt_count < 5;
"
```

#### Solution 3: Invalid Chat ID
```bash
# Error: "Bad Request: chat not found"

# Verify user's Telegram ID
psql -h localhost -U botuser -d sigmatrade -c "
  SELECT telegram_id, username FROM users
  WHERE id = <user_id>;
"

# Test sending to this chat ID
curl -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
  -d "chat_id=<telegram_id>" \
  -d "text=Test"

# If fails, ask user to /start bot again
```

---

## ⚡ Performance Issues

### Issue: Bot Slow to Respond

**Symptoms:**
- Commands take >5 seconds to respond
- Users report timeouts
- High response time in metrics

**Diagnosis:**
```bash
# Check system resources
top
free -h
df -h

# Check slow queries
psql -h localhost -U botuser -d sigmatrade -c "
  SELECT
    query,
    mean_time,
    calls
  FROM pg_stat_statements
  ORDER BY mean_time DESC
  LIMIT 10;
"

# Check Redis latency
redis-cli --latency

# Check bot logs for slow operations
pm2 logs sigmatrade-bot | grep -i "slow"
```

**Solutions:**

#### Solution 1: Clear Redis Cache
```bash
# Clear all caches to force rebuild
redis-cli FLUSHDB

# Restart bot
pm2 restart sigmatrade-bot
```

#### Solution 2: Optimize Database
```bash
# Run maintenance script
/home/bot/scripts/weekly-maintenance.sh

# Or manually:
psql -h localhost -U botuser -d sigmatrade -c "VACUUM ANALYZE;"
```

#### Solution 3: Upgrade Resources
```bash
# Check if system resources are maxed out
# CPU >80%, Memory >85%, Disk >85%

# If yes, consider:
# - Upgrading VM instance type
# - Adding more memory
# - Scaling horizontally (multiple bot instances)
```

---

## 👥 User-Reported Issues

### Issue: "My balance is incorrect"

**Investigation:**
```sql
-- Check user's transaction history
SELECT
  t.id,
  t.type,
  t.amount,
  t.status,
  t.created_at
FROM transactions t
JOIN users u ON t.user_id = u.id
WHERE u.telegram_id = '<user_telegram_id>'
ORDER BY t.created_at DESC;

-- Calculate expected balance
SELECT
  SUM(CASE WHEN type IN ('deposit', 'referral_reward') THEN amount ELSE 0 END) -
  SUM(CASE WHEN type IN ('withdrawal') THEN amount ELSE 0 END) as calculated_balance,
  (SELECT balance FROM users WHERE telegram_id = '<user_telegram_id>') as actual_balance
FROM transactions t
JOIN users u ON t.user_id = u.id
WHERE u.telegram_id = '<user_telegram_id>';
```

---

### Issue: "I can't withdraw my funds"

**Investigation:**
```sql
-- Check withdrawal eligibility
SELECT
  u.balance,
  u.is_banned,
  u.is_verified,
  COUNT(d.id) as deposit_count,
  COUNT(DISTINCT r.referral_id) as referral_count
FROM users u
LEFT JOIN deposits d ON d.user_id = u.id AND d.status = 'confirmed'
LEFT JOIN referrals r ON r.referrer_id = u.id
WHERE u.telegram_id = '<user_telegram_id>'
GROUP BY u.id;

-- Check pending withdrawals
SELECT * FROM payment_retry
WHERE user_id = (SELECT id FROM users WHERE telegram_id = '<user_telegram_id>')
ORDER BY created_at DESC;
```

---

### Issue: "My referral link doesn't work"

**Investigation:**
```sql
-- Check referral structure
SELECT
  u.telegram_id,
  u.first_name,
  r.first_name as referred_by,
  u.created_at
FROM users u
LEFT JOIN users r ON u.referrer_id = r.id
WHERE u.telegram_id = '<user_telegram_id>';

-- Check for circular referrals
WITH RECURSIVE ref_chain AS (
  SELECT id, referrer_id, 1 as depth, ARRAY[id] as path
  FROM users WHERE telegram_id = '<user_telegram_id>'

  UNION ALL

  SELECT u.id, u.referrer_id, rc.depth + 1, rc.path || u.id
  FROM users u
  JOIN ref_chain rc ON u.id = rc.referrer_id
  WHERE rc.depth < 10 AND NOT u.id = ANY(rc.path)
)
SELECT * FROM ref_chain;
```

---

## 📞 Getting Help

### When to Escalate

- Issue not resolved after 30 minutes
- Critical issue affecting multiple users
- Security concern
- Data integrity issue

### Escalation Contacts

```yaml
Level 1 - On-Call Engineer:
  Telegram: @oncall_engineer
  Response: 15 minutes (P1), 1 hour (P2)

Level 2 - Team Lead:
  Telegram: @team_lead
  Email: team.lead@example.com
  Response: 30 minutes (P1), 2 hours (P2)

Level 3 - CTO:
  Phone: +1-XXX-XXX-XXXX
  Email: cto@example.com
  Response: 1 hour (P1 only)
```

---

## 📚 Additional Resources

- [Operations Runbook](./OPERATIONS.md)
- [Monitoring Guide](./MONITORING.md)
- [Architecture Documentation](./ARCHITECTURE.md)
- [Deployment Guide](./DEPLOYMENT_GUIDE.md)

---

**Last Updated:** 2025-11-11
**Version:** 1.0
**Next Review:** 2025-12-11
