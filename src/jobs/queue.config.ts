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
  const rewardCalculatorQueue = new Queue(QueueName.REWARD_CALCULATOR, queueOptions);
  const backupQueue = new Queue(QueueName.BACKUP, queueOptions);
  const logCleanupQueue = new Queue(QueueName.LOG_CLEANUP, queueOptions);

  queues.set(QueueName.BLOCKCHAIN_MONITOR, blockchainMonitorQueue);
  queues.set(QueueName.PAYMENT_PROCESSOR, paymentProcessorQueue);
  queues.set(QueueName.PAYMENT_RETRY, paymentRetryQueue);
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
 * Close all queues
 */
export const closeQueues = async (): Promise<void> => {
  logger.info('🔄 Closing all queues...');

  const promises: Promise<void>[] = [];

  for (const [name, queue] of queues) {
    promises.push(
      queue.close().then(() => {
        logger.debug(`✅ Queue ${name} closed`);
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
