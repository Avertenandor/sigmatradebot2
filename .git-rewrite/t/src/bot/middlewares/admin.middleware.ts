/**
 * Admin Middleware
 * Checks if user has admin privileges
 */

import { Context, MiddlewareFn } from 'telegraf';
import { AppDataSource } from '../../database/data-source';
import { Admin } from '../../database/entities';
import { ERROR_MESSAGES } from '../../utils/constants';
import { config } from '../../config';
import { createLogger, logSecurityEvent } from '../../utils/logger.util';

const logger = createLogger('AdminMiddleware');

// Extend Context with admin status
export interface AdminContext extends Context {
  admin?: Admin;
  isAdmin: boolean;
  isSuperAdmin: boolean;
}

/**
 * Admin middleware - checks if user is admin
 */
export const adminMiddleware: MiddlewareFn<Context> = async (ctx, next) => {
  const telegramId = ctx.from?.id;

  if (!telegramId) {
    return next();
  }

  // Check if user is super admin from config
  const isSuperAdmin = telegramId === config.telegram.superAdminId;

  if (isSuperAdmin) {
    (ctx as AdminContext).isAdmin = true;
    (ctx as AdminContext).isSuperAdmin = true;
    return next();
  }

  // Load admin from database
  const adminRepository = AppDataSource.getRepository(Admin);

  try {
    const admin = await adminRepository.findOne({
      where: { telegram_id: telegramId },
    });

    (ctx as AdminContext).admin = admin || undefined;
    (ctx as AdminContext).isAdmin = !!admin;
    (ctx as AdminContext).isSuperAdmin = admin?.isSuperAdmin || false;

    if (admin) {
      logger.debug('Admin loaded', {
        adminId: admin.id,
        telegramId: admin.telegram_id,
        role: admin.role,
      });
    }
  } catch (error) {
    logger.error('Error loading admin', {
      telegramId,
      error: error instanceof Error ? error.message : String(error),
    });

    (ctx as AdminContext).isAdmin = false;
    (ctx as AdminContext).isSuperAdmin = false;
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

export default adminMiddleware;
