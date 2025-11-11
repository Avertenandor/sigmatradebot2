/**
 * Payment Retry Job
 * Processes pending payment retries with exponential backoff
 * Runs every minute to check for retries that are ready to be processed
 *
 * Related Bug: FIX #4 - Payment Retry with Exponential Backoff
 */

import { Job } from 'bull';
import { getQueue, QueueName } from './queue.config';
import { paymentRetryService } from '../services/payment-retry.service';
import { config } from '../config';
import { logger } from '../utils/logger.util';

export interface PaymentRetryJobData {
  timestamp: number;
}

/**
 * Process pending payment retries
 */
export const processPaymentRetries = async (
  job: Job<PaymentRetryJobData>
): Promise<void> => {
  try {
    logger.debug('🔄 Running payment retry processor job...');

    const result = await paymentRetryService.processPendingRetries();

    if (result.processed > 0) {
      logger.info(
        `✅ Payment retry processor: ${result.successful} successful, ${result.failed} failed, ${result.movedToDLQ} moved to DLQ out of ${result.processed} total`
      );
    } else {
      logger.debug('ℹ️ No pending payment retries to process');
    }
  } catch (error) {
    logger.error('❌ Payment retry processor job failed:', error);
    throw error; // Let Bull handle retries
  }
};

/**
 * Start payment retry processor
 */
export const startPaymentRetryProcessor = async (): Promise<void> => {
  if (!config.jobs.paymentRetryProcessor?.enabled) {
    logger.warn('⚠️ Payment retry processor is disabled');
    return;
  }

  try {
    const queue = getQueue(QueueName.PAYMENT_RETRY);

    // Add repeating job (every minute)
    await queue.add(
      'process-payment-retries',
      { timestamp: Date.now() },
      {
        repeat: {
          every: 60000, // 1 minute
        },
        removeOnComplete: true,
        removeOnFail: false,
      }
    );

    // Process jobs
    queue.process('process-payment-retries', processPaymentRetries);

    logger.info('✅ Payment retry processor started (running every 1 minute)');
  } catch (error) {
    logger.error('❌ Failed to start payment retry processor:', error);
    throw error;
  }
};

/**
 * Stop payment retry processor
 */
export const stopPaymentRetryProcessor = async (): Promise<void> => {
  try {
    const queue = getQueue(QueueName.PAYMENT_RETRY);
    await queue.removeRepeatable('process-payment-retries', {
      every: 60000,
    });

    logger.info('✅ Payment retry processor stopped');
  } catch (error) {
    logger.error('❌ Error stopping payment retry processor:', error);
  }
};

/**
 * Manually trigger payment retry processing (for admin panel)
 */
export const triggerPaymentRetryProcessing = async (): Promise<{
  processed: number;
  successful: number;
  failed: number;
  movedToDLQ: number;
}> => {
  try {
    logger.info('🔄 Manual payment retry processing triggered');

    const result = await paymentRetryService.processPendingRetries();

    logger.info(
      `✅ Manual payment retry processing complete: ${result.successful} successful, ${result.failed} failed, ${result.movedToDLQ} moved to DLQ`
    );

    return result;
  } catch (error) {
    logger.error('❌ Manual payment retry processing failed:', error);
    throw error;
  }
};

/**
 * Get DLQ items for admin review
 */
export const getDLQItems = async () => {
  try {
    const dlqItems = await paymentRetryService.getDLQItems();
    return dlqItems;
  } catch (error) {
    logger.error('❌ Failed to get DLQ items:', error);
    throw error;
  }
};

/**
 * Manually retry a DLQ item (for admin)
 */
export const retryDLQItem = async (retryId: number) => {
  try {
    logger.info(`🔧 Admin manually retrying DLQ item ${retryId}`);
    const result = await paymentRetryService.retryDLQItem(retryId);

    if (result.success) {
      logger.info(`✅ DLQ item ${retryId} successfully retried, txHash: ${result.txHash}`);
    } else {
      logger.error(`❌ DLQ item ${retryId} retry failed: ${result.error}`);
    }

    return result;
  } catch (error) {
    logger.error(`❌ Failed to retry DLQ item ${retryId}:`, error);
    throw error;
  }
};
