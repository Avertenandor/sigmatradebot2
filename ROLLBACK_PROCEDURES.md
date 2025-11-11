# Rollback Procedures

## Overview

This document describes procedures for rolling back changes in case of problems after deployment, database migrations, or critical bugs. All procedures are designed to minimize downtime and data loss.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Rollback Scenarios](#rollback-scenarios)
3. [Database Rollback](#database-rollback)
4. [Code Rollback](#code-rollback)
5. [Configuration Rollback](#configuration-rollback)
6. [Emergency Procedures](#emergency-procedures)
7. [Post-Rollback Verification](#post-rollback-verification)
8. [Incident Response](#incident-response)

---

## Prerequisites

### Required Access

- SSH access to production server
- Database credentials (read from `.env` file)
- Git repository access
- Admin privileges for application restart

### Required Tools

```bash
# Verify all tools are available
command -v git && echo "✓ Git" || echo "✗ Git missing"
command -v pg_dump && echo "✓ pg_dump" || echo "✗ PostgreSQL tools missing"
command -v pg_restore && echo "✓ pg_restore" || echo "✗ PostgreSQL tools missing"
command -v psql && echo "✓ psql" || echo "✗ PostgreSQL tools missing"
command -v node && echo "✓ Node.js" || echo "✗ Node.js missing"
command -v npm && echo "✓ npm" || echo "✗ npm missing"
command -v pm2 && echo "✓ PM2" || echo "✗ PM2 missing"
```

### Backup Verification

Before any rollback, verify backups exist:

```bash
# List available backups
ls -lh backups/daily/ | tail -10
ls -lh backups/monthly/ | tail -10
ls -lh backups/safety/ | tail -5

# Verify latest backup
./scripts/backup-production.sh --verify-only
```

---

## Rollback Scenarios

### Scenario Matrix

| Issue | Severity | Rollback Type | Estimated Time | Risk Level |
|-------|----------|---------------|----------------|------------|
| Bad code deployment | HIGH | Code rollback | 2-5 min | LOW |
| Failed database migration | CRITICAL | Database rollback | 5-15 min | MEDIUM |
| Configuration error | MEDIUM | Config rollback | 1-2 min | LOW |
| Data corruption | CRITICAL | Database restore | 10-30 min | HIGH |
| Security breach | CRITICAL | Full rollback | 15-45 min | HIGH |
| Performance degradation | MEDIUM | Selective rollback | 5-10 min | LOW |

---

## Database Rollback

### 1. Rollback Recent Migration

**When to use:** After a failed or problematic database migration

**Steps:**

```bash
# 1. Stop the application immediately
pm2 stop sigmatradebot

# 2. Check migration status
npm run migration:show

# 3. Revert the last migration
npm run migration:revert

# 4. Verify database state
npm run migration:show

# 5. Restart application
pm2 start sigmatradebot
pm2 logs --lines 50
```

**Rollback if still broken:** Continue to full database restore below.

### 2. Full Database Restore

**When to use:** Data corruption, multiple failed migrations, or critical database issues

**CRITICAL: This will lose all data since the backup was created!**

```bash
# 1. IMMEDIATELY stop the application to prevent further damage
pm2 stop sigmatradebot

# 2. Notify users (if possible)
# TODO: Send Telegram broadcast about maintenance

# 3. Create safety backup of current state (even if broken)
./scripts/backup-production.sh

# 4. Choose backup to restore from
ls -lht backups/daily/ | head -10

# 5. Dry-run to verify backup
./scripts/restore-from-backup.sh backups/daily/sigmatrade_YYYYMMDD_HHMMSS.sql.gz --dry-run

# 6. Perform restore (creates automatic safety backup)
./scripts/restore-from-backup.sh backups/daily/sigmatrade_YYYYMMDD_HHMMSS.sql.gz

# 7. Verify database
npm run migration:show
psql $DATABASE_URL -c "SELECT COUNT(*) FROM users;"
psql $DATABASE_URL -c "SELECT COUNT(*) FROM deposits;"

# 8. Restart application
pm2 start sigmatradebot
pm2 logs --lines 100
```

**Important Notes:**
- The restore script automatically creates a safety backup before restoration
- If restore fails, you can restore from the safety backup
- All transactions between backup time and restore time will be lost
- After restore, manually reconcile blockchain deposits that occurred during the gap

### 3. Partial Data Restore

**When to use:** Only specific table(s) are corrupted

```bash
# 1. Stop application
pm2 stop sigmatradebot

# 2. Export specific table from backup
pg_restore -h $DB_HOST -p $DB_PORT -U $DB_USERNAME \
  --table=users \
  backups/daily/sigmatrade_YYYYMMDD_HHMMSS.sql.gz \
  > /tmp/users_backup.sql

# 3. Backup current table state
pg_dump -h $DB_HOST -p $DB_PORT -U $DB_USERNAME \
  --table=users \
  $DB_DATABASE > /tmp/users_current.sql

# 4. Restore table
psql -h $DB_HOST -p $DB_PORT -U $DB_USERNAME -d $DB_DATABASE <<EOF
BEGIN;
TRUNCATE users CASCADE;
-- Then restore from backup
\i /tmp/users_backup.sql
COMMIT;
EOF

# 5. Restart application
pm2 start sigmatradebot
```

---

## Code Rollback

### 1. Git-Based Rollback

**When to use:** Bad code deployment, introduced bugs

**Steps:**

```bash
# 1. Check current commit
git log --oneline -5

# 2. Check application logs to identify problem
pm2 logs --lines 200

# 3. Stop application
pm2 stop sigmatradebot

# 4. Rollback to previous commit
git log --oneline -10  # Find the good commit
git checkout <GOOD_COMMIT_HASH>

# 5. Reinstall dependencies (if package.json changed)
npm install

# 6. Rebuild application
npm run build

# 7. Restart application
pm2 start sigmatradebot

# 8. Verify functionality
pm2 logs --lines 50

# 9. If successful, create a new branch from good commit
git checkout -b hotfix/rollback-$(date +%Y%m%d)
```

### 2. Selective File Rollback

**When to use:** Only specific files are problematic

```bash
# 1. Identify problematic files from logs/errors
pm2 logs --err --lines 100

# 2. Rollback specific files
git checkout HEAD~1 -- src/services/payment.service.ts
git checkout HEAD~1 -- src/services/deposit.service.ts

# 3. Rebuild
npm run build

# 4. Restart
pm2 restart sigmatradebot
```

### 3. Emergency Stop (No Rollback Yet)

**When to use:** Need to stop quickly while investigating

```bash
# Stop application immediately
pm2 stop sigmatradebot

# Check what's happening
pm2 logs --lines 500 > /tmp/emergency-logs.txt

# Check database state
psql $DATABASE_URL -c "SELECT status, COUNT(*) FROM deposits GROUP BY status;"
psql $DATABASE_URL -c "SELECT status, COUNT(*) FROM withdrawals GROUP BY status;"

# Analyze and decide next steps
```

---

## Configuration Rollback

### 1. Environment Variables

**When to use:** Configuration changes caused issues

```bash
# 1. Check current config
cat .env | grep -v PASSWORD | grep -v PRIVATE_KEY

# 2. Restore from git (if tracked)
git checkout HEAD~1 -- .env.example

# 3. Or restore from backup
cp .env .env.broken
cp backups/config/.env.backup-YYYYMMDD .env

# 4. Restart application
pm2 restart sigmatradebot
```

### 2. Feature Flags

**When to use:** A feature flag caused problems

```bash
# Edit .env and disable the problematic feature
# Example:
# FEATURE_DEPOSITS_ENABLED=false
# FEATURE_WITHDRAWALS_ENABLED=false

pm2 restart sigmatradebot
```

---

## Emergency Procedures

### Critical Financial Issue Detected

**Symptoms:** Wrong amounts paid, double payments, missing funds

```bash
# STEP 1: STOP EVERYTHING IMMEDIATELY
pm2 stop sigmatradebot
pm2 stop all  # Stop all background jobs

# STEP 2: Disable blockchain monitoring
# Edit .env:
echo "JOB_BLOCKCHAIN_MONITOR_ENABLED=false" >> .env
echo "JOB_PAYMENT_PROCESSOR_ENABLED=false" >> .env

# STEP 3: Create emergency backup
./scripts/backup-production.sh

# STEP 4: Document the issue
cat > /tmp/incident-$(date +%Y%m%d_%H%M%S).txt <<EOF
INCIDENT REPORT
Date: $(date)
Issue: [DESCRIBE ISSUE]
Affected: [users/deposits/withdrawals]
Log excerpt:
$(pm2 logs --lines 100 --nostream)
EOF

# STEP 5: Check financial state
psql $DATABASE_URL <<EOF
-- Total deposits
SELECT status, SUM(amount) as total, COUNT(*) as count
FROM deposits
GROUP BY status;

-- Total withdrawals
SELECT status, SUM(amount) as total, COUNT(*) as count
FROM withdrawals
GROUP BY status;

-- Recent transactions (last hour)
SELECT type, status, amount, created_at
FROM transactions
WHERE created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC;
EOF

# STEP 6: DO NOT restart until issue is understood and fixed
```

### Security Breach Detected

```bash
# STEP 1: IMMEDIATELY ISOLATE
pm2 stop sigmatradebot

# STEP 2: Change all secrets
# Generate new master key
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"

# Update .env with new credentials

# STEP 3: Revoke all admin sessions
psql $DATABASE_URL <<EOF
DELETE FROM admin_sessions;
COMMIT;
EOF

# STEP 4: Create forensic backup
./scripts/backup-production.sh
cp -r backups backups-forensics-$(date +%Y%m%d)

# STEP 5: Investigate logs
grep -i "unauthorized\|invalid\|attack" logs/*.log > /tmp/security-analysis.txt

# STEP 6: After investigation and fixes, restart with new security measures
pm2 start sigmatradebot
```

---

## Post-Rollback Verification

### Checklist

After any rollback, verify the following:

#### 1. Application Health

```bash
# Check application is running
pm2 status

# Check for errors in logs
pm2 logs --lines 100 --err

# Check memory usage
pm2 monit
```

#### 2. Database Integrity

```bash
psql $DATABASE_URL <<EOF
-- Check table counts
SELECT 'users' as table_name, COUNT(*) FROM users
UNION ALL
SELECT 'deposits', COUNT(*) FROM deposits
UNION ALL
SELECT 'withdrawals', COUNT(*) FROM withdrawals
UNION ALL
SELECT 'transactions', COUNT(*) FROM transactions
UNION ALL
SELECT 'referrals', COUNT(*) FROM referrals;

-- Check for orphaned records
SELECT 'orphaned deposits' as issue, COUNT(*)
FROM deposits d
WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.id = d.user_id);

-- Check recent activity
SELECT 'recent deposits' as activity, COUNT(*)
FROM deposits
WHERE created_at > NOW() - INTERVAL '1 hour';
EOF
```

#### 3. Blockchain Synchronization

```bash
# Check if blockchain monitor is working
pm2 logs | grep -i "blockchain\|deposit\|confirmation"

# Manually check latest deposits
psql $DATABASE_URL <<EOF
SELECT tx_hash, amount, status, confirmations, created_at
FROM deposits
WHERE created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC
LIMIT 10;
EOF
```

#### 4. User Functionality

Test critical user flows:

1. **/start command** - User registration
2. **/deposit command** - Deposit flow
3. **/balance command** - Balance display
4. **/withdraw command** - Withdrawal flow
5. **/referral command** - Referral system

#### 5. Admin Panel

```bash
# Test admin authentication
# Try to access admin panel via bot

# Check admin logs
pm2 logs | grep -i admin
```

---

## Incident Response

### Post-Incident Report Template

After any rollback, document the incident:

```markdown
# Incident Report: [TITLE]

**Date:** YYYY-MM-DD HH:MM UTC
**Duration:** [X hours Y minutes]
**Severity:** [CRITICAL / HIGH / MEDIUM / LOW]
**Status:** RESOLVED

## Summary
[Brief description of what happened]

## Timeline
- HH:MM - Issue first detected
- HH:MM - Application stopped
- HH:MM - Rollback initiated
- HH:MM - Rollback completed
- HH:MM - Verification completed
- HH:MM - Application restored

## Impact
- Users affected: [number]
- Transactions affected: [number]
- Financial impact: [amount]
- Data lost: [description]

## Root Cause
[What caused the issue]

## Resolution
[What was done to fix it]

## Rollback Procedure Used
[Which procedure from this document]

## Lessons Learned
[What we learned]

## Action Items
- [ ] Improve monitoring for [specific area]
- [ ] Add test coverage for [specific scenario]
- [ ] Update documentation for [specific process]
- [ ] Notify affected users (if applicable)

## Data Reconciliation
[If any data was lost, describe reconciliation plan]
```

### Communication Template

For user communication after an incident:

```
🔔 Service Update

We experienced a technical issue between [START_TIME] and [END_TIME] UTC.

Impact:
- [Description of what was affected]
- [Any data loss or transaction issues]

Resolution:
- Service has been restored
- All systems are operating normally

If you were affected:
- [Specific actions users should take]
- [How to report issues]

We apologize for any inconvenience.
```

---

## Quick Reference

### Emergency Commands

```bash
# STOP EVERYTHING
pm2 stop all && echo "JOB_BLOCKCHAIN_MONITOR_ENABLED=false" >> .env

# EMERGENCY BACKUP
./scripts/backup-production.sh

# LATEST BACKUP
ls -lht backups/daily/ | head -1

# RESTORE LATEST
LATEST=$(ls -t backups/daily/*.sql.gz | head -1) && \
  ./scripts/restore-from-backup.sh "$LATEST"

# CHECK DATABASE
psql $DATABASE_URL -c "SELECT COUNT(*) FROM users;"

# ROLLBACK GIT
git log --oneline -5 && \
  git checkout HEAD~1 && \
  npm run build && \
  pm2 restart sigmatradebot
```

### Support Contacts

**Technical Team:**
- Primary: [Contact info]
- Secondary: [Contact info]
- Emergency: [Contact info]

**Database Admin:**
- [Contact info]

**DevOps:**
- [Contact info]

---

## Testing Rollback Procedures

### Practice Rollbacks (In Test Environment)

It's critical to practice these procedures in a test environment:

```bash
# 1. Setup test environment
cp .env .env.test.backup
cp .env.test .env

# 2. Run test deployment
git checkout test-branch
npm install
npm run build

# 3. Practice rollback
./scripts/backup-production.sh
# ... make some changes ...
./scripts/restore-from-backup.sh backups/daily/sigmatrade_test.sql.gz

# 4. Verify rollback worked
npm test
```

### Rollback Drills

Schedule regular rollback drills:

- **Monthly:** Practice code rollback
- **Quarterly:** Practice database rollback
- **Annually:** Practice full emergency procedure

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-10 | Initial rollback procedures document |

---

## Related Documentation

- [REFACTORING_MASTER_PLAN.md](./REFACTORING_MASTER_PLAN.md) - Complete refactoring plan
- [AUDIT_LOGGING_GUIDE.md](./AUDIT_LOGGING_GUIDE.md) - Audit logging system
- [tests/README.md](./tests/README.md) - Testing guide
- `scripts/backup-production.sh` - Backup script
- `scripts/restore-from-backup.sh` - Restore script
