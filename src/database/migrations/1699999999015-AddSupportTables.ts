/**
 * Migration: Add Support Ticket Tables
 * Creates support_tickets and support_messages tables for the help desk system
 */

import { MigrationInterface, QueryRunner } from 'typeorm';

export class AddSupportTables1699999999015 implements MigrationInterface {
  public async up(queryRunner: QueryRunner): Promise<void> {
    // Create support_tickets table
    await queryRunner.query(`
      CREATE TABLE IF NOT EXISTS support_tickets (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        category VARCHAR(20) NOT NULL CHECK (category IN ('payments', 'withdrawals', 'finpass', 'referrals', 'tech', 'other')),
        status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'answered', 'closed')),
        assigned_admin_id INTEGER REFERENCES admins(id) ON DELETE SET NULL,
        last_user_message_at TIMESTAMP,
        last_admin_message_at TIMESTAMP,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
      )
    `);

    // Create indexes on support_tickets
    await queryRunner.query(`
      CREATE INDEX IF NOT EXISTS idx_support_tickets_user_id ON support_tickets(user_id)
    `);
    await queryRunner.query(`
      CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status)
    `);
    await queryRunner.query(`
      CREATE INDEX IF NOT EXISTS idx_support_tickets_assigned_admin_id ON support_tickets(assigned_admin_id)
    `);

    // Create partial UNIQUE index: one open ticket per user
    await queryRunner.query(`
      CREATE UNIQUE INDEX IF NOT EXISTS idx_support_tickets_user_one_open
      ON support_tickets(user_id)
      WHERE status IN ('open', 'in_progress', 'answered')
    `);

    // Create support_messages table
    await queryRunner.query(`
      CREATE TABLE IF NOT EXISTS support_messages (
        id SERIAL PRIMARY KEY,
        ticket_id INTEGER NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
        sender VARCHAR(10) NOT NULL CHECK (sender IN ('user', 'admin', 'system')),
        admin_id INTEGER,
        text TEXT,
        attachments JSONB,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
      )
    `);

    // Create index on support_messages
    await queryRunner.query(`
      CREATE INDEX IF NOT EXISTS idx_support_messages_ticket_id ON support_messages(ticket_id)
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    // Drop tables in reverse order
    await queryRunner.query(`DROP TABLE IF EXISTS support_messages CASCADE`);
    await queryRunner.query(`DROP TABLE IF EXISTS support_tickets CASCADE`);
  }
}
