/**
 * Payment Service
 * Handles automated payouts for referral rewards
 * - Processes pending referral earnings
 * - Batches payments by user (gas optimization)
 * - Creates transaction records
 * - Handles payment failures and retries
 */

import { In } from 'typeorm';
import { AppDataSource } from '../database/data-source';
import { ReferralEarning } from '../database/entities/ReferralEarning.entity';
import { DepositReward } from '../database/entities/DepositReward.entity';
import { Transaction } from '../database/entities/Transaction.entity';
import { User } from '../database/entities/User.entity';
import { Referral } from '../database/entities/Referral.entity';
import { TransactionStatus, TransactionType } from '../utils/constants';
import { blockchainService } from './blockchain.service';
import { notificationService } from './notification.service';
import { paymentRetryService } from './payment-retry.service';
import { logger } from '../utils/logger.util';

export class PaymentService {
  private static instance: PaymentService;

  private constructor() {}

  public static getInstance(): PaymentService {
    if (!PaymentService.instance) {
      PaymentService.instance = new PaymentService();
    }
    return PaymentService.instance;
  }

  /**
   * Process pending referral earnings and deposit rewards
   * Called by payment processor job
   */
  public async processPendingPayments(): Promise<{
    processed: number;
    successful: number;
    failed: number;
  }> {
    try {
      const earningRepo = AppDataSource.getRepository(ReferralEarning);
      const rewardRepo = AppDataSource.getRepository(DepositReward);
      const userRepo = AppDataSource.getRepository(User);

      // Get all pending referral earnings
      const pendingEarnings = await earningRepo.find({
        where: { paid: false },
        relations: ['referral', 'referral.referrer'],
        order: { created_at: 'ASC' },
      });

      // Get all pending deposit rewards
      const pendingRewards = await rewardRepo.find({
        where: { paid: false },
        order: { calculated_at: 'ASC' },
      });

      if (pendingEarnings.length === 0 && pendingRewards.length === 0) {
        return { processed: 0, successful: 0, failed: 0 };
      }

      logger.info(
        `💸 Processing ${pendingEarnings.length} referral earnings + ${pendingRewards.length} deposit rewards...`
      );

      let processed = 0;
      let successful = 0;
      let failed = 0;

      // Process referral earnings
      if (pendingEarnings.length > 0) {
        // Group earnings by user (referrer)
        const earningsByUser = new Map<number, ReferralEarning[]>();

        for (const earning of pendingEarnings) {
          const referrerId = earning.referral.referrer_id;
          if (!earningsByUser.has(referrerId)) {
            earningsByUser.set(referrerId, []);
          }
          earningsByUser.get(referrerId)!.push(earning);
        }

        // Process payments for each user
        for (const [referrerId, earnings] of earningsByUser) {
          try {
            const result = await this.processUserPayments(referrerId, earnings);
            processed += result.processed;
            successful += result.successful;
            failed += result.failed;
          } catch (error) {
            logger.error(`❌ Error processing referral payments for user ${referrerId}:`, error);
            failed += earnings.length;
          }
        }
      }

      // Process deposit rewards
      if (pendingRewards.length > 0) {
        // Group rewards by user
        const rewardsByUser = new Map<number, DepositReward[]>();

        for (const reward of pendingRewards) {
          const userId = reward.user_id;
          if (!rewardsByUser.has(userId)) {
            rewardsByUser.set(userId, []);
          }
          rewardsByUser.get(userId)!.push(reward);
        }

        // Process reward payments for each user
        for (const [userId, rewards] of rewardsByUser) {
          try {
            const result = await this.processUserRewardPayments(userId, rewards);
            processed += result.processed;
            successful += result.successful;
            failed += result.failed;
          } catch (error) {
            logger.error(`❌ Error processing reward payments for user ${userId}:`, error);
            failed += rewards.length;
          }
        }
      }

      logger.info(
        `✅ Payment processing complete: ${successful} successful, ${failed} failed out of ${processed} total`
      );

      return { processed, successful, failed };
    } catch (error) {
      logger.error('❌ Error processing pending payments:', error);
      throw error;
    }
  }

