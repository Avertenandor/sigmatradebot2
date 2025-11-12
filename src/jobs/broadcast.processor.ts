/**
 * Broadcast Processor
 * Worker for processing broadcast messages from queue
 * Features:
 * - RPS limiting (15 msg/s via Bull limiter)
 * - Exponential backoff on FloodWait/429 errors
 * - Progress tracking for real-time admin updates
 * - Retry logic for transient failures
 */

import { Job } from 'bull';
import { createLogger } from '../utils/logger.util';
import { notificationService } from '../services/notification.service';

const logger = createLogger('BroadcastProcessor');

/**
 * Broadcast job data types
 */
export interface BroadcastJobData {
  type: 'text' | 'photo' | 'voice' | 'audio';
  telegramId: number;
  adminId: number;
  broadcastId: string; // Unique ID for tracking this broadcast session

  // For text messages
  text?: string;

  // For media messages
  fileId?: string;
  caption?: string;

  // Progress tracking
  totalUsers: number;
  currentIndex: number;
}

/**
 * Process single broadcast message
 */
export const processBroadcastMessage = async (
  job: Job<BroadcastJobData>
): Promise<{ success: boolean; error?: string }> => {
  const { type, telegramId, fileId, caption, text, broadcastId, currentIndex, totalUsers } = job.data;

  try {
    // Update progress (every 10 messages or last message)
    if (currentIndex % 10 === 0 || currentIndex === totalUsers - 1) {
      job.progress({
        sent: currentIndex + 1,
        total: totalUsers,
        percent: Math.round(((currentIndex + 1) / totalUsers) * 100),
      });
    }

    let success = false;

    // Send message based on type
    switch (type) {
      case 'text':
        if (!text) throw new Error('Text is required for text broadcast');
        success = await notificationService.sendCustomMessage(telegramId, text, {
          parse_mode: 'Markdown',
        });
        break;

      case 'photo':
        if (!fileId) throw new Error('FileId is required for photo broadcast');
        success = await notificationService.sendPhotoMessage(telegramId, fileId, caption, {
          parse_mode: 'Markdown',
        });
        break;

      case 'voice':
        if (!fileId) throw new Error('FileId is required for voice broadcast');
        success = await notificationService.sendVoiceMessage(telegramId, fileId, caption);
        break;

      case 'audio':
        if (!fileId) throw new Error('FileId is required for audio broadcast');
        success = await notificationService.sendAudioMessage(telegramId, fileId, caption);
        break;

      default:
        throw new Error(`Unknown broadcast type: ${type}`);
    }

    if (!success) {
      logger.warn('Failed to send broadcast message', {
        broadcastId,
        telegramId,
        type,
        currentIndex,
      });
      return { success: false, error: 'Notification service returned false' };
    }

    logger.debug('Broadcast message sent', {
      broadcastId,
      telegramId,
      type,
      progress: `${currentIndex + 1}/${totalUsers}`,
    });

    return { success: true };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);

    // Check for FloodWait error (Telegram rate limiting)
    if (errorMessage.includes('FloodWait') || errorMessage.includes('429')) {
      // Parse wait time if available
      const match = errorMessage.match(/FloodWait.*?(\d+)/);
      const waitSeconds = match ? parseInt(match[1], 10) : 30;

      logger.warn('FloodWait error encountered, will retry with backoff', {
        broadcastId,
        telegramId,
        waitSeconds,
        currentIndex,
      });

      // Let Bull handle the retry with exponential backoff
      throw new Error(`FLOOD_WAIT:${waitSeconds}`);
    }

    // Check for user blocked bot
    if (errorMessage.includes('bot was blocked') || errorMessage.includes('user is deactivated')) {
      logger.debug('User blocked bot or deactivated', {
        broadcastId,
        telegramId,
        currentIndex,
      });
      // Don't retry for blocked users
      return { success: false, error: 'User blocked bot' };
    }

    // Other errors - log and let Bull retry
    logger.error('Error processing broadcast message', {
      broadcastId,
      telegramId,
      type,
      error: errorMessage,
      currentIndex,
    });

    return { success: false, error: errorMessage };
  }
};

/**
 * Get broadcast progress for a session
 * (Can be called by admin to check status)
 */
export const getBroadcastProgress = async (
  broadcastId: string,
  queue: any
): Promise<{
  total: number;
  completed: number;
  failed: number;
  active: number;
  waiting: number;
  percent: number;
}> => {
  try {
    const jobs = await queue.getJobs(['completed', 'failed', 'active', 'waiting']);

    // Filter jobs for this broadcast session
    const sessionJobs = jobs.filter((j: any) => j.data?.broadcastId === broadcastId);

    const total = sessionJobs.length;
    const completed = sessionJobs.filter((j: any) => j.finishedOn && !j.failedReason).length;
    const failed = sessionJobs.filter((j: any) => j.failedReason).length;
    const active = sessionJobs.filter((j: any) => j.processedOn && !j.finishedOn).length;
    const waiting = sessionJobs.filter((j: any) => !j.processedOn).length;

    const percent = total > 0 ? Math.round((completed / total) * 100) : 0;

    return {
      total,
      completed,
      failed,
      active,
      waiting,
      percent,
    };
  } catch (error) {
    logger.error('Error getting broadcast progress', {
      broadcastId,
      error: error instanceof Error ? error.message : String(error),
    });

    return {
      total: 0,
      completed: 0,
      failed: 0,
      active: 0,
      waiting: 0,
      percent: 0,
    };
  }
};

/**
 * Start broadcast processor
 * Registers the processor to handle broadcast jobs from queue
 */
export const startBroadcastProcessor = async (): Promise<void> => {
  try {
    const { getQueue, QueueName } = await import('./queue.config');
    const queue = getQueue(QueueName.BROADCAST);

    // Register processor for broadcast jobs
    queue.process('send-message', 3, processBroadcastMessage); // Process up to 3 jobs concurrently

    logger.info('✅ Broadcast processor started (concurrency: 3, RPS limit: 15/s)');
  } catch (error) {
    logger.error('❌ Failed to start broadcast processor:', error);
    throw error;
  }
};

/**
 * Stop broadcast processor
 */
export const stopBroadcastProcessor = async (): Promise<void> => {
  try {
    const { getQueue, QueueName } = await import('./queue.config');
    const queue = getQueue(QueueName.BROADCAST);

    await queue.pause();
    logger.info('✅ Broadcast processor stopped');
  } catch (error) {
    logger.error('❌ Failed to stop broadcast processor:', error);
    throw error;
  }
};

export default {
  processBroadcastMessage,
  getBroadcastProgress,
  startBroadcastProcessor,
  stopBroadcastProcessor,
};
