/**
 * Payment Processor Job
 * Processes pending referral earnings and sends payouts
 * Runs every minute to batch and send payments
 */

import { Job } from 'bull';
import { getQueue, QueueName } from './queue.config';
import { paymentService } from '../services/payment.service';
import { config } from '../config';
import { logger } from '../utils/logger.util';

export interface PaymentProcessorJobData {
  timestamp: number;
}

/**
 * Process pending payments
 */
export const processPayments = async (
  job: Job<PaymentProcessorJobData>
): Promise<void> => {
  try {
    logger.debug('💸 Running payment processor job...');

    const result = await paymentService.processPendingPayments();

    if (result.processed > 0) {
      logger.info(
        `✅ Payment processor: ${result.successful} successful, ${result.failed} failed out of ${result.processed} total`
      );
    } else {
      logger.debug('ℹ️ No pending payments to process');
    }
  } catch (error) {
    logger.error('❌ Payment processor job failed:', error);
    throw error; // Let Bull handle retries
  }
};

/**
 * Start payment processor
 */
export const startPaymentProcessor = async (): Promise<void> => {
  if (!config.jobs.paymentProcessor.enabled) {
    logger.warn('⚠️ Payment processor is disabled');
    return;
  }

  try {
    const queue = getQueue(QueueName.PAYMENT_PROCESSOR);

    // Add repeating job (every minute)
    await queue.add(
      'process-payments',
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
    queue.process('process-payments', processPayments);

    logger.info('✅ Payment processor started (running every 1 minute)');
  } catch (error) {
    logger.error('❌ Failed to start payment processor:', error);
    throw error;
  }
};

/**
 * Stop payment processor
 */
export const stopPaymentProcessor = async (): Promise<void> => {
  try {
    const queue = getQueue(QueueName.PAYMENT_PROCESSOR);
    await queue.removeRepeatable('process-payments', {
      every: 60000,
    });

    logger.info('✅ Payment processor stopped');
  } catch (error) {
    logger.error('❌ Error stopping payment processor:', error);
  }
};

/**
 * Manually trigger payment processing (for admin panel)
 */
export const triggerPaymentProcessing = async (): Promise<{
  processed: number;
  successful: number;
  failed: number;
}> => {
  try {
    logger.info('🔄 Manual payment processing triggered');

    const result = await paymentService.processPendingPayments();

    logger.info(
      `✅ Manual payment processing complete: ${result.successful} successful, ${result.failed} failed`
    );

    return result;
  } catch (error) {
    logger.error('❌ Manual payment processing failed:', error);
    throw error;
  }
};
