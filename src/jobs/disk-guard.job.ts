/**
 * Disk Guard Job
 * Automated disk space management and emergency cleanup
 *
 * Features:
 * - Monitor disk usage every hour
 * - Three-tier watermark system (WARN/SHED/EMERGENCY)
 * - Dynamic log level adjustment
 * - Automatic cleanup of temporary files and old backups
 * - Emergency compression and purging
 */

import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';
import { logger } from '../utils/logger.util';

const GB = 1024 * 1024 * 1024;
const MB = 1024 * 1024;

/**
 * Get disk usage percentage for root filesystem
 */
function getDiskUsagePercent(): number {
  try {
    // Linux: df -P / returns filesystem stats
    const output = execSync("df -P / | awk 'NR==2 {print $5}'")
      .toString()
      .trim()
      .replace('%', '');
    return parseInt(output, 10);
  } catch (error) {
    logger.error('Failed to get disk usage', { error });
    return 0;
  }
}

/**
 * Get directory size in bytes
 */
function dirSizeBytes(dirPath: string): number {
  try {
    if (!fs.existsSync(dirPath)) {
      return 0;
    }
    const output = execSync(`du -sb "${dirPath}" | awk '{print $1}'`).toString();
    return parseInt(output, 10);
  } catch (error) {
    return 0;
  }
}

/**
 * Get directory size in human-readable format
 */
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < MB) return `${(bytes / 1024).toFixed(2)} KB`;
  if (bytes < GB) return `${(bytes / MB).toFixed(2)} MB`;
  return `${(bytes / GB).toFixed(2)} GB`;
}

/**
 * Compress uncompressed log files
 */
function compressOldLogs(logsDir: string): void {
  try {
    // Find .log files older than 1 day and compress them
    execSync(`find "${logsDir}" -type f -name "*.log" -mtime +1 -exec gzip -f {} +`, {
      stdio: 'ignore',
    });
    logger.info('DiskGuard: Compressed old log files', { logsDir });
  } catch (error) {
    logger.error('Failed to compress old logs', { error, logsDir });
  }
}

/**
 * Clean temporary files older than specified days
 */
function cleanTempFiles(tmpDir: string, daysOld: number = 7): void {
  try {
    if (!fs.existsSync(tmpDir)) {
      return;
    }
    const before = dirSizeBytes(tmpDir);
    execSync(`find "${tmpDir}" -type f -mtime +${daysOld} -delete`, { stdio: 'ignore' });
    const after = dirSizeBytes(tmpDir);
    const freed = before - after;

    if (freed > 0) {
      logger.info('DiskGuard: Cleaned temp files', {
        tmpDir,
        daysOld,
        freed: formatBytes(freed),
      });
    }
  } catch (error) {
    logger.error('Failed to clean temp files', { error, tmpDir });
  }
}

/**
 * Trim daily backups to stay under size cap
 */
function trimDailyBackups(backupsDaily: string, maxSizeGB: number): void {
  try {
    if (!fs.existsSync(backupsDaily)) {
      return;
    }

    const maxBytes = maxSizeGB * GB;
    let currentSize = dirSizeBytes(backupsDaily);

    if (currentSize <= maxBytes) {
      return;
    }

    logger.warn('DiskGuard: Daily backups exceed size cap, trimming...', {
      current: formatBytes(currentSize),
      max: formatBytes(maxBytes),
    });

    let removed = 0;
    while (currentSize > maxBytes) {
      try {
        // Find oldest backup file
        const output = execSync(
          `find "${backupsDaily}" -name "sigmatrade_*.sql.gz" -type f -printf '%T@ %p\n' | sort -n | head -1`,
          { encoding: 'utf-8' }
        ).trim();

        if (!output) {
          break; // No more files
        }

        const oldestFile = output.split(' ').slice(1).join(' ');
        const fileSize = fs.statSync(oldestFile).size;

        fs.unlinkSync(oldestFile);
        removed++;
        currentSize -= fileSize;

        logger.info('DiskGuard: Removed oldest daily backup', {
          file: path.basename(oldestFile),
          size: formatBytes(fileSize),
        });
      } catch (error) {
        break;
      }
    }

    if (removed > 0) {
      logger.info('DiskGuard: Daily backup trim complete', {
        removed,
        newSize: formatBytes(currentSize),
      });
    }
  } catch (error) {
    logger.error('Failed to trim daily backups', { error, backupsDaily });
  }
}

/**
 * Clean old backup logs
 */
function cleanBackupLogs(backupsLogs: string, daysOld: number = 90): void {
  try {
    if (!fs.existsSync(backupsLogs)) {
      return;
    }
    const before = dirSizeBytes(backupsLogs);
    execSync(`find "${backupsLogs}" -name "backup_*.log" -type f -mtime +${daysOld} -delete`, {
      stdio: 'ignore',
    });
    const after = dirSizeBytes(backupsLogs);
    const freed = before - after;

    if (freed > 0) {
      logger.info('DiskGuard: Cleaned old backup logs', {
        daysOld,
        freed: formatBytes(freed),
      });
    }
  } catch (error) {
    logger.error('Failed to clean backup logs', { error });
  }
}

// ==================== SCHEDULER ====================

let schedulerInterval: NodeJS.Timeout | null = null;

/**
 * Start DiskGuard scheduler (runs every hour)
 */
