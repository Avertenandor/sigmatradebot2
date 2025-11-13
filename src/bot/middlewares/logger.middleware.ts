/**
 * Logger Middleware
 * Logs all bot interactions
 */

import { Context, MiddlewareFn } from 'telegraf';
import { createLogger } from '../../utils/logger.util';

const logger = createLogger('BotMiddleware');

/**
 * Logger middleware - logs all incoming updates
 */
export const loggerMiddleware: MiddlewareFn<Context> = async (ctx, next) => {
  const startTime = Date.now();

  // Extract user info
  const userId = ctx.from?.id;
  const username = ctx.from?.username;
  const chatId = ctx.chat?.id;

  // Extract update type
  const updateType = ctx.updateType;
  const messageText = ctx.message && 'text' in ctx.message ? ctx.message.text : undefined;
  const callbackData = ctx.callbackQuery && 'data' in ctx.callbackQuery ? ctx.callbackQuery.data : undefined;

  // Log incoming update
  logger.info('Incoming update', {
    userId,
    username,
    chatId,
    updateType,
    messageText,
    callbackData,
  });

  try {
    await next();

    const duration = Date.now() - startTime;
    logger.debug('Update processed', {
      userId,
      duration,
    });
  } catch (error) {
    const duration = Date.now() - startTime;
    logger.error('Error processing update', {
      userId,
      username,
      updateType,
      duration,
      error: error instanceof Error ? error.message : String(error),
      stack: error instanceof Error ? error.stack : undefined,
    });
    throw error;
  }
};

export default loggerMiddleware;
