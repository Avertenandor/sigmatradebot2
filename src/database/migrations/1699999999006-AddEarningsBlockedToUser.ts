/**
 * Migration: Add earnings_blocked field to users table
 *
 * CRITICAL SECURITY: Block all earnings during finpass recovery period
 *
 * Purpose:
 * - Prevents financial operations while user's finpass is being recovered
 * - Protects against unauthorized earnings during password reset
 * - Blocks referral earnings, deposit rewards, and all other payouts
 *
 * Lifecycle:
 * 1. User requests finpass recovery → earnings_blocked = true
 * 2. Admin approves and sends new password → earnings_blocked REMAINS true
 * 3. User successfully uses new password → earnings_blocked = false
 *
 * This ensures no funds can be withdrawn until user proves possession
 * of the new password by successfully using it.
 */

import { MigrationInterface, QueryRunner, TableColumn } from 'typeorm';

export class AddEarningsBlockedToUser1699999999006 implements MigrationInterface {
  public async up(queryRunner: QueryRunner): Promise<void> {
    // Add earnings_blocked column
    await queryRunner.addColumn(
      'users',
      new TableColumn({
        name: 'earnings_blocked',
        type: 'boolean',
        default: false,
        isNullable: false,
      })
    );

    // Add index for fast filtering during earnings processing
    await queryRunner.query(`
      CREATE INDEX idx_users_earnings_blocked
      ON users(earnings_blocked)
      WHERE earnings_blocked = true
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    // Drop index
    await queryRunner.query(`DROP INDEX IF EXISTS idx_users_earnings_blocked`);

    // Drop column
    await queryRunner.dropColumn('users', 'earnings_blocked');
  }
}
