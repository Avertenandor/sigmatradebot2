import { MigrationInterface, QueryRunner, TableCheck, TableIndex } from 'typeorm';

/**
 * Migration: Add Deposit Constraints
 *
 * This migration adds critical constraints and indexes to the deposits table
 * to prevent race conditions, data corruption, and performance issues.
 *
 * Changes:
 * 1. Add CHECK constraint: amount must be positive
 * 2. Add CHECK constraint: level must be valid (1-7)
 * 3. Add CHECK constraint: status must be valid enum value
 * 4. Add CHECK constraint: confirmations must be non-negative
 * 5. Add UNIQUE constraint on (tx_hash, user_id) to prevent duplicate processing
 * 6. Add index on (status, created_at) for efficient querying
 * 7. Add index on (user_id, status) for user deposit lookups
 * 8. Add index on tx_hash for blockchain confirmations
 *
 * Rollback: All constraints and indexes can be safely dropped
 *
 * Risk: LOW - Only adds constraints, doesn't modify existing data
 * Time: ~1-2 seconds on tables with < 100k rows
 */
export class AddDepositConstraints1699999999001 implements MigrationInterface {
  name = 'AddDepositConstraints1699999999001';

  public async up(queryRunner: QueryRunner): Promise<void> {
    // 1. Add CHECK constraint: amount must be positive
    await queryRunner.createCheckConstraint('deposits', new TableCheck({
      name: 'CHK_deposits_amount_positive',
      expression: 'amount > 0',
    }));

    // 2. Add CHECK constraint: level must be valid (1-7)
    await queryRunner.createCheckConstraint('deposits', new TableCheck({
      name: 'CHK_deposits_level_valid',
      expression: 'level >= 1 AND level <= 7',
    }));

    // 3. Add CHECK constraint: status must be valid enum value
    await queryRunner.createCheckConstraint('deposits', new TableCheck({
      name: 'CHK_deposits_status_valid',
      expression: "status IN ('PENDING', 'CONFIRMING', 'COMPLETED', 'FAILED', 'EXPIRED')",
    }));

    // 4. Add CHECK constraint: confirmations must be non-negative
    await queryRunner.createCheckConstraint('deposits', new TableCheck({
      name: 'CHK_deposits_confirmations_nonnegative',
      expression: 'confirmations >= 0',
    }));

    // 5. Add UNIQUE constraint on (tx_hash, user_id) to prevent duplicate processing
    // This prevents the same transaction from being processed multiple times
    await queryRunner.query(`
      CREATE UNIQUE INDEX IF NOT EXISTS "IDX_deposits_tx_hash_user_id_unique"
      ON "deposits" ("tx_hash", "user_id")
      WHERE "tx_hash" IS NOT NULL;
    `);

    // 6. Add index on (status, created_at) for efficient status-based queries
    // Used by: deposit cleanup jobs, pending deposit queries
    await queryRunner.createIndex('deposits', new TableIndex({
      name: 'IDX_deposits_status_created_at',
      columnNames: ['status', 'created_at'],
    }));

    // 7. Add index on (user_id, status) for user deposit lookups
    // Used by: user deposit history, pending deposit checks
    await queryRunner.createIndex('deposits', new TableIndex({
      name: 'IDX_deposits_user_id_status',
      columnNames: ['user_id', 'status'],
    }));

    // 8. Add index on tx_hash for blockchain confirmation lookups
    // Used by: blockchain monitor, transaction verification
    await queryRunner.createIndex('deposits', new TableIndex({
      name: 'IDX_deposits_tx_hash',
      columnNames: ['tx_hash'],
    }));

    // 9. Add partial index on expired deposits for cleanup job
    // Only indexes EXPIRED deposits to keep index small
    await queryRunner.query(`
      CREATE INDEX IF NOT EXISTS "IDX_deposits_expired_cleanup"
      ON "deposits" ("created_at")
      WHERE "status" = 'EXPIRED';
    `);

    // 10. Add index on wallet_address for address validation
    // Used by: deposit address verification
    await queryRunner.createIndex('deposits', new TableIndex({
      name: 'IDX_deposits_wallet_address',
      columnNames: ['wallet_address'],
    }));
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    // Drop indexes first (foreign key dependencies)
    await queryRunner.dropIndex('deposits', 'IDX_deposits_wallet_address');
    await queryRunner.query(`DROP INDEX IF EXISTS "IDX_deposits_expired_cleanup";`);
    await queryRunner.dropIndex('deposits', 'IDX_deposits_tx_hash');
    await queryRunner.dropIndex('deposits', 'IDX_deposits_user_id_status');
    await queryRunner.dropIndex('deposits', 'IDX_deposits_status_created_at');
    await queryRunner.query(`DROP INDEX IF EXISTS "IDX_deposits_tx_hash_user_id_unique";`);

    // Drop CHECK constraints
    await queryRunner.dropCheckConstraint('deposits', 'CHK_deposits_confirmations_nonnegative');
    await queryRunner.dropCheckConstraint('deposits', 'CHK_deposits_status_valid');
    await queryRunner.dropCheckConstraint('deposits', 'CHK_deposits_level_valid');
    await queryRunner.dropCheckConstraint('deposits', 'CHK_deposits_amount_positive');
  }
}
