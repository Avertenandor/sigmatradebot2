/**
 * Reward Service
 * Manages reward sessions and deposit reward calculations
 */

import { AppDataSource } from '../database/data-source';
import { RewardSession, DepositReward, Deposit } from '../database/entities';
import { createLogger } from '../utils/logger.util';
import { Between, LessThanOrEqual, MoreThanOrEqual, IsNull } from 'typeorm';
import { fromDbString, fromUsdtString, toUsdtString, sum as sumMoney, type MoneyAmount } from '../utils/money.util';

const logger = createLogger('RewardService');

export class RewardService {
  private rewardSessionRepository = AppDataSource.getRepository(RewardSession);
  private depositRewardRepository = AppDataSource.getRepository(DepositReward);
  private depositRepository = AppDataSource.getRepository(Deposit);

  /**
   * Create new reward session
   */
  async createSession(data: {
    name: string;
    rewardRates: Record<number, number>; // { 1: 1.117, 2: 1.5, ... }
    startDate: Date;
    endDate: Date;
    createdBy: number;
  }): Promise<{ session?: RewardSession; error?: string }> {
    try {
      // Validate dates
      if (data.startDate >= data.endDate) {
        return { error: 'Дата начала должна быть раньше даты окончания' };
      }

      // Validate reward rates
      for (let level = 1; level <= 5; level++) {
        if (!data.rewardRates[level] || data.rewardRates[level] < 0) {
          return { error: `Некорректная ставка для уровня ${level}` };
        }
      }

      const session = this.rewardSessionRepository.create({
        name: data.name,
        reward_rate_level_1: data.rewardRates[1].toString(),
        reward_rate_level_2: data.rewardRates[2].toString(),
        reward_rate_level_3: data.rewardRates[3].toString(),
        reward_rate_level_4: data.rewardRates[4].toString(),
        reward_rate_level_5: data.rewardRates[5].toString(),
        start_date: data.startDate,
        end_date: data.endDate,
        is_active: true,
        created_by: data.createdBy,
      });

      await this.rewardSessionRepository.save(session);

      logger.info('Reward session created', {
        sessionId: session.id,
        name: session.name,
        createdBy: data.createdBy,
      });

      return { session };
    } catch (error) {
      logger.error('Error creating reward session', { error });
      return { error: 'Не удалось создать сессию наград' };
    }
  }

  /**
   * Update reward session
   */
  async updateSession(
    sessionId: number,
    data: {
      name?: string;
      rewardRates?: Record<number, number>;
      startDate?: Date;
      endDate?: Date;
      isActive?: boolean;
    }
  ): Promise<{ success: boolean; error?: string }> {
    try {
      const session = await this.rewardSessionRepository.findOne({
        where: { id: sessionId },
      });

      if (!session) {
        return { success: false, error: 'Сессия не найдена' };
      }

      if (data.name) session.name = data.name;
      if (data.startDate) session.start_date = data.startDate;
      if (data.endDate) session.end_date = data.endDate;
      if (typeof data.isActive === 'boolean') session.is_active = data.isActive;

      if (data.rewardRates) {
        if (data.rewardRates[1] !== undefined) session.reward_rate_level_1 = data.rewardRates[1].toString();
        if (data.rewardRates[2] !== undefined) session.reward_rate_level_2 = data.rewardRates[2].toString();
        if (data.rewardRates[3] !== undefined) session.reward_rate_level_3 = data.rewardRates[3].toString();
        if (data.rewardRates[4] !== undefined) session.reward_rate_level_4 = data.rewardRates[4].toString();
        if (data.rewardRates[5] !== undefined) session.reward_rate_level_5 = data.rewardRates[5].toString();
      }

      // Validate dates
      if (session.start_date >= session.end_date) {
        return { success: false, error: 'Дата начала должна быть раньше даты окончания' };
      }

      await this.rewardSessionRepository.save(session);

      logger.info('Reward session updated', { sessionId });

      return { success: true };
    } catch (error) {
      logger.error('Error updating reward session', { sessionId, error });
      return { success: false, error: 'Не удалось обновить сессию' };
    }
  }

