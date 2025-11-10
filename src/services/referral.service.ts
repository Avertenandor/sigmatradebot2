/**
 * Referral Service
 * Business logic for referral program
 */

import { AppDataSource } from '../database/data-source';
import { Referral, ReferralEarning, User, Transaction } from '../database/entities';
import { createLogger } from '../utils/logger.util';
import { REFERRAL_RATES, REFERRAL_DEPTH } from '../utils/constants';
import { notificationService } from './notification.service';

const logger = createLogger('ReferralService');

export class ReferralService {
  private referralRepository = AppDataSource.getRepository(Referral);
  private referralEarningRepository = AppDataSource.getRepository(ReferralEarning);
  private userRepository = AppDataSource.getRepository(User);

  /**
   * Build referral chain for user up to N levels
   * Returns array of users from direct referrer to Nth level
   */
  async getReferralChain(
    userId: number,
    depth: number = REFERRAL_DEPTH
  ): Promise<User[]> {
    const chain: User[] = [];

    try {
      let currentUser = await this.userRepository.findOne({
        where: { id: userId },
        relations: ['referrer'],
      });

      for (let level = 0; level < depth && currentUser?.referrer; level++) {
        chain.push(currentUser.referrer);
        currentUser = await this.userRepository.findOne({
          where: { id: currentUser.referrer.id },
          relations: ['referrer'],
        });
      }

      return chain;
    } catch (error) {
      logger.error('Error getting referral chain', {
        userId,
        depth,
        error: error instanceof Error ? error.message : String(error),
      });
      return [];
    }
  }

  /**
   * Create or update referral relationships
   * Called when new user registers with referrer
   */
  async createReferralRelationships(
    newUserId: number,
    directReferrerId: number
  ): Promise<{ success: boolean; error?: string }> {
    try {
      // Get new user info for notification
      const newUser = await this.userRepository.findOne({ where: { id: newUserId } });

      // Get referral chain from direct referrer
      const referrers = await this.getReferralChain(directReferrerId, REFERRAL_DEPTH);

      // Add direct referrer as level 1
      referrers.unshift(
        (await this.userRepository.findOne({ where: { id: directReferrerId } }))!
      );

      // Detect referral loops: check if new user is already in the referral chain
      // This prevents circular referral chains (A → B → C → A)
      const referrerIds = referrers.map((r) => r.id);
      if (referrerIds.includes(newUserId)) {
        logger.warn('Referral loop detected', {
          newUserId,
          directReferrerId,
          chainIds: referrerIds,
        });
        return {
          success: false,
          error: 'Нельзя создать циклическую реферальную цепочку',
        };
      }

      // Also check if new user would become their own referrer
      if (newUserId === directReferrerId) {
        logger.warn('Self-referral attempt detected', {
          userId: newUserId,
        });
        return {
          success: false,
          error: 'Нельзя пригласить самого себя',
        };
      }

      // Track if direct referrer was notified
      let directReferrerNotified = false;

      // Create referral records for each level
      for (let i = 0; i < referrers.length && i < REFERRAL_DEPTH; i++) {
        const referrer = referrers[i];
        const level = i + 1; // Level 1, 2, 3

        // Check if relationship already exists
        const existing = await this.referralRepository.findOne({
          where: {
            referrer_id: referrer.id,
            referral_id: newUserId,
          },
        });

        if (!existing) {
          const referralRelation = this.referralRepository.create({
            referrer_id: referrer.id,
            referral_id: newUserId,
            level,
            total_earned: '0',
          });

          await this.referralRepository.save(referralRelation);

          logger.info('Referral relationship created', {
            referrerId: referrer.id,
            referralId: newUserId,
            level,
          });

          // Notify direct referrer (level 1 only) about new referral
          if (level === 1 && !directReferrerNotified && newUser) {
            try {
              const username = newUser.username ? `@${newUser.username}` : `ID ${newUser.telegram_id}`;
              await notificationService.sendNotification(
                referrer.telegram_id,
                `🎉 **Новый реферал!**\n\n` +
                `Пользователь ${username} зарегистрировался по вашей ссылке.\n` +
                `Вы будете получать вознаграждения от его депозитов.`
              );
              directReferrerNotified = true;

              logger.info('Referrer notified about new referral', {
                referrerId: referrer.id,
                referralId: newUserId,
              });
            } catch (notifError) {
              // Log but don't fail the referral creation if notification fails
              logger.error('Failed to notify referrer about new referral', {
                referrerId: referrer.id,
                referralId: newUserId,
                error: notifError instanceof Error ? notifError.message : String(notifError),
              });
            }
          }
        }
      }

      return { success: true };
    } catch (error) {
      logger.error('Error creating referral relationships', {
        newUserId,
        directReferrerId,
        error: error instanceof Error ? error.message : String(error),
      });
      return { success: false, error: 'Ошибка при создании реферальных связей' };
    }
  }

