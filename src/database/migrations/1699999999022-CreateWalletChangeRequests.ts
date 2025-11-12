/**
 * Migration: Create wallet_change_requests table
 *
 * PURPOSE:
 * - Implement approval workflow for wallet changes
 * - Track who initiated, approved, and applied wallet changes
 * - Audit trail for security compliance
 *
 * WORKFLOW:
 * 1. Extended/Super admin creates request (status: pending)
 * 2. Super admin approves request (status: approved)
 * 3. Super admin applies request (status: applied)
 * 4. Alternatively, Super admin can reject (status: rejected)
 *
 * SECURITY:
 * - Only one active (pending/approved) request per wallet type
 * - Private keys stored in Secret Manager, only reference ID in DB
 * - All actions logged in audit trail
 * - Requests cannot be modified after approval
 */

import { MigrationInterface, QueryRunner } from 'typeorm';

export class CreateWalletChangeRequests1699999999022
  implements MigrationInterface
{
  name = 'CreateWalletChangeRequests1699999999022';

  public async up(queryRunner: QueryRunner): Promise<void> {
    // Create wallet_change_requests table
    await queryRunner.query(`
      CREATE TABLE wallet_change_requests (
        id SERIAL PRIMARY KEY,
        type VARCHAR(50) NOT NULL CHECK (type IN ('system_deposit', 'payout_withdrawal')),
        new_address VARCHAR(42) NOT NULL,
        secret_ref VARCHAR(255),
        initiated_by_admin_id INTEGER NOT NULL REFERENCES admins(id),
        approved_by_admin_id INTEGER REFERENCES admins(id),
        status VARCHAR(20) NOT NULL DEFAULT 'pending'
          CHECK (status IN ('pending', 'approved', 'applied', 'rejected')),
        reason TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        approved_at TIMESTAMP,
        applied_at TIMESTAMP,
        CONSTRAINT check_secret_ref_for_payout
          CHECK (
            (type = 'system_deposit' AND secret_ref IS NULL) OR
            (type = 'payout_withdrawal' AND secret_ref IS NOT NULL)
          )
      )
    `);

    // Create partial unique index: only one active request per type
    await queryRunner.query(`
      CREATE UNIQUE INDEX idx_wallet_change_requests_active_unique
      ON wallet_change_requests(type)
      WHERE status IN ('pending', 'approved')
    `);

    // Create indexes for efficient querying
    await queryRunner.query(`
      CREATE INDEX idx_wallet_change_requests_status ON wallet_change_requests(status)
    `);

    await queryRunner.query(`
      CREATE INDEX idx_wallet_change_requests_initiated_by
      ON wallet_change_requests(initiated_by_admin_id)
    `);

    await queryRunner.query(`
      CREATE INDEX idx_wallet_change_requests_type ON wallet_change_requests(type)
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP TABLE IF EXISTS wallet_change_requests`);
  }
}
