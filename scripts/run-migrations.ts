#!/usr/bin/env ts-node

/**
 * Migration Runner Script
 *
 * This script provides a CLI interface for managing database migrations.
 *
 * Commands:
 *   run      - Run all pending migrations
 *   revert   - Revert the last executed migration
 *   show     - Show all migrations and their status
 *   generate - Generate a new migration file
 *   create   - Create an empty migration file
 *
 * Usage:
 *   npm run migration:run
 *   npm run migration:revert
 *   npm run migration:show
 *   npm run migration:generate -- MyMigrationName
 *   npm run migration:create -- MyMigrationName
 *
 * Options:
 *   --dry-run    Show what would be executed without running
 *   --fake       Mark migration as executed without running
 *   --transaction=all|each|none  Control transaction wrapping
 *
 * Examples:
 *   # Run all pending migrations
 *   npm run migration:run
 *
 *   # Dry-run to see what would be executed
 *   npm run migration:run -- --dry-run
 *
 *   # Revert last migration
 *   npm run migration:revert
 *
 *   # Show migration status
 *   npm run migration:show
 *
 *   # Generate migration from entity changes
 *   npm run migration:generate -- AddUserEmailIndex
 *
 *   # Create empty migration
 *   npm run migration:create -- CustomMigration
 */

import 'reflect-metadata';
import { AppDataSource } from '../src/database/data-source';
import { DataSource } from 'typeorm';
import * as dotenv from 'dotenv';

// Load environment variables
dotenv.config();

// Parse command line arguments
const args = process.argv.slice(2);
const command = args[0];
const options = {
  dryRun: args.includes('--dry-run'),
  fake: args.includes('--fake'),
  transaction: getOptionValue(args, '--transaction', 'all'),
  migrationName: args.find(arg => !arg.startsWith('--')),
};

function getOptionValue(args: string[], option: string, defaultValue: string): string {
  const arg = args.find(a => a.startsWith(`${option}=`));
  if (!arg) return defaultValue;
  return arg.split('=')[1];
}

/**
 * Print colored output
 */
function log(message: string, type: 'info' | 'success' | 'error' | 'warn' = 'info'): void {
  const colors = {
    info: '\x1b[36m',    // Cyan
    success: '\x1b[32m', // Green
    error: '\x1b[31m',   // Red
    warn: '\x1b[33m',    // Yellow
  };
  const reset = '\x1b[0m';
  console.log(`${colors[type]}${message}${reset}`);
}

/**
 * Run all pending migrations
 */
async function runMigrations(dataSource: DataSource): Promise<void> {
  log('📋 Checking for pending migrations...', 'info');

  const pendingMigrations = await dataSource.showMigrations();

  if (!pendingMigrations) {
    log('✅ No pending migrations', 'success');
    return;
  }

  if (options.dryRun) {
    log('\n🔍 DRY RUN MODE - No changes will be made\n', 'warn');
    const migrations = await dataSource.migrations;
    const executed = await dataSource.query(
      `SELECT * FROM migrations ORDER BY timestamp ASC`
    ).catch(() => []);
    const executedIds = new Set(executed.map((m: any) => m.name));

    log('Pending migrations:');
    migrations.forEach(migration => {
      if (!executedIds.has(migration.name)) {
        log(`  - ${migration.name}`, 'info');
      }
    });
    return;
  }

  if (options.fake) {
    log('\n⚠️  FAKE MODE - Migrations will be marked as executed without running\n', 'warn');
    // TypeORM doesn't have built-in fake mode, we need to implement it
    const migrations = await dataSource.migrations;
    const executed = await dataSource.query(
      `SELECT * FROM migrations ORDER BY timestamp ASC`
    ).catch(() => []);
    const executedIds = new Set(executed.map((m: any) => m.name));

    for (const migration of migrations) {
      if (!executedIds.has(migration.name)) {
        await dataSource.query(
          `INSERT INTO migrations (timestamp, name) VALUES ($1, $2)`,
          [migration.name.match(/\d+/)?.[0] || Date.now(), migration.name]
        );
        log(`  ✓ Marked as executed: ${migration.name}`, 'success');
      }
    }
    return;
  }

  log('\n🚀 Running migrations...\n', 'info');

  try {
    const executedMigrations = await dataSource.runMigrations({
      transaction: options.transaction as 'all' | 'each' | 'none',
    });

    if (executedMigrations.length === 0) {
      log('✅ All migrations are already executed', 'success');
    } else {
      log(`\n✅ Successfully executed ${executedMigrations.length} migration(s):\n`, 'success');
      executedMigrations.forEach(migration => {
        log(`  ✓ ${migration.name}`, 'success');
      });
    }
  } catch (error) {
    log(`\n❌ Migration failed: ${(error as Error).message}`, 'error');
    throw error;
  }
}

/**
 * Revert last migration
 */
async function revertMigration(dataSource: DataSource): Promise<void> {
  log('📋 Checking executed migrations...', 'info');

  const executed = await dataSource.query(
    `SELECT * FROM migrations ORDER BY timestamp DESC LIMIT 1`
  ).catch(() => []);

  if (executed.length === 0) {
    log('⚠️  No migrations to revert', 'warn');
    return;
  }

  const lastMigration = executed[0];
  log(`\n⏪ Reverting migration: ${lastMigration.name}\n`, 'warn');

  if (options.dryRun) {
    log('🔍 DRY RUN MODE - No changes will be made', 'warn');
    log(`Would revert: ${lastMigration.name}`, 'info');
    return;
  }

  try {
    await dataSource.undoLastMigration({
      transaction: options.transaction as 'all' | 'each' | 'none',
    });
    log(`\n✅ Successfully reverted: ${lastMigration.name}`, 'success');
  } catch (error) {
    log(`\n❌ Revert failed: ${(error as Error).message}`, 'error');
    throw error;
  }
}

