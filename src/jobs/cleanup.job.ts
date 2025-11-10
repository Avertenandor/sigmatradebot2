/**
 * Cleanup Job
 * Cleans up old logs and user actions (7-day TTL)
 * Runs weekly (default: Sunday at 3 AM)
 */

import { Job } from 'bull';
import { LessThan } from 'typeorm';
import { exec } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs/promises';
import * as path from 'path';
import { getQueue, QueueName } from './queue.config';
import { AppDataSource } from '../database/data-source';
import { UserAction } from '../database/entities/UserAction.entity';
import { config } from '../config';
import { logger } from '../utils/logger.util';
import adminService from '../services/admin.service';

const execAsync = promisify(exec);

export interface CleanupJobData {
  timestamp: number;
}

/**
 * Clean up old data and logs
 */
export const performCleanup = async (job: Job<CleanupJobData>): Promise<void> => {
  try {
    logger.info('🧹 Starting cleanup job...');

    // Clean old user actions (7-day TTL)
    await cleanOldUserActions();

    // Clean expired admin sessions
    await cleanExpiredAdminSessions();

    // Clean old log files
    await cleanOldLogFiles();

    // Clean completed/failed jobs from queues
    await cleanOldQueueJobs();

    logger.info('✅ Cleanup job completed successfully');
  } catch (error) {
    logger.error('❌ Cleanup job failed:', error);
    throw error;
  }
};

/**
 * Clean user actions older than 7 days
 */
const cleanOldUserActions = async (): Promise<void> => {
  try {
    const userActionRepo = AppDataSource.getRepository(UserAction);

    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

    const result = await userActionRepo.delete({
      created_at: LessThan(sevenDaysAgo),
    });

    logger.info(
      `🗑️ Deleted ${result.affected || 0} user actions older than 7 days`
    );
  } catch (error) {
    logger.error('❌ Error cleaning old user actions:', error);
  }
};

/**
 * Clean expired admin sessions
 */
const cleanExpiredAdminSessions = async (): Promise<void> => {
  try {
    const cleaned = await adminService.cleanupExpiredSessions();

    if (cleaned > 0) {
      logger.info(`🗑️ Deactivated ${cleaned} expired admin sessions`);
    } else {
      logger.debug('ℹ️ No expired admin sessions to clean');
    }
  } catch (error) {
    logger.error('❌ Error cleaning expired admin sessions:', error);
  }
};

/**
 * Clean log files older than 90 days
 */
const cleanOldLogFiles = async (): Promise<void> => {
  try {
    const logsDir = path.join(process.cwd(), 'logs');

    // Check if logs directory exists
    try {
      await fs.access(logsDir);
    } catch {
      logger.debug('ℹ️ Logs directory does not exist, skipping log cleanup');
      return;
    }

    const files = await fs.readdir(logsDir);
    const ninetyDaysAgo = Date.now() - 90 * 24 * 60 * 60 * 1000;

    let deletedCount = 0;

    for (const file of files) {
      if (!file.endsWith('.log') && !file.endsWith('.log.gz')) {
        continue;
      }

      const filePath = path.join(logsDir, file);
      const stats = await fs.stat(filePath);

      if (stats.mtimeMs < ninetyDaysAgo) {
        await fs.unlink(filePath);
        deletedCount++;
        logger.debug(`🗑️ Deleted old log file: ${file}`);
      }
    }

    logger.info(`🗑️ Deleted ${deletedCount} log files older than 90 days`);
  } catch (error) {
    logger.error('❌ Error cleaning old log files:', error);
  }
};

/**
 * Clean old jobs from Bull queues
 */
const cleanOldQueueJobs = async (): Promise<void> => {
  try {
    const queueNames = Object.values(QueueName);
    let totalCleaned = 0;

    for (const queueName of queueNames) {
      try {
        const queue = getQueue(queueName as QueueName);

        // Clean completed jobs older than 24 hours
        const completedJobs = await queue.getCompleted();
        const oneDayAgo = Date.now() - 24 * 60 * 60 * 1000;

        for (const job of completedJobs) {
          if (job.finishedOn && job.finishedOn < oneDayAgo) {
            await job.remove();
            totalCleaned++;
          }
        }

        // Clean failed jobs older than 7 days
        const failedJobs = await queue.getFailed();
        const sevenDaysAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;

        for (const job of failedJobs) {
          if (job.finishedOn && job.finishedOn < sevenDaysAgo) {
            await job.remove();
            totalCleaned++;
          }
        }
      } catch (error) {
        logger.error(`❌ Error cleaning queue ${queueName}:`, error);
      }
    }

    logger.info(`🗑️ Cleaned ${totalCleaned} old jobs from queues`);
  } catch (error) {
    logger.error('❌ Error cleaning old queue jobs:', error);
  }
};

/**
 * Start cleanup scheduler
 */
export const startCleanupScheduler = async (): Promise<void> => {
  if (!config.jobs.logCleanup.enabled) {
    logger.warn('⚠️ Cleanup scheduler is disabled');
    return;
  }

  try {
    const queue = getQueue(QueueName.LOG_CLEANUP);

    // Schedule weekly cleanup
    await queue.add(
      'weekly-cleanup',
      { timestamp: Date.now() },
      {
        repeat: {
          cron: config.jobs.logCleanup.cron, // Default: "0 3 * * 0" (Sunday 3 AM)
        },
        removeOnComplete: 5,
        removeOnFail: false,
      }
    );

    // Process jobs
    queue.process('weekly-cleanup', performCleanup);

    logger.info(
      `✅ Cleanup scheduler started (cron: ${config.jobs.logCleanup.cron})`
    );
  } catch (error) {
    logger.error('❌ Failed to start cleanup scheduler:', error);
    throw error;
  }
};

/**
 * Stop cleanup scheduler
 */
export const stopCleanupScheduler = async (): Promise<void> => {
  try {
    const queue = getQueue(QueueName.LOG_CLEANUP);
    await queue.removeRepeatable('weekly-cleanup', {
      cron: config.jobs.logCleanup.cron,
    });

    logger.info('✅ Cleanup scheduler stopped');
  } catch (error) {
    logger.error('❌ Error stopping cleanup scheduler:', error);
  }
};

/**
 * Trigger manual cleanup (for admin panel)
 */
export const triggerManualCleanup = async (): Promise<void> => {
  try {
    logger.info('🔄 Manual cleanup triggered');

    const queue = getQueue(QueueName.LOG_CLEANUP);
    await queue.add('manual-cleanup', {
      timestamp: Date.now(),
    });

    logger.info('✅ Manual cleanup queued');
  } catch (error) {
    logger.error('❌ Manual cleanup failed:', error);
    throw error;
  }
};
