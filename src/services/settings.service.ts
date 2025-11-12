/**
 * Settings Service
 * Manages system-wide runtime configuration settings
 *
 * Features:
 * - In-memory cache with 60s TTL for performance
 * - Admin-configurable settings without app restart
 * - Type-safe getters for specific settings
 *
 * Settings:
 * - DEPOSITS_MAX_OPEN_LEVEL: Maximum deposit level open to users (1-5)
 */

import { AppDataSource } from '../database/data-source';
import { SystemSetting } from '../database/entities';
import { createLogger } from '../utils/logger.util';

const logger = createLogger('SettingsService');

interface CacheEntry {
  value: string;
  timestamp: number;
}

export class SettingsService {
  private repo = AppDataSource.getRepository(SystemSetting);
  private cache = new Map<string, CacheEntry>();
  private readonly TTL = 60_000; // 60 seconds

  /**
   * Get setting value with cache
   */
  async get(key: string, fallback?: string): Promise<string> {
    const now = Date.now();
    const cached = this.cache.get(key);

    // Return cached value if fresh
    if (cached && (now - cached.timestamp) < this.TTL) {
      return cached.value;
    }

    // Fetch from database
    const row = await this.repo.findOne({ where: { key } });
    const value = row?.value ?? (fallback ?? '');

    // Update cache
    this.cache.set(key, { value, timestamp: now });

    logger.debug('Setting fetched', { key, value, cached: !!cached });
    return value;
  }

  /**
   * Set setting value and invalidate cache
   */
  async set(key: string, value: string): Promise<void> {
    await this.repo.save({ key, value, updated_at: new Date() });
    this.cache.delete(key);

    logger.info('Setting updated', { key, value });
  }

  /**
   * Get maximum open deposit level (1-5)
   * Default: 1 (only Level 1 / 10 USDT open)
   */
  async getMaxOpenLevel(): Promise<number> {
    const value = await this.get('DEPOSITS_MAX_OPEN_LEVEL', '1');
    const parsed = parseInt(value, 10);

    // Validate: must be 1-5
    if (isNaN(parsed) || parsed < 1 || parsed > 5) {
      logger.warn('Invalid DEPOSITS_MAX_OPEN_LEVEL value, using default 1', { value });
      return 1;
    }

    return parsed;
  }

  /**
   * Set maximum open deposit level (1-5)
   */
  async setMaxOpenLevel(level: number): Promise<void> {
    if (level < 1 || level > 5) {
      throw new Error('Level must be between 1 and 5');
    }

    await this.set('DEPOSITS_MAX_OPEN_LEVEL', String(level));
    logger.info('Max open level updated', { level });
  }

  /**
   * Clear all cache (useful for testing)
   */
  clearCache(): void {
    this.cache.clear();
    logger.debug('Settings cache cleared');
  }
}

export const settingsService = new SettingsService();
export default settingsService;