/**
 * Show all migrations and their status
 */
async function showMigrations(dataSource: DataSource): Promise<void> {
  log('📋 Migration Status:\n', 'info');

  try {
    const migrations = await dataSource.migrations;
    const executed = await dataSource.query(
      `SELECT * FROM migrations ORDER BY timestamp ASC`
    ).catch(() => []);
    const executedIds = new Set(executed.map((m: any) => m.name));

    if (migrations.length === 0) {
      log('No migrations found', 'warn');
      return;
    }

    // Get max length for formatting
    const maxLength = Math.max(...migrations.map(m => m.name.length));

    log('┌─ Executed Migrations ─────────────────────────────────────┐\n');
    let executedCount = 0;
    migrations.forEach(migration => {
      if (executedIds.has(migration.name)) {
        log(`  ✓ ${migration.name.padEnd(maxLength)}  [EXECUTED]`, 'success');
        executedCount++;
      }
    });

    if (executedCount === 0) {
      log('  (none)', 'warn');
    }

    log('\n┌─ Pending Migrations ──────────────────────────────────────┐\n');
    let pendingCount = 0;
    migrations.forEach(migration => {
      if (!executedIds.has(migration.name)) {
        log(`  ○ ${migration.name.padEnd(maxLength)}  [PENDING]`, 'warn');
        pendingCount++;
      }
    });

    if (pendingCount === 0) {
      log('  (none)', 'info');
    }

    log('\n└───────────────────────────────────────────────────────────┘');
    log(`\nTotal: ${migrations.length} | Executed: ${executedCount} | Pending: ${pendingCount}`, 'info');

    if (pendingCount > 0) {
      log('\n💡 Run "npm run migration:run" to execute pending migrations', 'info');
    }
  } catch (error) {
    log(`\n❌ Failed to show migrations: ${(error as Error).message}`, 'error');
    throw error;
  }
}

/**
 * Generate migration from entity changes
 */
async function generateMigration(dataSource: DataSource, name: string): Promise<void> {
  log(`\n🔧 Generating migration: ${name}\n`, 'info');

  if (!name) {
    log('❌ Migration name is required', 'error');
    log('Usage: npm run migration:generate -- MigrationName', 'info');
    process.exit(1);
  }

  try {
    // TypeORM CLI equivalent
    const { execSync } = require('child_process');
    const timestamp = Date.now();
    const migrationName = `${timestamp}-${name}`;
    const migrationPath = `src/database/migrations/${migrationName}`;

    execSync(
      `npx typeorm migration:generate ${migrationPath} -d src/database/data-source.ts`,
      { stdio: 'inherit' }
    );

    log(`\n✅ Migration generated: ${migrationPath}.ts`, 'success');
  } catch (error) {
    log(`\n❌ Failed to generate migration: ${(error as Error).message}`, 'error');
    throw error;
  }
}

/**
 * Create empty migration
 */
async function createMigration(name: string): Promise<void> {
  log(`\n🔧 Creating empty migration: ${name}\n`, 'info');

  if (!name) {
    log('❌ Migration name is required', 'error');
    log('Usage: npm run migration:create -- MigrationName', 'info');
    process.exit(1);
  }

  try {
    const { execSync } = require('child_process');
    const timestamp = Date.now();
    const migrationName = `${timestamp}-${name}`;
    const migrationPath = `src/database/migrations/${migrationName}`;

    execSync(
      `npx typeorm migration:create ${migrationPath}`,
      { stdio: 'inherit' }
    );

    log(`\n✅ Migration created: ${migrationPath}.ts`, 'success');
  } catch (error) {
    log(`\n❌ Failed to create migration: ${(error as Error).message}`, 'error');
    throw error;
  }
}

/**
 * Main function
 */
async function main(): Promise<void> {
  log('\n═══════════════════════════════════════════', 'info');
  log('   Database Migration Manager', 'info');
  log('═══════════════════════════════════════════\n', 'info');

  // Validate command
  const validCommands = ['run', 'revert', 'show', 'generate', 'create'];
  if (!command || !validCommands.includes(command)) {
    log('❌ Invalid command', 'error');
    log('\nAvailable commands:', 'info');
    log('  run      - Run all pending migrations', 'info');
    log('  revert   - Revert the last executed migration', 'info');
    log('  show     - Show all migrations and their status', 'info');
    log('  generate - Generate a new migration file from entity changes', 'info');
    log('  create   - Create an empty migration file', 'info');
    log('\nUsage: npm run migration:<command> [-- options]', 'info');
    process.exit(1);
  }

  let dataSource: DataSource | null = null;

  try {
    // Initialize data source
    log('🔌 Connecting to database...', 'info');
    dataSource = await AppDataSource.initialize();
    log('✅ Database connected\n', 'success');

    // Execute command
    switch (command) {
      case 'run':
        await runMigrations(dataSource);
        break;

      case 'revert':
        await revertMigration(dataSource);
        break;

      case 'show':
        await showMigrations(dataSource);
        break;

      case 'generate':
        const generateName = args[1] || options.migrationName;
        await generateMigration(dataSource, generateName!);
        break;

      case 'create':
        const createName = args[1] || options.migrationName;
        await createMigration(createName!);
        break;
    }

    log('\n✅ Migration operation completed successfully', 'success');
    process.exit(0);
  } catch (error) {
    log(`\n❌ Error: ${(error as Error).message}`, 'error');
    if (process.env.NODE_ENV === 'development') {
      console.error(error);
    }
    process.exit(1);
  } finally {
    // Close connection
    if (dataSource?.isInitialized) {
      await dataSource.destroy();
      log('\n🔌 Database connection closed', 'info');
    }
  }
}

// Run main function
main();
