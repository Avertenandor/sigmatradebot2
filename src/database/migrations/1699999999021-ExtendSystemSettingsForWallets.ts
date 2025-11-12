/**
 * Migration: Extend system_settings for wallet management
 *
 * PURPOSE:
 * - Store system and payout wallet addresses in database
 * - Version tracking for wallet changes
 * - Enable runtime wallet switching without restart
 *
 * SETTINGS:
 * - SYSTEM_WALLET_ADDRESS: Address for receiving deposits (BSC/BEP-20 USDT)
 * - PAYOUT_WALLET_ADDRESS: Address for sending payments
 * - WALLETS_VERSION: Incremented on each wallet change (for cache invalidation)
 *
 * SECURITY:
 * - Addresses stored in checksum format (EIP-55)
 * - Private keys NEVER stored in database (use Secret Manager)
 * - All changes go through approval workflow
 */

import { MigrationInterface, QueryRunner } from 'typeorm';

export class ExtendSystemSettingsForWallets1699999999021
  implements MigrationInterface
{
  name = 'ExtendSystemSettingsForWallets1699999999021';

  public async up(queryRunner: QueryRunner): Promise<void> {
    // Insert default wallet addresses from ENV (will be overridden in production)
    await queryRunner.query(`
      INSERT INTO system_settings (key, value, updated_at)
      VALUES
        ('SYSTEM_WALLET_ADDRESS', '0xb64E541EEEC55406286171725fc1b86a9034e52f', NOW()),
        ('PAYOUT_WALLET_ADDRESS', '0x72d4fa818A36cf5677E2abec8f56E1d810b2Aa3e', NOW()),
        ('WALLETS_VERSION', '1', NOW())
      ON CONFLICT (key) DO NOTHING
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    // Remove wallet settings
    await queryRunner.query(`
      DELETE FROM system_settings
      WHERE key IN (
        'SYSTEM_WALLET_ADDRESS',
        'PAYOUT_WALLET_ADDRESS',
        'WALLETS_VERSION'
      )
    `);
  }
}
