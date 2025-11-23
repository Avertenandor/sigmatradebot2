/**
 * Auth Middleware
 * Checks if user is registered and verified
 */

import { Context, MiddlewareFn } from 'telegraf';
import { AppDataSource } from '../../database/data-source';
import { User } from '../../database/entities';
import { ERROR_MESSAGES } from '../../utils/constants';
import { createLogger } from '../../utils/logger.util';

const logger = createLogger('AuthMiddleware');

// Extend Context with user
export interface AuthContext extends Context {
  user?: User;
  isRegistered: boolean;
  isVerified: boolean;
}

/**
 * Auth middleware - loads user from database
 */
export const authMiddleware: MiddlewareFn<Context> = async (ctx, next) => {
  const telegramId = ctx.from?.id;

  if (!telegramId) {
    return next();
  }

  // Load user from database
  const userRepository = AppDataSource.getRepository(User);

  try {
    const user = await userRepository.findOne({
      where: { telegram_id: telegramId },
    });

    // Attach user to context
    (ctx as AuthContext).user = user || undefined;
    (ctx as AuthContext).isRegistered = !!user;
    (ctx as AuthContext).isVerified = user?.is_verified || false;

    if (user) {
      logger.debug('User loaded', {
        userId: user.id,
        telegramId: user.telegram_id,
        isVerified: user.is_verified,
      });
    }
  } catch (error) {
    logger.error('Error loading user', {
      telegramId,
      error: error instanceof Error ? error.message : String(error),
    });
  }

  return next();
};

/**
 * Require registration middleware
 * Blocks access if user is not registered
 */
export const requireAuth: MiddlewareFn<Context> = async (ctx, next) => {
  const authCtx = ctx as AuthContext;

  if (!authCtx.isRegistered) {
    await ctx.reply(ERROR_MESSAGES.USER_NOT_REGISTERED);
    return;
  }

  return next();
};

/**
 * Require verification middleware
 * Blocks access if user is not verified
 */
export const requireVerification: MiddlewareFn<Context> = async (ctx, next) => {
  const authCtx = ctx as AuthContext;

  if (!authCtx.isRegistered) {
    await ctx.reply(ERROR_MESSAGES.USER_NOT_REGISTERED);
    return;
  }

  if (!authCtx.isVerified) {
    await ctx.reply(ERROR_MESSAGES.USER_NOT_VERIFIED);
    return;
  }

  return next();
};

export default authMiddleware;
