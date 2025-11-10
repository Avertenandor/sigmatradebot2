  # Database Migration Guide

## Overview

This guide explains how to create, run, and manage database migrations in the SigmaTrade Bot project.

Database migrations allow us to:
- Version control database schema changes
- Apply changes incrementally and safely
- Rollback changes if needed
- Keep development, staging, and production databases in sync
- Document database changes with code

## Table of Contents

1. [Quick Start](#quick-start)
2. [Migration Commands](#migration-commands)
3. [Creating Migrations](#creating-migrations)
4. [Running Migrations](#running-migrations)
5. [Reverting Migrations](#reverting-migrations)
6. [Best Practices](#best-practices)
7. [Migration Examples](#migration-examples)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Check Migration Status

```bash
npm run migration:show
```

This shows all migrations and their status (executed/pending).

### Run Pending Migrations

```bash
npm run migration:run
```

This runs all pending migrations in order.

### Revert Last Migration

```bash
npm run migration:revert
```

This reverts the most recently executed migration.

---

## Migration Commands

### Standard Commands

```bash
# Show migration status
npm run migration:show

# Run all pending migrations
npm run migration:run

# Revert last migration
npm run migration:revert

# Generate migration from entity changes
npm run migration:generate -- MigrationName

# Create empty migration
npm run migration:create -- MigrationName
```

### Advanced Commands (Custom CLI)

```bash
# Dry-run (see what would be executed without running)
npm run migration:cli run -- --dry-run

# Fake (mark as executed without running - for manual migrations)
npm run migration:cli run -- --fake

# Control transaction behavior
npm run migration:cli run -- --transaction=all   # Wrap all in one transaction (default)
npm run migration:cli run -- --transaction=each  # Each migration in separate transaction
npm run migration:cli run -- --transaction=none  # No transaction wrapping
```

---

## Creating Migrations

### Auto-Generate from Entity Changes

When you modify TypeORM entities, generate a migration automatically:

```bash
npm run migration:generate -- AddUserEmailIndex
```

This will:
1. Compare your entities with the current database schema
2. Generate a migration file with the differences
3. Place it in `src/database/migrations/`

### Create Empty Migration

For manual migrations (data migrations, custom SQL, etc.):

```bash
npm run migration:create -- CustomDataMigration
```

This creates an empty migration template that you fill in manually.

### Migration File Structure

```typescript
import { MigrationInterface, QueryRunner } from 'typeorm';

export class MigrationName1234567890123 implements MigrationInterface {
  name = 'MigrationName1234567890123';

  public async up(queryRunner: QueryRunner): Promise<void> {
    // Forward migration code
    // This runs when migrating UP
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    // Rollback migration code
    // This runs when reverting
  }
}
```

---

## Running Migrations

### Development Environment

```bash
# Run all pending migrations
npm run migration:run
```

Migrations run automatically on app startup in production (configured in `data-source.ts`).

### Production Environment

**IMPORTANT:** Always test migrations on a copy of production data first!

```bash
# 1. Create database backup
./scripts/backup-production.sh

# 2. Test migration on backup/staging
npm run migration:run

# 3. If successful, run on production
NODE_ENV=production npm run migration:run

# 4. Verify application works
npm start

# 5. If issues occur, revert immediately
npm run migration:revert
```

### Dry-Run (Testing)

```bash
# See what would be executed without making changes
npm run migration:cli run -- --dry-run
```

---

## Reverting Migrations

### Revert Last Migration

```bash
npm run migration:revert
```

This reverts the most recently executed migration by calling its `down()` method.

### Revert Multiple Migrations

```bash
# Revert last 3 migrations
npm run migration:revert
npm run migration:revert
npm run migration:revert
```

### Emergency Rollback

If a migration fails in production:

```bash
# 1. Stop application immediately
pm2 stop sigmatradebot

# 2. Revert the failed migration
npm run migration:revert

# 3. Restore from backup if needed
./scripts/restore-from-backup.sh backups/daily/sigmatrade_YYYYMMDD_HHMMSS.sql.gz

# 4. Restart application
pm2 start sigmatradebot
```

See [ROLLBACK_PROCEDURES.md](./ROLLBACK_PROCEDURES.md) for detailed emergency procedures.

---

## Best Practices

### 1. Always Write Reversible Migrations

Every migration must have a working `down()` method for rollback.

```typescript
public async up(queryRunner: QueryRunner): Promise<void> {
  await queryRunner.createTable(/* ... */);
}

public async down(queryRunner: QueryRunner): Promise<void> {
  await queryRunner.dropTable('table_name');
}
```

### 2. Test Migrations on Copy of Production Data

Before running in production:

```bash
# 1. Restore production backup to test database
./scripts/restore-from-backup.sh backups/latest.sql.gz --target-db test_db

# 2. Run migration on test database
DATABASE_NAME=test_db npm run migration:run

# 3. Verify data integrity
psql test_db -c "SELECT COUNT(*) FROM users;"
```

### 3. One Change Per Migration

Keep migrations focused on a single change:

- ✅ Good: `AddUserEmailIndex`
- ✅ Good: `AddDepositConstraints`
- ❌ Bad: `UpdateSchemaAndMigrateDataAndAddIndexes`

### 4. Use Transactions

Migrations run in transactions by default. If a migration fails, all changes are rolled back.

For data migrations that might fail partially, consider using `--transaction=none`:

```bash
npm run migration:cli run -- --transaction=none
```

### 5. Document Complex Migrations

Add comments explaining complex logic:

```typescript
public async up(queryRunner: QueryRunner): Promise<void> {
  // IMPORTANT: This migration adds a UNIQUE constraint on (tx_hash, user_id)
  // It will fail if duplicate transactions exist in the database.
  // Clean up duplicates first:

  await queryRunner.query(`
    DELETE FROM deposits
    WHERE id NOT IN (
      SELECT MIN(id) FROM deposits GROUP BY tx_hash, user_id
    );
  `);

  await queryRunner.query(`
    CREATE UNIQUE INDEX IDX_deposits_tx_hash_user_id
    ON deposits (tx_hash, user_id);
  `);
}
```

### 6. Backup Before Production Migrations

Always create a backup before running migrations in production:

```bash
./scripts/backup-production.sh
npm run migration:run
```

### 7. Monitor Migration Performance

Long-running migrations can block database operations:

```bash
# Check migration duration
\timing on
npm run migration:run
```

For large tables, consider:
- Running during low-traffic periods
- Creating indexes `CONCURRENTLY` (doesn't block writes)
- Batching data migrations

### 8. Never Modify Executed Migrations

Once a migration is executed in any environment (dev/staging/prod), **never modify it**.

Instead, create a new migration to fix issues:

```bash
# ❌ DON'T: Modify existing migration
# ✅ DO: Create new migration
npm run migration:create -- FixPreviousMigrationIssue
```

---

## Migration Examples

### Example 1: Add Column

```typescript
import { MigrationInterface, QueryRunner, TableColumn } from 'typeorm';

export class AddUserEmailColumn1234567890 implements MigrationInterface {
  public async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.addColumn('users', new TableColumn({
      name: 'email',
      type: 'varchar',
      length: '255',
      isNullable: true,
    }));
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.dropColumn('users', 'email');
  }
}
```

### Example 2: Add Index

```typescript
import { MigrationInterface, QueryRunner, TableIndex } from 'typeorm';

export class AddUserEmailIndex1234567891 implements MigrationInterface {
  public async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.createIndex('users', new TableIndex({
      name: 'IDX_users_email',
      columnNames: ['email'],
    }));
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.dropIndex('users', 'IDX_users_email');
  }
}
```

### Example 3: Add Constraint

```typescript
import { MigrationInterface, QueryRunner, TableCheck } from 'typeorm';

export class AddBalanceConstraint1234567892 implements MigrationInterface {
  public async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.createCheckConstraint('users', new TableCheck({
      name: 'CHK_users_balance_positive',
      expression: 'balance >= 0',
    }));
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.dropCheckConstraint('users', 'CHK_users_balance_positive');
  }
}
```

### Example 4: Data Migration

```typescript
import { MigrationInterface, QueryRunner } from 'typeorm';

export class MigrateOldDataFormat1234567893 implements MigrationInterface {
  public async up(queryRunner: QueryRunner): Promise<void> {
    // Migrate old data format to new format
    await queryRunner.query(`
      UPDATE deposits
      SET status = 'COMPLETED'
      WHERE status = 'SUCCESS' AND status_updated_at < NOW() - INTERVAL '7 days';
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    // Revert data migration
    await queryRunner.query(`
      UPDATE deposits
      SET status = 'SUCCESS'
      WHERE status = 'COMPLETED' AND status_updated_at < NOW() - INTERVAL '7 days';
    `);
  }
}
```

### Example 5: Complex Migration with Multiple Changes

```typescript
import { MigrationInterface, QueryRunner } from 'typeorm';

export class RefactorDepositTable1234567894 implements MigrationInterface {
  public async up(queryRunner: QueryRunner): Promise<void> {
    // 1. Add new columns
    await queryRunner.query(`
      ALTER TABLE deposits
      ADD COLUMN tx_hash_normalized VARCHAR(66),
      ADD COLUMN blockchain_network VARCHAR(20) DEFAULT 'BSC';
    `);

    // 2. Migrate data
    await queryRunner.query(`
      UPDATE deposits
      SET tx_hash_normalized = LOWER(tx_hash);
    `);

    // 3. Add constraints
    await queryRunner.query(`
      ALTER TABLE deposits
      ALTER COLUMN tx_hash_normalized SET NOT NULL;
    `);

    // 4. Create indexes
    await queryRunner.query(`
      CREATE INDEX IDX_deposits_tx_hash_normalized
      ON deposits (tx_hash_normalized);
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP INDEX IF EXISTS IDX_deposits_tx_hash_normalized;`);
    await queryRunner.query(`ALTER TABLE deposits DROP COLUMN blockchain_network;`);
    await queryRunner.query(`ALTER TABLE deposits DROP COLUMN tx_hash_normalized;`);
  }
}
```

---

## Troubleshooting

### Migration Fails with "relation does not exist"

**Problem:** Migration references a table that doesn't exist yet.

**Solution:** Check migration order. Migrations run in timestamp order, so ensure dependencies are in earlier migrations.

### Migration Fails with "duplicate key violation"

**Problem:** Adding a UNIQUE constraint when duplicates exist.

**Solution:** Clean up duplicates first:

```typescript
public async up(queryRunner: QueryRunner): Promise<void> {
  // Remove duplicates
  await queryRunner.query(`
    DELETE FROM table_name
    WHERE id NOT IN (
      SELECT MIN(id) FROM table_name GROUP BY unique_column
    );
  `);

  // Now add constraint
  await queryRunner.createUniqueConstraint(/* ... */);
}
```

### Migration Takes Too Long

**Problem:** Migration blocks database for extended period.

**Solutions:**

1. **Create indexes concurrently** (doesn't block writes):

```typescript
await queryRunner.query(`
  CREATE INDEX CONCURRENTLY IDX_users_email ON users (email);
`);
```

2. **Batch large data migrations**:

```typescript
public async up(queryRunner: QueryRunner): Promise<void> {
  let offset = 0;
  const batchSize = 1000;

  while (true) {
    const result = await queryRunner.query(`
      UPDATE users
      SET migrated = true
      WHERE id IN (
        SELECT id FROM users WHERE migrated = false LIMIT ${batchSize}
      );
    `);

    if (result.affectedRows === 0) break;
    offset += batchSize;

    // Optional: Add delay to reduce load
    await new Promise(resolve => setTimeout(resolve, 100));
  }
}
```

### Can't Revert Migration

**Problem:** `down()` method fails.

**Solution:** Manual rollback:

```bash
# 1. Connect to database
psql $DATABASE_URL

# 2. Manually revert changes
ALTER TABLE users DROP COLUMN email;

# 3. Remove migration record
DELETE FROM migrations WHERE name = 'MigrationName1234567890';
```

### TypeORM CLI Not Found

**Problem:** `typeorm` command not available.

**Solution:** Use npm scripts instead of direct CLI:

```bash
# Instead of: typeorm migration:run
npm run migration:run
```

---

## Migration Checklist

Before deploying a migration to production:

- [ ] Migration has been tested on copy of production data
- [ ] Migration has working `up()` and `down()` methods
- [ ] Backup has been created
- [ ] Migration runs in reasonable time (< 5 minutes)
- [ ] Migration doesn't block critical operations
- [ ] Team has been notified of planned migration
- [ ] Rollback procedure has been documented
- [ ] Monitoring is in place to detect issues

---

## Related Documentation

- [ROLLBACK_PROCEDURES.md](./ROLLBACK_PROCEDURES.md) - Emergency rollback procedures
- [REFACTORING_MASTER_PLAN.md](./REFACTORING_MASTER_PLAN.md) - Overall refactoring plan
- [scripts/backup-production.sh](./scripts/backup-production.sh) - Backup script
- [scripts/restore-from-backup.sh](./scripts/restore-from-backup.sh) - Restore script

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-10 | Initial migration guide |

---

## Support

If you encounter issues with migrations:

1. Check this guide for solutions
2. Review [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
3. Check migration logs in `logs/`
4. Contact the development team
