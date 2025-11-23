/**
 * Backup Job
 * Creates database backups and pushes to git repository
 * Runs daily at configured time (default: 4 AM)
 */

import { Job } from 'bull';
import { exec } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs/promises';
import * as path from 'path';
import { getQueue, QueueName } from './queue.config';
import { config } from '../config';
import { logger } from '../utils/logger.util';

const execAsync = promisify(exec);

export interface BackupJobData {
  timestamp: number;
  manual?: boolean;
}

/**
 * Create database backup
 */
export const createBackup = async (job: Job<BackupJobData>): Promise<void> => {
  if (!config.backup.enabled) {
    logger.warn('⚠️ Backup is disabled');
    return;
  }

  try {
    logger.info('💾 Starting database backup...');

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const backupDir = config.backup.dir;
    const backupFile = path.join(backupDir, `backup-${timestamp}.sql`);

    // Ensure backup directory exists
    await fs.mkdir(backupDir, { recursive: true });

    // Create PostgreSQL dump
    const dumpCommand = `PGPASSWORD="${config.database.password}" pg_dump \
      -h ${config.database.host} \
      -p ${config.database.port} \
      -U ${config.database.username} \
      -d ${config.database.database} \
      -F p \
      -f "${backupFile}"`;

    await execAsync(dumpCommand);

    logger.info(`✅ Database backup created: ${backupFile}`);

    // Compress backup
    const compressedFile = `${backupFile}.gz`;
    await execAsync(`gzip "${backupFile}"`);

    logger.info(`✅ Backup compressed: ${compressedFile}`);

    // Clean old backups
    await cleanOldBackups();

    // Push to git (if configured)
    if (config.backup.gitRemote && config.backup.gitBranch) {
      await pushBackupToGit(compressedFile);
    }

    logger.info('✅ Backup job completed successfully');
  } catch (error) {
    logger.error('❌ Backup job failed:', error);
    throw error;
  }
};

/**
 * Clean old backups (older than retention period)
 */
const cleanOldBackups = async (): Promise<void> => {
  try {
    const backupDir = config.backup.dir;
    const retentionMs = config.backup.retentionDays * 24 * 60 * 60 * 1000;
    const now = Date.now();

    const files = await fs.readdir(backupDir);

    for (const file of files) {
      if (!file.startsWith('backup-') || !file.endsWith('.sql.gz')) {
        continue;
      }

      const filePath = path.join(backupDir, file);
      const stats = await fs.stat(filePath);
      const age = now - stats.mtimeMs;

      if (age > retentionMs) {
        await fs.unlink(filePath);
        logger.info(`🗑️ Deleted old backup: ${file}`);
      }
    }
  } catch (error) {
    logger.error('❌ Error cleaning old backups:', error);
  }
};

/**
 * Push backup to git repository
 */
const pushBackupToGit = async (backupFile: string): Promise<void> => {
  try {
    logger.info('📤 Pushing backup to git...');

    // Add backup file
    await execAsync(`git add "${backupFile}"`);

    // Commit
    const commitMessage = `Automated backup: ${path.basename(backupFile)}`;
    await execAsync(`git commit -m "${commitMessage}"`);

    // Push
    await execAsync(
      `git push ${config.backup.gitRemote} ${config.backup.gitBranch}`
    );

    logger.info('✅ Backup pushed to git');
  } catch (error) {
    logger.error('❌ Error pushing backup to git:', error);
    // Don't throw - backup is still created locally
  }
};

/**
 * Start backup scheduler
 */
export const startBackupScheduler = async (): Promise<void> => {
  if (!config.jobs.backup.enabled) {
    logger.warn('⚠️ Backup scheduler is disabled');
    return;
  }

  try {
    const queue = getQueue(QueueName.BACKUP);

    // Schedule daily backup
    await queue.add(
      'daily-backup',
      { timestamp: Date.now() },
      {
        repeat: {
          cron: config.jobs.backup.cron, // Default: "0 4 * * *" (4 AM daily)
        },
        removeOnComplete: 10,
        removeOnFail: false,
      }
    );

    // Process jobs
    queue.process('daily-backup', createBackup);

    logger.info(
      `✅ Backup scheduler started (cron: ${config.jobs.backup.cron})`
    );
  } catch (error) {
    logger.error('❌ Failed to start backup scheduler:', error);
    throw error;
  }
};

/**
 * Stop backup scheduler
 */
export const stopBackupScheduler = async (): Promise<void> => {
  try {
    const queue = getQueue(QueueName.BACKUP);
    await queue.removeRepeatable('daily-backup', {
      cron: config.jobs.backup.cron,
    });

    logger.info('✅ Backup scheduler stopped');
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

    const queue = getQueue(QueueName.BACKUP);
    await queue.add('manual-backup', {
      timestamp: Date.now(),
      manual: true,
    });

    logger.info('✅ Manual backup queued');
  } catch (error) {
    logger.error('❌ Manual backup failed:', error);
    throw error;
  }
};