  /**
   * Calculate referral rewards for a transaction
   * Returns rewards for each level
   */
  calculateRewards(amount: number): Array<{
    level: number;
    rate: number;
    reward: number;
  }> {
    const rewards = [];

    for (let level = 1; level <= REFERRAL_DEPTH; level++) {
      const rate = REFERRAL_RATES[level as keyof typeof REFERRAL_RATES];
      const reward = amount * rate;

      rewards.push({ level, rate, reward });
    }

    return rewards;
  }

  /**
   * Process referral rewards for a deposit
   * Creates earning records for all referrers in chain
   */
  async processReferralRewards(
    userId: number,
    depositAmount: number,
    sourceTransactionId?: number
  ): Promise<{ success: boolean; rewards: number; error?: string }> {
    try {
      // Get all referral relationships where this user is the referral
      const relationships = await this.referralRepository.find({
        where: { referral_id: userId },
        relations: ['referrer'],
        order: { level: 'ASC' },
      });

      if (relationships.length === 0) {
        logger.debug('No referrers found for user', { userId });
        return { success: true, rewards: 0 };
      }

      let totalRewards = 0;

      // Create earning records for each referrer
      for (const relationship of relationships) {
        const level = relationship.level;
        const rate = REFERRAL_RATES[level as keyof typeof REFERRAL_RATES];
        const rewardAmount = depositAmount * rate;

        // Create earning record
        const earning = this.referralEarningRepository.create({
          referral_id: relationship.id,
          amount: rewardAmount.toFixed(8),
          source_transaction_id: sourceTransactionId,
          paid: false, // Will be paid by payment processor
        });

        await this.referralEarningRepository.save(earning);

        // Update total earned in relationship
        const currentTotal = parseFloat(relationship.total_earned);
        relationship.total_earned = (currentTotal + rewardAmount).toFixed(8);
        await this.referralRepository.save(relationship);

        totalRewards += rewardAmount;

        logger.info('Referral reward created', {
          referrerId: relationship.referrer_id,
          referralUserId: userId,
          level,
          rate,
          amount: rewardAmount,
          sourceTransactionId,
        });
      }

      return { success: true, rewards: totalRewards };
    } catch (error) {
      logger.error('Error processing referral rewards', {
        userId,
        depositAmount,
        error: error instanceof Error ? error.message : String(error),
      });
      return {
        success: false,
        rewards: 0,
        error: 'Ошибка при начислении реферальных вознаграждений',
      };
    }
  }

