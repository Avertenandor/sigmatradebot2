/**
 * Rate Limit Middleware
 * Prevents spam and abuse using Redis
 */

import { Context, MiddlewareFn } from 'telegraf';
import Redis from 'ioredis';
import { config } from '../../config';
import { RATE_LIMITS, ERROR_MESSAGES } from '../../utils/constants';
import { logSecurityEvent } from '../../utils/logger.util';

// Initialize Redis client
const redis = new Redis({
  host: config.redis.host,
  port: config.redis.port,
  password: config.redis.password,
  db: config.redis.db,
});

/**
 * Rate limit key generator
 */
const getRateLimitKey = (userId: number, type: string = 'general'): string => {
  return `rate_limit:${type}:user:${userId}`;
};

/**
 * Check rate limit
 * @returns true if rate limit exceeded
 */
const checkRateLimit = async (
  userId: number,
  maxRequests: number,
  windowMs: number,
  type: string = 'general'
): Promise<boolean> => {
  const key = getRateLimitKey(userId, type);

  // Get current count
  const current = await redis.get(key);
  const count = current ? parseInt(current, 10) : 0;

  if (count >= maxRequests) {
    // Rate limit exceeded
    return true;
  }

  // Increment counter
  if (count === 0) {
    // First request, set with expiry
    await redis.setex(key, Math.ceil(windowMs / 1000), '1');
  } else {
    // Increment existing counter
    await redis.incr(key);
  }

  return false;
};

/**
 * Ban user temporarily
 */
const banUser = async (userId: number, durationMs: number): Promise<void> => {
  const banKey = `rate_limit:banned:${userId}`;
  await redis.setex(banKey, Math.ceil(durationMs / 1000), '1');
};

/**
 * Check if user is banned
 */
const isUserBanned = async (userId: number): Promise<boolean> => {
  const banKey = `rate_limit:banned:${userId}`;
  const banned = await redis.get(banKey);
  return !!banned;
};

/**
 * General rate limit middleware
 * Applies to all requests
 */
export const rateLimitMiddleware: MiddlewareFn<Context> = async (ctx, next) => {
  const userId = ctx.from?.id;

  if (!userId) {
    return next();
  }

  // Check if user is temporarily banned
  if (await isUserBanned(userId)) {
    logSecurityEvent(
      'Rate-limited user attempted access',
      'low',
      {
        userId,
        username: ctx.from?.username,
      }
    );

    await ctx.reply(ERROR_MESSAGES.RATE_LIMIT_EXCEEDED);
    return;
  }

  // Check general rate limit
  const exceeded = await checkRateLimit(
    userId,
    RATE_LIMITS.USER.MAX_REQUESTS,
    RATE_LIMITS.USER.WINDOW_MS,
    'general'
  );

  if (exceeded) {
    // Ban user temporarily
    await banUser(userId, RATE_LIMITS.USER.BAN_DURATION_MS);

    logSecurityEvent(
      'User exceeded rate limit',
      'medium',
      {
        userId,
        username: ctx.from?.username,
        banDuration: RATE_LIMITS.USER.BAN_DURATION_MS,
      }
    );

    await ctx.reply(ERROR_MESSAGES.RATE_LIMIT_EXCEEDED);
    return;
  }

  return next();
};

/**
 * Registration rate limit middleware
 * Stricter limits for registration attempts
 */
export const registrationRateLimitMiddleware: MiddlewareFn<Context> = async (
  ctx,
  next
) => {
  const userId = ctx.from?.id;

  if (!userId) {
    return next();
  }

  const exceeded = await checkRateLimit(
    userId,
    RATE_LIMITS.REGISTRATION.MAX_REQUESTS,
    RATE_LIMITS.REGISTRATION.WINDOW_MS,
    'registration'
  );

  if (exceeded) {
    logSecurityEvent(
      'User exceeded registration rate limit',
      'high',
      {
        userId,
        username: ctx.from?.username,
      }
    );

    await ctx.reply(
      '❌ Слишком много попыток регистрации. Пожалуйста, подождите час и попробуйте снова.'
    );
    return;
  }

  return next();
};

/**
 * Deposit rate limit middleware
 * Limits deposit-related actions
 */
export const depositRateLimitMiddleware: MiddlewareFn<Context> = async (
  ctx,
  next
) => {
  const userId = ctx.from?.id;

  if (!userId) {
    return next();
  }

  const exceeded = await checkRateLimit(
    userId,
    RATE_LIMITS.DEPOSIT.MAX_REQUESTS,
    RATE_LIMITS.DEPOSIT.WINDOW_MS,
    'deposit'
  );

  if (exceeded) {
    logSecurityEvent(
      'User exceeded deposit rate limit',
      'medium',
      {
        userId,
        username: ctx.from?.username,
      }
    );

    await ctx.reply(
      '❌ Слишком много запросов по депозитам. Пожалуйста, подождите несколько минут.'
    );
    return;
  }

  return next();
};

export default rateLimitMiddleware;