  /**
   * Process all pending payments for a single user
   */
  private async processUserPayments(
    referrerId: number,
    earnings: ReferralEarning[]
  ): Promise<{
    processed: number;
    successful: number;
    failed: number;
  }> {
    const userRepo = AppDataSource.getRepository(User);
    const earningRepo = AppDataSource.getRepository(ReferralEarning);
    const transactionRepo = AppDataSource.getRepository(Transaction);

    try {
      // Get user
      const user = await userRepo.findOne({ where: { id: referrerId } });

      if (!user) {
        logger.error(`❌ User not found: ${referrerId}`);
        return { processed: earnings.length, successful: 0, failed: earnings.length };
      }

      if (!user.wallet_address) {
        logger.error(`❌ User ${user.telegram_id} has no wallet address`);
        return { processed: earnings.length, successful: 0, failed: earnings.length };
      }

      // Calculate total amount to pay
      const totalAmount = earnings.reduce(
        (sum, earning) => sum + parseFloat(earning.amount),
        0
      );

      logger.info(
        `💰 Paying ${totalAmount} USDT to user ${user.telegram_id} (${earnings.length} earnings)`
      );

      // Send payment via blockchain
      const paymentResult = await blockchainService.sendPayment(
        user.wallet_address,
        totalAmount
      );

      if (!paymentResult.success) {
        logger.error(
          `❌ Payment failed for user ${user.telegram_id}: ${paymentResult.error}`
        );

        // Create retry record for automatic retry with exponential backoff
        const earningIds = earnings.map(e => e.id);
        await paymentRetryService.createRetryRecord({
          userId: user.id,
          amount: totalAmount,
          paymentType: 'REFERRAL_EARNING',
          earningIds,
          error: paymentResult.error || 'Unknown error',
        });

        logger.info(
          `📝 Created payment retry record for user ${user.telegram_id}, amount: ${totalAmount} USDT`
        );

        return { processed: earnings.length, successful: 0, failed: earnings.length };
      }

      // Mark earnings as paid
      for (const earning of earnings) {
        earning.paid = true;
        earning.tx_hash = paymentResult.txHash;
        await earningRepo.save(earning);
      }

      // Create transaction record
      await transactionRepo.save({
        user_id: user.id,
        tx_hash: paymentResult.txHash!,
        type: TransactionType.REFERRAL_REWARD,
        amount: totalAmount.toString(),
        from_address: '', // Will be filled by blockchain service
        to_address: user.wallet_address,
        status: TransactionStatus.CONFIRMED,
      });

      logger.info(
        `✅ Payment successful: ${totalAmount} USDT to user ${user.telegram_id} (tx: ${paymentResult.txHash})`
      );

      // Send notification to user about payment
      await notificationService.notifyPaymentSent(
        user.telegram_id,
        totalAmount,
        paymentResult.txHash!
      );

      return {
        processed: earnings.length,
        successful: earnings.length,
        failed: 0,
      };
    } catch (error) {
      logger.error(`❌ Error processing user ${referrerId} payments:`, error);
      return {
        processed: earnings.length,
        successful: 0,
        failed: earnings.length,
      };
    }
  }

  /**
   * Process all pending deposit reward payments for a single user
   */
  private async processUserRewardPayments(
    userId: number,
    rewards: DepositReward[]
  ): Promise<{
    processed: number;
    successful: number;
    failed: number;
  }> {
    const userRepo = AppDataSource.getRepository(User);
    const rewardRepo = AppDataSource.getRepository(DepositReward);
    const transactionRepo = AppDataSource.getRepository(Transaction);

    try {
      // Get user
      const user = await userRepo.findOne({ where: { id: userId } });

      if (!user) {
        logger.error(`❌ User not found: ${userId}`);
        return { processed: rewards.length, successful: 0, failed: rewards.length };
      }

      if (!user.wallet_address) {
        logger.error(`❌ User ${user.telegram_id} has no wallet address`);
        return { processed: rewards.length, successful: 0, failed: rewards.length };
      }

      // Calculate total amount to pay
      const totalAmount = rewards.reduce(
        (sum, reward) => sum + parseFloat(reward.reward_amount),
        0
      );

      logger.info(
        `💰 Paying ${totalAmount} USDT deposit rewards to user ${user.telegram_id} (${rewards.length} rewards)`
      );

      // Send payment via blockchain
      const paymentResult = await blockchainService.sendPayment(
        user.wallet_address,
        totalAmount
      );

      if (!paymentResult.success) {
        logger.error(
          `❌ Deposit reward payment failed for user ${user.telegram_id}: ${paymentResult.error}`
        );

        // Create retry record for automatic retry with exponential backoff
        const rewardIds = rewards.map(r => r.id);
        await paymentRetryService.createRetryRecord({
          userId: user.id,
          amount: totalAmount,
          paymentType: 'DEPOSIT_REWARD',
          earningIds: rewardIds,
          error: paymentResult.error || 'Unknown error',
        });

        logger.info(
          `📝 Created payment retry record for user ${user.telegram_id}, amount: ${totalAmount} USDT`
        );

        return { processed: rewards.length, successful: 0, failed: rewards.length };
      }

      // Mark rewards as paid
      for (const reward of rewards) {
        reward.paid = true;
        reward.paid_at = new Date();
        reward.tx_hash = paymentResult.txHash;
        await rewardRepo.save(reward);
      }

      // Create transaction record
      await transactionRepo.save({
        user_id: user.id,
        tx_hash: paymentResult.txHash!,
        type: TransactionType.DEPOSIT_REWARD,
        amount: totalAmount.toString(),
        from_address: '', // Will be filled by blockchain service
        to_address: user.wallet_address,
        status: TransactionStatus.CONFIRMED,
      });

      logger.info(
        `✅ Deposit reward payment successful: ${totalAmount} USDT to user ${user.telegram_id} (tx: ${paymentResult.txHash})`
      );

      // Send notification to user about deposit reward payment
      await notificationService.notifyDepositRewardPayment(
        user.telegram_id,
        totalAmount,
        paymentResult.txHash!
      );

      return {
        processed: rewards.length,
        successful: rewards.length,
        failed: 0,
      };
    } catch (error) {
      logger.error(`❌ Error processing user ${userId} reward payments:`, error);
      return {
        processed: rewards.length,
        successful: 0,
        failed: rewards.length,
      };
    }
  }