  /**
   * Get referral statistics for user
   */
  async getReferralStats(userId: number): Promise<{
    directReferrals: number;
    level2Referrals: number;
    level3Referrals: number;
    totalEarned: number;
    pendingEarnings: number;
    paidEarnings: number;
  }> {
    try {
      // Get all relationships where user is referrer
      const relationships = await this.referralRepository.find({
        where: { referrer_id: userId },
      });

      // Count by level
      const level1 = relationships.filter((r) => r.level === 1).length;
      const level2 = relationships.filter((r) => r.level === 2).length;
      const level3 = relationships.filter((r) => r.level === 3).length;

      // Calculate total earned
      const totalEarned = relationships.reduce(
        (sum, r) => sum + parseFloat(r.total_earned),
        0
      );

      // Get earnings
      const relationshipIds = relationships.map((r) => r.id);

      const earnings = await this.referralEarningRepository.find({
        where: relationshipIds.map((id) => ({ referral_id: id })),
      });

      const pendingEarnings = earnings
        .filter((e) => !e.paid)
        .reduce((sum, e) => sum + parseFloat(e.amount), 0);

      const paidEarnings = earnings
        .filter((e) => e.paid)
        .reduce((sum, e) => sum + parseFloat(e.amount), 0);

      return {
        directReferrals: level1,
        level2Referrals: level2,
        level3Referrals: level3,
        totalEarned,
        pendingEarnings,
        paidEarnings,
      };
    } catch (error) {
      logger.error('Error getting referral stats', {
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      return {
        directReferrals: 0,
        level2Referrals: 0,
        level3Referrals: 0,
        totalEarned: 0,
        pendingEarnings: 0,
        paidEarnings: 0,
      };
    }
  }

  /**
   * Get referral list by level
   */
  async getReferralsByLevel(
    userId: number,
    level: number,
    options?: { page?: number; limit?: number }
  ): Promise<{
    referrals: Array<{
      user: User;
      earned: number;
      joinedAt: Date;
    }>;
    total: number;
    page: number;
    pages: number;
  }> {
    const page = options?.page || 1;
    const limit = options?.limit || 10;
    const skip = (page - 1) * limit;

    try {
      const [relationships, total] = await this.referralRepository.findAndCount({
        where: {
          referrer_id: userId,
          level,
        },
        relations: ['referral_user'],
        order: { created_at: 'DESC' },
        take: limit,
        skip,
      });

      const referrals = relationships.map((r) => ({
        user: r.referral_user,
        earned: parseFloat(r.total_earned),
        joinedAt: r.created_at,
      }));

      const pages = Math.ceil(total / limit);

      return { referrals, total, page, pages };
    } catch (error) {
      logger.error('Error getting referrals by level', {
        userId,
        level,
        error: error instanceof Error ? error.message : String(error),
      });
      return { referrals: [], total: 0, page: 1, pages: 0 };
    }
  }

  /**
   * Get pending earnings to be paid
   */
  async getPendingEarnings(
    userId: number,
    options?: { page?: number; limit?: number }
  ): Promise<{
    earnings: ReferralEarning[];
    total: number;
    totalAmount: number;
    page: number;
    pages: number;
  }> {
    const page = options?.page || 1;
    const limit = options?.limit || 10;
    const skip = (page - 1) * limit;

    try {
      // Get user's referral relationships
      const relationships = await this.referralRepository.find({
        where: { referrer_id: userId },
      });

      const relationshipIds = relationships.map((r) => r.id);

      if (relationshipIds.length === 0) {
        return {
          earnings: [],
          total: 0,
          totalAmount: 0,
          page: 1,
          pages: 0,
        };
      }

      const [earnings, total] = await this.referralEarningRepository.findAndCount({
        where: relationshipIds.map((id) => ({
          referral_id: id,
          paid: false,
        })),
        order: { created_at: 'DESC' },
        take: limit,
        skip,
      });

      const totalAmount = earnings.reduce(
        (sum, e) => sum + parseFloat(e.amount),
        0
      );

      const pages = Math.ceil(total / limit);

      return { earnings, total, totalAmount, page, pages };
    } catch (error) {
      logger.error('Error getting pending earnings', {
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      return {
        earnings: [],
        total: 0,
        totalAmount: 0,
        page: 1,
        pages: 0,
      };
    }
  }

  /**
   * Mark earning as paid (called by payment processor)
   */
  async markEarningAsPaid(
    earningId: number,
    txHash: string
  ): Promise<{ success: boolean; error?: string }> {
    try {
      const earning = await this.referralEarningRepository.findOne({
        where: { id: earningId },
      });

      if (!earning) {
        return { success: false, error: 'Earning not found' };
      }

      if (earning.paid) {
        return { success: false, error: 'Already paid' };
      }

      earning.paid = true;
      earning.tx_hash = txHash;

      await this.referralEarningRepository.save(earning);

      logger.info('Earning marked as paid', {
        earningId,
        amount: earning.amount,
        txHash,
      });

      return { success: true };
    } catch (error) {
      logger.error('Error marking earning as paid', {
        earningId,
        error: error instanceof Error ? error.message : String(error),
      });
      return { success: false, error: 'Error marking as paid' };
    }
  }

  /**
   * Get platform referral statistics
   */
  async getPlatformReferralStats(): Promise<{
    totalReferrals: number;
    totalEarnings: number;
    paidEarnings: number;
    pendingEarnings: number;
    byLevel: Record<number, { count: number; earnings: number }>;
  }> {
    try {
      const relationships = await this.referralRepository.find();

      const byLevel: Record<number, { count: number; earnings: number }> = {
        1: { count: 0, earnings: 0 },
        2: { count: 0, earnings: 0 },
        3: { count: 0, earnings: 0 },
      };

      let totalEarnings = 0;

      relationships.forEach((r) => {
        byLevel[r.level].count++;
        const earned = parseFloat(r.total_earned);
        byLevel[r.level].earnings += earned;
        totalEarnings += earned;
      });

      // Get all earnings
      const earnings = await this.referralEarningRepository.find();

      const paidEarnings = earnings
        .filter((e) => e.paid)
        .reduce((sum, e) => sum + parseFloat(e.amount), 0);

      const pendingEarnings = earnings
        .filter((e) => !e.paid)
        .reduce((sum, e) => sum + parseFloat(e.amount), 0);

      return {
        totalReferrals: relationships.length,
        totalEarnings,
        paidEarnings,
        pendingEarnings,
        byLevel,
      };
    } catch (error) {
      logger.error('Error getting platform referral stats', {
        error: error instanceof Error ? error.message : String(error),
      });
      return {
        totalReferrals: 0,
        totalEarnings: 0,
        paidEarnings: 0,
        pendingEarnings: 0,
        byLevel: {
          1: { count: 0, earnings: 0 },
          2: { count: 0, earnings: 0 },
          3: { count: 0, earnings: 0 },
        },
      };
    }
  }

  /**
   * Get referral leaderboard
   * Returns top users by referral count and earnings
   */
  async getReferralLeaderboard(options: {
    limit?: number;
    sortBy?: 'referrals' | 'earnings';
  } = {}): Promise<{
    byReferrals: Array<{
      userId: number;
      username?: string;
      telegramId: number;
      referralCount: number;
      totalEarnings: number;
      rank: number;
    }>;
    byEarnings: Array<{
      userId: number;
      username?: string;
      telegramId: number;
      referralCount: number;
      totalEarnings: number;
      rank: number;
    }>;
  }> {
    const limit = options.limit || 10;

    try {
      // Get all users with their referral counts
      const usersWithReferrals = await this.referralRepository
        .createQueryBuilder('referral')
        .select('referral.referrer_id', 'userId')
        .addSelect('COUNT(DISTINCT referral.referral_id)', 'referralCount')
        .addSelect('SUM(CAST(referral.total_earned AS DECIMAL))', 'totalEarnings')
        .groupBy('referral.referrer_id')
        .having('COUNT(DISTINCT referral.referral_id) > 0')
        .getRawMany();

      // Fetch all users in a single query (fix N+1 query issue)
      const userIds = usersWithReferrals.map((item) => parseInt(item.userId));
      const users = await this.userRepository.findByIds(userIds);

      // Create user lookup map for O(1) access
      const userMap = new Map(users.map((user) => [user.id, user]));

      // Map user data using in-memory lookup
      const leaderboardData = usersWithReferrals.map((item) => {
        const userId = parseInt(item.userId);
        const user = userMap.get(userId);

        return {
          userId,
          username: user?.username,
          telegramId: user?.telegram_id || 0,
          referralCount: parseInt(item.referralCount || '0'),
          totalEarnings: parseFloat(item.totalEarnings || '0'),
        };
      });

      // Sort by referral count
      const byReferrals = [...leaderboardData]
        .sort((a, b) => b.referralCount - a.referralCount)
        .slice(0, limit)
        .map((item, index) => ({
          ...item,
          rank: index + 1,
        }));

      // Sort by earnings
      const byEarnings = [...leaderboardData]
        .sort((a, b) => b.totalEarnings - a.totalEarnings)
        .slice(0, limit)
        .map((item, index) => ({
          ...item,
          rank: index + 1,
        }));

      logger.debug('Referral leaderboard retrieved', {
        byReferralsCount: byReferrals.length,
        byEarningsCount: byEarnings.length,
      });

      return {
        byReferrals,
        byEarnings,
      };
    } catch (error) {
      logger.error('Error getting referral leaderboard', {
        error: error instanceof Error ? error.message : String(error),
      });
      return {
        byReferrals: [],
        byEarnings: [],
      };
    }
  }

  /**
   * Get user's position in leaderboard
   */
  async getUserLeaderboardPosition(userId: number): Promise<{
    referralRank: number | null;
    earningsRank: number | null;
    totalUsers: number;
  }> {
    try {
      const leaderboard = await this.getReferralLeaderboard({ limit: 1000 });

      const referralRank = leaderboard.byReferrals.findIndex(
        (item) => item.userId === userId
      );
      const earningsRank = leaderboard.byEarnings.findIndex(
        (item) => item.userId === userId
      );

      return {
        referralRank: referralRank >= 0 ? referralRank + 1 : null,
        earningsRank: earningsRank >= 0 ? earningsRank + 1 : null,
        totalUsers: leaderboard.byReferrals.length,
      };
    } catch (error) {
      logger.error('Error getting user leaderboard position', {
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      return {
        referralRank: null,
        earningsRank: null,
        totalUsers: 0,
      };
    }
  }
}

export default new ReferralService();
