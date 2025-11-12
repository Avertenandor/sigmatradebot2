/**
 * Financial Password Recovery Service
 *
 * Manages user requests to reset their financial password
 * SLA: 3-5 business days for manual admin processing
 *
 * Process:
 * 1. User creates request → BLOCKS ALL EARNINGS → notifies all admins
 * 2. Admin conducts video verification OUTSIDE bot (Telegram/WhatsApp/etc)
 * 3. Admin reviews → changes status to 'in_review'
 * 4. Admin approves → generates new password, sends to user
 * 5. User receives new password via bot (1-hour TTL for repeat view)
 * 6. User successfully uses new password → UNBLOCKS EARNINGS
 *
 * CRITICAL Security:
 * - ALL earnings blocked from request creation until first successful password use
 * - Prevents unauthorized withdrawals during recovery period
 * - User must prove possession of new password before earnings resume
 *
 * Anti-abuse:
 * - Unique constraint: only one open request per user
 * - Optional: Add cooldown period (e.g., 30 days between requests)
 *
 * Video Verification:
 * - Conducted OUTSIDE bot via external channels (Telegram DM, WhatsApp, etc)
 * - Fields video_required/video_verified are admin markers only
 * - Bot does not handle video upload/storage
 */

import { AppDataSource } from '../database/data-source';
import { FinancialPasswordRecovery, User } from '../database/entities';
import { createLogger, logAdminAction } from '../utils/logger.util';
import { generateFinancialPassword, hashPassword } from '../utils/crypto.util';
import { notificationService } from './notification.service';
import Redis from 'ioredis';
import { config } from '../config';

const logger = createLogger('FinpassRecoveryService');

// Redis client for 1-hour password reveal TTL (same pattern as registration)
const redis = new Redis({
  host: config.redis.host,
  port: config.redis.port,
  password: config.redis.password,
  db: config.redis.db,
});

export class FinpassRecoveryService {
  private repo = AppDataSource.getRepository(FinancialPasswordRecovery);
  private userRepo = AppDataSource.getRepository(User);

  /**
   * Create recovery request from user
   * Prevents duplicate open requests via unique constraint
   *
   * CRITICAL: Blocks ALL earnings for user during recovery period
   * Earnings will be unblocked only after user successfully uses new password
   *
   * @returns requestId if successful
   */
  async createRequest(userId: number): Promise<{ success: boolean; error?: string; requestId?: number }> {
    try {
      // Check for existing open request
      const existing = await this.repo.findOne({
        where: [
          { user_id: userId, status: 'pending' },
          { user_id: userId, status: 'in_review' },
          { user_id: userId, status: 'approved' },
        ],
      });

      if (existing) {
        // Return existing request ID (idempotent)
        logger.info('User already has open finpass recovery request', {
          userId,
          requestId: existing.id,
          status: existing.status,
        });
        return { success: true, requestId: existing.id };
      }

      // CRITICAL: Block earnings during recovery period
      const user = await this.userRepo.findOne({ where: { id: userId } });
      if (!user) {
        return { success: false, error: 'Пользователь не найден' };
      }

      user.earnings_blocked = true;
      await this.userRepo.save(user);

      logger.warn('Earnings blocked for user during finpass recovery', {
        userId,
        telegram_id: user.telegram_id,
      });

      // Create new request
      const request = this.repo.create({
        user_id: userId,
        status: 'pending',
        video_required: true, // Note: video verification conducted outside bot
        video_verified: false,
      });

      const saved = await this.repo.save(request);

      // Notify all admins
      await notificationService.notifyAllAdmins(
        'Заявка на восстановление финпароля',
        `👤 Пользователь ID: ${userId}\n` +
        `🆔 Заявка: #${saved.id}\n\n` +
        `⏳ SLA: 3–5 рабочих дней\n` +
        `Требуется ручная проверка и сброс пароля.`
      ).catch(err => {
        logger.error('Failed to notify admins about finpass recovery request', {
          requestId: saved.id,
          error: err,
        });
      });

      logger.info('Finpass recovery request created', {
        userId,
        requestId: saved.id,
      });

      return { success: true, requestId: saved.id };
    } catch (error) {
      logger.error('Error creating finpass recovery request', {
        userId,
        error: error instanceof Error ? error.message : String(error),
      });
      return {
        success: false,
        error: 'Не удалось создать заявку. Попробуйте позже.',
      };
    }
  }

  /**
   * List pending recovery requests (for admin panel)
   *
   * @param limit Max number of requests to return
   */
  async listPending(limit = 20): Promise<FinancialPasswordRecovery[]> {
    return this.repo.find({
      where: [
        { status: 'pending' },
        { status: 'in_review' },
        { status: 'approved' },
      ],
      relations: ['user'],
      order: { created_at: 'ASC' }, // FIFO: oldest first
      take: limit,
    });
  }

