/**
 * User Service
 * Business logic for user management
 */

import { In } from 'typeorm';
import { AppDataSource } from '../database/data-source';
import { User, Deposit, Referral, ReferralEarning } from '../database/entities';
import { createLogger } from '../utils/logger.util';
import { TransactionStatus } from '../utils/constants';
import {
  generateFinancialPassword,
  hashPassword,
  verifyPassword,
  generateReferralCode,
} from '../utils/crypto.util';
import {
  normalizeWalletAddress,
  isValidBSCAddress,
  isValidEmail,
  isValidPhone,
} from '../utils/validation.util';

const logger = createLogger('UserService');

export class UserService {
  private userRepository = AppDataSource.getRepository(User);

  /**
   * Find user by Telegram ID
   */
  async findByTelegramId(telegramId: number): Promise<User | null> {
    try {
      return await this.userRepository.findOne({
        where: { telegram_id: telegramId },
        relations: ['referrer'],
      });
    } catch (error) {
      logger.error('Error finding user by telegram ID', {
        telegramId,
        error: error instanceof Error ? error.message : String(error),
      });
      return null;
    }
  }

  /**
   * Find user by wallet address
   */
  async findByWalletAddress(walletAddress: string): Promise<User | null> {
    const normalizedAddress = normalizeWalletAddress(walletAddress);

    try {
      return await this.userRepository.findOne({
        where: { wallet_address: normalizedAddress },
      });
    } catch (error) {
      logger.error('Error finding user by wallet', {
        walletAddress: normalizedAddress,
        error: error instanceof Error ? error.message : String(error),
      });
      return null;
    }
  }

