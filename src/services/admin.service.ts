/**
 * Admin Service
 * Handles admin management, authentication, and session control
 */

import { AppDataSource } from '../database/data-source';
import { Admin, AdminSession } from '../database/entities';
import { createLogger } from '../utils/logger.util';
import {
  generateMasterKey,
  hashMasterKey,
  verifyMasterKey,
  generateSessionToken,
  getSessionExpiration,
  isValidMasterKeyFormat,
} from '../utils/admin-auth.util';
import { LessThan } from 'typeorm';

const logger = createLogger('AdminService');

export class AdminService {
  private adminRepository = AppDataSource.getRepository(Admin);
  private sessionRepository = AppDataSource.getRepository(AdminSession);

  /**
   * Create new admin with master key (Super Admin only)
   */
  async createAdmin(data: {
    telegramId: number;
    username?: string;
    role: 'admin' | 'super_admin';
    createdBy: number;
  }): Promise<{ admin?: Admin; masterKey?: string; error?: string }> {
    try {
      // Check if admin already exists
      const existing = await this.adminRepository.findOne({
        where: { telegram_id: data.telegramId },
      });

      if (existing) {
        return { error: 'Админ с таким Telegram ID уже существует' };
      }

      // Generate master key
      const plainMasterKey = generateMasterKey();
      const hashedMasterKey = await hashMasterKey(plainMasterKey);

      // Create admin
      const admin = this.adminRepository.create({
        telegram_id: data.telegramId,
        username: data.username,
        role: data.role,
        master_key: hashedMasterKey,
        created_by: data.createdBy,
      });

      await this.adminRepository.save(admin);

      logger.info('Admin created', {
        adminId: admin.id,
        telegramId: data.telegramId,
        role: data.role,
        createdBy: data.createdBy,
      });

      return { admin, masterKey: plainMasterKey };
    } catch (error) {
      logger.error('Error creating admin', {
        telegramId: data.telegramId,
        error: error instanceof Error ? error.message : String(error),
      });
      return { error: 'Не удалось создать администратора' };
    }
  }

  /**
   * Authenticate admin with master key and create session
   */
  async login(data: {
    telegramId: number;
    masterKey: string;
    ipAddress?: string;
    userAgent?: string;
  }): Promise<{ session?: AdminSession; admin?: Admin; error?: string }> {
    try {
      // Validate master key format
      if (!isValidMasterKeyFormat(data.masterKey)) {
        return { error: 'Неверный формат мастер-ключа' };
      }

      // Find admin
      const admin = await this.adminRepository.findOne({
        where: { telegram_id: data.telegramId },
      });

      if (!admin) {
        logger.warn('Admin not found', { telegramId: data.telegramId });
        return { error: 'Администратор не найден' };
      }

      if (!admin.master_key) {
        return { error: 'Мастер-ключ не установлен' };
      }

      // Verify master key
      const isValid = await verifyMasterKey(data.masterKey, admin.master_key);

      if (!isValid) {
        logger.warn('Invalid master key attempt', {
          adminId: admin.id,
          telegramId: data.telegramId,
        });
        return { error: 'Неверный мастер-ключ' };
      }

      // Deactivate all existing sessions for this admin
      await this.sessionRepository.update(
        { admin_id: admin.id, is_active: true },
        { is_active: false }
      );

      // Create new session
      const sessionToken = generateSessionToken();
      const session = this.sessionRepository.create({
        admin_id: admin.id,
        session_token: sessionToken,
        is_active: true,
        ip_address: data.ipAddress,
        user_agent: data.userAgent,
        expires_at: getSessionExpiration(),
      });

      await this.sessionRepository.save(session);

      logger.info('Admin logged in', {
        adminId: admin.id,
        telegramId: data.telegramId,
        sessionId: session.id,
      });

      return { session, admin };
    } catch (error) {
      logger.error('Error during admin login', {
        telegramId: data.telegramId,
        error: error instanceof Error ? error.message : String(error),
      });
      return { error: 'Ошибка при входе' };
    }
  }

