/**
 * Admin Broadcast Handler
 * Handles broadcasting messages and sending to specific users
 */

import { Context } from 'telegraf';
import { AdminContext } from '../../middlewares/admin.middleware';
import { SessionContext, updateSessionState } from '../../middlewares/session.middleware';
import { getCancelButton } from '../../keyboards';
import { BotState, ERROR_MESSAGES } from '../../../utils/constants';
import userService from '../../../services/user.service';
import { createLogger, logAdminAction } from '../../../utils/logger.util';
import { requireAuthenticatedAdmin, broadcastRateLimits, BROADCAST_COOLDOWN_MS } from './utils';

const logger = createLogger('AdminBroadcastHandler');

/**
 * Start broadcast message
 */
export const handleStartBroadcast = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext & SessionContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery(ERROR_MESSAGES.ADMIN_ONLY);
    return;
  }

  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  // Check rate limit
  const adminId = ctx.from!.id;
  const lastBroadcast = broadcastRateLimits.get(adminId);
  const now = Date.now();

  if (lastBroadcast) {
    const timeSinceLastBroadcast = now - lastBroadcast;
    const remainingCooldown = BROADCAST_COOLDOWN_MS - timeSinceLastBroadcast;

    if (remainingCooldown > 0) {
      const remainingMinutes = Math.ceil(remainingCooldown / 60000);
      await ctx.answerCbQuery(
        `⏳ Подождите ${remainingMinutes} мин. перед следующей рассылкой`,
        { show_alert: true }
      );
      return;
    }
  }

  await updateSessionState(
    ctx.from!.id,
    BotState.AWAITING_ADMIN_BROADCAST_MESSAGE
  );

  const message = `
📢 **Рассылка всем пользователям**

Отправьте сообщение, которое хотите разослать всем пользователям бота.

⚠️ Сообщение получат все зарегистрированные пользователи.

**Поддерживается:**
• Текст (Markdown форматирование)
• Фото (с caption)
• Голосовые сообщения (с caption)
• Аудио файлы (с caption)
  `.trim();

  await ctx.editMessageText(message, {
    parse_mode: 'Markdown',
    ...getCancelButton(),
  });

  await ctx.answerCbQuery();

  logAdminAction(ctx.from!.id, 'started_broadcast');
};

/**
 * Handle broadcast message input
 */
export const handleBroadcastMessage = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext & SessionContext;

  if (!adminCtx.isAdmin) {
    return;
  }

  if (adminCtx.session.state !== BotState.AWAITING_ADMIN_BROADCAST_MESSAGE) {
    return;
  }

  const message = ctx.text;

  if (!message) {
    await ctx.reply('❌ Пожалуйста, отправьте текстовое сообщение');
    return;
  }

  await ctx.reply('📨 Начинаю рассылку...');

  // Get all user telegram IDs
  const userTelegramIds = await userService.getAllUserTelegramIds();

  let sent = 0;
  let failed = 0;

  // Send to all users
  for (const telegramId of userTelegramIds) {
    try {
      await ctx.telegram.sendMessage(telegramId, message, {
        parse_mode: 'Markdown',
      });
      sent++;

      // Small delay to avoid rate limiting
      await new Promise((resolve) => setTimeout(resolve, 50));
    } catch (error) {
      failed++;
      logger.warn('Failed to send broadcast to user', {
        userId: telegramId,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  // Record broadcast timestamp for rate limiting
  broadcastRateLimits.set(ctx.from!.id, Date.now());

  await ctx.reply(
    `✅ Рассылка завершена!\n\n` +
    `📨 Отправлено: ${sent}\n` +
    `❌ Не удалось: ${failed}\n` +
    `👥 Всего: ${userTelegramIds.length}`
  );

  // Reset session
  await updateSessionState(ctx.from!.id, BotState.IDLE);

  logAdminAction(ctx.from!.id, 'completed_broadcast', { sent, failed, total: userTelegramIds.length });
};

/**
 * Start send to user
 */
export const handleStartSendToUser = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext & SessionContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery(ERROR_MESSAGES.ADMIN_ONLY);
    return;
  }

  // Require authentication
  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  await updateSessionState(
    ctx.from!.id,
    BotState.AWAITING_ADMIN_USER_MESSAGE
  );

  const message = `
✉️ **Отправка сообщения пользователю**

**Для текста:** Отправьте сообщение в формате:
\`@username Текст сообщения\`
или
\`123456789 Текст сообщения\`

**Для медиа:** Прикрепите фото/голос/аудио, а в caption укажите:
\`@username Текст сообщения\`

Где первое слово - username или Telegram ID пользователя.

**Поддерживается:**
• Текст (Markdown форматирование)
• Фото (с caption)
• Голосовые сообщения (с caption)
• Аудио файлы (с caption)
  `.trim();

  await ctx.editMessageText(message, {
    parse_mode: 'Markdown',
    ...getCancelButton(),
  });

  await ctx.answerCbQuery();

  logAdminAction(ctx.from!.id, 'started_send_to_user');
};

/**
 * Handle send to user message
 */
export const handleSendToUserMessage = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext & SessionContext;

  if (!adminCtx.isAdmin) {
    return;
  }

  // Require authentication
  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  if (adminCtx.session.state !== BotState.AWAITING_ADMIN_USER_MESSAGE) {
    return;
  }

  const text = ctx.text;

  if (!text) {
    await ctx.reply('❌ Отправьте текстовое сообщение');
    return;
  }

  // Parse username/id and message
  const parts = text.split(' ');
  if (parts.length < 2) {
    await ctx.reply('❌ Неверный формат. Используйте: @username Текст');
    return;
  }

  const identifier = parts[0];
  const message = parts.slice(1).join(' ');

  // Find user
  let user;

  if (identifier.startsWith('@')) {
    const username = identifier.substring(1);
    user = await userService.findByUsername(username);
  } else if (/^\d+$/.test(identifier)) {
    const telegramId = parseInt(identifier, 10);
    user = await userService.findByTelegramId(telegramId);
  }

  if (!user) {
    await ctx.reply('❌ Пользователь не найден');
    return;
  }

  // Send message
  try {
    await ctx.telegram.sendMessage(user.telegram_id, message, {
      parse_mode: 'Markdown',
    });

    await ctx.reply(
      `✅ Сообщение отправлено пользователю ${user.displayName}`
    );

    logAdminAction(ctx.from!.id, 'sent_message_to_user', {
      targetUserId: user.id,
    });
  } catch (error) {
    await ctx.reply('❌ Ошибка при отправке сообщения');
    logger.error('Failed to send message to user', {
      adminId: ctx.from!.id,
      targetUserId: user.id,
      error: error instanceof Error ? error.message : String(error),
    });
  }

  // Reset session
  await updateSessionState(ctx.from!.id, BotState.IDLE);
};
