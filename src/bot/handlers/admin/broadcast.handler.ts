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
import { getQueue, QueueName } from '../../../jobs/queue.config';
import { BroadcastJobData } from '../../../jobs/broadcast.processor';

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
⚙️ Рассылка использует очередь с ограничением **15 сообщений/сек**.

**Поддерживается:**
• **Текст** — Просто отправьте текстовое сообщение (поддерживается Markdown)
• **Фото** — Прикрепите фото и добавьте текст в caption
• **Голосовые** — Отправьте голосовое сообщение (caption опционален)
• **Аудио** — Отправьте аудиофайл (caption опционален)

**Примеры:**
📝 Текст: "Привет! **Новая акция** до конца недели!"
🖼 Фото: Прикрепите фото + caption "Новые продукты в наличии"
🎙 Голосовое: Запишите аудиосообщение для пользователей
🎵 Аудио: Отправьте музыкальный файл + описание

После отправки используйте /broadcast_status для проверки прогресса.
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

  await ctx.reply('📨 Ставлю рассылку в очередь...');

  // Get all user telegram IDs
  const userTelegramIds = await userService.getAllUserTelegramIds();

  if (userTelegramIds.length === 0) {
    await ctx.reply('❌ Нет пользователей для рассылки');
    await updateSessionState(ctx.from!.id, BotState.IDLE);
    return;
  }

  // Generate unique broadcast ID
  const broadcastId = `broadcast_${ctx.from!.id}_${Date.now()}`;
  const broadcastQueue = getQueue(QueueName.BROADCAST);

  try {
    // Enqueue broadcast jobs (queue will respect 15 msg/s rate limit)
    const jobs = userTelegramIds.map((telegramId, index) => ({
      name: 'send-message',
      data: {
        type: 'text',
        telegramId,
        adminId: ctx.from!.id,
        broadcastId,
        text: message,
        totalUsers: userTelegramIds.length,
        currentIndex: index,
      } as BroadcastJobData,
      opts: {
        attempts: 3, // Retry up to 3 times
        backoff: {
          type: 'exponential',
          delay: 2000, // Start with 2s, doubles each retry
        },
        removeOnComplete: 100, // Keep last 100 completed jobs
        removeOnFail: false, // Keep failed jobs for inspection
      },
    }));

    // Add all jobs to queue
    await broadcastQueue.addBulk(jobs);

    // Record broadcast timestamp for rate limiting
    broadcastRateLimits.set(ctx.from!.id, Date.now());

    await ctx.reply(
      `✅ Рассылка запущена!\n\n` +
      `👥 Всего пользователей: ${userTelegramIds.length}\n` +
      `⏱ Примерное время: ${Math.ceil(userTelegramIds.length / 15)} сек.\n\n` +
      `📊 Рассылка идёт в фоновом режиме с ограничением 15 сообщений/сек.\n` +
      `✉️ ID рассылки: \`${broadcastId}\`\n\n` +
      `Используйте /broadcast_status для проверки прогресса.`,
      { parse_mode: 'Markdown' }
    );

    logAdminAction(ctx.from!.id, 'started_broadcast_queue', {
      broadcastId,
      total: userTelegramIds.length,
    });
  } catch (error) {
    logger.error('Failed to enqueue broadcast', {
      adminId: ctx.from!.id,
      error: error instanceof Error ? error.message : String(error),
    });

    await ctx.reply('❌ Ошибка при запуске рассылки. Попробуйте позже.');
  }

  // Reset session
  await updateSessionState(ctx.from!.id, BotState.IDLE);
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

Отправьте сообщение конкретному пользователю по username или Telegram ID.

**Формат:**
• **Текст:** \`@username Текст сообщения\` или \`123456789 Текст\`
• **Медиа:** Прикрепите фото/голос/аудио, в caption укажите \`@username Текст\`

**Поддерживается:**
• Текст (Markdown форматирование)
• Фото (с caption)
• Голосовые сообщения (с caption)
• Аудио файлы (с caption)

**Примеры:**
📝 \`@john_doe Привет! Проверьте новый депозит\`
📝 \`123456789 Ваш запрос одобрен ✅\`
🖼 Прикрепить фото + caption: \`@john_doe Вот информация\`
🎙 Голосовое + caption: \`@john_doe\` (можно без текста после username)
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

/**
 * Check broadcast status
 * Command: /broadcast_status
 */
export const handleBroadcastStatus = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isAdmin) {
    await ctx.reply(ERROR_MESSAGES.ADMIN_ONLY);
    return;
  }

  try {
    const broadcastQueue = getQueue(QueueName.BROADCAST);

    // Get queue statistics
    const [waiting, active, completed, failed] = await Promise.all([
      broadcastQueue.getWaitingCount(),
      broadcastQueue.getActiveCount(),
      broadcastQueue.getCompletedCount(),
      broadcastQueue.getFailedCount(),
    ]);

    const total = waiting + active + completed + failed;
    const percent = total > 0 ? Math.round(((completed + failed) / total) * 100) : 0;

    const statusMessage = `
📊 **Статус очереди рассылок**

⏳ Ожидают: ${waiting}
🔄 В процессе: ${active}
✅ Отправлено: ${completed}
❌ Ошибки: ${failed}

📈 Прогресс: ${percent}%
👥 Всего сообщений: ${total}

⚙️ Лимит: 15 сообщений/сек
    `.trim();

    await ctx.reply(statusMessage, { parse_mode: 'Markdown' });
  } catch (error) {
    logger.error('Failed to get broadcast status', {
      adminId: ctx.from!.id,
      error: error instanceof Error ? error.message : String(error),
    });

    await ctx.reply('❌ Ошибка при получении статуса рассылки');
  }
};
