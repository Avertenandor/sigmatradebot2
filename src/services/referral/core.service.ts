/**
 * Referral Core Service
 * Manages referral chains and relationships
 */

import { EntityManager } from 'typeorm';
import { AppDataSource } from '../../database/data-source';
import { Referral, User } from '../../database/entities';
import { createLogger } from '../../utils/logger.util';
import { REFERRAL_DEPTH } from '../../utils/constants';
import { notificationService } from '../notification.service';

const logger = createLogger('ReferralCoreService');

export class ReferralCoreService {
  private referralRepository = AppDataSource.getRepository(Referral);
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
   * FIX #9 & #10: Now accepts optional EntityManager for atomic transactions
   */
  async createReferralRelationships(
    newUserId: number,
    directReferrerId: number,
    transactionManager?: EntityManager
  ): Promise<{ success: boolean; error?: string }> {
    // FIX #10: Use transaction manager if provided, otherwise use normal repositories
    const referralRepo = transactionManager
      ? transactionManager.getRepository(Referral)
      : this.referralRepository;

    const userRepo = transactionManager
      ? transactionManager.getRepository(User)
      : this.userRepository;

    try {
      // Get new user info for notification
      const newUser = await userRepo.findOne({ where: { id: newUserId } });

      // Get referral chain from direct referrer
      const referrers = await this.getReferralChain(directReferrerId, REFERRAL_DEPTH);

      // Add direct referrer as level 1
      // FIX #11: Add null check for direct referrer
      const directReferrer = await userRepo.findOne({ where: { id: directReferrerId } });
      if (!directReferrer) {
        return {
          success: false,
          error: 'Реферер не найден',
        };
      }

      referrers.unshift(directReferrer);

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

      // FIX #10: Collect all referrals to create atomically
      const referralsToCreate: Partial<Referral>[] = [];

      // Create referral records for each level
      for (let i = 0; i < referrers.length && i < REFERRAL_DEPTH; i++) {
        const referrer = referrers[i];
        const level = i + 1; // Level 1, 2, 3

        // FIX #11: Add null check for referrer
        if (!referrer) {
          logger.warn('Referrer is null at level', { level, newUserId, directReferrerId });
          continue;
        }

        // Check if relationship already exists
        const existing = await referralRepo.findOne({
          where: {
            referrer_id: referrer.id,
            referral_id: newUserId,
          },
        });

        if (!existing) {
          referralsToCreate.push({
            referrer_id: referrer.id,
            referral_id: newUserId,
            level,
            total_earned: '0',
          });

          logger.debug('Referral relationship prepared for creation', {
            referrerId: referrer.id,
            referralId: newUserId,
            level,
          });
        }
      }

      // FIX #10: Create all referrals at once (atomic)
      if (referralsToCreate.length > 0) {
        await referralRepo.save(referralsToCreate);

        logger.info('Referral chain created atomically', {
          newUserId,
          directReferrerId,
          levelsCreated: referralsToCreate.length,
        });
      }

      return { success: true };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      logger.error('Error creating referral relationships', {
        newUserId,
        directReferrerId,
        error: errorMessage,
      });
      return {
        success: false,
        error: `Не удалось создать реферальную связь: ${errorMessage.includes('duplicate') ? 'связь уже существует' : errorMessage.includes('not found') ? 'реферер не найден' : 'внутренняя ошибка'}`,
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
}

export default new ReferralCoreService();
