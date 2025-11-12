/**
 * Migration: Add system_settings table for runtime configuration
 *
 * PURPOSE:
 * - Store system-wide settings that can be changed by admins
 * - No need to restart application when settings change
 * - Settings cached in memory with TTL for performance
 *
 * Initial settings:
 * - DEPOSITS_MAX_OPEN_LEVEL: Maximum deposit level available to users (default: 1)
 *   Admin can open levels 2-5 through admin panel when ready
 *
 * BUSINESS LOGIC:
 * - By default, only Level 1 (10 USDT) is open
 * - Admin can open higher levels (2-5) via admin panel
 * - Users can only activate deposits up to max open level
 */

import { MigrationInterface, QueryRunner } from 'typeorm';

export class AddSystemSettings1699999999012 implements MigrationInterface {
  name = 'AddSystemSettings1699999999012';

  public async up(queryRunner: QueryRunner): Promise<void> {
    // Create system_settings table
    await queryRunner.query(`
      CREATE TABLE IF NOT EXISTS system_settings (
        key VARCHAR(100) PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
      )
    `);

    // Set default: only Level 1 is open
    await queryRunner.query(`
      INSERT INTO system_settings (key, value, updated_at)
      VALUES ('DEPOSITS_MAX_OPEN_LEVEL', '1', NOW())
      ON CONFLICT (key) DO NOTHING
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP TABLE IF EXISTS system_settings`);
  }
}
