/**
 * Queue Configuration
 * Bull queue setup for background jobs
 */

import Queue from 'bull';
import { config } from '../config';
import { logger } from '../utils/logger.util';

// Queue names
export enum QueueName {
  BLOCKCHAIN_MONITOR = 'blockchain-monitor',
  PAYMENT_PROCESSOR = 'payment-processor',
  PAYMENT_RETRY = 'payment-retry',
  NOTIFICATION_RETRY = 'notification-retry', // FIX #17
  REWARD_CALCULATOR = 'reward-calculator',
  BACKUP = 'backup',
  LOG_CLEANUP = 'log-cleanup',
}

// Queue instances
export const queues = new Map<QueueName, Queue.Queue>();

/**
 * Initialize all queues
 */
export const initializeQueues = (): void => {
  const queueOptions: Queue.QueueOptions = {
    redis: {
      host: config.redis.host,
      port: config.redis.port,
      password: config.redis.password,
      db: config.redis.db,
      tls: config.redis.tls,
    },
    defaultJobOptions: {
      removeOnComplete: 100, // Keep last 100 completed jobs
      removeOnFail: 500, // Keep last 500 failed jobs
      attempts: 3, // Retry up to 3 times
      backoff: {
        type: 'exponential',
        delay: 2000, // Start with 2 seconds
      },
    },
  };

  // Create queues
  const blockchainMonitorQueue = new Queue(QueueName.BLOCKCHAIN_MONITOR, queueOptions);
  const paymentProcessorQueue = new Queue(QueueName.PAYMENT_PROCESSOR, queueOptions);
  const paymentRetryQueue = new Queue(QueueName.PAYMENT_RETRY, queueOptions);
  const notificationRetryQueue = new Queue(QueueName.NOTIFICATION_RETRY, queueOptions); // FIX #17
  const rewardCalculatorQueue = new Queue(QueueName.REWARD_CALCULATOR, queueOptions);
  const backupQueue = new Queue(QueueName.BACKUP, queueOptions);
  const logCleanupQueue = new Queue(QueueName.LOG_CLEANUP, queueOptions);

  queues.set(QueueName.BLOCKCHAIN_MONITOR, blockchainMonitorQueue);
  queues.set(QueueName.PAYMENT_PROCESSOR, paymentProcessorQueue);
  queues.set(QueueName.PAYMENT_RETRY, paymentRetryQueue);
  queues.set(QueueName.NOTIFICATION_RETRY, notificationRetryQueue); // FIX #17
  queues.set(QueueName.REWARD_CALCULATOR, rewardCalculatorQueue);
  queues.set(QueueName.BACKUP, backupQueue);
  queues.set(QueueName.LOG_CLEANUP, logCleanupQueue);

  // Error handlers
  for (const [name, queue] of queues) {
    queue.on('error', (error) => {
      logger.error(`❌ Queue ${name} error:`, error);
    });

    queue.on('failed', (job, error) => {
      logger.error(`❌ Job ${job.id} in queue ${name} failed:`, error);
    });

    queue.on('stalled', (job) => {
      logger.warn(`⚠️ Job ${job.id} in queue ${name} stalled`);
    });

    queue.on('completed', (job) => {
      logger.debug(`✅ Job ${job.id} in queue ${name} completed`);
    });
  }

  logger.info('✅ Bull queues initialized');
};

/**
 * Get queue by name
 */
export const getQueue = (name: QueueName): Queue.Queue => {
  const queue = queues.get(name);
  if (!queue) {
    throw new Error(`Queue ${name} not found`);
  }
  return queue;
};

/**
 * Close all queues with graceful drain
 *
 * IMPROVEMENT: Wait for active jobs to complete before forcing shutdown
 * - Check active jobs count
 * - Wait up to DRAIN_TIMEOUT_MS for jobs to finish
 * - Log remaining unfinished jobs
 * - Force close after timeout
 */
export const closeQueues = async (options?: { drainTimeoutMs?: number }): Promise<void> => {
  const DRAIN_TIMEOUT_MS = options?.drainTimeoutMs || 30000; // 30 seconds default

  logger.info('🔄 Closing all queues...');

  // Step 1: Check active jobs before closing
  const activeJobs = new Map<QueueName, number>();
  for (const [name, queue] of queues) {
    const activeCount = await queue.getActiveCount();
    if (activeCount > 0) {
      activeJobs.set(name, activeCount);
      logger.info(`⏳ Queue ${name} has ${activeCount} active job(s), waiting...`);
    }
  }

  // Step 2: If there are active jobs, wait for drain
  if (activeJobs.size > 0) {
    logger.info(`⏳ Draining ${activeJobs.size} queue(s) with active jobs (timeout: ${DRAIN_TIMEOUT_MS}ms)...`);

    const drainStart = Date.now();
    const checkInterval = 1000; // Check every second

    while (Date.now() - drainStart < DRAIN_TIMEOUT_MS) {
      let allDrained = true;

      for (const [name, queue] of queues) {
        if (activeJobs.has(name)) {
          const currentActive = await queue.getActiveCount();
          if (currentActive > 0) {
            allDrained = false;
            logger.debug(`⏳ Queue ${name} still has ${currentActive} active job(s)...`);
          } else {
            logger.info(`✅ Queue ${name} drained`);
            activeJobs.delete(name);
          }
        }
      }

      if (allDrained) {
        logger.info('✅ All queues drained successfully');
        break;
      }

      // Wait before next check
      await new Promise(resolve => setTimeout(resolve, checkInterval));
    }

    // Step 3: Log remaining active jobs after timeout
    if (activeJobs.size > 0) {
      logger.warn(`⚠️  Drain timeout reached, ${activeJobs.size} queue(s) still have active jobs:`);
      for (const [name, count] of activeJobs) {
        const currentActive = await queues.get(name)?.getActiveCount();
        logger.warn(`   - ${name}: ${currentActive} active job(s) will be interrupted`);
      }
    }
  }

  // Step 4: Force close all queues
  logger.info('🔄 Force closing all queues...');
  const promises: Promise<void>[] = [];

  for (const [name, queue] of queues) {
    promises.push(
      queue.close().then(() => {
        logger.debug(`✅ Queue ${name} closed`);
      }).catch((error) => {
        logger.error(`❌ Error closing queue ${name}:`, error);
      })
    );
  }

  await Promise.all(promises);
  queues.clear();

  logger.info('✅ All queues closed');
};