  /**
   * Create referral earnings when a deposit is confirmed
   * This is called from deposit.service.ts after confirmation
   */
  public async createReferralEarnings(
    userId: number,
    depositAmount: number,
    sourceTransactionId: number
  ): Promise<{
    created: number;
    totalAmount: number;
  }> {
    try {
      const referralRepo = AppDataSource.getRepository(Referral);
      const earningRepo = AppDataSource.getRepository(ReferralEarning);

      // Get all referrals for this user (up to 3 levels)
      const referrals = await referralRepo.find({
        where: { referral_id: userId },
        relations: ['referrer'],
        order: { level: 'ASC' },
      });

      if (referrals.length === 0) {
        logger.info(`ℹ️ User ${userId} has no referrers`);
        return { created: 0, totalAmount: 0 };
      }

      const rewards = this.calculateRewards(depositAmount);
      let created = 0;
      let totalAmount = 0;

      for (const referral of referrals) {
        const reward = rewards.find((r) => r.level === referral.level);

        if (!reward || reward.reward <= 0) {
          continue;
        }

        // Create earning record
        await earningRepo.save({
          referral_id: referral.id,
          amount: reward.reward.toString(),
          source_transaction_id: sourceTransactionId,
          paid: false,
        });

        created++;
        totalAmount += reward.reward;

        logger.info(
          `💵 Created earning: ${reward.reward} USDT for user ${referral.referrer.telegram_id} (level ${referral.level})`
        );

        // Notify referrer about earning
        await notificationService.notifyReferralEarning(
          referral.referrer.telegram_id,
          reward.reward,
          referral.level
        );
      }

      logger.info(
        `✅ Created ${created} referral earnings totaling ${totalAmount} USDT`
      );

      return { created, totalAmount };
    } catch (error) {
      logger.error('❌ Error creating referral earnings:', error);
      throw error;
    }
  }

  /**
   * Calculate referral rewards based on deposit amount
   */
  private calculateRewards(
    amount: number
  ): Array<{ level: number; rate: number; reward: number }> {
    const REFERRAL_RATES = {
      1: 0.03, // 3%
      2: 0.02, // 2%
      3: 0.05, // 5%
    };

    return [
      {
        level: 1,
        rate: REFERRAL_RATES[1],
        reward: amount * REFERRAL_RATES[1],
      },
      {
        level: 2,
        rate: REFERRAL_RATES[2],
        reward: amount * REFERRAL_RATES[2],
      },
      {
        level: 3,
        rate: REFERRAL_RATES[3],
        reward: amount * REFERRAL_RATES[3],
      },
    ];
  }

