/**
 * Transaction Service
 * Comprehensive transaction history management
 */

import { AppDataSource } from '../database/data-source';
import { Transaction } from '../database/entities/Transaction.entity';
import { Deposit } from '../database/entities/Deposit.entity';
import { ReferralEarning } from '../database/entities/ReferralEarning.entity';
import { TransactionStatus, TransactionType } from '../utils/constants';
import { createLogger } from '../utils/logger.util';

const logger = createLogger('TransactionService');

/**
 * Unified transaction item for display
 */
export interface UnifiedTransaction {
  id: string; // Composite ID: "type:id"
  type: TransactionType;
  amount: number;
  status: TransactionStatus;
  createdAt: Date;
  description: string;
  txHash?: string;
  explorerLink?: string;
  metadata?: {
    level?: number; // For deposits
    referralLevel?: number; // For referral rewards
    referredUserId?: number;
  };
}

export class TransactionService {
  private transactionRepository = AppDataSource.getRepository(Transaction);
  private depositRepository = AppDataSource.getRepository(Deposit);
  private referralEarningRepository = AppDataSource.getRepository(ReferralEarning);

  /**
   * Get all transactions for a user (deposits, withdrawals, referral earnings)
   */
  async getAllTransactions(
    userId: number,
    options: {
      limit?: number;
      offset?: number;
      type?: TransactionType;
      status?: TransactionStatus;
    } = {}
  ): Promise<{
    transactions: UnifiedTransaction[];
    total: number;
    hasMore: boolean;
  }> {
    const limit = options.limit || 20;
    const offset = options.offset || 0;

    try {
      // Collect all transactions
      const allTransactions: UnifiedTransaction[] = [];

      // 1. Get deposits
      if (!options.type || options.type === TransactionType.DEPOSIT) {
        const depositsQuery = this.depositRepository
          .createQueryBuilder('deposit')
          .where('deposit.user_id = :userId', { userId });

        if (options.status) {
          depositsQuery.andWhere('deposit.status = :status', { status: options.status });
        }

        const deposits = await depositsQuery
          .orderBy('deposit.created_at', 'DESC')
          .getMany();

        deposits.forEach(deposit => {
          allTransactions.push({
            id: `deposit:${deposit.id}`,
            type: TransactionType.DEPOSIT,
            amount: deposit.amountAsNumber,
            status: deposit.status as TransactionStatus,
            createdAt: deposit.created_at,
            description: `Депозит уровня ${deposit.level}`,
            txHash: deposit.tx_hash,
            explorerLink: deposit.tx_hash ? `https://bscscan.com/tx/${deposit.tx_hash}` : undefined,
            metadata: {
              level: deposit.level,
            },
          });
        });
      }

      // 2. Get withdrawals
      if (!options.type || options.type === TransactionType.WITHDRAWAL) {
        const withdrawalsQuery = this.transactionRepository
          .createQueryBuilder('transaction')
          .where('transaction.user_id = :userId', { userId })
          .andWhere('transaction.type = :type', { type: TransactionType.WITHDRAWAL });

        if (options.status) {
          withdrawalsQuery.andWhere('transaction.status = :status', { status: options.status });
        }

        const withdrawals = await withdrawalsQuery
          .orderBy('transaction.created_at', 'DESC')
          .getMany();

        withdrawals.forEach(withdrawal => {
          allTransactions.push({
            id: `withdrawal:${withdrawal.id}`,
            type: TransactionType.WITHDRAWAL,
            amount: withdrawal.amountAsNumber,
            status: withdrawal.status as TransactionStatus,
            createdAt: withdrawal.created_at,
            description: 'Вывод средств',
            txHash: withdrawal.tx_hash,
            explorerLink: withdrawal.tx_hash ? withdrawal.explorerLink : undefined,
          });
        });
      }

      // 3. Get referral earnings
      if (!options.type || options.type === TransactionType.REFERRAL_REWARD) {
        const earningsQuery = this.referralEarningRepository
          .createQueryBuilder('earning')
          .leftJoinAndSelect('earning.referral', 'referral')
          .where('referral.referrer_id = :userId', { userId });

        const earnings = await earningsQuery
          .orderBy('earning.created_at', 'DESC')
          .getMany();

        earnings.forEach(earning => {
          const statusMap: { [key: string]: TransactionStatus } = {
            'pending': TransactionStatus.PENDING,
            'paid': TransactionStatus.CONFIRMED,
            'failed': TransactionStatus.FAILED,
          };

          allTransactions.push({
            id: `referral:${earning.id}`,
            type: TransactionType.REFERRAL_REWARD,
            amount: parseFloat(earning.amount),
            status: earning.paid ? TransactionStatus.CONFIRMED : TransactionStatus.PENDING,
            createdAt: earning.created_at,
            description: `Реферальное вознаграждение (уровень ${earning.referral?.level || '?'})`,
            metadata: {
              referralLevel: earning.referral?.level,
              referredUserId: earning.referral?.referral_id,
            },
          });
        });
      }

      // Sort all transactions by date (newest first)
      allTransactions.sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime());

      // Apply pagination
      const total = allTransactions.length;
      const paginatedTransactions = allTransactions.slice(offset, offset + limit);
      const hasMore = offset + limit < total;

      logger.debug('Retrieved all transactions', {
        userId,
        total,
        returned: paginatedTransactions.length,
        hasMore,
      });

      return {
        transactions: paginatedTransactions,
        total,
        hasMore,
      };
    } catch (error) {
      logger.error('Error getting all transactions', {
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      throw error;
    }
  }

  /**
   * Get transaction statistics for a user
   */
  async getTransactionStats(userId: number): Promise<{
    totalDeposits: number;
    totalWithdrawals: number;
    totalReferralEarnings: number;
    pendingWithdrawals: number;
    pendingEarnings: number;
    transactionCount: {
      deposits: number;
      withdrawals: number;
      referralRewards: number;
    };
  }> {
    try {
      // Get deposits
      const deposits = await this.depositRepository.find({
        where: { user_id: userId, status: TransactionStatus.CONFIRMED },
      });
      const totalDeposits = deposits.reduce((sum, d) => sum + d.amountAsNumber, 0);

      // Get withdrawals
      const withdrawals = await this.transactionRepository.find({
        where: {
          user_id: userId,
          type: TransactionType.WITHDRAWAL,
        },
      });
      const confirmedWithdrawals = withdrawals.filter(w => w.status === TransactionStatus.CONFIRMED);
      const pendingWithdrawals = withdrawals.filter(w => w.status === TransactionStatus.PENDING);
      const totalWithdrawals = confirmedWithdrawals.reduce((sum, w) => sum + w.amountAsNumber, 0);
      const pendingWithdrawalsAmount = pendingWithdrawals.reduce((sum, w) => sum + w.amountAsNumber, 0);

      // Get referral earnings
      const earnings = await this.referralEarningRepository
        .createQueryBuilder('earning')
        .leftJoin('earning.referral', 'referral')
        .where('referral.referrer_id = :userId', { userId })
        .getMany();

      const totalReferralEarnings = earnings.reduce((sum, e) => sum + parseFloat(e.amount), 0);
      const pendingEarnings = earnings
        .filter(e => !e.paid)
        .reduce((sum, e) => sum + parseFloat(e.amount), 0);

      return {
        totalDeposits,
        totalWithdrawals,
        totalReferralEarnings,
        pendingWithdrawals: pendingWithdrawalsAmount,
        pendingEarnings,
        transactionCount: {
          deposits: deposits.length,
          withdrawals: confirmedWithdrawals.length,
          referralRewards: earnings.filter(e => e.paid).length,
        },
      };
    } catch (error) {
      logger.error('Error getting transaction stats', {
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      throw error;
    }
  }

  /**
   * Get recent transactions (last N transactions)
   */
  async getRecentTransactions(userId: number, limit: number = 5): Promise<UnifiedTransaction[]> {
    const result = await this.getAllTransactions(userId, { limit, offset: 0 });
    return result.transactions;
  }
}

export default new TransactionService();
