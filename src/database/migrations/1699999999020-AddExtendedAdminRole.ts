/**
 * Migration: Add Extended Admin role
 *
 * PURPOSE:
 * - Add new 'extended_admin' role for wallet management delegation
 * - Extended admins can create (stage) wallet change requests
 * - Only super_admin can approve and apply wallet changes
 *
 * ROLES:
 * - super_admin: Full permissions, can approve/apply wallet changes
 * - extended_admin: Can stage wallet changes, cannot apply
 * - admin: Regular admin, no wallet management permissions
 *
 * SECURITY:
 * - No automatic role upgrades - must be assigned by super_admin
 * - All role changes are audited
 */

import { MigrationInterface, QueryRunner } from 'typeorm';

export class AddExtendedAdminRole1699999999020 implements MigrationInterface {
  name = 'AddExtendedAdminRole1699999999020';

  public async up(queryRunner: QueryRunner): Promise<void> {
    // Extend role column to support extended_admin
    // Using CHECK constraint for enum-like behavior
    await queryRunner.query(`
      ALTER TABLE admins
      DROP CONSTRAINT IF EXISTS admins_role_check
    `);

    await queryRunner.query(`
      ALTER TABLE admins
      ADD CONSTRAINT admins_role_check
      CHECK (role IN ('super_admin', 'extended_admin', 'admin'))
    `);

    // Create index on role for efficient filtering
    await queryRunner.query(`
      CREATE INDEX IF NOT EXISTS idx_admins_role ON admins(role)
    `);

    // Add system setting for "two eyes" policy (optional second approver)
    await queryRunner.query(`
      INSERT INTO system_settings (key, value, updated_at)
      VALUES ('WALLET_CHANGE_REQUIRE_SECOND_APPROVER', 'false', NOW())
      ON CONFLICT (key) DO NOTHING
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    // Remove extended_admin from check constraint
    await queryRunner.query(`
      ALTER TABLE admins
      DROP CONSTRAINT IF EXISTS admins_role_check
    `);

    await queryRunner.query(`
      ALTER TABLE admins
      ADD CONSTRAINT admins_role_check
      CHECK (role IN ('super_admin', 'admin'))
    `);

    // Remove index
    await queryRunner.query(`
      DROP INDEX IF EXISTS idx_admins_role
    `);

    // Remove system setting
    await queryRunner.query(`
      DELETE FROM system_settings
      WHERE key = 'WALLET_CHANGE_REQUIRE_SECOND_APPROVER'
    `);

    // Downgrade any extended_admin to regular admin
    await queryRunner.query(`
      UPDATE admins
      SET role = 'admin'
      WHERE role = 'extended_admin'
    `);
  }
}
