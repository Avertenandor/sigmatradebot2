/**
 * Session Middleware
 * Manages user session state using Redis
 */

import { Context, MiddlewareFn } from 'telegraf';
import Redis from 'ioredis';
import { config } from '../../config';
import { BotState } from '../../utils/constants';
import { logger } from '../../utils/logger.util';

// Initialize Redis client
const redis = new Redis({
  host: config.redis.host,
  port: config.redis.port,
  password: config.redis.password,
  db: config.redis.db,
  retryStrategy: (times) => {
    const delay = Math.min(times * 50, 2000);
    return delay;
  },
});

// Session interface
export interface SessionData {
  state: BotState;
  data?: Record<string, any>;
  lastActivity: number;
  // Support ticket fields
  supportCategory?: string;
  supportMessages?: Array<{ type: string; text?: string; file_id?: string; caption?: string }>;
  // Admin support reply fields
  supportReplyTicketId?: number;
  supportReplyMessages?: Array<{ type: string; text?: string; file_id?: string; caption?: string }>;
}

// Extend Context with session
export interface SessionContext extends Context {
  session: SessionData;
}

/**
 * Get session key for user
 */
const getSessionKey = (userId: number): string => {
  return `session:${userId}`;
};

/**
 * Session middleware - loads and saves session data
 */
export const sessionMiddleware: MiddlewareFn<Context> = async (ctx, next) => {
  const userId = ctx.from?.id;

  if (!userId) {
    return next();
  }

  const sessionKey = getSessionKey(userId);

  // Load session from Redis
  const sessionJson = await redis.get(sessionKey);
  let session: SessionData;

  if (sessionJson) {
    try {
      session = JSON.parse(sessionJson);
    } catch (error) {
      // Invalid JSON, create new session
      session = {
        state: BotState.IDLE,
        lastActivity: Date.now(),
      };
    }
  } else {
    // New session
    session = {
      state: BotState.IDLE,
      lastActivity: Date.now(),
    };
  }

  // Attach session to context
  (ctx as SessionContext).session = session;

  // Continue with next middleware
  await next();

  // Update last activity
  session.lastActivity = Date.now();

  // Save session to Redis (TTL: 24 hours)
  await redis.setex(sessionKey, 86400, JSON.stringify(session));
};

/**
 * Clear session for user
 */
export const clearSession = async (userId: number): Promise<void> => {
  const sessionKey = getSessionKey(userId);
  await redis.del(sessionKey);
};

/**
 * Get session for user
 */
export const getSession = async (userId: number): Promise<SessionData | null> => {
  const sessionKey = getSessionKey(userId);
  const sessionJson = await redis.get(sessionKey);

  if (!sessionJson) {
    return null;
  }

  try {
    return JSON.parse(sessionJson);
  } catch (error) {
    return null;
  }
};

/**
 * Update session state
 * FIX #7: Creates session if it doesn't exist
 */
export const updateSessionState = async (
  userId: number,
  state: BotState,
  data?: Record<string, any>
): Promise<void> => {
  let session = await getSession(userId);

  // CREATE SESSION IF NOT EXISTS (FIX #7)
  if (!session) {
    logger.info('Creating new session for state update', { userId, state });
    session = {
      state: BotState.IDLE,
      data: {},
      lastActivity: Date.now(),
    };
  }

  session.state = state;
  if (data) {
    session.data = { ...session.data, ...data };
  }
  session.lastActivity = Date.now();

  const sessionKey = getSessionKey(userId);
  await redis.setex(sessionKey, 86400, JSON.stringify(session));

  logger.debug('Session state updated', { userId, state, hasData: !!data });
};

export default sessionMiddleware;
