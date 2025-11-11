# Database Migrations Guide

## Overview

This document provides comprehensive information about all database migrations created during the refactoring process, including rollback procedures and deployment guidelines.

---

## Migration List

All migrations are located in `src/database/migrations/` and follow the naming pattern:
`{timestamp}-{DescriptiveName}.ts`

### Migration 1: AddDepositConstraints (1699999999001)
**Related Fix:** FIX #3 - Race Conditions in Deposit Processing
**Purpose:** Add database-level locking for deposit processing to prevent race conditions

**Changes:**
- Adds `processing_started_at` column to `deposits` table (TIMESTAMP, nullable)
- Adds `processed_by` column to `deposits` table (VARCHAR(255), nullable)
- Creates index `IDX_deposits_processing` for efficient lock queries

**Impact:** Medium - Adds columns but doesn't modify existing data

**Rollback:**
```sql
DROP INDEX IF EXISTS "IDX_deposits_processing";
ALTER TABLE "deposits" DROP COLUMN IF EXISTS "processed_by";
ALTER TABLE "deposits" DROP COLUMN IF EXISTS "processing_started_at";
```

---

### Migration 2: AddTransactionDeduplication (1699999999002)
**Related Fix:** FIX #18 - Transaction Deduplication
**Purpose:** Prevent duplicate transaction processing with database-level constraints

**Changes:**
- Creates UNIQUE partial index on `transactions.tx_hash`
- Index only applies where `tx_hash IS NOT NULL AND tx_hash != ''`

**Impact:** Low - Only adds an index, no data modification

**Rollback:**
```sql
DROP INDEX IF EXISTS "IDX_transactions_tx_hash_unique";
```

---

### Migration 3: AddPaymentRetrySystem (1699999999003)
**Related Fix:** FIX #4 - Payment Retry with Exponential Backoff
**Purpose:** Create infrastructure for automatic payment retry mechanism

**Changes:**
- Creates `payment_retries` table with fields:
  - `id` (SERIAL PRIMARY KEY)
  - `user_id` (INTEGER, NOT NULL)
  - `amount` (DECIMAL(18,8), NOT NULL)
  - `payment_type` (ENUM: 'REFERRAL_EARNING', 'DEPOSIT_REWARD')
  - `earning_ids` (INTEGER ARRAY)
  - `attempt_count` (INTEGER, DEFAULT 0)
  - `max_retries` (INTEGER, DEFAULT 5)
  - `next_retry_at` (TIMESTAMP, nullable)
  - `last_error` (TEXT, nullable)
  - `in_dlq` (BOOLEAN, DEFAULT false)
  - `resolved` (BOOLEAN, DEFAULT false)
  - `created_at`, `updated_at` (TIMESTAMP)
- Creates index `IDX_payment_retries_pending` for efficient retry queries
- Creates index `IDX_payment_retries_dlq` for DLQ monitoring

**Impact:** High - Creates new table, but doesn't modify existing tables

**Rollback:**
```sql
DROP INDEX IF EXISTS "IDX_payment_retries_dlq";
DROP INDEX IF EXISTS "IDX_payment_retries_pending";
DROP TABLE IF EXISTS "payment_retries";
```

---

### Migration 4: AddFailedNotifications (1699999999004)
**Related Fix:** FIX #17 - Notification Failure Alerting
**Purpose:** Track and retry failed notification deliveries

**Changes:**
- Creates `failed_notifications` table with fields:
  - `id` (SERIAL PRIMARY KEY)
  - `user_telegram_id` (BIGINT, NOT NULL)
  - `notification_type` (VARCHAR(100), NOT NULL)
  - `message` (TEXT, NOT NULL)
  - `metadata` (JSONB, nullable)
  - `attempt_count` (INTEGER, DEFAULT 1)
  - `last_error` (TEXT, nullable)
  - `resolved` (BOOLEAN, DEFAULT false)
  - `critical` (BOOLEAN, DEFAULT false)
  - `created_at`, `updated_at`, `last_attempt_at`, `resolved_at` (TIMESTAMP)
- Creates index `IDX_failed_notifications_retry` for pending retries
- Creates index `IDX_failed_notifications_critical` for critical alerts
- Creates index `IDX_failed_notifications_user` for user lookup
- Creates index `IDX_failed_notifications_type` for type analytics

**Impact:** High - Creates new table with multiple indexes

