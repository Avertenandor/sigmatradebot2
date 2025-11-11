/**
 * Payment Retry Service
 *
 * Implements exponential backoff retry mechanism for failed payments
 * Prevents user fund loss from transient failures (network errors, low gas, etc.)
 *
 * Related Bug: FIX #4 - Payment Retry with Exponential Backoff
 *
 * Features:
 * - Exponential backoff: 1min, 2min, 4min, 8min, 16min
 * - Dead Letter Queue (DLQ) for permanent failures
 * - Admin interface to manually retry DLQ items
 * - Automatic retry processing via background job
 */

import { LessThanOrEqual, In } from 'typeorm';
import { AppDataSource } from '../database/data-source';
import { PaymentRetry } from '../database/entities/PaymentRetry.entity';
import { ReferralEarning } from '../database/entities/ReferralEarning.entity';
import { DepositReward } from '../database/entities/DepositReward.entity';
import { User } from '../database/entities/User.entity';
import { Transaction } from '../database/entities/Transaction.entity';
import { TransactionStatus, TransactionType } from '../utils/constants';
import { blockchainService } from './blockchain.service';
import { notificationService } from './notification.service';
import { logger } from '../utils/logger.util';
import { logFinancialOperation } from '../utils/audit-logger.util';
import { withTransaction, TRANSACTION_PRESETS } from '../database/transaction.util';

export class PaymentRetryService {
  private static instance: PaymentRetryService;

  // Exponential backoff: 1min, 2min, 4min, 8min, 16min
  private readonly BASE_RETRY_DELAY_MS = 60000; // 1 minute
  private readonly DEFAULT_MAX_RETRIES = 5;

  private constructor() {}

  public static getInstance(): PaymentRetryService {
    if (!PaymentRetryService.instance) {
      PaymentRetryService.instance = new PaymentRetryService();
    }
    return PaymentRetryService.instance;
  }

  /**
   * Create a retry record for failed payment
   * Called when a payment fails in payment.service.ts
   */
  public async createRetryRecord(params: {
    userId: number;
    amount: number;
    paymentType: 'REFERRAL_EARNING' | 'DEPOSIT_REWARD';
    earningIds: number[];
    error: string;
    errorStack?: string;
  }): Promise<PaymentRetry> {
    const { userId, amount, paymentType, earningIds, error, errorStack } = params;

    logger.info(`📝 Creating retry record for user ${userId}, amount: ${amount} USDT`, {
      paymentType,
      earningIds,
    });

    const retryRepo = AppDataSource.getRepository(PaymentRetry);

    // Check if retry record already exists for these earning IDs
    const existing = await retryRepo.findOne({
      where: {
        user_id: userId,
        payment_type: paymentType,
        resolved: false,
      },
    });

    let retry: PaymentRetry;

    if (existing) {
      // Update existing record
      existing.amount = amount.toString();
      existing.earning_ids = earningIds;
      existing.last_error = error;
      existing.error_stack = errorStack || null;
      retry = await retryRepo.save(existing);

      logger.info(`Updated existing retry record ${retry.id}`);
    } else {
      // Create new retry record
      const nextRetryAt = this.calculateNextRetryTime(0);

      retry = await retryRepo.save({
        user_id: userId,
        amount: amount.toString(),
        payment_type: paymentType,
        earning_ids: earningIds,
        attempt_count: 0,
        max_retries: this.DEFAULT_MAX_RETRIES,
        last_attempt_at: null,
        next_retry_at: nextRetryAt,
        last_error: error,
        error_stack: errorStack || null,
        in_dlq: false,
        resolved: false,
        tx_hash: null,
      });

      logger.info(`Created new retry record ${retry.id}, next retry at: ${nextRetryAt.toISOString()}`);
    }

    // Audit log
    logFinancialOperation({
      category: 'payment',
      userId,
      action: 'payment_retry_created',
      amount,
      success: false,
      error,
      details: {
        retryId: retry.id,
        paymentType,
        earningIds,
        nextRetryAt: retry.next_retry_at,
      },
    });

    return retry;
  }

  /**
   * Process all pending retries
   * Called by background job (e.g., every minute)
   */
  public async processPendingRetries(): Promise<{
    processed: number;
    successful: number;
    failed: number;
    movedToDLQ: number;
  }> {
    const retryRepo = AppDataSource.getRepository(PaymentRetry);

    // Get all pending retries where next_retry_at <= NOW
    const now = new Date();
    const pendingRetries = await retryRepo.find({
      where: {
        resolved: false,
        in_dlq: false,
        next_retry_at: LessThanOrEqual(now),
      },
      relations: ['user'],
      order: { next_retry_at: 'ASC' },
    });

    if (pendingRetries.length === 0) {
      return { processed: 0, successful: 0, failed: 0, movedToDLQ: 0 };
    }

    logger.info(`🔄 Processing ${pendingRetries.length} pending payment retries...`);

    let processed = 0;
    let successful = 0;
    let failed = 0;
    let movedToDLQ = 0;

    for (const retry of pendingRetries) {
      try {
        const result = await this.processRetry(retry);
        processed++;

        if (result.success) {
          successful++;
        } else if (result.movedToDLQ) {
          movedToDLQ++;
        } else {
          failed++;
        }
      } catch (error) {
        logger.error(`❌ Error processing retry ${retry.id}:`, error);
        failed++;
      }
    }

    logger.info(
      `✅ Retry processing complete: ${successful} successful, ${failed} failed, ${movedToDLQ} moved to DLQ out of ${processed} total`
    );

    return { processed, successful, failed, movedToDLQ };
  }

