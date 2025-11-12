/**
 * Migration: Add ROI (Return on Investment) tracking to deposits
 *
 * BUSINESS LOGIC CHANGE:
 * - Level 1 deposits (10 USDT) now have 500% ROI cap
 * - User can have only ONE active Level 1 deposit at a time
 * - After reaching 500% ROI, deposit cycle is completed
 * - User must create new 10 USDT deposit to continue
 *
 * Fields:
 * - roi_cap_amount: Maximum earnings allowed (5x deposit amount for L1)
 * - roi_paid_amount: Total earnings paid out so far
 * - is_roi_completed: Flag indicating ROI cap reached
 * - roi_completed_at: Timestamp when ROI cap was reached
 *
 * Unique constraint:
 * - Only ONE active (confirmed, non-ROI-completed) Level 1 deposit per user
 * - Prevents creating second 10 USDT deposit before completing first cycle
 */

import { MigrationInterface, QueryRunner } from 'typeorm';

export class AddDepositRoiColumns1699999999011 implements MigrationInterface {
  name = 'AddDepositRoiColumns1699999999011';

  public async up(queryRunner: QueryRunner): Promise<void> {
    // Add ROI tracking columns
    await queryRunner.query(`
      ALTER TABLE deposits
      ADD COLUMN IF NOT EXISTS roi_cap_amount DECIMAL(20,8),
      ADD COLUMN IF NOT EXISTS roi_paid_amount DECIMAL(20,8) DEFAULT 0,
      ADD COLUMN IF NOT EXISTS is_roi_completed BOOLEAN DEFAULT false,
      ADD COLUMN IF NOT EXISTS roi_completed_at TIMESTAMP NULL
    `);

    // Create unique partial index: only ONE active Level 1 deposit per user
    // Active = status='confirmed' AND is_roi_completed=false
    await queryRunner.query(`
      CREATE UNIQUE INDEX uq_active_level1_deposit_per_user
      ON deposits(user_id)
      WHERE level = 1 AND status = 'confirmed' AND is_roi_completed = false
    `);

    // Create index for querying ROI-completed deposits
    await queryRunner.query(`
      CREATE INDEX idx_deposits_roi_completed
      ON deposits(is_roi_completed, roi_completed_at)
      WHERE is_roi_completed = true
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP INDEX IF EXISTS idx_deposits_roi_completed`);
    await queryRunner.query(`DROP INDEX IF EXISTS uq_active_level1_deposit_per_user`);
    await queryRunner.query(`
      ALTER TABLE deposits
      DROP COLUMN IF EXISTS roi_completed_at,
      DROP COLUMN IF EXISTS is_roi_completed,
      DROP COLUMN IF EXISTS roi_paid_amount,
      DROP COLUMN IF EXISTS roi_cap_amount
    `);
  }
}