/**
 * Get queue statistics
 */
export const getQueueStats = async (
  name: QueueName
): Promise<{
  waiting: number;
  active: number;
  completed: number;
  failed: number;
  delayed: number;
}> => {
  const queue = getQueue(name);

  const [waiting, active, completed, failed, delayed] = await Promise.all([
    queue.getWaitingCount(),
    queue.getActiveCount(),
    queue.getCompletedCount(),
    queue.getFailedCount(),
    queue.getDelayedCount(),
  ]);

  return { waiting, active, completed, failed, delayed };
};

/**
 * Get all queue statistics
 */
export const getAllQueueStats = async (): Promise<
  Map<QueueName, {
    waiting: number;
    active: number;
    completed: number;
    failed: number;
    delayed: number;
  }>
> => {
  const stats = new Map();

  for (const name of queues.keys()) {
    stats.set(name, await getQueueStats(name));
  }

  return stats;
};

/**
 * Check DLQ (Dead Letter Queue) thresholds and alert
 *
 * MONITORING: Detect stuck/failed jobs that need attention
 * - Failed jobs > threshold: Jobs that exhausted all retries
 * - Delayed jobs > threshold: Jobs stuck waiting (stalled)
 * - Logs alerts for SRE investigation
 *
 * Call this periodically (e.g., every 15 minutes) from performance monitor
 */
export const checkDLQThresholds = async (options?: {
  failedThreshold?: number;
  delayedThreshold?: number;
}): Promise<void> => {
  const FAILED_THRESHOLD = options?.failedThreshold || 50; // Alert if >50 failed jobs
  const DELAYED_THRESHOLD = options?.delayedThreshold || 100; // Alert if >100 delayed jobs

  try {
    const stats = await getAllQueueStats();
    const alerts: string[] = [];

    for (const [name, counts] of stats) {
      // Check failed jobs (DLQ)
      if (counts.failed > FAILED_THRESHOLD) {
        const message = `⚠️  DLQ ALERT: Queue ${name} has ${counts.failed} failed jobs (threshold: ${FAILED_THRESHOLD})`;
        alerts.push(message);
        logger.warn(message, {
          queue: name,
          failed: counts.failed,
          threshold: FAILED_THRESHOLD,
        });
      }

      // Check delayed jobs (potentially stuck)
      if (counts.delayed > DELAYED_THRESHOLD) {
        const message = `⚠️  DELAYED JOBS ALERT: Queue ${name} has ${counts.delayed} delayed jobs (threshold: ${DELAYED_THRESHOLD})`;
        alerts.push(message);
        logger.warn(message, {
          queue: name,
          delayed: counts.delayed,
          threshold: DELAYED_THRESHOLD,
        });
      }

      // Check for backlog (waiting + active + delayed)
      const backlog = counts.waiting + counts.active + counts.delayed;
      if (backlog > 500) {
        const message = `⚠️  BACKLOG ALERT: Queue ${name} has ${backlog} jobs in backlog`;
        alerts.push(message);
        logger.warn(message, {
          queue: name,
          waiting: counts.waiting,
          active: counts.active,
          delayed: counts.delayed,
          backlog,
        });
      }
    }

    if (alerts.length === 0) {
      logger.debug('✅ DLQ check passed - all queues healthy');
    } else {
      logger.warn(`🚨 DLQ check found ${alerts.length} issue(s)`, {
        alerts,
      });
    }
  } catch (error) {
    logger.error('Error checking DLQ thresholds', { error });
  }
};

/**
 * Get detailed info about failed jobs for investigation
 *
 * @param queueName - Queue to inspect
 * @param limit - Max number of failed jobs to return
 * @returns Array of failed jobs with error details
 */
export const getFailedJobs = async (
  queueName: QueueName,
  limit: number = 10
): Promise<Array<{ id: string; data: any; failedReason: string; attemptsMade: number; timestamp: number }>> => {
  try {
    const queue = getQueue(queueName);
    const failed = await queue.getFailed(0, limit - 1);

    return failed.map(job => ({
      id: job.id?.toString() || 'unknown',
      data: job.data,
      failedReason: job.failedReason || 'Unknown',
      attemptsMade: job.attemptsMade,
      timestamp: job.finishedOn || job.timestamp,
    }));
  } catch (error) {
    logger.error(`Error getting failed jobs from queue ${queueName}`, { error });
    return [];
  }
};
