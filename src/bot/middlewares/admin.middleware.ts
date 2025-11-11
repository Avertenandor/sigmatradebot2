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
import Redis from 'ioredis';

const logger = createLogger('AdminMiddleware');

// FIX #14: Redis client for persistent admin sessions (survives restarts)
const redis = new Redis({
  host: config.redis.host,
  port: config.redis.port,
  password: config.redis.password,
  db: config.redis.db,
});

// FIX #14: Admin session configuration
const ADMIN_SESSION_PREFIX = 'admin:session:';
const ADMIN_SESSION_TTL = 3600; // 1 hour (same as database session TTL)

// Extend Context with admin status
export interface AdminContext extends Context {
  admin?: Admin;
  adminSession?: AdminSession;
  isAdmin: boolean;
  isSuperAdmin: boolean;
  isAuthenticated: boolean; // Has valid session
}

/**
 * Store admin session token in Redis
 * FIX #14: Persistent storage, survives bot restarts
 */
export async function setAdminSession(
  telegramId: number,
  sessionToken: string
): Promise<void> {
  const key = `${ADMIN_SESSION_PREFIX}${telegramId}`;
  await redis.setex(key, ADMIN_SESSION_TTL, sessionToken);

  logger.info('Admin session stored in Redis', {
    telegramId,
    ttl: ADMIN_SESSION_TTL,
  });
}

/**
 * Get admin session token from Redis
 * FIX #14: Persistent storage, survives bot restarts
 */
export async function getAdminSession(
  telegramId: number
): Promise<string | null> {
  const key = `${ADMIN_SESSION_PREFIX}${telegramId}`;
  return await redis.get(key);
}

/**
 * Clear admin session from Redis
 * FIX #14: Persistent storage, survives bot restarts
 */
export async function clearAdminSession(telegramId: number): Promise<void> {
  const key = `${ADMIN_SESSION_PREFIX}${telegramId}`;
  await redis.del(key);

  logger.info('Admin session cleared from Redis', { telegramId });
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

    // FIX #14: Check for active session from Redis (not memory)
    const sessionToken = await getAdminSession(telegramId);

    if (sessionToken) {
      const { session, error } = await adminService.validateSession(sessionToken);

      if (session && !error) {
        adminCtx.adminSession = session;
        adminCtx.isAuthenticated = true;

        // FIX #14: Refresh Redis TTL on activity
        await setAdminSession(telegramId, sessionToken);

        logger.debug('Admin session validated', {
          adminId: admin.id,
          telegramId: admin.telegram_id,
          sessionId: session.id,
          remainingMinutes: session.remainingTimeMinutes,
        });
      } else {
        // Session expired or invalid - clear it from Redis
        await clearAdminSession(telegramId);
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