**Rollback:**
```sql
DROP INDEX IF EXISTS "IDX_failed_notifications_type";
DROP INDEX IF EXISTS "IDX_failed_notifications_user";
DROP INDEX IF EXISTS "IDX_failed_notifications_critical";
DROP INDEX IF EXISTS "IDX_failed_notifications_retry";
DROP TABLE IF EXISTS "failed_notifications";
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] **Backup Database**
  ```bash
  pg_dump -h $DB_HOST -U $DB_USERNAME -d $DB_DATABASE -F c -b -v -f "backup_$(date +%Y%m%d_%H%M%S).dump"
  ```

- [ ] **Verify Environment Variables**
  - [ ] `DB_HOST`, `DB_PORT`, `DB_USERNAME`, `DB_PASSWORD`, `DB_DATABASE` are set
  - [ ] `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` are set
  - [ ] `TELEGRAM_BOT_TOKEN` is set
  - [ ] `QUICKNODE_HTTPS_URL`, `QUICKNODE_WSS_URL` are set
  - [ ] `SYSTEM_WALLET_ADDRESS`, `PAYOUT_WALLET_ADDRESS` are set

- [ ] **Test Migrations on Copy**
  ```bash
  # Create test database copy
  pg_dump -h $DB_HOST -U $DB_USERNAME -d $DB_DATABASE | psql -h $DB_HOST -U $DB_USERNAME -d ${DB_DATABASE}_test

  # Run migrations on test database
  DB_DATABASE=${DB_DATABASE}_test npm run migration:run

  # Verify migrations
  DB_DATABASE=${DB_DATABASE}_test npm run migration:show
  ```

- [ ] **Stop Bot Gracefully**
  ```bash
  # Send SIGTERM to allow graceful shutdown
  kill -SIGTERM $(cat bot.pid)

  # Wait for shutdown (max 30 seconds)
  timeout 30 tail --pid=$(cat bot.pid) -f /dev/null
  ```

### Deployment

- [ ] **Pull Latest Code**
  ```bash
  git fetch origin
  git checkout claude/project-exploration-011CUzxPR2oSUcyCnUd4oR1Q
  git pull
  ```

- [ ] **Install Dependencies**
  ```bash
  npm ci --production
  ```

- [ ] **Run Migrations**
  ```bash
  npm run migration:run
  ```

- [ ] **Verify Migration Status**
  ```bash
  npm run migration:show
  ```

- [ ] **Start Bot**
  ```bash
  npm start
  ```

### Post-Deployment Verification

- [ ] **Check Logs**
  ```bash
  tail -f logs/app.log | grep -E "ERROR|WARN|Migration"
  ```

- [ ] **Verify Database Schema**
  ```sql
  -- Check new columns exist
  SELECT column_name, data_type FROM information_schema.columns
  WHERE table_name = 'deposits' AND column_name IN ('processing_started_at', 'processed_by');

  -- Check new tables exist
  SELECT table_name FROM information_schema.tables
  WHERE table_name IN ('payment_retries', 'failed_notifications');

  -- Check indexes exist
  SELECT indexname FROM pg_indexes
  WHERE indexname LIKE 'IDX_payment_retries%' OR indexname LIKE 'IDX_failed_notifications%';
  ```

- [ ] **Test Core Functionality**
  - [ ] Send test message to bot → Verify response
  - [ ] Check blockchain monitoring → Verify WebSocket connection
  - [ ] Monitor Redis → Verify sessions are stored
  - [ ] Check admin panel → Verify admin login works

- [ ] **Monitor Background Jobs**
  ```bash
  # Check job queues in Redis
  redis-cli KEYS "bull:*"

  # Check job counts
  redis-cli HGETALL "bull:payment-retry:counts"
  redis-cli HGETALL "bull:notification-retry:counts"
  ```

### Rollback Procedure (If Needed)

If issues are detected after deployment:

1. **Stop Bot**
   ```bash
   kill -SIGTERM $(cat bot.pid)
   ```

2. **Restore Database from Backup**
   ```bash
   # Drop current database (BE CAREFUL!)
   dropdb -h $DB_HOST -U $DB_USERNAME $DB_DATABASE

   # Restore from backup
   pg_restore -h $DB_HOST -U $DB_USERNAME -d $DB_DATABASE -v "backup_YYYYMMDD_HHMMSS.dump"
   ```

3. **Checkout Previous Version**
   ```bash
   git checkout <previous-commit-hash>
   npm ci --production
   ```

4. **Start Bot**
   ```bash
   npm start
   ```

---

## Migration Testing Strategy

### Unit Testing

Test each migration independently:

```typescript
describe('Migration: AddDepositConstraints', () => {
  it('should add processing_started_at column', async () => {
    const result = await queryRunner.query(`
      SELECT column_name FROM information_schema.columns
      WHERE table_name = 'deposits' AND column_name = 'processing_started_at'
    `);
    expect(result.length).toBe(1);
  });

  it('should add processed_by column', async () => {
    const result = await queryRunner.query(`
      SELECT column_name FROM information_schema.columns
      WHERE table_name = 'deposits' AND column_name = 'processed_by'
    `);
    expect(result.length).toBe(1);
  });

  it('should create IDX_deposits_processing index', async () => {
    const result = await queryRunner.query(`
      SELECT indexname FROM pg_indexes
      WHERE indexname = 'IDX_deposits_processing'
    `);
    expect(result.length).toBe(1);
  });
});
```

### Integration Testing

Test migrations in sequence:

```typescript
describe('Migration Sequence', () => {
  it('should run all migrations without errors', async () => {
    await connection.runMigrations();
    const migrations = await connection.showMigrations();
    expect(migrations).toBe(false); // false means all migrations are applied
  });

  it('should rollback all migrations without errors', async () => {
    await connection.undoLastMigration();
    await connection.undoLastMigration();
    await connection.undoLastMigration();
    await connection.undoLastMigration();
    // Verify tables don't exist
  });
});
```

### Load Testing

After migration, test system under load:

```bash
# Simulate 100 concurrent users
artillery run load-test.yml

