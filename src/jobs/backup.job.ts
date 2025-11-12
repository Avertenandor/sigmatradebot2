/**
 * Sanitized DB Backup Job
 *
 * P0 SECURITY FIX: Only dumps whitelisted tables (no secrets/config)
 *
 * Features:
 * - Dumps only critical business tables (users, deposits, transactions, referrals, etc.)
 * - Excludes sensitive tables (config, sessions, retry queues, notifications)
 * - Verifies backup integrity with pg_restore --list
 * - Pushes to Git branch 'backups/sanitized' (separate from code)
 * - Custom format (--format=custom) with max compression (--compress=9)
 * - Automatic rotation (90 days retention)
 *
 * Schedule: Every 6 hours (cron configured in scheduler)
 */

import { Job } from 'bull';
import { exec } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs/promises';
import * as path from 'path';
import { sanitizedBackupConfig as cfg } from '../config/backup.sanitized';
import { config } from '../config';
import { logger } from '../utils/logger.util';

const sh = promisify(exec);

export interface BackupJobData {
  timestamp?: number;
  manual?: boolean;
}

/**
 * Create sanitized database backup
 */
export const createBackup = async (_job: Job<BackupJobData>): Promise<void> => {
  if (!cfg.enabled) {
    logger.warn('⚠️  Sanitized backup is disabled');
    return;
  }

  try {
    // Ensure backup dir exists
    await fs.mkdir(cfg.dir, { recursive: true });

    const ts = new Date().toISOString().replace(/[:.]/g, '-');
    const outFile = path.join(cfg.dir, `sigmatrade_${ts}.sql.gz`);

    // Build table args for pg_dump
    const tableArgs = cfg.tables.map(t => `-t ${t}`).join(' ');

    // DB credentials
    const { host, port, username, password, database } = config.database;

    logger.info(`💾 Creating sanitized backup → ${outFile}`);
    logger.info(`📋 Tables: ${cfg.tables.join(', ')}`);

    const env = { ...process.env, PGPASSWORD: password || '' };

    // CRITICAL: Dump only whitelisted tables (no secrets!)
    // - custom format: fast restore with pg_restore
    // - compress=9: maximum compression
    // - no-owner/no-acl: portable across environments
    // - gzip container: additional compression layer
    const dumpCmd =
      `pg_dump -h ${host} -p ${port} -U ${username} -d ${database} ` +
      `${tableArgs} --no-owner --no-acl --format=custom --compress=9 | gzip -c > "${outFile}"`;

    await sh(dumpCmd, { env });

    const stats = await fs.stat(outFile);
    const sizeMB = (stats.size / 1024 / 1024).toFixed(2);
    logger.info(`✅ Backup created: ${sizeMB} MB`);

    // CRITICAL: Verify backup integrity before committing to git
    logger.info('🔎 Verifying backup integrity...');
    const verifyCmd = `gzip -cd "${outFile}" | pg_restore --list > /dev/null`;
    await sh(verifyCmd, { env });
    logger.info('✅ Backup integrity verified');

    // Rotate old backups
    await rotateOldBackups(cfg.dir, cfg.retentionDays);

    // Push to git (separate branch: backups/sanitized)
    if (cfg.gitRemote && cfg.gitBranch) {
      await pushToGit(outFile, cfg.gitRemote, cfg.gitBranch);
    }

    logger.info('✅ Sanitized backup complete');
  } catch (error) {
    logger.error('❌ Sanitized backup failed:', error);
    throw error;
  }
};

/**
 * Rotate old backups (delete files older than retention period)
 */
async function rotateOldBackups(dir: string, keepDays: number): Promise<void> {
  try {
    const now = Date.now();
    const keepMs = keepDays * 24 * 60 * 60 * 1000;
    const files = await fs.readdir(dir);

    let deletedCount = 0;
    for (const f of files) {
      if (!f.endsWith('.sql.gz')) continue;

      const p = path.join(dir, f);
      const st = await fs.stat(p);

      if (now - st.mtimeMs > keepMs) {
        await fs.unlink(p);
        logger.info(`🗑️  Deleted old backup: ${f}`);
        deletedCount++;
      }
    }

    if (deletedCount > 0) {
      logger.info(`🗑️  Cleaned up ${deletedCount} old backup(s)`);
    }
  } catch (error) {
    logger.error('❌ Error rotating old backups:', error);
    // Don't throw - backup is still created
  }
}