  /**
   * Logout admin (deactivate session)
   */
  async logout(sessionToken: string): Promise<{ success: boolean }> {
    try {
      const result = await this.sessionRepository.update(
        { session_token: sessionToken, is_active: true },
        { is_active: false }
      );

      if (result.affected && result.affected > 0) {
        logger.info('Admin logged out', { sessionToken });
        return { success: true };
      }

      return { success: false };
    } catch (error) {
      logger.error('Error during logout', { error });
      return { success: false };
    }
  }

  /**
   * Validate session and update activity
   */
  async validateSession(
    sessionToken: string
  ): Promise<{ admin?: Admin; session?: AdminSession; error?: string }> {
    try {
      const session = await this.sessionRepository.findOne({
        where: { session_token: sessionToken, is_active: true },
        relations: ['admin'],
      });

      if (!session) {
        return { error: 'Сессия не найдена' };
      }

      // Check if session expired
      if (session.isExpired) {
        session.is_active = false;
        await this.sessionRepository.save(session);
        logger.info('Session expired', { sessionId: session.id });
        return { error: 'Сессия истекла. Войдите заново' };
      }

      // Update activity and extend expiration
      session.updateActivity();
      await this.sessionRepository.save(session);

      return { admin: session.admin, session };
    } catch (error) {
      logger.error('Error validating session', { error });
      return { error: 'Ошибка проверки сессии' };
    }
  }

  /**
   * Cleanup expired sessions (should be called periodically)
   */
  async cleanupExpiredSessions(): Promise<number> {
    try {
      const result = await this.sessionRepository.update(
        {
          is_active: true,
          expires_at: LessThan(new Date()),
        },
        { is_active: false }
      );

      const cleaned = result.affected || 0;

      if (cleaned > 0) {
        logger.info(`Cleaned up ${cleaned} expired admin sessions`);
      }

      return cleaned;
    } catch (error) {
      logger.error('Error cleaning up sessions', { error });
      return 0;
    }
  }

  /**
   * Get active sessions for admin
   */
  async getActiveSessions(adminId: number): Promise<AdminSession[]> {
    return await this.sessionRepository.find({
      where: { admin_id: adminId, is_active: true },
      order: { last_activity: 'DESC' },
    });
  }

  /**
   * Remove admin (Super Admin only)
   */
  async removeAdmin(
    adminId: number
  ): Promise<{ success: boolean; error?: string }> {
    try {
      // Deactivate all sessions
      await this.sessionRepository.update(
        { admin_id: adminId },
        { is_active: false }
      );

      // Delete admin
      const result = await this.adminRepository.delete({ id: adminId });

      if (result.affected && result.affected > 0) {
        logger.info('Admin removed', { adminId });
        return { success: true };
      }

      return { success: false, error: 'Админ не найден' };
    } catch (error) {
      logger.error('Error removing admin', { adminId, error });
      return { success: false, error: 'Ошибка при удалении админа' };
    }
  }

  /**
   * Get all admins
   */
  async getAllAdmins(): Promise<Admin[]> {
    return await this.adminRepository.find({
      order: { created_at: 'DESC' },
      relations: ['creator'],
    });
  }

  /**
   * Get admin by telegram ID
   */
  async getByTelegramId(telegramId: number): Promise<Admin | null> {
    return await this.adminRepository.findOne({
      where: { telegram_id: telegramId },
    });
  }

  /**
   * Regenerate master key for admin
   */
  async regenerateMasterKey(
    adminId: number
  ): Promise<{ masterKey?: string; error?: string }> {
    try {
      const admin = await this.adminRepository.findOne({
        where: { id: adminId },
      });

      if (!admin) {
        return { error: 'Админ не найден' };
      }

      // Generate new master key
      const plainMasterKey = generateMasterKey();
      const hashedMasterKey = await hashMasterKey(plainMasterKey);

      admin.master_key = hashedMasterKey;
      await this.adminRepository.save(admin);

      // Deactivate all sessions
      await this.sessionRepository.update(
        { admin_id: adminId },
        { is_active: false }
      );

      logger.info('Master key regenerated', { adminId });

      return { masterKey: plainMasterKey };
    } catch (error) {
      logger.error('Error regenerating master key', { adminId, error });
      return { error: 'Ошибка при генерации нового ключа' };
    }
  }
}

export default new AdminService();
