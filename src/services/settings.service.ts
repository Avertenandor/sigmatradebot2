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
 * - SYSTEM_WALLET_ADDRESS: System wallet for receiving deposits
 * - PAYOUT_WALLET_ADDRESS: Wallet for sending payments
 * - WALLETS_VERSION: Version counter for wallet changes
 * - WALLET_CHANGE_REQUIRE_SECOND_APPROVER: Require second approver for wallet changes
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

  // ==================== WALLET MANAGEMENT ====================

  /**
   * Get system wallet address (for receiving deposits)
   * Fallback to ENV if not in database
   */
  async getSystemWalletAddress(): Promise<string> {
    const value = await this.get(
      'SYSTEM_WALLET_ADDRESS',
      process.env.SYSTEM_WALLET_ADDRESS || ''
    );

    if (!value) {
      throw new Error('SYSTEM_WALLET_ADDRESS not configured');
    }

    return value;
  }

  /**
   * Get payout wallet address (for sending payments)
   * Fallback to ENV if not in database
   */
  async getPayoutWalletAddress(): Promise<string> {
    const value = await this.get(
      'PAYOUT_WALLET_ADDRESS',
      process.env.PAYOUT_WALLET_ADDRESS || ''
    );

    if (!value) {
      throw new Error('PAYOUT_WALLET_ADDRESS not configured');
    }

    return value;
  }

  /**
   * Get wallets version (incremented on each change)
   */
  async getWalletsVersion(): Promise<number> {
    const value = await this.get('WALLETS_VERSION', '1');
    return parseInt(value, 10) || 1;
  }

  /**
   * Increment wallets version (called after applying wallet change)
   */
  async incrementWalletsVersion(): Promise<number> {
    const current = await this.getWalletsVersion();
    const next = current + 1;
    await this.set('WALLETS_VERSION', String(next));
    logger.info('Wallets version incremented', { from: current, to: next });
    return next;
  }

  /**
   * Set system wallet address (internal use - called by WalletAdminService)
   */
  async setSystemWalletAddress(address: string): Promise<void> {
    await this.set('SYSTEM_WALLET_ADDRESS', address);
    logger.info('System wallet address updated', { address });
  }

  /**
   * Set payout wallet address (internal use - called by WalletAdminService)
   */
  async setPayoutWalletAddress(address: string): Promise<void> {
    await this.set('PAYOUT_WALLET_ADDRESS', address);
    logger.info('Payout wallet address updated', { address });
  }

  /**
   * Check if wallet changes require second approver
   */
  async requiresSecondApprover(): Promise<boolean> {
    const value = await this.get('WALLET_CHANGE_REQUIRE_SECOND_APPROVER', 'false');
    return value.toLowerCase() === 'true';
  }

  /**
   * Set second approver requirement (only super_admin can change)
   */
  async setRequireSecondApprover(require: boolean): Promise<void> {
    await this.set('WALLET_CHANGE_REQUIRE_SECOND_APPROVER', String(require));
    logger.info('Second approver requirement updated', { require });
  }
}

export const settingsService = new SettingsService();
export default settingsService;