# Monitor database performance
psql -h $DB_HOST -U $DB_USERNAME -d $DB_DATABASE -c "
  SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
  FROM pg_stat_user_indexes
  WHERE indexname LIKE 'IDX_%'
  ORDER BY idx_scan DESC;
"
```

---

## Troubleshooting

### Migration Failed Mid-Execution

If a migration fails partway through:

1. **Check error message**
   ```bash
   tail -100 logs/app.log | grep -A 10 "Migration.*failed"
   ```

2. **Check migration status**
   ```bash
   npm run migration:show
   ```

3. **Manually revert partial changes** (if needed)
   ```sql
   -- Example: If AddPaymentRetrySystem partially created table
   DROP TABLE IF EXISTS payment_retries CASCADE;
   ```

4. **Mark migration as reverted in migrations table**
   ```sql
   DELETE FROM migrations WHERE name = 'AddPaymentRetrySystem1699999999003';
   ```

5. **Fix migration code and retry**

### Index Creation Takes Too Long

If index creation is blocking:

1. **Create indexes concurrently** (requires manual intervention):
   ```sql
   CREATE INDEX CONCURRENTLY "IDX_deposits_processing"
   ON "deposits" ("status", "processing_started_at")
   WHERE "status" = 'PENDING';
   ```

2. **Monitor index creation progress**:
   ```sql
   SELECT
     now()::time(0),
     a.query,
     p.phase,
     p.blocks_done,
     p.blocks_total,
     round(p.blocks_done / p.blocks_total::numeric * 100, 2) AS "% Complete"
   FROM pg_stat_progress_create_index p
   JOIN pg_stat_activity a ON p.pid = a.pid;
   ```

### Rollback Failed

If rollback encounters errors:

1. **Manually drop objects in correct order**:
   ```sql
   -- Drop indexes first
   DROP INDEX IF EXISTS "IDX_payment_retries_dlq";
   DROP INDEX IF EXISTS "IDX_payment_retries_pending";

   -- Then drop tables
   DROP TABLE IF EXISTS "payment_retries" CASCADE;
   ```

2. **Clean up migrations table**:
   ```sql
   DELETE FROM migrations WHERE timestamp >= 1699999999001;
   ```

---

## Performance Considerations

### Migration 3 & 4 (New Tables)

**Impact:** These migrations create new tables that will grow over time.

**Monitoring:**
```sql
-- Check table sizes
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
  pg_total_relation_size(schemaname||'.'||tablename) AS size_bytes
FROM pg_tables
WHERE tablename IN ('payment_retries', 'failed_notifications')
ORDER BY size_bytes DESC;

-- Check index usage
SELECT
  schemaname,
  tablename,
  indexname,
  idx_scan AS index_scans,
  idx_tup_read AS tuples_read,
  idx_tup_fetch AS tuples_fetched
FROM pg_stat_user_indexes
WHERE tablename IN ('payment_retries', 'failed_notifications')
ORDER BY idx_scan DESC;
```

**Maintenance:**
```sql
-- Periodically clean up resolved entries (keep last 30 days for analytics)
DELETE FROM payment_retries
WHERE resolved = true
  AND updated_at < NOW() - INTERVAL '30 days';

DELETE FROM failed_notifications
WHERE resolved = true
  AND updated_at < NOW() - INTERVAL '30 days';

-- Vacuum tables after cleanup
VACUUM ANALYZE payment_retries;
VACUUM ANALYZE failed_notifications;
```

---

## Additional Notes

### Database User Permissions

Ensure the database user has necessary permissions:

```sql
GRANT ALL PRIVILEGES ON DATABASE your_database TO your_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_user;
```

### Connection Pooling

After migrations, consider adjusting connection pool settings if new background jobs increase load:

```typescript
// In data-source.ts
extra: {
  max: 20, // Maximum pool size (was 10)
  min: 5,  // Minimum pool size
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 5000,
}
```

---

## Success Criteria

Migrations are considered successful when:

- ✅ All migrations apply without errors
- ✅ Rollback procedure works correctly
- ✅ No data loss occurs
- ✅ Application starts and runs normally
- ✅ All background jobs process correctly
- ✅ No performance degradation
- ✅ Database indexes are being used (check `idx_scan > 0`)

---

## Contact & Support

If you encounter issues during migration:

1. Check logs: `tail -f logs/app.log`
2. Check database connections: `psql -h $DB_HOST -U $DB_USERNAME -d $DB_DATABASE -c "SELECT version();"`
3. Verify Redis: `redis-cli ping`
4. Review this document's troubleshooting section

**Emergency Rollback:** Follow "Rollback Procedure" section above.