  /**
   * Find user by ID
   */
  async findById(userId: number): Promise<User | null> {
    try {
      return await this.userRepository.findOne({
        where: { id: userId },
        relations: ['referrer'],
      });
    } catch (error) {
      logger.error('Error finding user by ID', {
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      return null;
    }
  }

  /**
   * Create new user
   */
  async createUser(data: {
    telegramId: number;
    username?: string;
    walletAddress: string;
    referrerId?: number;
  }): Promise<{ user?: User; error?: string }> {
    // Validate wallet address
    if (!isValidBSCAddress(data.walletAddress)) {
      return { error: 'Неверный формат адреса кошелька' };
    }

    const normalizedAddress = normalizeWalletAddress(data.walletAddress);

    // Check if telegram ID already exists
    const existingByTelegramId = await this.findByTelegramId(data.telegramId);
    if (existingByTelegramId) {
      return { error: 'Telegram аккаунт уже зарегистрирован' };
    }

    // Check if wallet already exists
    const existingByWallet = await this.findByWalletAddress(normalizedAddress);
    if (existingByWallet) {
      return { error: 'Этот кошелек уже зарегистрирован' };
    }

    // Validate referrer if provided
    if (data.referrerId) {
      const referrer = await this.findById(data.referrerId);
      if (!referrer) {
        logger.warn('Invalid referrer ID provided', {
          referrerId: data.referrerId,
          telegramId: data.telegramId,
        });
        // Don't fail registration, just ignore invalid referrer
        data.referrerId = undefined;
      }
    }

    // Generate financial password
    const plainPassword = generateFinancialPassword();
    const hashedPassword = await hashPassword(plainPassword);

    try {
      // Create user
      const user = this.userRepository.create({
        telegram_id: data.telegramId,
        username: data.username,
        wallet_address: normalizedAddress,
        financial_password: hashedPassword,
        referrer_id: data.referrerId,
        is_verified: false,
        is_banned: false,
      });

      await this.userRepository.save(user);

      logger.info('User created', {
        userId: user.id,
        telegramId: user.telegram_id,
        wallet: user.maskedWallet,
        hasReferrer: !!data.referrerId,
      });

      // Attach plain password for returning to user (only this once!)
      (user as any).plainPassword = plainPassword;

      return { user };
    } catch (error) {
      logger.error('Error creating user', {
        telegramId: data.telegramId,
        error: error instanceof Error ? error.message : String(error),
      });
      return { error: 'Ошибка при создании пользователя' };
    }
  }

  /**
   * Verify user and set contact info
   */
  async verifyUser(
    userId: number,
    contactInfo?: { phone?: string; email?: string }
  ): Promise<{ success: boolean; error?: string }> {
    try {
      const user = await this.findById(userId);

      if (!user) {
        return { success: false, error: 'Пользователь не найден' };
      }

      if (user.is_verified) {
        return { success: false, error: 'Пользователь уже верифицирован' };
      }

      // Validate contact info if provided
      if (contactInfo?.email && !isValidEmail(contactInfo.email)) {
        return { success: false, error: 'Неверный формат email' };
      }

      if (contactInfo?.phone && !isValidPhone(contactInfo.phone)) {
        return { success: false, error: 'Неверный формат телефона' };
      }

      // Update user
      user.is_verified = true;
      if (contactInfo?.phone) {
        user.phone = contactInfo.phone;
      }
      if (contactInfo?.email) {
        user.email = contactInfo.email;
      }

      await this.userRepository.save(user);

      logger.info('User verified', {
        userId: user.id,
        telegramId: user.telegram_id,
        hasPhone: !!user.phone,
        hasEmail: !!user.email,
      });

      return { success: true };
    } catch (error) {
      logger.error('Error verifying user', {
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      return { success: false, error: 'Ошибка при верификации' };
    }
  }

  /**
   * Ban user
   */
  async banUser(userId: number): Promise<{ success: boolean; error?: string }> {
    try {
      const user = await this.findById(userId);

      if (!user) {
        return { success: false, error: 'Пользователь не найден' };
      }

      user.is_banned = true;
      await this.userRepository.save(user);

      logger.warn('User banned', {
        userId: user.id,
        telegramId: user.telegram_id,
      });

      return { success: true };
    } catch (error) {
      logger.error('Error banning user', {
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      return { success: false, error: 'Ошибка при блокировке пользователя' };
    }
  }

  /**
   * Unban user
   */
  async unbanUser(userId: number): Promise<{ success: boolean; error?: string }> {
    try {
      const user = await this.findById(userId);

      if (!user) {
        return { success: false, error: 'Пользователь не найден' };
      }

      user.is_banned = false;
      await this.userRepository.save(user);

      logger.info('User unbanned', {
        userId: user.id,
        telegramId: user.telegram_id,
      });

      return { success: true };
    } catch (error) {
      logger.error('Error unbanning user', {
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      return { success: false, error: 'Ошибка при разблокировке пользователя' };
    }
  }

  /**
   * Get user balance information
   */
  async getUserBalance(userId: number): Promise<{
    availableBalance: number;
    totalEarned: number;
    totalPaid: number;
    pendingEarnings: number;
  } | null> {
    try {
      const user = await this.findById(userId);
      if (!user) {
        return null;
      }

      const referralRepo = AppDataSource.getRepository(Referral);
      const earningRepo = AppDataSource.getRepository(ReferralEarning);
      const transactionRepo = AppDataSource.getRepository(Transaction);

      // Get all referrals for this user
      const referrals = await referralRepo.find({
        where: { referrer_id: userId },
      });

      const referralIds = referrals.map(r => r.id);

      let totalEarned = 0;
      let pendingEarnings = 0;

      if (referralIds.length > 0) {
        // Get all earnings
        const earnings = await earningRepo.find({
          where: { referral_id: In(referralIds) },
        });

        totalEarned = earnings.reduce(
          (sum, earning) => sum + parseFloat(earning.amount),
          0
        );

        // Get pending earnings (not yet paid)
        const unpaidEarnings = earnings.filter(e => !e.paid);
        pendingEarnings = unpaidEarnings.reduce(
          (sum, earning) => sum + parseFloat(earning.amount),
          0
        );
      }

      // Get total paid out (confirmed withdrawal transactions)
      const withdrawals = await transactionRepo.find({
        where: {
          user_id: userId,
          type: TransactionType.WITHDRAWAL,
          status: TransactionStatus.CONFIRMED,
        },
      });

      const totalPaid = withdrawals.reduce(
        (sum, tx) => sum + parseFloat(tx.amount),
        0
      );

      const availableBalance = totalEarned - totalPaid;

      return {
        availableBalance,
        totalEarned,
        totalPaid,
        pendingEarnings,
      };
    } catch (error) {
      logger.error('Error getting user balance', {
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      return null;
    }
  }

  /**
   * Get user statistics
   */
  async getUserStats(userId: number): Promise<{
    totalDeposits: number;
    totalEarned: number;
    referralCount: number;
    activatedLevels: number[];
  } | null> {
    try {
      const user = await this.findById(userId);

      if (!user) {
        return null;
      }

      // Get deposit statistics
      const depositRepo = AppDataSource.getRepository(Deposit);
      const deposits = await depositRepo.find({
        where: {
          user_id: userId,
          status: TransactionStatus.CONFIRMED,
        },
      });

      const totalDeposits = deposits.reduce(
        (sum, deposit) => sum + parseFloat(deposit.amount),
        0
      );

      const activatedLevels = deposits.map(d => d.level).sort((a, b) => a - b);

      // Get referral count (direct referrals only)
      const referralRepo = AppDataSource.getRepository(Referral);
      const referralCount = await referralRepo.count({
        where: {
          referrer_id: userId,
          level: 1, // Only direct referrals
        },
      });

      // Get referral earnings (all earned from referrals)
      const referrals = await referralRepo.find({
        where: { referrer_id: userId },
      });

      const referralIds = referrals.map(r => r.id);

      let totalEarned = 0;
      if (referralIds.length > 0) {
        const earningRepo = AppDataSource.getRepository(ReferralEarning);
        const earnings = await earningRepo.find({
          where: { referral_id: In(referralIds) },
        });

        totalEarned = earnings.reduce(
          (sum, earning) => sum + parseFloat(earning.amount),
          0
        );
      }

      return {
        totalDeposits,
        totalEarned,
        referralCount,
        activatedLevels,
      };
    } catch (error) {
      logger.error('Error getting user stats', {
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      return null;
    }
  }

  /**
   * Generate referral link for user
   */
  generateReferralLink(userId: number, botUsername: string): string {
    const referralCode = generateReferralCode(userId);
    return `https://t.me/${botUsername}?start=ref_${referralCode}_${userId}`;
  }

  /**
   * Parse referral code from start command
   */
  parseReferralCode(startPayload: string): number | null {
    // Format: ref_{code}_{userId}
    const match = startPayload.match(/^ref_[a-zA-Z0-9]+_(\d+)$/);

    if (match) {
      return parseInt(match[1], 10);
    }

    return null;
  }

  /**
   * Get total user count
   */
  async getTotalUsers(): Promise<number> {
    try {
      return await this.userRepository.count();
    } catch (error) {
      logger.error('Error getting total users', {
        error: error instanceof Error ? error.message : String(error),
      });
      return 0;
    }
  }

  /**
   * Get verified user count
   */
  async getVerifiedUsers(): Promise<number> {
    try {
      return await this.userRepository.count({
        where: { is_verified: true },
      });
    } catch (error) {
      logger.error('Error getting verified users', {
        error: error instanceof Error ? error.message : String(error),
      });
      return 0;
    }
  }

  /**
   * Verify user's financial password
   */
  async verifyFinancialPassword(
    userId: number,
    password: string
  ): Promise<{ success: boolean; error?: string }> {
    try {
      const user = await this.userRepository.findOne({
        where: { id: userId },
      });

      if (!user) {
        return { success: false, error: 'Пользователь не найден' };
      }

      if (!user.financial_password) {
        return { success: false, error: 'Финансовый пароль не установлен' };
      }

      const isValid = await verifyPassword(password, user.financial_password);

      if (!isValid) {
        logger.warn('Failed financial password verification attempt', {
          userId,
        });
        return { success: false, error: 'Неверный финансовый пароль' };
      }

      logger.info('Financial password verified successfully', {
        userId,
      });

      return { success: true };
    } catch (error) {
      logger.error('Error verifying financial password', {
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      return { success: false, error: 'Ошибка при проверке пароля' };
    }
  }
}

export default new UserService();
