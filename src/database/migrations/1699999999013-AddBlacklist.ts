/**
 * Migration: Add blacklist table for pre-registration ban
 *
 * PURPOSE:
 * - Store users banned BEFORE registration (pre-registration ban)
 * - Prevent unwanted users from joining the platform
 * - Admins can add telegram IDs to blacklist
 *
 * BUSINESS LOGIC:
 * - Users in blacklist cannot start registration
 * - They receive rejection message immediately
 * - Separate from regular user bans (is_banned flag on users table)
 */

import { MigrationInterface, QueryRunner } from 'typeorm';

export class AddBlacklist1699999999013 implements MigrationInterface {
  name = 'AddBlacklist1699999999013';

  public async up(queryRunner: QueryRunner): Promise<void> {
    // Create blacklist table
    await queryRunner.query(`
      CREATE TABLE IF NOT EXISTS blacklist (
        id SERIAL PRIMARY KEY,
        telegram_id BIGINT UNIQUE NOT NULL,
        reason TEXT,
        created_by_admin_id INTEGER,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
      )
    `);

    // Create index on telegram_id for fast lookups
    await queryRunner.query(`
      CREATE INDEX IF NOT EXISTS idx_blacklist_telegram_id
      ON blacklist(telegram_id)
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP INDEX IF EXISTS idx_blacklist_telegram_id`);
    await queryRunner.query(`DROP TABLE IF EXISTS blacklist`);
  }
}
