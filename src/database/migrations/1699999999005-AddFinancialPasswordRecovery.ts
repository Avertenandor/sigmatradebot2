/**
 * Migration: Add Financial Password Recovery System
 *
 * Creates table for manual financial password reset requests
 * - Users create requests (3-5 business days SLA)
 * - All admins notified
 * - Admin manually resets password
 * - New password sent to user via bot
 *
 * Anti-abuse: Unique constraint on open requests per user
 */

import { MigrationInterface, QueryRunner } from 'typeorm';

export class AddFinancialPasswordRecovery1699999999005 implements MigrationInterface {
  name = 'AddFinancialPasswordRecovery1699999999005';

  public async up(queryRunner: QueryRunner): Promise<void> {
    // Create table
    await queryRunner.query(`
      CREATE TABLE IF NOT EXISTS financial_password_recovery (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        video_required BOOLEAN NOT NULL DEFAULT TRUE,
        video_verified BOOLEAN NOT NULL DEFAULT FALSE,
        processed_by_admin_id INTEGER NULL,
        processed_at TIMESTAMP NULL,
        admin_comment TEXT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

        -- Status constraint
        CONSTRAINT chk_fpr_status CHECK (status IN ('pending','in_review','approved','rejected','sent')),

        -- Foreign keys
        CONSTRAINT fk_fpr_user FOREIGN KEY (user_id)
          REFERENCES users (id) ON DELETE CASCADE,
        CONSTRAINT fk_fpr_admin FOREIGN KEY (processed_by_admin_id)
          REFERENCES admins (id) ON DELETE SET NULL
      );
    `);

    // Unique constraint: only one open request per user
    // (prevents abuse - user can't spam multiple requests)
    await queryRunner.query(`
      CREATE UNIQUE INDEX IF NOT EXISTS uq_fpr_user_open
      ON financial_password_recovery (user_id)
      WHERE status IN ('pending','in_review','approved');
    `);

    // Regular indexes for queries
    await queryRunner.query(`
      CREATE INDEX IF NOT EXISTS idx_fpr_status
      ON financial_password_recovery (status);
    `);

    await queryRunner.query(`
      CREATE INDEX IF NOT EXISTS idx_fpr_user
      ON financial_password_recovery (user_id);
    `);

    await queryRunner.query(`
      CREATE INDEX IF NOT EXISTS idx_fpr_created
      ON financial_password_recovery (created_at);
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP INDEX IF EXISTS idx_fpr_created;`);
    await queryRunner.query(`DROP INDEX IF EXISTS idx_fpr_user;`);
    await queryRunner.query(`DROP INDEX IF EXISTS idx_fpr_status;`);
    await queryRunner.query(`DROP INDEX IF EXISTS uq_fpr_user_open;`);
    await queryRunner.query(`DROP TABLE IF EXISTS financial_password_recovery;`);
  }
}