/**
 * Push backup to git branch (backups/sanitized)
 *
 * SECURITY: Only sanitized backups (whitelisted tables) go to git
 * Never push full database dumps with secrets to git!
 */
async function pushToGit(
  filePath: string,
  remote: string,
  branch: string
): Promise<void> {
  try {
    logger.info(`📤 Pushing backup to git (${remote} ${branch})...`);

    // Ensure branch exists locally
    try {
      await sh(`git rev-parse --verify ${branch}`);
      logger.info(`✓ Branch ${branch} exists`);
    } catch {
      logger.info(`✓ Creating new branch ${branch}`);
      await sh(`git checkout -b ${branch}`);
    }

    // Switch to backup branch if not already on it
    const { stdout: currentBranch } = await sh('git rev-parse --abbrev-ref HEAD');
    if (currentBranch.trim() !== branch) {
      logger.info(`✓ Switching to branch ${branch}`);
      await sh(`git checkout ${branch}`);
    }

    // Add backup file (relative path for portability)
    const rel = path.relative(process.cwd(), filePath).replace(/\\/g, '/');
    await sh(`git add -- "${rel}"`);

    // Commit (skip if no changes)
    const commitMsg = `Sanitized backup: ${path.basename(filePath)}`;
    try {
      await sh(`git commit -m "${commitMsg}"`);
      logger.info('✓ Backup committed');
    } catch (error: any) {
      if (error.message?.includes('nothing to commit')) {
        logger.info('✓ No changes to commit (backup already exists)');
      } else {
        throw error;
      }
    }

    // Push to remote
    await sh(`git push ${remote} ${branch}`);
    logger.info('✅ Backup pushed to git');
  } catch (error) {
    logger.error('❌ Error pushing backup to git:', error);
    // Don't throw - backup is still created locally
  }
}

/**
 * Start backup scheduler (called from main process)
 *
 * Schedules sanitized backups every 6 hours using Bull queue
 */
export const startBackupScheduler = async (): Promise<void> => {
  if (!cfg.enabled) {
    logger.warn('⚠️  Sanitized backup scheduler is disabled');
    return;
  }

  try {
    const { getQueue, QueueName } = await import('./queue.config');
    const queue = getQueue(QueueName.BACKUP);

    // Schedule sanitized backups (every 6 hours by default)
    await queue.add(
      'sanitized-backup',
      { timestamp: Date.now() },
      {
        repeat: {
          cron: cfg.cron, // Default: "0 */6 * * *" (every 6 hours)
        },
        removeOnComplete: 10,
        removeOnFail: false,
      }
    );

    // Process backup jobs
    queue.process('sanitized-backup', createBackup);

    logger.info(
      `✅ Sanitized backup scheduler started (cron: ${cfg.cron})`
    );
    logger.info(`📋 Whitelisted tables: ${cfg.tables.join(', ')}`);
    logger.info(`📤 Git push: ${cfg.gitRemote}/${cfg.gitBranch}`);
  } catch (error) {
    logger.error('❌ Failed to start sanitized backup scheduler:', error);
    throw error;
  }
};

/**
 * Stop backup scheduler
 */
export const stopBackupScheduler = async (): Promise<void> => {
  try {
    const { getQueue, QueueName } = await import('./queue.config');
    const queue = getQueue(QueueName.BACKUP);

    await queue.removeRepeatable('sanitized-backup', {
      cron: cfg.cron,
    });

    logger.info('✅ Sanitized backup scheduler stopped');
  } catch (error) {
    logger.error('❌ Error stopping backup scheduler:', error);
  }
};

/**
 * Trigger manual backup (for admin panel)
 */
export const triggerManualBackup = async (): Promise<void> => {
  try {
    logger.info('🔄 Manual backup triggered');

    // Call createBackup directly (no queue)
    await createBackup({ id: 'manual', data: { timestamp: Date.now(), manual: true } } as Job<BackupJobData>);

    logger.info('✅ Manual backup completed');
  } catch (error) {
    logger.error('❌ Manual backup failed:', error);
    throw error;
  }
};