  /**
   * Delete reward session
   */
  async deleteSession(sessionId: number): Promise<{ success: boolean; error?: string }> {
    try {
      // Check if rewards have been calculated
      const rewardsCount = await this.depositRewardRepository.count({
        where: { reward_session_id: sessionId },
      });

      if (rewardsCount > 0) {
        return {
          success: false,
          error: `Невозможно удалить сессию с ${rewardsCount} начисленными наградами. Деактивируйте сессию вместо удаления.`,
        };
      }

      const result = await this.rewardSessionRepository.delete({ id: sessionId });

      if (result.affected && result.affected > 0) {
        logger.info('Reward session deleted', { sessionId });
        return { success: true };
      }

      return { success: false, error: 'Сессия не найдена' };
    } catch (error) {
      logger.error('Error deleting reward session', { sessionId, error });
      return { success: false, error: 'Не удалось удалить сессию' };
    }
  }

  /**
   * Get all reward sessions
   */
  async getAllSessions(): Promise<RewardSession[]> {
    return await this.rewardSessionRepository.find({
      relations: ['creator'],
      order: { created_at: 'DESC' },
    });
  }

  /**
   * Get active reward sessions
   */
  async getActiveSessions(): Promise<RewardSession[]> {
    const now = new Date();

    return await this.rewardSessionRepository.find({
      where: {
        is_active: true,
        start_date: LessThanOrEqual(now),
        end_date: MoreThanOrEqual(now),
      },
      order: { start_date: 'DESC' },
    });
  }

  /**
   * Get reward session by ID
   */
  async getSessionById(sessionId: number): Promise<RewardSession | null> {
    return await this.rewardSessionRepository.findOne({
      where: { id: sessionId },
      relations: ['creator'],
    });
  }

  /**
   * Calculate rewards for a session
   * Finds all eligible deposits and creates reward records
   */
  async calculateRewardsForSession(sessionId: number): Promise<{
    success: boolean;
    rewardsCalculated?: number;
    totalRewardAmount?: number;
    error?: string;
  }> {
    try {
      const session = await this.getSessionById(sessionId);

      if (!session) {
        return { success: false, error: 'Сессия не найдена' };
      }

      if (!session.is_active) {
        return { success: false, error: 'Сессия неактивна' };
      }

      // Find all confirmed deposits within the session period
      const deposits = await this.depositRepository.find({
        where: {
          status: 'confirmed',
          confirmed_at: Between(session.start_date, session.end_date),
        },
        relations: ['user'],
      });

      logger.info('Calculating rewards for session', {
        sessionId,
        depositsFound: deposits.length,
      });

      let rewardsCalculated = 0;
      const totalRewardAmounts: MoneyAmount[] = [];  // Collect for precise summation

      for (const deposit of deposits) {
        // CRITICAL: Skip rewards if user has earnings blocked (finpass recovery)
        if (deposit.user.earnings_blocked) {
          logger.warn('Skipped deposit reward - earnings blocked during finpass recovery', {
            userId: deposit.user_id,
            depositId: deposit.id,
            telegram_id: deposit.user.telegram_id,
            reason: 'finpass_recovery_in_progress',
          });
          continue;
        }

        // Check if reward already calculated for this deposit in this session
        const existingReward = await this.depositRewardRepository.findOne({
          where: {
            deposit_id: deposit.id,
            reward_session_id: sessionId,
          },
        });

        if (existingReward) {
          logger.debug('Reward already calculated for deposit', {
            depositId: deposit.id,
            sessionId,
          });
          continue;
        }

        // Get reward rate for deposit level
        const rewardRate = session.getRewardRateForLevel(deposit.level);

        if (rewardRate === 0) {
          logger.warn('No reward rate for deposit level', {
            depositId: deposit.id,
            level: deposit.level,
          });
          continue;
        }

        // CRITICAL: Use precise money calculation for deposit amount
        const depositAmountMoney: MoneyAmount = fromDbString(deposit.amount);

        // Calculate reward amount with percentage
        // For decimal rate percentage, convert to display string for calculation
        const depositAmountValue = parseFloat(toUsdtString(depositAmountMoney));
        const rewardAmountValue = (depositAmountValue * rewardRate) / 100;
        const rewardAmountStr = rewardAmountValue.toFixed(6);  // 6 decimals for USDT precision

        // Convert reward to MoneyAmount for precise summation
        const rewardAmountMoney = fromUsdtString(rewardAmountStr);

        // Create reward record
        const reward = this.depositRewardRepository.create({
          user_id: deposit.user_id,
          deposit_id: deposit.id,
          reward_session_id: sessionId,
          deposit_level: deposit.level,
          deposit_amount: deposit.amount,
          reward_rate: rewardRate.toString(),
          reward_amount: rewardAmountStr,
          paid: false,
        });

        await this.depositRewardRepository.save(reward);

        rewardsCalculated++;
        totalRewardAmounts.push(rewardAmountMoney);  // Collect for precise summation

        logger.debug('Reward calculated', {
          rewardId: reward.id,
          depositId: deposit.id,
          rewardAmount: rewardAmountStr,
        });
      }

      // CRITICAL: Use precise money summation instead of float accumulation
      const totalRewardMoney = sumMoney(totalRewardAmounts);
      const totalRewardAmount = parseFloat(toUsdtString(totalRewardMoney));  // Convert for return value

      logger.info('Rewards calculation completed', {
        sessionId,
        rewardsCalculated,
        totalRewardAmount,
      });

      return {
        success: true,
        rewardsCalculated,
        totalRewardAmount,
      };
    } catch (error) {
      logger.error('Error calculating rewards for session', { sessionId, error });
      return { success: false, error: 'Ошибка при расчете наград' };
    }
  }

