/**
 * Admin Middleware
 * Checks if user has admin privileges and validates session
 */

import { Context, MiddlewareFn } from 'telegraf';
import { AppDataSource } from '../../database/data-source';
import { Admin, AdminSession } from '../../database/entities';
import { ERROR_MESSAGES } from '../../utils/constants';
import { config } from '../../config';
import { createLogger, logSecurityEvent } from '../../utils/logger.util';
import adminService from '../../services/admin.service';

const logger = createLogger('AdminMiddleware');

// Store session tokens in-memory (telegram_id -> session_token)
const adminSessions = new Map<number, string>();

// Extend Context with admin status
export interface AdminContext extends Context {
  admin?: Admin;
  adminSession?: AdminSession;
  isAdmin: boolean;
  isSuperAdmin: boolean;
  isAuthenticated: boolean; // Has valid session
}

/**
 * Store admin session token
 */
export function setAdminSession(telegramId: number, sessionToken: string): void {
  adminSessions.set(telegramId, sessionToken);
}

/**
 * Get admin session token
 */
export function getAdminSession(telegramId: number): string | undefined {
  return adminSessions.get(telegramId);
}

/**
 * Clear admin session
 */
export function clearAdminSession(telegramId: number): void {
  adminSessions.delete(telegramId);
}

/**
 * Admin middleware - checks if user is admin and validates session
 */
export const adminMiddleware: MiddlewareFn<Context> = async (ctx, next) => {
  const telegramId = ctx.from?.id;

  if (!telegramId) {
    return next();
  }

  const adminCtx = ctx as AdminContext;
  adminCtx.isAuthenticated = false;
  adminCtx.isAdmin = false;
  adminCtx.isSuperAdmin = false;

  // Check if user is super admin from config (no session needed)
  const isSuperAdmin = telegramId === config.telegram.superAdminId;

  if (isSuperAdmin) {
    adminCtx.isAdmin = true;
    adminCtx.isSuperAdmin = true;
    adminCtx.isAuthenticated = true;
    return next();
  }

  // Load admin from database
  const adminRepository = AppDataSource.getRepository(Admin);

  try {
    const admin = await adminRepository.findOne({
      where: { telegram_id: telegramId },
    });

    if (!admin) {
      return next();
    }

    adminCtx.admin = admin;
    adminCtx.isAdmin = true;
    adminCtx.isSuperAdmin = admin.isSuperAdmin;

    // Check for active session
    const sessionToken = adminSessions.get(telegramId);

    if (sessionToken) {
      const { session, error } = await adminService.validateSession(sessionToken);

      if (session && !error) {
        adminCtx.adminSession = session;
        adminCtx.isAuthenticated = true;

        logger.debug('Admin session validated', {
          adminId: admin.id,
          telegramId: admin.telegram_id,
          sessionId: session.id,
          remainingMinutes: session.remainingTimeMinutes,
        });
      } else {
        // Session expired or invalid - clear it
        adminSessions.delete(telegramId);
        logger.info('Admin session invalidated', {
          adminId: admin.id,
          telegramId: admin.telegram_id,
          error,
        });
      }
    }
  } catch (error) {
    logger.error('Error loading admin', {
      telegramId,
      error: error instanceof Error ? error.message : String(error),
    });
  }

  return next();
};

/**
 * Require admin middleware
 * Blocks non-admin users
 */
export const requireAdmin: MiddlewareFn<Context> = async (ctx, next) => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isAdmin) {
    logSecurityEvent(
      'Non-admin attempted admin action',
      'medium',
      {
        telegramId: ctx.from?.id,
        username: ctx.from?.username,
        action: 'callbackQuery' in ctx ? ctx.callbackQuery?.data : undefined,
      }
    );

    await ctx.reply(ERROR_MESSAGES.ADMIN_ONLY);
    return;
  }

  return next();
};

/**
 * Require super admin middleware
 * Blocks non-super-admin users
 */
export const requireSuperAdmin: MiddlewareFn<Context> = async (ctx, next) => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isSuperAdmin) {
    logSecurityEvent(
      'Non-super-admin attempted super admin action',
      'high',
      {
        telegramId: ctx.from?.id,
        username: ctx.from?.username,
        isAdmin: adminCtx.isAdmin,
        action: 'callbackQuery' in ctx ? ctx.callbackQuery?.data : undefined,
      }
    );

    await ctx.reply('❌ Эта команда доступна только главному администратору.');
    return;
  }

  return next();
};

/**
 * Require authenticated admin middleware
 * Blocks admins without active session (except super admin)
 */
export const requireAuthenticated: MiddlewareFn<Context> = async (ctx, next) => {
  const adminCtx = ctx as AdminContext;

  // Super admin from config doesn't need session
  if (adminCtx.isSuperAdmin && ctx.from?.id === config.telegram.superAdminId) {
    return next();
  }

  if (!adminCtx.isAuthenticated) {
    logSecurityEvent(
      'Unauthenticated admin attempted action',
      'medium',
      {
        telegramId: ctx.from?.id,
        username: ctx.from?.username,
        isAdmin: adminCtx.isAdmin,
        action: 'callbackQuery' in ctx ? ctx.callbackQuery?.data : undefined,
      }
    );

    await ctx.reply(
      '🔐 Требуется аутентификация.\n\n' +
      'Используйте команду /admin_login для входа с мастер-ключом.\n\n' +
      'Сессия действует 1 час с момента последней активности.'
    );
    return;
  }

  return next();
};

export default adminMiddleware;
