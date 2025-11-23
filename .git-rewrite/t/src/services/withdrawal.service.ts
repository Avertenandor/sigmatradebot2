/**
 * Withdrawal Service
 * Handles withdrawal requests and processing
 */

import { AppDataSource } from '../database/data-source';
import { Transaction, User } from '../database/entities';
import { createLogger } from '../utils/logger.util';
import { TransactionStatus, TransactionType } from '../utils/constants';
import userService from './user.service';

const logger = createLogger('WithdrawalService');

// Minimum withdrawal amount in USDT
const MIN_WITHDRAWAL_AMOUNT = 5;

export class WithdrawalService {
  private transactionRepository = AppDataSource.getRepository(Transaction);

  /**
   * Request withdrawal
   */
  async requestWithdrawal(data: {
    userId: number;
    amount: number;
  }): Promise<{ transaction?: Transaction; error?: string }> {
    try {
      // Validate amount
      if (data.amount < MIN_WITHDRAWAL_AMOUNT) {
        return {
          error: `Минимальная сумма вывода: ${MIN_WITHDRAWAL_AMOUNT} USDT`,
        };
      }

      // Get user balance
      const balance = await userService.getUserBalance(data.userId);
      if (!balance) {
        return { error: 'Не удалось получить баланс' };
      }

      // Check if user has enough balance
      if (balance.availableBalance < data.amount) {
        return {
          error: `Недостаточно средств. Доступно: ${balance.availableBalance.toFixed(2)} USDT`,
        };
      }

      // Get user for wallet address
      const user = await userService.findById(data.userId);
      if (!user) {
        return { error: 'Пользователь не найден' };
      }

      // Create withdrawal transaction
      const transaction = this.transactionRepository.create({
        user_id: data.userId,
        type: TransactionType.WITHDRAWAL,
        amount: data.amount.toString(),
        to_address: user.wallet_address, // Withdraw to user's wallet
        status: TransactionStatus.PENDING,
      });

      await this.transactionRepository.save(transaction);

      logger.info('Withdrawal request created', {
        transactionId: transaction.id,
        userId: data.userId,
        amount: data.amount,
      });

      return { transaction };
    } catch (error) {
      logger.error('Error creating withdrawal request', {
        userId: data.userId,
        error: error instanceof Error ? error.message : String(error),
      });
      return { error: 'Ошибка при создании заявки на вывод' };
    }
  }

  /**
   * Get pending withdrawals (for admin)
   */
  async getPendingWithdrawals(): Promise<Transaction[]> {
    try {
      return await this.transactionRepository.find({
        where: {
          type: TransactionType.WITHDRAWAL,
          status: TransactionStatus.PENDING,
        },
        relations: ['user'],
        order: { created_at: 'ASC' },
      });
    } catch (error) {
      logger.error('Error getting pending withdrawals', {
        error: error instanceof Error ? error.message : String(error),
      });
      return [];
    }
  }

  /**
   * Get user withdrawal history
   */
  async getUserWithdrawals(
    userId: number,
    options?: {
      page?: number;
      limit?: number;
    }
  ): Promise<{
    withdrawals: Transaction[];
    total: number;
    page: number;
    pages: number;
  }> {
    const page = options?.page || 1;
    const limit = options?.limit || 10;
    const skip = (page - 1) * limit;

    try {
      const [withdrawals, total] = await this.transactionRepository.findAndCount({
        where: {
          user_id: userId,
          type: TransactionType.WITHDRAWAL,
        },
        order: { created_at: 'DESC' },
        take: limit,
        skip,
      });

      const pages = Math.ceil(total / limit);

      return { withdrawals, total, page, pages };
    } catch (error) {
      logger.error('Error getting user withdrawals', {
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      return { withdrawals: [], total: 0, page: 1, pages: 0 };
    }
  }

  /**
   * Cancel withdrawal (by user, only if pending)
   */
  async cancelWithdrawal(
    transactionId: number,
    userId: number
  ): Promise<{ success: boolean; error?: string }> {
    try {
      const transaction = await this.transactionRepository.findOne({
        where: {
          id: transactionId,
          user_id: userId,
          type: TransactionType.WITHDRAWAL,
          status: TransactionStatus.PENDING,
        },
      });

      if (!transaction) {
        return { success: false, error: 'Заявка не найдена или не может быть отменена' };
      }

      transaction.status = TransactionStatus.FAILED;
      await this.transactionRepository.save(transaction);

      logger.info('Withdrawal cancelled by user', {
        transactionId,
        userId,
      });

      return { success: true };
    } catch (error) {
      logger.error('Error cancelling withdrawal', {
        transactionId,
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      return { success: false, error: 'Ошибка при отмене заявки' };
    }
  }

  /**
   * Approve withdrawal (admin only)
   */
  async approveWithdrawal(
    transactionId: number,
    txHash: string
  ): Promise<{ success: boolean; error?: string }> {
    try {
      const withdrawal = await this.transactionRepository.findOne({
        where: {
          id: transactionId,
          type: TransactionType.WITHDRAWAL,
          status: TransactionStatus.PENDING,
        },
        relations: ['user'],
      });

      if (!withdrawal) {
        return { success: false, error: 'Заявка на вывод не найдена или уже обработана' };
      }

      // Update withdrawal status
      withdrawal.status = TransactionStatus.CONFIRMED;
      withdrawal.tx_hash = txHash;
      await this.transactionRepository.save(withdrawal);

      logger.info('Withdrawal approved', {
        transactionId,
        userId: withdrawal.user_id,
        amount: withdrawal.amount,
        txHash,
      });

      return { success: true };
    } catch (error) {
      logger.error('Error approving withdrawal', {
        transactionId,
        error: error instanceof Error ? error.message : String(error),
      });
      return { success: false, error: 'Ошибка при подтверждении заявки' };
    }
  }

  /**
   * Reject withdrawal (admin only)
   */
  async rejectWithdrawal(
    transactionId: number,
    reason?: string
  ): Promise<{ success: boolean; error?: string }> {
    try {
      const withdrawal = await this.transactionRepository.findOne({
        where: {
          id: transactionId,
          type: TransactionType.WITHDRAWAL,
          status: TransactionStatus.PENDING,
        },
        relations: ['user'],
      });

      if (!withdrawal) {
        return { success: false, error: 'Заявка на вывод не найдена или уже обработана' };
      }

      // Update withdrawal status
      withdrawal.status = TransactionStatus.FAILED;
      await this.transactionRepository.save(withdrawal);

      logger.info('Withdrawal rejected', {
        transactionId,
        userId: withdrawal.user_id,
        amount: withdrawal.amount,
        reason,
      });

      return { success: true };
    } catch (error) {
      logger.error('Error rejecting withdrawal', {
        transactionId,
        error: error instanceof Error ? error.message : String(error),
      });
      return { success: false, error: 'Ошибка при отклонении заявки' };
    }
  }

  /**
   * Get withdrawal by ID (admin only)
   */
  async getWithdrawalById(transactionId: number): Promise<Transaction | null> {
    try {
      return await this.transactionRepository.findOne({
        where: {
          id: transactionId,
          type: TransactionType.WITHDRAWAL,
        },
        relations: ['user'],
      });
    } catch (error) {
      logger.error('Error getting withdrawal by ID', {
        transactionId,
        error: error instanceof Error ? error.message : String(error),
      });
      return null;
    }
  }

  /**
   * Get minimum withdrawal amount
   */
  getMinWithdrawalAmount(): number {
    return MIN_WITHDRAWAL_AMOUNT;
  }
}

export default new WithdrawalService();
