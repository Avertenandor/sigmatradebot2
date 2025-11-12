/**
 * Deposit Service
 * Business logic for deposit management
 */

import { AppDataSource } from '../database/data-source';
import { Deposit, User, Transaction } from '../database/entities';
import { createLogger } from '../utils/logger.util';
import { DEPOSIT_LEVELS, REQUIRED_REFERRALS_PER_LEVEL, TransactionStatus } from '../utils/constants';
import userService from './user.service';
import { paymentService } from './payment.service';
import { notificationService } from './notification.service';
import { settingsService } from './settings.service';
import { fromDbString, toUsdtString, sum as sumMoney, type MoneyAmount } from '../utils/money.util';

const logger = createLogger('DepositService');

export class DepositService {
  private depositRepository = AppDataSource.getRepository(Deposit);

  /**
   * Get activated deposit levels for user
   */
  async getActivatedLevels(userId: number): Promise<number[]> {
    try {
      const deposits = await this.depositRepository.find({
        where: {
          user_id: userId,
          status: TransactionStatus.CONFIRMED,
        },
        order: {
          level: 'ASC',
        },
      });

      return deposits.map((d) => d.level);
    } catch (error) {
      logger.error('Error getting activated levels', {
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      return [];
    }
  }

  /**
   * Get active Level 1 ROI cycle for user
   * Returns the active Level 1 deposit that hasn't completed its 500% ROI
   */
  async getActiveLevel1Cycle(userId: number): Promise<Deposit | null> {
    try {
      const activeL1 = await this.depositRepository.findOne({
        where: {
          user_id: userId,
          level: 1,
          status: TransactionStatus.CONFIRMED,
          is_roi_completed: false,
        },
      });

      return activeL1 || null;
    } catch (error) {
      logger.error('Error getting active L1 cycle', {
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      return null;
    }
  }

  /**
   * Check if user can activate specific level
   */
  async canActivateLevel(
    userId: number,
    level: number
  ): Promise<{ canActivate: boolean; reason?: string }> {
    // Validate level
    if (level < 1 || level > 5) {
      return { canActivate: false, reason: 'Неверный уровень депозита' };
    }

    // CRITICAL: Check if level is open (admin can restrict levels)
    const maxOpenLevel = await settingsService.getMaxOpenLevel();
    if (level > maxOpenLevel) {
      return {
        canActivate: false,
        reason: `Этот уровень пока не открыт. Доступны уровни 1-${maxOpenLevel}`,
      };
    }

    // CRITICAL: For Level 1, check if user has active ROI cycle
    if (level === 1) {
      const activeL1 = await this.getActiveLevel1Cycle(userId);
      if (activeL1) {
        return {
          canActivate: false,
          reason: 'У вас уже есть активный депозит уровня 1. Дождитесь завершения 500% ROI',
        };
      }
      return { canActivate: true };
    }

    // Check if already activated
    const activatedLevels = await this.getActivatedLevels(userId);

    if (activatedLevels.includes(level)) {
      return { canActivate: false, reason: 'Этот уровень уже активирован' };
    }

    // Check if previous level is activated
    if (!activatedLevels.includes(level - 1)) {
      return {
        canActivate: false,
        reason: `Сначала активируйте уровень ${level - 1}`,
      };
    }

    // Check referral requirements
    const requiredReferrals = REQUIRED_REFERRALS_PER_LEVEL[level as keyof typeof REQUIRED_REFERRALS_PER_LEVEL];
    const referralCount = await this.getDirectReferralCount(userId);

    if (referralCount < requiredReferrals) {
      return {
        canActivate: false,
        reason: `Для активации этого уровня нужно ${requiredReferrals} ${
          requiredReferrals === 1 ? 'реферал' : 'рефералов'
        }. У вас: ${referralCount}`,
      };
    }

    return { canActivate: true };
  }

  /**
   * Get available levels for user to activate
   */
  async getAvailableLevels(userId: number): Promise<number[]> {
    const available: number[] = [];

    // CRITICAL: Only show levels up to maxOpenLevel
    const maxOpenLevel = await settingsService.getMaxOpenLevel();

    for (let level = 1; level <= maxOpenLevel; level++) {
      const { canActivate } = await this.canActivateLevel(userId, level);
      if (canActivate) {
        available.push(level);
      }
    }

    return available;
  }

  /**
   * Get deposit info for level
   */
  getDepositInfo(level: number): {
    level: number;
    amount: number;
    requiredReferrals: number;
  } | null {
    if (level < 1 || level > 5) {
      return null;
    }

    return {
      level,
      amount: DEPOSIT_LEVELS[level as keyof typeof DEPOSIT_LEVELS],
      requiredReferrals: REQUIRED_REFERRALS_PER_LEVEL[level as keyof typeof REQUIRED_REFERRALS_PER_LEVEL],
    };
  }

  /**
   * Get direct referral count (for deposit eligibility)
   */
  async getDirectReferralCount(userId: number): Promise<number> {
    try {
      const userRepository = AppDataSource.getRepository(User);

      const count = await userRepository.count({
        where: {
          referrer_id: userId,
          is_verified: true, // Only count verified referrals
        },
      });

      return count;
    } catch (error) {
      logger.error('Error getting referral count', {
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      return 0;
    }
  }

  /**
   * Get pending deposits for user
   */
  async getPendingDeposits(userId: number): Promise<Deposit[]> {
    try {
      return await this.depositRepository.find({
        where: {
          user_id: userId,
          status: TransactionStatus.PENDING,
        },
        order: { created_at: 'DESC' },
      });
    } catch (error) {
      logger.error('Error getting pending deposits', {
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      return [];
    }
  }

  /**
   * Get deposit history for user
   */
  async getDepositHistory(
    userId: number,
    options?: {
      page?: number;
      limit?: number;
    }
  ): Promise<{
    deposits: Deposit[];
    total: number;
    page: number;
    pages: number;
  }> {
    const page = options?.page || 1;
    const limit = options?.limit || 10;
    const skip = (page - 1) * limit;

    try {
      const [deposits, total] = await this.depositRepository.findAndCount({
        where: { user_id: userId },
        order: { created_at: 'DESC' },
        take: limit,
        skip,
      });

      const pages = Math.ceil(total / limit);

      return { deposits, total, page, pages };
    } catch (error) {
      logger.error('Error getting deposit history', {
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      return { deposits: [], total: 0, page: 1, pages: 0 };
    }
  }

  /**
   * Get deposit by transaction hash
   */
  async getDepositByTxHash(txHash: string): Promise<Deposit | null> {
    try {
      return await this.depositRepository.findOne({
        where: { tx_hash: txHash },
        relations: ['user'],
      });
    } catch (error) {
      logger.error('Error getting deposit by tx hash', {
        txHash,
        error: error instanceof Error ? error.message : String(error),
      });
      return null;
    }
  }

  /**
   * Create pending deposit
   * (Will be confirmed by blockchain monitor)
   */
  async createPendingDeposit(data: {
    userId: number;
    level: number;
    amount: number;
    txHash?: string; // Optional - can be added later by blockchain monitor
  }): Promise<{ deposit?: Deposit; error?: string }> {
    try {
      // Check if deposit with this tx hash already exists (if tx hash provided)
      if (data.txHash) {
        const existing = await this.getDepositByTxHash(data.txHash);
        if (existing) {
          return { error: 'Депозит с этим хешом транзакции уже существует' };
        }
      }

      // CRITICAL: For Level 1, check if user has active ROI cycle
      if (data.level === 1) {
        const activeL1 = await this.getActiveLevel1Cycle(data.userId);
        if (activeL1) {
          return {
            error: 'У вас уже есть активный депозит 10 USDT. Дождитесь завершения 500% ROI, затем создайте новый депозит',
          };
        }
      }

      // Check if user already has pending deposit for this level
      const existingPending = await this.depositRepository.findOne({
        where: {
          user_id: data.userId,
          level: data.level,
          status: TransactionStatus.PENDING,
        },
      });

      if (existingPending) {
        return { error: 'У вас уже есть ожидающий подтверждения депозит этого уровня' };
      }

      // Validate level and amount
      const depositInfo = this.getDepositInfo(data.level);
      if (!depositInfo) {
        return { error: 'Неверный уровень депозита' };
      }

      if (data.amount !== depositInfo.amount) {
        return { error: 'Неверная сумма депозита' };
      }

      // Check if can activate
      const { canActivate, reason } = await this.canActivateLevel(
        data.userId,
        data.level
      );

      if (!canActivate) {
        return { error: reason };
      }

      // Create deposit
      const deposit = this.depositRepository.create({
        user_id: data.userId,
        level: data.level,
        amount: data.amount.toString(),
        tx_hash: data.txHash || undefined,
        status: TransactionStatus.PENDING,
      });

      await this.depositRepository.save(deposit);

      logger.info('Pending deposit created', {
        depositId: deposit.id,
        userId: data.userId,
        level: data.level,
        amount: data.amount,
        txHash: data.txHash || 'awaiting blockchain confirmation',
      });

      return { deposit };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      logger.error('Error creating pending deposit', {
        userId: data.userId,
        level: data.level,
        error: errorMessage,
      });
      return {
        error: `Не удалось создать депозит уровня ${data.level}: ${errorMessage.includes('duplicate') ? 'депозит уже существует' : errorMessage.includes('constraint') ? 'нарушение правил депозита' : 'внутренняя ошибка базы данных'}`,
      };
    }
  }

  /**
   * Confirm deposit (called by blockchain monitor)
   */
  async confirmDeposit(
    txHash: string,
    blockNumber: number
  ): Promise<{ success: boolean; error?: string }> {
    try {
      const deposit = await this.getDepositByTxHash(txHash);

      if (!deposit) {
        return { success: false, error: 'Депозит не найден' };
      }

      if (deposit.isConfirmed) {
        return { success: false, error: 'Депозит уже подтвержден' };
      }

      // Update deposit status
      deposit.status = TransactionStatus.CONFIRMED;
      deposit.block_number = blockNumber;
      deposit.confirmed_at = new Date();

      // CRITICAL: For Level 1, initialize ROI cap (500% = 5x amount)
      if (deposit.level === 1) {
        const depositAmountMoney = fromDbString(deposit.amount);
        const roiCapMoney: MoneyAmount = {
          value: depositAmountMoney.value * BigInt(5),
          decimals: depositAmountMoney.decimals,
        };

        deposit.roi_cap_amount = toUsdtString(roiCapMoney);
        deposit.roi_paid_amount = '0';
        deposit.is_roi_completed = false;

        logger.info('ROI cap initialized for Level 1 deposit', {
          depositId: deposit.id,
          amount: deposit.amount,
          roiCap: deposit.roi_cap_amount,
        });
      }

      await this.depositRepository.save(deposit);

      logger.info('Deposit confirmed', {
        depositId: deposit.id,
        userId: deposit.user_id,
        level: deposit.level,
        amount: deposit.amount,
        blockNumber,
      });

      // Get user for notifications
      const userRepo = AppDataSource.getRepository(User);
      const user = await userRepo.findOne({ where: { id: deposit.user_id } });

      // CRITICAL: Use precise money calculation
      const depositAmountMoney = fromDbString(deposit.amount);

      // Send notification to user
      if (user) {
        await notificationService.notifyDepositConfirmed(
          user.telegram_id,
          parseFloat(toUsdtString(depositAmountMoney)),  // Convert for notification
          deposit.level,
          txHash
        );

        // Send level activation notification
        await notificationService.notifyLevelActivated(
          user.telegram_id,
          deposit.level
        ).catch((err) => {
          logger.error('Failed to send level activation notification', { error: err });
        });
      }

      // Find associated transaction for source_transaction_id
      const transactionRepo = AppDataSource.getRepository(Transaction);
      const transaction = await transactionRepo.findOne({
        where: { tx_hash: txHash },
      });

      // Create referral earnings
      if (transaction) {
        try {
          const result = await paymentService.createReferralEarnings(
            deposit.user_id,
            parseFloat(toUsdtString(depositAmountMoney)),  // Convert for payment service
            transaction.id
          );

          logger.info('Referral earnings created', {
            depositId: deposit.id,
            created: result.created,
            totalAmount: result.totalAmount,
          });
        } catch (error) {
          logger.error('Error creating referral earnings', {
            depositId: deposit.id,
            error: error instanceof Error ? error.message : String(error),
          });
          // Don't fail the deposit confirmation if referral earnings fail
        }
      }

      return { success: true };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      logger.error('Error confirming deposit', {
        txHash,
        error: errorMessage,
      });
      return {
        success: false,
        error: `Не удалось подтвердить депозит (TX: ${txHash.substring(0, 10)}...): ${errorMessage.includes('not found') ? 'депозит не найден' : errorMessage.includes('already confirmed') ? 'уже подтвержден' : 'ошибка сохранения'}`,
      };
    }
  }

  /**
   * Get ROI progress for user's active Level 1 deposit
   */
  async getLevel1RoiProgress(userId: number): Promise<{
    hasActiveDeposit: boolean;
    depositAmount?: number;
    roiCap?: number;
    roiPaid?: number;
    roiRemaining?: number;
    roiPercent?: number;
    isCompleted?: boolean;
  }> {
    try {
      const activeL1 = await this.getActiveLevel1Cycle(userId);

      if (!activeL1 || !activeL1.roi_cap_amount) {
        return { hasActiveDeposit: false };
      }

      const depositAmountMoney = fromDbString(activeL1.amount);
      const roiCapMoney = fromDbString(activeL1.roi_cap_amount);
      const roiPaidMoney = fromDbString(activeL1.roi_paid_amount || '0');

      const depositAmount = parseFloat(toUsdtString(depositAmountMoney));
      const roiCap = parseFloat(toUsdtString(roiCapMoney));
      const roiPaid = parseFloat(toUsdtString(roiPaidMoney));
      const roiRemaining = Math.max(roiCap - roiPaid, 0);
      const roiPercent = roiCap > 0 ? (roiPaid / roiCap) * 100 : 0;

      return {
        hasActiveDeposit: true,
        depositAmount,
        roiCap,
        roiPaid,
        roiRemaining,
        roiPercent: Math.min(roiPercent, 100),
        isCompleted: activeL1.is_roi_completed,
      };
    } catch (error) {
      logger.error('Error getting L1 ROI progress', {
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      return { hasActiveDeposit: false };
    }
  }

  /**
   * Get total deposited by user
   */
  async getTotalDeposited(userId: number): Promise<number> {
    try {
      const deposits = await this.depositRepository.find({
        where: {
          user_id: userId,
          status: TransactionStatus.CONFIRMED,
        },
      });

      // CRITICAL: Use precise money summation
      const totalMoney = sumMoney(deposits.map(d => fromDbString(d.amount)));
      return parseFloat(toUsdtString(totalMoney));  // Convert for return value
    } catch (error) {
      logger.error('Error getting total deposited', {
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      return 0;
    }
  }

  /**
   * Get ROI statistics for admins
   */
  async getRoiStatistics(): Promise<{
    totalActiveL1Deposits: number;
    totalCompletedL1Cycles: number;
    totalL1Deposited: number;
    totalL1RoiPaid: number;
    averageRoiProgress: number;
    nearingCompletion: Array<{
      userId: number;
      telegramId: number;
      depositAmount: number;
      roiPaid: number;
      roiRemaining: number;
      roiPercent: number;
    }>;
  }> {
    try {
      // Get all Level 1 deposits
      const allL1Deposits = await this.depositRepository.find({
        where: {
          level: 1,
          status: TransactionStatus.CONFIRMED,
        },
        relations: ['user'],
      });

      // Active deposits (not completed)
      const activeL1 = allL1Deposits.filter((d) => !d.is_roi_completed && d.roi_cap_amount);

      // Completed deposits
      const completedL1 = allL1Deposits.filter((d) => d.is_roi_completed);

      // Calculate totals
      let totalL1Deposited = 0;
      let totalL1RoiPaid = 0;
      let totalRoiProgress = 0;

      for (const deposit of allL1Deposits) {
        if (deposit.roi_cap_amount) {
          const depositAmountMoney = fromDbString(deposit.amount);
          const roiPaidMoney = fromDbString(deposit.roi_paid_amount || '0');

          totalL1Deposited += parseFloat(toUsdtString(depositAmountMoney));
          totalL1RoiPaid += parseFloat(toUsdtString(roiPaidMoney));
        }
      }

      // Calculate average progress for active deposits
      for (const deposit of activeL1) {
        const roiCapMoney = fromDbString(deposit.roi_cap_amount!);
        const roiPaidMoney = fromDbString(deposit.roi_paid_amount || '0');

        const roiCap = parseFloat(toUsdtString(roiCapMoney));
        const roiPaid = parseFloat(toUsdtString(roiPaidMoney));

        totalRoiProgress += roiCap > 0 ? (roiPaid / roiCap) * 100 : 0;
      }

      const averageRoiProgress = activeL1.length > 0 ? totalRoiProgress / activeL1.length : 0;

      // Find deposits nearing completion (>80% ROI)
      const nearingCompletion = activeL1
        .filter((deposit) => deposit.user) // Filter out deposits without user relation
        .map((deposit) => {
          const depositAmountMoney = fromDbString(deposit.amount);
          const roiCapMoney = fromDbString(deposit.roi_cap_amount!);
          const roiPaidMoney = fromDbString(deposit.roi_paid_amount || '0');

          const depositAmount = parseFloat(toUsdtString(depositAmountMoney));
          const roiCap = parseFloat(toUsdtString(roiCapMoney));
          const roiPaid = parseFloat(toUsdtString(roiPaidMoney));
          const roiRemaining = Math.max(roiCap - roiPaid, 0);
          const roiPercent = roiCap > 0 ? (roiPaid / roiCap) * 100 : 0;

          return {
            userId: deposit.user_id,
            telegramId: deposit.user!.telegram_id, // Safe after filter
            depositAmount,
            roiPaid,
            roiRemaining,
            roiPercent,
          };
        })
        .filter((d) => d.roiPercent >= 80)
        .sort((a, b) => b.roiPercent - a.roiPercent)
        .slice(0, 10);

      return {
        totalActiveL1Deposits: activeL1.length,
        totalCompletedL1Cycles: completedL1.length,
        totalL1Deposited,
        totalL1RoiPaid,
        averageRoiProgress,
        nearingCompletion,
      };
    } catch (error) {
      logger.error('Error getting ROI statistics', {
        error: error instanceof Error ? error.message : String(error),
      });
      return {
        totalActiveL1Deposits: 0,
        totalCompletedL1Cycles: 0,
        totalL1Deposited: 0,
        totalL1RoiPaid: 0,
        averageRoiProgress: 0,
        nearingCompletion: [],
      };
    }
  }

  /**
   * Get platform statistics
   */
  async getPlatformStats(): Promise<{
    totalDeposits: number;
    totalAmount: number;
    totalUsers: number;
    depositsByLevel: Record<number, number>;
  }> {
    try {
      const deposits = await this.depositRepository.find({
        where: { status: TransactionStatus.CONFIRMED },
      });

      // CRITICAL: Use precise money summation
      const totalAmountMoney = sumMoney(deposits.map(d => fromDbString(d.amount)));
      const totalAmount = parseFloat(toUsdtString(totalAmountMoney));  // Convert for return value

      const depositsByLevel: Record<number, number> = {
        1: 0,
        2: 0,
        3: 0,
        4: 0,
        5: 0,
      };

      deposits.forEach((d) => {
        depositsByLevel[d.level] = (depositsByLevel[d.level] || 0) + 1;
      });

      // Get unique user count who made deposits
      const uniqueUsers = new Set(deposits.map((d) => d.user_id));

      return {
        totalDeposits: deposits.length,
        totalAmount,
        totalUsers: uniqueUsers.size,
        depositsByLevel,
      };
    } catch (error) {
      logger.error('Error getting platform stats', {
        error: error instanceof Error ? error.message : String(error),
      });
      return {
        totalDeposits: 0,
        totalAmount: 0,
        totalUsers: 0,
        depositsByLevel: { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 },
      };
    }
  }

  /**
   * Cleanup orphaned deposits (pending deposits without tx_hash older than 24 hours)
   */
  async cleanupOrphanedDeposits(): Promise<{
    cleaned: number;
    errors: number;
  }> {
    try {
      const TIMEOUT_MS = 24 * 60 * 60 * 1000; // 24 hours
      const timeoutDate = new Date(Date.now() - TIMEOUT_MS);

      // Find pending deposits without tx_hash older than 24 hours
      const orphanedDeposits = await this.depositRepository
        .createQueryBuilder('deposit')
        .where('deposit.status = :status', { status: TransactionStatus.PENDING })
        .andWhere('(deposit.tx_hash IS NULL OR deposit.tx_hash = \'\')')
        .andWhere('deposit.created_at < :timeoutDate', { timeoutDate })
        .getMany();

      let cleaned = 0;
      let errors = 0;

      for (const deposit of orphanedDeposits) {
        try {
          // Mark as failed/expired
          deposit.status = TransactionStatus.FAILED;
          await this.depositRepository.save(deposit);
          cleaned++;

          logger.info('Orphaned deposit cleaned', {
            depositId: deposit.id,
            userId: deposit.user_id,
            level: deposit.level,
            age: Date.now() - deposit.created_at.getTime(),
          });

          // Optionally notify user
          if (deposit.user_id) {
            const user = await userService.findById(deposit.user_id);
            if (user) {
              await notificationService.sendCustomMessage(
                user.telegram_id,
                `⏱️ Ваш запрос на депозит уровня ${deposit.level} истёк.\n\n` +
                `Депозит был создан более 24 часов назад, но средства не были отправлены.\n\n` +
                `Вы можете создать новый запрос на депозит.`
              );
            }
          }
        } catch (error) {
          errors++;
          logger.error('Error cleaning orphaned deposit', {
            depositId: deposit.id,
            error: error instanceof Error ? error.message : String(error),
          });
        }
      }

      logger.info('Orphaned deposits cleanup completed', {
        found: orphanedDeposits.length,
        cleaned,
        errors,
      });

      return { cleaned, errors };
    } catch (error) {
      logger.error('Error in cleanupOrphanedDeposits', {
        error: error instanceof Error ? error.message : String(error),
      });
      return { cleaned: 0, errors: 1 };
    }
  }

  /**
   * Cancel pending deposit (user-initiated)
   */
  async cancelPendingDeposit(
    userId: number,
    depositId: number
  ): Promise<{ success: boolean; error?: string }> {
    try {
      const deposit = await this.depositRepository.findOne({
        where: {
          id: depositId,
          user_id: userId,
          status: TransactionStatus.PENDING,
        },
      });

      if (!deposit) {
        return { success: false, error: 'Депозит не найден или уже обработан' };
      }

      // Only allow cancellation if no tx_hash (funds not sent)
      if (deposit.tx_hash && deposit.tx_hash.length > 0) {
        return {
          success: false,
          error: 'Нельзя отменить депозит после отправки средств',
        };
      }

      deposit.status = TransactionStatus.FAILED;
      await this.depositRepository.save(deposit);

      logger.info('Deposit cancelled by user', {
        depositId,
        userId,
        level: deposit.level,
      });

      return { success: true };
    } catch (error) {
      logger.error('Error cancelling deposit', {
        depositId,
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      return { success: false, error: 'Ошибка при отмене депозита' };
    }
  }
}

export default new DepositService();
