/**
 * Ban Middleware
 * Blocks banned users from using the bot
 */

import { Context, MiddlewareFn } from 'telegraf';
import { AuthContext } from './auth.middleware';
import { ERROR_MESSAGES } from '../../utils/constants';
import { logSecurityEvent } from '../../utils/logger.util';

/**
 * Ban check middleware
 * Blocks banned users
 */
export const banMiddleware: MiddlewareFn<Context> = async (ctx, next) => {
  const authCtx = ctx as AuthContext;

  // Check if user exists and is banned
  if (authCtx.user && authCtx.user.is_banned) {
    logSecurityEvent(
      'Banned user attempted access',
      'medium',
      {
        userId: authCtx.user.id,
        telegramId: authCtx.user.telegram_id,
        username: authCtx.user.username,
      }
    );

    await ctx.reply(ERROR_MESSAGES.USER_BANNED);
    return;
  }

  return next();
};

export default banMiddleware;
