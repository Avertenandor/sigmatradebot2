/**
 * Request ID Middleware
 * Automatically generates and tracks request ID for each bot interaction
 * Enables end-to-end tracing of user requests through all services
 */

import { Context, MiddlewareFn } from 'telegraf';
import { generateRequestId, setRequestId, runWithRequestContext } from '../../utils/audit-logger.util';
import { createLogger } from '../../utils/logger.util';

const logger = createLogger('RequestIDMiddleware');

/**
 * Extend Context with request ID
 */
export interface RequestContext extends Context {
  requestId: string;
}

/**
 * Request ID middleware
 * Generates unique request ID for each incoming update and stores in context
 */
export const requestIdMiddleware: MiddlewareFn<Context> = async (ctx, next) => {
  // Generate unique request ID
  const requestId = generateRequestId();

  // Store in context for easy access
  (ctx as RequestContext).requestId = requestId;

  // Set in async local storage for automatic tracking across services
  setRequestId(requestId);

  // Log incoming request
  logger.debug('Incoming request', {
    requestId,
    updateType: ctx.updateType,
    userId: ctx.from?.id,
    username: ctx.from?.username,
    chatId: ctx.chat?.id,
  });

  try {
    // Process next middleware/handler
    await next();
  } catch (error) {
    // Log error with request ID
    logger.error('Request processing error', {
      requestId,
      error: error instanceof Error ? error.message : String(error),
      stack: error instanceof Error ? error.stack : undefined,
    });

    throw error; // Re-throw for global error handler
  }
};

/**
 * Wrap async function with request context
 * Use this for background jobs or async operations that don't have bot context
 */
export function withRequestContext<T>(fn: () => Promise<T>): Promise<T> {
  return runWithRequestContext(async () => {
    try {
      return await fn();
    } catch (error) {
      logger.error('Error in request context', {
        requestId: require('../../utils/audit-logger.util').getRequestId(),
        error: error instanceof Error ? error.message : String(error),
      });
      throw error;
    }
  });
}

export default requestIdMiddleware;
