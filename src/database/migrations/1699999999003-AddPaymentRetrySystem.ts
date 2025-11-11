import { MigrationInterface, QueryRunner, Table, TableForeignKey, TableIndex } from 'typeorm';

/**
 * Migration: Add Payment Retry System
 *
 * Creates payment_retries table for tracking failed payment attempts
 * Implements exponential backoff retry mechanism and Dead Letter Queue
 *
 * Related Bug: FIX #4 - Payment Retry with Exponential Backoff
 *
 * Problem:
 * - Failed payments stay unpaid forever
 * - No retry mechanism for transient failures (network errors, low gas, etc.)
 * - Users don't receive their earnings
 *
 * Solution:
 * - Track failed payments in payment_retries table
 * - Retry with exponential backoff (1min, 2min, 4min, 8min, 16min)
 * - Move to DLQ after max retries (default: 5)
 * - Admin interface to manually retry DLQ items
 *
 * Risk: LOW - Only adds new table, doesn't modify existing data
 * Time: ~1 second
 */
export class AddPaymentRetrySystem1699999999003 implements MigrationInterface {
  name = 'AddPaymentRetrySystem1699999999003';

  public async up(queryRunner: QueryRunner): Promise<void> {
    // Create payment_retries table
    await queryRunner.createTable(
      new Table({
        name: 'payment_retries',
        columns: [
          {
            name: 'id',
            type: 'int',
            isPrimary: true,
            isGenerated: true,
            generationStrategy: 'increment',
          },
          {
            name: 'user_id',
            type: 'int',
            isNullable: false,
          },
          {
            name: 'amount',
            type: 'decimal',
            precision: 18,
            scale: 8,
            isNullable: false,
          },
          {
            name: 'payment_type',
            type: 'enum',
            enum: ['REFERRAL_EARNING', 'DEPOSIT_REWARD'],
            isNullable: false,
          },
          {
            name: 'earning_ids',
            type: 'text',
            isNullable: false,
            comment: 'JSON array of earning IDs',
          },
          {
            name: 'attempt_count',
            type: 'int',
            default: 0,
          },
          {
            name: 'max_retries',
            type: 'int',
            default: 5,
          },
          {
            name: 'last_attempt_at',
            type: 'timestamp',
            isNullable: true,
          },
          {
            name: 'next_retry_at',
            type: 'timestamp',
            isNullable: true,
          },
          {
            name: 'last_error',
            type: 'text',
            isNullable: true,
          },
          {
            name: 'error_stack',
            type: 'text',
            isNullable: true,
          },
          {
            name: 'in_dlq',
            type: 'boolean',
            default: false,
            comment: 'Dead Letter Queue - max retries exceeded',
          },
          {
            name: 'resolved',
            type: 'boolean',
            default: false,
            comment: 'Successfully paid',
          },
          {
            name: 'tx_hash',
            type: 'varchar',
            length: '100',
            isNullable: true,
          },
          {
            name: 'created_at',
            type: 'timestamp',
            default: 'CURRENT_TIMESTAMP',
          },
          {
            name: 'updated_at',
            type: 'timestamp',
            default: 'CURRENT_TIMESTAMP',
          },
        ],
      }),
      true
    );

    // Add foreign key to users table
    await queryRunner.createForeignKey(
      'payment_retries',
      new TableForeignKey({
        columnNames: ['user_id'],
        referencedColumnNames: ['id'],
        referencedTableName: 'users',
        onDelete: 'CASCADE',
      })
    );

    // Add index on user_id for user payment retry lookups
    await queryRunner.createIndex(
      'payment_retries',
      new TableIndex({
        name: 'IDX_payment_retries_user_id',
        columnNames: ['user_id'],
      })
    );

    // Add partial index on pending retries (not resolved, not in DLQ, next_retry_at <= now)
    // This is the main query for payment retry processor
    await queryRunner.query(`
      CREATE INDEX "IDX_payment_retries_pending"
      ON "payment_retries" ("next_retry_at")
      WHERE "resolved" = false AND "in_dlq" = false AND "next_retry_at" IS NOT NULL;
    `);

    // Add partial index on DLQ items for admin review
    await queryRunner.query(`
      CREATE INDEX "IDX_payment_retries_dlq"
      ON "payment_retries" ("created_at")
      WHERE "in_dlq" = true AND "resolved" = false;
    `);

    // Add index on resolved status for cleanup jobs
    await queryRunner.createIndex(
      'payment_retries',
      new TableIndex({
        name: 'IDX_payment_retries_resolved',
        columnNames: ['resolved', 'created_at'],
      })
    );
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    // Drop indexes
    await queryRunner.dropIndex('payment_retries', 'IDX_payment_retries_resolved');
    await queryRunner.query(`DROP INDEX IF EXISTS "IDX_payment_retries_dlq";`);
    await queryRunner.query(`DROP INDEX IF EXISTS "IDX_payment_retries_pending";`);
    await queryRunner.dropIndex('payment_retries', 'IDX_payment_retries_user_id');

    // Drop foreign key
    const table = await queryRunner.getTable('payment_retries');
    const foreignKey = table?.foreignKeys.find(fk => fk.columnNames.indexOf('user_id') !== -1);
    if (foreignKey) {
      await queryRunner.dropForeignKey('payment_retries', foreignKey);
    }

    // Drop table
    await queryRunner.dropTable('payment_retries');
  }
}