  /**
   * Get single request by ID
   */
  async getRequest(requestId: number): Promise<FinancialPasswordRecovery | null> {
    return this.repo.findOne({
      where: { id: requestId },
      relations: ['user', 'processed_by_admin'],
    });
  }

  /**
   * Admin takes request for review
   */
  async takeInReview(requestId: number, adminId: number): Promise<boolean> {
    try {
      const request = await this.repo.findOne({ where: { id: requestId } });
      if (!request) return false;
      if (request.status === 'rejected' || request.status === 'sent') return false;

      request.status = 'in_review';
      request.processed_by_admin_id = adminId;
      await this.repo.save(request);

      logAdminAction(adminId, 'finpass_in_review', { requestId });
      logger.info('Finpass recovery request in review', {
        requestId,
        adminId,
      });

      return true;
    } catch (error) {
      logger.error('Error taking finpass request in review', {
        requestId,
        adminId,
        error,
      });
      return false;
    }
  }

  /**
   * Admin rejects request
   */
  async reject(requestId: number, adminId: number, comment?: string): Promise<boolean> {
    try {
      const request = await this.repo.findOne({ where: { id: requestId } });
      if (!request) return false;
      if (request.status === 'sent') return false; // Can't reject if already sent

      request.status = 'rejected';
      request.processed_by_admin_id = adminId;
      request.processed_at = new Date();
      request.admin_comment = comment || undefined;
      await this.repo.save(request);

      logAdminAction(adminId, 'finpass_reject', { requestId, comment });
      logger.info('Finpass recovery request rejected', {
        requestId,
        adminId,
        comment,
      });

      return true;
    } catch (error) {
      logger.error('Error rejecting finpass request', {
        requestId,
        adminId,
        error,
      });
      return false;
    }
  }

  /**
   * Admin approves and resets financial password
   *
   * Process:
   * 1. Generate new password (6-digit PIN)
   * 2. Hash with bcrypt
   * 3. Update user record
   * 4. Store plain password in Redis (1-hour TTL for repeat view)
   * 5. Send password to user via bot
   * 6. Mark request as 'sent'
   */
  async approveAndReset(requestId: number, adminId: number): Promise<{ success: boolean; error?: string }> {
    try {
      const request = await this.repo.findOne({
        where: { id: requestId },
        relations: ['user'],
      });

      if (!request || !request.user) {
        return { success: false, error: 'Заявка не найдена' };
      }

      if (request.status === 'sent') {
        return { success: false, error: 'Пароль уже был отправлен' };
      }

      if (request.status === 'rejected') {
        return { success: false, error: 'Заявка отклонена' };
      }

      // Get user
      const user = await this.userRepo.findOne({ where: { id: request.user_id } });
      if (!user) {
        return { success: false, error: 'Пользователь не найден' };
      }

      // Generate new password
      const plainPassword = generateFinancialPassword();
      const hashedPassword = await hashPassword(plainPassword);

      // Update user
      user.financial_password = hashedPassword;
      await this.userRepo.save(user);

      // Store plain password in Redis for 1-hour repeat view (same pattern as registration)
      const redisKey = `password:plain:${user.id}`;
      await redis.setex(redisKey, 3600, plainPassword); // 1 hour TTL

      // Update request
      request.status = 'sent';
      request.processed_by_admin_id = adminId;
      request.processed_at = new Date();
      await this.repo.save(request);

      // Send password to user
      const message = [
        '🔐 **Ваш финансовый пароль сброшен**',
        '',
        'Пожалуйста, сохраните новый пароль. Он потребуется для подтверждения финансовых операций.',
        '',
        `**Новый пароль:** \`${plainPassword}\``,
        '',
        '_⚠️ Пароль доступен повторно в течение **1 часа** через кнопку «Показать пароль ещё раз» в профиле_',
      ].join('\n');

      await notificationService.sendCustomMessage(user.telegram_id, message, {
        parse_mode: 'Markdown',
      }).catch((err: Error) => {
        logger.error('Failed to send finpass reset message to user', {
          userId: user.id,
          requestId,
          error: err,
        });
      });

      logAdminAction(adminId, 'finpass_reset_sent', {
        requestId,
        userId: user.id,
      });

      logger.info('Finpass reset and delivered', {
        requestId,
        userId: user.id,
        adminId,
      });

      return { success: true };
    } catch (error) {
      logger.error('Error approving and resetting finpass', {
        requestId,
        adminId,
        error: error instanceof Error ? error.message : String(error),
      });
      return {
        success: false,
        error: 'Не удалось сбросить пароль. Попробуйте позже.',
      };
    }
  }

  /**
   * Get user's last recovery request (for anti-abuse checks)
   */
  async getLastRequest(userId: number): Promise<FinancialPasswordRecovery | null> {
    return this.repo.findOne({
      where: { user_id: userId },
      order: { created_at: 'DESC' },
    });
  }
}

export const finpassRecoveryService = new FinpassRecoveryService();
export default finpassRecoveryService;