  /**
   * Get session statistics
   */
  async getSessionStatistics(sessionId: number): Promise<{
    totalRewards: number;
    totalAmount: number;
    paidRewards: number;
    paidAmount: number;
    pendingRewards: number;
    pendingAmount: number;
  }> {
    const queryBuilder = this.depositRewardRepository
      .createQueryBuilder('reward')
      .where('reward.reward_session_id = :sessionId', { sessionId });

    const total = await queryBuilder.clone().getCount();

    const totalAmountResult = await queryBuilder
      .clone()
      .select('SUM(CAST(reward.reward_amount AS DECIMAL))', 'total')
      .getRawOne();

    const paid = await queryBuilder.clone().andWhere('reward.paid = :paid', { paid: true }).getCount();

    const paidAmountResult = await queryBuilder
      .clone()
      .select('SUM(CAST(reward.reward_amount AS DECIMAL))', 'total')
      .andWhere('reward.paid = :paid', { paid: true })
      .getRawOne();

    const pending = total - paid;

    const pendingAmountResult = await queryBuilder
      .clone()
      .select('SUM(CAST(reward.reward_amount AS DECIMAL))', 'total')
      .andWhere('reward.paid = :paid', { paid: false })
      .getRawOne();

    // CRITICAL: Use precise money conversion (no parseFloat!)
    const totalAmountMoney = fromDbString(totalAmountResult?.total || '0');
    const paidAmountMoney = fromDbString(paidAmountResult?.total || '0');
    const pendingAmountMoney = fromDbString(pendingAmountResult?.total || '0');

    return {
      totalRewards: total,
      totalAmount: parseFloat(toUsdtString(totalAmountMoney)),  // Convert for return value
      paidRewards: paid,
      paidAmount: parseFloat(toUsdtString(paidAmountMoney)),  // Convert for return value
      pendingRewards: pending,
      pendingAmount: parseFloat(toUsdtString(pendingAmountMoney)),  // Convert for return value
    };
  }

  /**
   * Get unpaid rewards for a user
   */
  async getUserUnpaidRewards(userId: number): Promise<DepositReward[]> {
    return await this.depositRewardRepository.find({
      where: {
        user_id: userId,
        paid: false,
      },
      relations: ['reward_session', 'deposit'],
      order: { calculated_at: 'DESC' },
    });
  }

  /**
   * Mark rewards as paid (bulk operation)
   */
  async markRewardsAsPaid(rewardIds: number[], txHash: string): Promise<{
    success: boolean;
    updated?: number;
    error?: string;
  }> {
    try {
      const result = await this.depositRewardRepository
        .createQueryBuilder()
        .update(DepositReward)
        .set({
          paid: true,
          paid_at: new Date(),
          tx_hash: txHash,
        })
        .whereInIds(rewardIds)
        .execute();

      logger.info('Rewards marked as paid', {
        rewardIds,
        txHash,
        updated: result.affected,
      });

      return { success: true, updated: result.affected };
    } catch (error) {
      logger.error('Error marking rewards as paid', { rewardIds, error });
      return { success: false, error: 'Не удалось отметить награды как выплаченные' };
    }
  }
}

export default new RewardService();