export async function startDiskGuardScheduler(): Promise<void> {
  if (schedulerInterval) {
    logger.warn('DiskGuard scheduler already running');
    return;
  }

  logger.info('Starting DiskGuard scheduler (hourly)...');

  // Run immediately on start
  await runDiskGuard();

  // Then run every hour (at minute 7 to avoid collision with other jobs)
  const HOUR_MS = 60 * 60 * 1000;
  schedulerInterval = setInterval(async () => {
    await runDiskGuard();
  }, HOUR_MS);

  logger.info('✅ DiskGuard scheduler started');
}

/**
 * Stop DiskGuard scheduler
 */
export async function stopDiskGuardScheduler(): Promise<void> {
  if (schedulerInterval) {
    clearInterval(schedulerInterval);
    schedulerInterval = null;
    logger.info('DiskGuard scheduler stopped');
  }
}

// ==================== MAIN EXECUTION ====================

/**
 * Main DiskGuard execution
 */
export async function runDiskGuard(): Promise<void> {
  try {
    // Get watermark thresholds from ENV
    const WARN_THRESHOLD = parseInt(process.env.DISK_WATERMARK_WARN || '75', 10);
    const SHED_THRESHOLD = parseInt(process.env.DISK_WATERMARK_SHED || '85', 10);
    const EMER_THRESHOLD = parseInt(process.env.DISK_WATERMARK_EMERGENCY || '92', 10);

    // Get current disk usage
    const diskUsage = getDiskUsagePercent();

    // Paths
    const logsDir = path.join(process.cwd(), 'logs');
    const backupsDaily = path.join(process.cwd(), 'backups', 'daily');
    const backupsLogs = path.join(process.cwd(), 'backups', 'logs');
    const tmpDir = path.join(process.cwd(), 'tmp');

    // Measure sizes
    const sizes = {
      logs: dirSizeBytes(logsDir),
      backupsDaily: dirSizeBytes(backupsDaily),
      backupsLogs: dirSizeBytes(backupsLogs),
      tmp: dirSizeBytes(tmpDir),
      total: 0,
    };
    sizes.total = sizes.logs + sizes.backupsDaily + sizes.backupsLogs + sizes.tmp;

    logger.info('DiskGuard: Health check', {
      diskUsage: `${diskUsage}%`,
      sizes: {
        logs: formatBytes(sizes.logs),
        backupsDaily: formatBytes(sizes.backupsDaily),
        backupsLogs: formatBytes(sizes.backupsLogs),
        tmp: formatBytes(sizes.tmp),
        total: formatBytes(sizes.total),
      },
    });

    // ==================== NORMAL OPERATION (<75%) ====================
    if (diskUsage < WARN_THRESHOLD) {
      // All good, nothing to do
      return;
    }

    // ==================== WARNING (75-84%) ====================
    if (diskUsage >= WARN_THRESHOLD && diskUsage < SHED_THRESHOLD) {
      logger.warn('DiskGuard: WARN threshold reached', {
        diskUsage: `${diskUsage}%`,
        threshold: `${WARN_THRESHOLD}%`,
      });

      // Lower log verbosity to 'info'
      process.env.LOG_LEVEL = 'info';

      // Clean temp files older than 7 days
      cleanTempFiles(tmpDir, 7);

      return;
    }

    // ==================== LOAD SHEDDING (85-91%) ====================
    if (diskUsage >= SHED_THRESHOLD && diskUsage < EMER_THRESHOLD) {
      logger.warn('DiskGuard: SHED threshold reached, reducing load...', {
        diskUsage: `${diskUsage}%`,
        threshold: `${SHED_THRESHOLD}%`,
      });

      // Lower log verbosity to 'warn'
      process.env.LOG_LEVEL = 'warn';

      // Aggressive temp cleanup (>3 days)
      cleanTempFiles(tmpDir, 3);

      // Clean backup logs older than 90 days
      cleanBackupLogs(backupsLogs, 90);

      // Trim daily backups if over limit
      const maxGB = parseInt(process.env.BACKUP_LOCAL_MAX_GB || '2', 10);
      trimDailyBackups(backupsDaily, maxGB);

      return;
    }

    // ==================== EMERGENCY (92%+) ====================
    if (diskUsage >= EMER_THRESHOLD) {
      logger.error('DiskGuard: EMERGENCY threshold reached! Aggressive cleanup...', {
        diskUsage: `${diskUsage}%`,
        threshold: `${EMER_THRESHOLD}%`,
      });

      // Minimize logging (errors only)
      process.env.LOG_LEVEL = 'error';

      // 1. Compress all uncompressed log files
      compressOldLogs(logsDir);

      // 2. Aggressive temp cleanup (>1 day)
      cleanTempFiles(tmpDir, 1);

      // 3. Clean backup logs older than 60 days (instead of 90)
      cleanBackupLogs(backupsLogs, 60);

      // 4. Aggressively trim daily backups
      const maxGB = parseInt(process.env.BACKUP_LOCAL_MAX_GB || '2', 10);
      trimDailyBackups(backupsDaily, Math.min(maxGB, 1)); // Max 1GB in emergency

      // 5. Final check - if still critical, alert
      const newUsage = getDiskUsagePercent();
      if (newUsage >= EMER_THRESHOLD) {
        logger.error('DiskGuard: CRITICAL - Disk still full after emergency cleanup!', {
          beforeCleanup: `${diskUsage}%`,
          afterCleanup: `${newUsage}%`,
          action: 'Manual intervention required',
        });
      } else {
        logger.info('DiskGuard: Emergency cleanup successful', {
          beforeCleanup: `${diskUsage}%`,
          afterCleanup: `${newUsage}%`,
          freed: `${diskUsage - newUsage}%`,
        });
      }

      return;
    }
  } catch (error) {
    logger.error('DiskGuard: Execution failed', { error });
  }
}

export default {
  runDiskGuard,
};
