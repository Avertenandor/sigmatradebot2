/**
 * Blockchain Monitor Job
 * Continuously monitors blockchain for pending deposits
 * Runs every 10 seconds to check for confirmations
 */

import { Job } from 'bull';
import { getQueue, QueueName } from './queue.config';
import { blockchainService } from '../services/blockchain.service';
import { config } from '../config';
import { logger } from '../utils/logger.util';

export interface BlockchainMonitorJobData {
  timestamp: number;
}

/**
 * Process blockchain monitoring
 */
export const processBlockchainMonitor = async (
  job: Job<BlockchainMonitorJobData>
): Promise<void> => {
  try {
    logger.debug('🔍 Running blockchain monitor job...');

    // Check pending deposits for confirmations
    await blockchainService.checkPendingDeposits();

    logger.debug('✅ Blockchain monitor job completed');
  } catch (error) {
    logger.error('❌ Blockchain monitor job failed:', error);
    throw error; // Let Bull handle retries
  }
};

/**
 * Start blockchain monitoring
 * This starts the WebSocket listener and repeating job
 */
export const startBlockchainMonitor = async (): Promise<void> => {
  if (!config.jobs.blockchainMonitor.enabled) {
    logger.warn('⚠️ Blockchain monitor is disabled');
    return;
  }

  try {
    // Start WebSocket monitoring for real-time events
    await blockchainService.startMonitoring();

    // Schedule repeating job to check confirmations
    const queue = getQueue(QueueName.BLOCKCHAIN_MONITOR);

    // Add repeating job (every 10 seconds)
    await queue.add(
      'check-confirmations',
      { timestamp: Date.now() },
      {
        repeat: {
          every: 10000, // 10 seconds
        },
        removeOnComplete: true,
        removeOnFail: false,
      }
    );

    // Process jobs
    queue.process('check-confirmations', processBlockchainMonitor);

    logger.info('✅ Blockchain monitor started (WebSocket + polling every 10s)');
  } catch (error) {
    logger.error('❌ Failed to start blockchain monitor:', error);
    throw error;
  }
};

/**
 * Stop blockchain monitoring
 */
export const stopBlockchainMonitor = async (): Promise<void> => {
  try {
    await blockchainService.stopMonitoring();

    const queue = getQueue(QueueName.BLOCKCHAIN_MONITOR);
    await queue.removeRepeatable('check-confirmations', {
      every: 10000,
    });

    logger.info('✅ Blockchain monitor stopped');
  } catch (error) {
    logger.error('❌ Error stopping blockchain monitor:', error);
  }
};