  /**
   * Get payment statistics
   */
  public async getPaymentStats(): Promise<{
    pendingEarnings: number;
    pendingAmount: number;
    paidEarnings: number;
    paidAmount: number;
  }> {
    try {
      const earningRepo = AppDataSource.getRepository(ReferralEarning);

      const pending = await earningRepo.find({
        where: { paid: false },
      });

      const paid = await earningRepo.find({
        where: { paid: true },
      });

      const pendingAmount = pending.reduce(
        (sum, e) => sum + parseFloat(e.amount),
        0
      );

      const paidAmount = paid.reduce((sum, e) => sum + parseFloat(e.amount), 0);

      return {
        pendingEarnings: pending.length,
        pendingAmount,
        paidEarnings: paid.length,
        paidAmount,
      };
    } catch (error) {
      logger.error('❌ Error getting payment stats:', error);
      throw error;
    }
  }

  /**
   * Get pending earnings for a specific user
   */
  public async getUserPendingEarnings(userId: number): Promise<{
    count: number;
    totalAmount: number;
    earnings: ReferralEarning[];
  }> {
    try {
      const earningRepo = AppDataSource.getRepository(ReferralEarning);
      const referralRepo = AppDataSource.getRepository(Referral);

      // Get user's referrals
      const referrals = await referralRepo.find({
        where: { referrer_id: userId },
      });

      if (referrals.length === 0) {
        return { count: 0, totalAmount: 0, earnings: [] };
      }

      const referralIds = referrals.map((r) => r.id);

      // Get pending earnings
      const earnings = await earningRepo.find({
        where: {
          referral_id: In(referralIds),
          paid: false,
        },
        relations: ['referral', 'referral.referred'],
        order: { created_at: 'DESC' },
      });

      const totalAmount = earnings.reduce(
        (sum, e) => sum + parseFloat(e.amount),
        0
      );

      return {
        count: earnings.length,
        totalAmount,
        earnings,
      };
    } catch (error) {
      logger.error(`❌ Error getting pending earnings for user ${userId}:`, error);
      throw error;
    }
  }

  /**
   * Get paid earnings for a specific user
   */
  public async getUserPaidEarnings(userId: number): Promise<{
    count: number;
    totalAmount: number;
    earnings: ReferralEarning[];
  }> {
    try {
      const earningRepo = AppDataSource.getRepository(ReferralEarning);
      const referralRepo = AppDataSource.getRepository(Referral);

      // Get user's referrals
      const referrals = await referralRepo.find({
        where: { referrer_id: userId },
      });

      if (referrals.length === 0) {
        return { count: 0, totalAmount: 0, earnings: [] };
      }

      const referralIds = referrals.map((r) => r.id);

      // Get paid earnings
      const earnings = await earningRepo.find({
        where: {
          referral_id: In(referralIds),
          paid: true,
        },
        relations: ['referral', 'referral.referred'],
        order: { created_at: 'DESC' },
      });

      const totalAmount = earnings.reduce(
        (sum, e) => sum + parseFloat(e.amount),
        0
      );

      return {
        count: earnings.length,
        totalAmount,
        earnings,
      };
    } catch (error) {
      logger.error(`❌ Error getting paid earnings for user ${userId}:`, error);
      throw error;
    }
  }

  /**
   * Retry failed payments (for manual intervention)
   */
  public async retryFailedPayments(
    earningIds: number[]
  ): Promise<{
    processed: number;
    successful: number;
    failed: number;
  }> {
    try {
      const earningRepo = AppDataSource.getRepository(ReferralEarning);

      const earnings = await earningRepo.find({
        where: {
          id: In(earningIds),
          paid: false,
        },
        relations: ['referral', 'referral.referrer'],
      });

      if (earnings.length === 0) {
        return { processed: 0, successful: 0, failed: 0 };
      }

      logger.info(`🔄 Retrying ${earnings.length} failed payments...`);

      // Group by user
      const earningsByUser = new Map<number, ReferralEarning[]>();

      for (const earning of earnings) {
        const referrerId = earning.referral.referrer_id;
        if (!earningsByUser.has(referrerId)) {
          earningsByUser.set(referrerId, []);
        }
        earningsByUser.get(referrerId)!.push(earning);
      }

      let processed = 0;
      let successful = 0;
      let failed = 0;

      for (const [referrerId, userEarnings] of earningsByUser) {
        const result = await this.processUserPayments(referrerId, userEarnings);
        processed += result.processed;
        successful += result.successful;
        failed += result.failed;
      }

      return { processed, successful, failed };
    } catch (error) {
      logger.error('❌ Error retrying failed payments:', error);
      throw error;
    }
  }
}

// Export singleton instance
export const paymentService = PaymentService.getInstance();
