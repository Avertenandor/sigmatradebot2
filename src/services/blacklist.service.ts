/**
 * Blacklist Service
 * Manages pre-registration ban list (blacklist)
 * Prevents unwanted users from registering
 */

import { AppDataSource } from '../database/data-source';
import { Blacklist } from '../database/entities';
import { createLogger, logAdminAction } from '../utils/logger.util';

const logger = createLogger('BlacklistService');

class BlacklistService {
  private repo = AppDataSource.getRepository(Blacklist);

  /**
   * Check if telegram ID is blacklisted
   */
  async isBlacklisted(telegramId: number): Promise<boolean> {
    try {
      const entry = await this.repo.findOne({ where: { telegram_id: telegramId } });
      return !!entry;
    } catch (error) {
      logger.error('Error checking blacklist', {
        telegramId,
        error: error instanceof Error ? error.message : String(error),
      });
      return false;
    }
  }

  /**
   * Add telegram ID to blacklist
   * Idempotent - returns success if already exists
   */
  async add(
    telegramId: number,
    adminId?: number,
    reason?: string
  ): Promise<{ success: boolean; error?: string }> {
    try {
      // Check if already exists (idempotent)
      const exists = await this.repo.findOne({ where: { telegram_id: telegramId } });
      if (exists) {
        logger.debug('User already in blacklist', { telegramId });
        return { success: true }; // Already blacklisted - success
      }

      // Create new entry
      const entry = this.repo.create({
        telegram_id: telegramId,
        reason: reason?.trim() || null,
        created_by_admin_id: adminId || null,
      });

      await this.repo.save(entry);

      logAdminAction(adminId || 0, 'blacklist_add', { telegramId, reason });
      logger.info('Added to blacklist', { telegramId, adminId, reason });

      return { success: true };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      logger.error('Failed to add to blacklist', {
        telegramId,
        adminId,
        error: errorMessage,
      });
      return { success: false, error: 'Ошибка базы данных' };
    }
  }

  /**
   * Remove telegram ID from blacklist
   */
  async remove(
    telegramId: number,
    adminId?: number
  ): Promise<{ success: boolean; error?: string }> {
    try {
      const result = await this.repo.delete({ telegram_id: telegramId });

      logAdminAction(adminId || 0, 'blacklist_remove', {
        telegramId,
        affected: result.affected || 0,
      });

      logger.info('Removed from blacklist', {
        telegramId,
        adminId,
        removed: result.affected || 0,
      });

      return { success: true };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      logger.error('Failed to remove from blacklist', {
        telegramId,
        adminId,
        error: errorMessage,
      });
      return { success: false, error: 'Ошибка базы данных' };
    }
  }

  /**
   * Get blacklist entry with details
   */
  async getEntry(telegramId: number): Promise<Blacklist | null> {
    try {
      return await this.repo.findOne({ where: { telegram_id: telegramId } });
    } catch (error) {
      logger.error('Error getting blacklist entry', {
        telegramId,
        error: error instanceof Error ? error.message : String(error),
      });
      return null;
    }
  }

  /**
   * Get total blacklist count
   */
  async getCount(): Promise<number> {
    try {
      return await this.repo.count();
    } catch (error) {
      logger.error('Error getting blacklist count', {
        error: error instanceof Error ? error.message : String(error),
      });
      return 0;
    }
  }
}

export const blacklistService = new BlacklistService();
export default blacklistService;