  /**
   * Process a single retry attempt
   */
  private async processRetry(retry: PaymentRetry): Promise<{
    success: boolean;
    movedToDLQ: boolean;
  }> {
    const retryRepo = AppDataSource.getRepository(PaymentRetry);

    logger.info(`🔄 Processing retry ${retry.id} for user ${retry.user_id}, attempt ${retry.attempt_count + 1}/${retry.max_retries}`);

    // Increment attempt count
    retry.attempt_count++;
    retry.last_attempt_at = new Date();

    try {
      // Validate user has wallet address
      if (!retry.user.wallet_address) {
        throw new Error(`User ${retry.user.telegram_id} has no wallet address`);
      }

      const amount = parseFloat(retry.amount);

      // Send payment via blockchain
      logger.info(`💸 Attempting payment: ${amount} USDT to ${retry.user.wallet_address}`);

      const paymentResult = await blockchainService.sendPayment(
        retry.user.wallet_address,
        amount
      );

      if (!paymentResult.success) {
        throw new Error(paymentResult.error || 'Unknown payment error');
      }

      // Payment succeeded!
      logger.info(`✅ Payment retry ${retry.id} succeeded! TxHash: ${paymentResult.txHash}`);

      // Use transaction to ensure atomicity
      await withTransaction(async (manager) => {
        // Mark retry as resolved
        retry.resolved = true;
        retry.tx_hash = paymentResult.txHash!;
        await manager.save(PaymentRetry, retry);

        // Mark earnings/rewards as paid
        if (retry.payment_type === 'REFERRAL_EARNING') {
          const earningRepo = manager.getRepository(ReferralEarning);
          await earningRepo.update(
            { id: In(retry.earning_ids) },
            { paid: true, tx_hash: paymentResult.txHash! }
          );
        } else if (retry.payment_type === 'DEPOSIT_REWARD') {
          const rewardRepo = manager.getRepository(DepositReward);
          await rewardRepo.update(
            { id: In(retry.earning_ids) },
            { paid: true, paid_at: new Date(), tx_hash: paymentResult.txHash! }
          );
        }

        // Create transaction record
        const transactionRepo = manager.getRepository(Transaction);
        await transactionRepo.save({
          user_id: retry.user_id,
          tx_hash: paymentResult.txHash!,
          type: retry.payment_type === 'REFERRAL_EARNING'
            ? TransactionType.REFERRAL_REWARD
            : TransactionType.DEPOSIT_REWARD,
          amount: retry.amount,
          from_address: '',
          to_address: retry.user.wallet_address,
          status: TransactionStatus.CONFIRMED,
        });
      }, TRANSACTION_PRESETS.FINANCIAL);

      // Audit log
      logFinancialOperation({
        category: 'payment',
        userId: retry.user_id,
        action: 'payment_retry_succeeded',
        amount,
        success: true,
        details: {
          retryId: retry.id,
          attemptCount: retry.attempt_count,
          txHash: paymentResult.txHash,
          paymentType: retry.payment_type,
          earningIds: retry.earning_ids,
        },
      });

      // Notify user
      await notificationService.notifyPaymentSent(
        retry.user.telegram_id,
        amount,
        paymentResult.txHash!
      );

      return { success: true, movedToDLQ: false };

    } catch (error: any) {
      const errorMessage = error.message || 'Unknown error';
      logger.error(`❌ Retry ${retry.id} attempt ${retry.attempt_count} failed: ${errorMessage}`);

      // Update retry record with error
      retry.last_error = errorMessage;
      retry.error_stack = error.stack || null;

      // Check if max retries exceeded
      if (retry.attempt_count >= retry.max_retries) {
        // Move to Dead Letter Queue
        retry.in_dlq = true;
        retry.next_retry_at = null;

        await retryRepo.save(retry);

        logger.warn(`⚠️ Retry ${retry.id} moved to DLQ after ${retry.attempt_count} attempts`);

        // Audit log
        logFinancialOperation({
          category: 'payment',
          userId: retry.user_id,
          action: 'payment_retry_moved_to_dlq',
          amount: parseFloat(retry.amount),
          success: false,
          error: errorMessage,
          details: {
            retryId: retry.id,
            attemptCount: retry.attempt_count,
            paymentType: retry.payment_type,
            earningIds: retry.earning_ids,
          },
        });

        // Alert admins about DLQ item
        await notificationService.alertPaymentMovedToDLQ(
          retry.user_id,
          parseFloat(retry.amount),
          retry.attempt_count,
          errorMessage
        ).catch((err) => {
          logger.error('Failed to send DLQ alert', { error: err });
        });

        return { success: false, movedToDLQ: true };
      } else {
        // Schedule next retry with exponential backoff
        retry.next_retry_at = this.calculateNextRetryTime(retry.attempt_count);
        await retryRepo.save(retry);

        logger.info(`⏰ Retry ${retry.id} scheduled for next attempt at: ${retry.next_retry_at.toISOString()}`);

        // Audit log
        logFinancialOperation({
          category: 'payment',
          userId: retry.user_id,
          action: 'payment_retry_failed',
          amount: parseFloat(retry.amount),
          success: false,
          error: errorMessage,
          details: {
            retryId: retry.id,
            attemptCount: retry.attempt_count,
            nextRetryAt: retry.next_retry_at,
            paymentType: retry.payment_type,
            earningIds: retry.earning_ids,
          },
        });

        return { success: false, movedToDLQ: false };
      }
    }
  }

  /**
   * Calculate next retry time using exponential backoff
   * Formula: delay = BASE_DELAY * 2^attempt_count
   * Example: 1min, 2min, 4min, 8min, 16min
   */
  private calculateNextRetryTime(attemptCount: number): Date {
    const delayMs = this.BASE_RETRY_DELAY_MS * Math.pow(2, attemptCount);
    const nextRetry = new Date(Date.now() + delayMs);
    return nextRetry;
  }

  /**
   * Get all DLQ items (for admin review)
   */
  public async getDLQItems(): Promise<PaymentRetry[]> {
    const retryRepo = AppDataSource.getRepository(PaymentRetry);

    const dlqItems = await retryRepo.find({
      where: {
        in_dlq: true,
        resolved: false,
      },
      relations: ['user'],
      order: { created_at: 'DESC' },
    });

    return dlqItems;
  }

  /**
   * Manually retry a DLQ item
   * Called by admin to manually retry failed payments
   */
  public async retryDLQItem(retryId: number): Promise<{
    success: boolean;
    txHash?: string;
    error?: string;
  }> {
    const retryRepo = AppDataSource.getRepository(PaymentRetry);

    const retry = await retryRepo.findOne({
      where: { id: retryId },
      relations: ['user'],
    });

    if (!retry) {
      return { success: false, error: 'Retry record not found' };
    }

    if (retry.resolved) {
      return { success: false, error: 'Payment already resolved' };
    }

    logger.info(`🔧 Manual retry of DLQ item ${retryId} by admin`);

    // Remove from DLQ and reset attempt count
    retry.in_dlq = false;
    retry.attempt_count = 0;
    retry.next_retry_at = new Date(); // Retry immediately
    await retryRepo.save(retry);

    // Process the retry
    const result = await this.processRetry(retry);

    if (result.success) {
      return { success: true, txHash: retry.tx_hash || undefined };
    } else {
      return { success: false, error: retry.last_error || 'Retry failed' };
    }
  }

  /**
   * Get retry statistics
   */
  public async getRetryStats(): Promise<{
    pendingRetries: number;
    dlqItems: number;
    resolvedRetries: number;
    totalAmount: number;
    dlqAmount: number;
  }> {
    const retryRepo = AppDataSource.getRepository(PaymentRetry);

    const pending = await retryRepo.count({
      where: { resolved: false, in_dlq: false },
    });

    const dlq = await retryRepo.count({
      where: { in_dlq: true, resolved: false },
    });

    const resolved = await retryRepo.count({
      where: { resolved: true },
    });

    const allUnresolved = await retryRepo.find({
      where: { resolved: false },
    });

    const dlqItems = await retryRepo.find({
      where: { in_dlq: true, resolved: false },
    });

    const totalAmount = allUnresolved.reduce(
      (sum, r) => sum + parseFloat(r.amount),
      0
    );

    const dlqAmount = dlqItems.reduce(
      (sum, r) => sum + parseFloat(r.amount),
      0
    );

    return {
      pendingRetries: pending,
      dlqItems: dlq,
      resolvedRetries: resolved,
      totalAmount,
      dlqAmount,
    };
  }

  /**
   * Get pending retries for a specific user
   */
  public async getUserRetries(userId: number): Promise<PaymentRetry[]> {
    const retryRepo = AppDataSource.getRepository(PaymentRetry);

    const retries = await retryRepo.find({
      where: { user_id: userId, resolved: false },
      order: { created_at: 'DESC' },
    });

    return retries;
  }
}

// Export singleton instance
export const paymentRetryService = PaymentRetryService.getInstance();
