/**
 * Admin Handler
 * Handles admin panel operations
 */

import { Context } from 'telegraf';
import { Markup } from 'telegraf';
import { AuthContext } from '../middlewares/auth.middleware';
import { AdminContext } from '../middlewares/admin.middleware';
import { SessionContext, updateSessionState } from '../middlewares/session.middleware';
import { getAdminPanelKeyboard, getAdminStatsKeyboard, getCancelButton } from '../keyboards';
import { BotState, ERROR_MESSAGES } from '../../utils/constants';
import userService from '../../services/user.service';
import depositService from '../../services/deposit.service';
import referralService from '../../services/referral.service';
import withdrawalService from '../../services/withdrawal.service';
import { AppDataSource } from '../../database/data-source';
import { Admin } from '../../database/entities';
import { createLogger, logAdminAction } from '../../utils/logger.util';

const logger = createLogger('AdminHandler');

/**
 * Handle admin panel main menu
 */
export const handleAdminPanel = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery(ERROR_MESSAGES.ADMIN_ONLY);
    return;
  }

  const message = `
👑 **Панель администратора**

Добро пожаловать в панель управления SigmaTrade Bot.

Выберите действие:
  `.trim();

  if (ctx.callbackQuery && 'message' in ctx.callbackQuery) {
    await ctx.editMessageText(message, {
      parse_mode: 'Markdown',
      ...getAdminPanelKeyboard(),
    });
  } else {
    await ctx.reply(message, {
      parse_mode: 'Markdown',
      ...getAdminPanelKeyboard(),
    });
  }

  if (ctx.callbackQuery) {
    await ctx.answerCbQuery();
  }

  logAdminAction(ctx.from!.id, 'opened_admin_panel');
};

/**
 * Handle platform statistics
 */
export const handleAdminStats = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery(ERROR_MESSAGES.ADMIN_ONLY);
    return;
  }

  // Get range from callback data
  const callbackData = ctx.callbackQuery && 'data' in ctx.callbackQuery ? ctx.callbackQuery.data : '';
  const range = callbackData.split('_').pop() || 'all';

  // Get statistics
  const totalUsers = await userService.getTotalUsers();
  const verifiedUsers = await userService.getVerifiedUsers();
  const depositStats = await depositService.getPlatformStats();
  const referralStats = await referralService.getPlatformReferralStats();

  const message = `
📊 **Статистика платформы**

**Пользователи:**
👥 Всего: ${totalUsers}
✅ Верифицированы: ${verifiedUsers}
❌ Не верифицированы: ${totalUsers - verifiedUsers}

**Депозиты:**
💰 Всего депозитов: ${depositStats.totalDeposits}
💵 Общая сумма: ${depositStats.totalAmount.toFixed(2)} USDT
👤 Пользователей с депозитами: ${depositStats.totalUsers}

**По уровням:**
• Уровень 1: ${depositStats.depositsByLevel[1]} депозитов
• Уровень 2: ${depositStats.depositsByLevel[2]} депозитов
• Уровень 3: ${depositStats.depositsByLevel[3]} депозитов
• Уровень 4: ${depositStats.depositsByLevel[4]} депозитов
• Уровень 5: ${depositStats.depositsByLevel[5]} депозитов

**Рефералы:**
🤝 Всего связей: ${referralStats.totalReferrals}
💰 Всего начислено: ${referralStats.totalEarnings.toFixed(2)} USDT
✅ Выплачено: ${referralStats.paidEarnings.toFixed(2)} USDT
⏳ Ожидает выплаты: ${referralStats.pendingEarnings.toFixed(2)} USDT

**По уровням:**
• Уровень 1: ${referralStats.byLevel[1].count} (${referralStats.byLevel[1].earnings.toFixed(2)} USDT)
• Уровень 2: ${referralStats.byLevel[2].count} (${referralStats.byLevel[2].earnings.toFixed(2)} USDT)
• Уровень 3: ${referralStats.byLevel[3].count} (${referralStats.byLevel[3].earnings.toFixed(2)} USDT)
  `.trim();

  await ctx.editMessageText(message, {
    parse_mode: 'Markdown',
    ...getAdminStatsKeyboard(range),
  });

  await ctx.answerCbQuery();

  logAdminAction(ctx.from!.id, 'viewed_stats', { range });
};

// Rate limiting for broadcasts: Map of adminId -> last broadcast timestamp
const broadcastRateLimits = new Map<number, number>();
const BROADCAST_COOLDOWN_MS = 5 * 60 * 1000; // 5 minutes

/**
 * Start broadcast message
 */
export const handleStartBroadcast = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext & SessionContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery(ERROR_MESSAGES.ADMIN_ONLY);
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

Поддерживается Markdown форматирование.
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

  await updateSessionState(
    ctx.from!.id,
    BotState.AWAITING_ADMIN_USER_MESSAGE
  );

  const message = `
✉️ **Отправка сообщения пользователю**

Отправьте сообщение в формате:

\`@username Текст сообщения\`

или

\`123456789 Текст сообщения\`

Где первое слово - username или Telegram ID пользователя.
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
 * Start ban user
 */
export const handleStartBanUser = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext & SessionContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery(ERROR_MESSAGES.ADMIN_ONLY);
    return;
  }

  await updateSessionState(
    ctx.from!.id,
    BotState.AWAITING_ADMIN_USER_TO_BAN
  );

  const message = `
🚫 **Блокировка пользователя**

Отправьте username (с @) или Telegram ID пользователя для блокировки.

Пример: \`@username\` или \`123456789\`
  `.trim();

  await ctx.editMessageText(message, {
    parse_mode: 'Markdown',
    ...getCancelButton(),
  });

  await ctx.answerCbQuery();
};

/**
 * Handle ban user input
 */
export const handleBanUserInput = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext & SessionContext;

  if (!adminCtx.isAdmin) {
    return;
  }

  if (adminCtx.session.state !== BotState.AWAITING_ADMIN_USER_TO_BAN) {
    return;
  }

  const identifier = ctx.text?.trim();

  if (!identifier) {
    await ctx.reply('❌ Отправьте username или ID');
    return;
  }

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

  // Ban user
  const result = await userService.banUser(user.id);

  if (result.success) {
    await ctx.reply(
      `✅ Пользователь ${user.displayName} заблокирован`
    );

    logAdminAction(ctx.from!.id, 'banned_user', {
      targetUserId: user.id,
    });
  } else {
    await ctx.reply(`❌ Ошибка: ${result.error}`);
  }

  // Reset session
  await updateSessionState(ctx.from!.id, BotState.IDLE);
};

/**
 * Start unban user
 */
export const handleStartUnbanUser = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext & SessionContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery(ERROR_MESSAGES.ADMIN_ONLY);
    return;
  }

  await updateSessionState(
    ctx.from!.id,
    BotState.AWAITING_ADMIN_USER_TO_UNBAN
  );

  const message = `
✅ **Разблокировка пользователя**

Отправьте username (с @) или Telegram ID пользователя для разблокировки.

Пример: \`@username\` или \`123456789\`
  `.trim();

  await ctx.editMessageText(message, {
    parse_mode: 'Markdown',
    ...getCancelButton(),
  });

  await ctx.answerCbQuery();
};

/**
 * Handle unban user input
 */
export const handleUnbanUserInput = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext & SessionContext;

  if (!adminCtx.isAdmin) {
    return;
  }

  if (adminCtx.session.state !== BotState.AWAITING_ADMIN_USER_TO_UNBAN) {
    return;
  }

  const identifier = ctx.text?.trim();

  if (!identifier) {
    await ctx.reply('❌ Отправьте username или ID');
    return;
  }

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

  // Unban user
  const result = await userService.unbanUser(user.id);

  if (result.success) {
    await ctx.reply(
      `✅ Пользователь ${user.displayName} разблокирован`
    );

    logAdminAction(ctx.from!.id, 'unbanned_user', {
      targetUserId: user.id,
    });
  } else {
    await ctx.reply(`❌ Ошибка: ${result.error}`);
  }

  // Reset session
  await updateSessionState(ctx.from!.id, BotState.IDLE);
};

/**
 * Start promote admin
 */
export const handleStartPromoteAdmin = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext & SessionContext;

  if (!adminCtx.isSuperAdmin) {
    await ctx.answerCbQuery('Только главный администратор может назначать админов');
    return;
  }

  await updateSessionState(
    ctx.from!.id,
    BotState.AWAITING_ADMIN_USER_TO_PROMOTE
  );

  const message = `
👑 **Назначить администратора**

Отправьте Telegram ID пользователя для назначения администратором.

Пример: \`123456789\`
  `.trim();

  await ctx.editMessageText(message, {
    parse_mode: 'Markdown',
    ...getCancelButton(),
  });

  await ctx.answerCbQuery();
};

/**
 * Handle promote admin input
 */
export const handlePromoteAdminInput = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext & SessionContext;

  if (!adminCtx.isSuperAdmin) {
    return;
  }

  if (adminCtx.session.state !== BotState.AWAITING_ADMIN_USER_TO_PROMOTE) {
    return;
  }

  const telegramIdStr = ctx.text?.trim();

  if (!telegramIdStr || !/^\d+$/.test(telegramIdStr)) {
    await ctx.reply('❌ Отправьте корректный Telegram ID (только цифры)');
    return;
  }

  const telegramId = parseInt(telegramIdStr, 10);

  // Check if already admin
  const adminRepository = AppDataSource.getRepository(Admin);
  const existing = await adminRepository.findOne({
    where: { telegram_id: telegramId },
  });

  if (existing) {
    await ctx.reply('❌ Этот пользователь уже является администратором');
    return;
  }

  // Create admin
  const admin = adminRepository.create({
    telegram_id: telegramId,
    username: undefined, // Will be filled on first login
    role: 'admin',
    created_by: adminCtx.admin?.id || null,
  });

  try {
    await adminRepository.save(admin);

    await ctx.reply(
      `✅ Пользователь ${telegramId} назначен администратором`
    );

    logAdminAction(ctx.from!.id, 'promoted_admin', {
      targetTelegramId: telegramId,
    });
  } catch (error) {
    await ctx.reply('❌ Ошибка при назначении администратора');
    logger.error('Failed to promote admin', {
      adminId: ctx.from!.id,
      targetTelegramId: telegramId,
      error: error instanceof Error ? error.message : String(error),
    });
  }

  // Reset session
  await updateSessionState(ctx.from!.id, BotState.IDLE);
};

/**
 * Handle pending withdrawals list (admin only)
 */
export const handlePendingWithdrawals = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery(ERROR_MESSAGES.ADMIN_ONLY);
    return;
  }

  try {
    const pendingWithdrawals = await withdrawalService.getPendingWithdrawals();

    let message = `💸 **Ожидающие заявки на вывод**\n\n`;

    if (pendingWithdrawals.length === 0) {
      message += 'Нет ожидающих заявок.';
      await ctx.editMessageText(message, {
        parse_mode: 'Markdown',
        ...Markup.inlineKeyboard([
          [Markup.button.callback('◀️ Назад', 'admin_panel')],
        ]),
      });
      await ctx.answerCbQuery();
      return;
    }

    message += `Всего заявок: **${pendingWithdrawals.length}**\n\n`;

    pendingWithdrawals.forEach((withdrawal, index) => {
      const date = new Date(withdrawal.created_at).toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });

      message += `**${index + 1}. Заявка #${withdrawal.id}**\n`;
      message += `💰 Сумма: ${parseFloat(withdrawal.amount).toFixed(2)} USDT\n`;
      message += `👤 Пользователь ID: ${withdrawal.user_id}\n`;
      if (withdrawal.user?.username) {
        message += `📱 @${withdrawal.user.username}\n`;
      }
      message += `💳 Кошелек: \`${withdrawal.to_address}\`\n`;
      message += `📅 Дата: ${date}\n`;
      message += `\n`;
    });

    const buttons: any[][] = [];

    // Add approve/reject buttons for each withdrawal (first 5)
    const displayCount = Math.min(pendingWithdrawals.length, 5);
    for (let i = 0; i < displayCount; i++) {
      const withdrawal = pendingWithdrawals[i];
      buttons.push([
        Markup.button.callback(
          `✅ #${withdrawal.id} Одобрить`,
          `admin_approve_withdrawal_${withdrawal.id}`
        ),
        Markup.button.callback(
          `❌ #${withdrawal.id} Отклонить`,
          `admin_reject_withdrawal_${withdrawal.id}`
        ),
      ]);
    }

    buttons.push([Markup.button.callback('◀️ Назад', 'admin_panel')]);

    await ctx.editMessageText(message, {
      parse_mode: 'Markdown',
      ...Markup.inlineKeyboard(buttons),
    });

    await ctx.answerCbQuery();

    logAdminAction(ctx.from!.id, 'view_pending_withdrawals', {
      count: pendingWithdrawals.length,
    });
  } catch (error) {
    await ctx.answerCbQuery('❌ Ошибка при загрузке заявок');
    logger.error('Failed to get pending withdrawals', {
      adminId: ctx.from!.id,
      error: error instanceof Error ? error.message : String(error),
    });
  }
};

/**
 * Handle approve withdrawal (admin only)
 */
export const handleApproveWithdrawal = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery(ERROR_MESSAGES.ADMIN_ONLY);
    return;
  }

  // Extract withdrawal ID from callback data
  const callbackData = ctx.callbackQuery && 'data' in ctx.callbackQuery ? ctx.callbackQuery.data : '';
  const match = callbackData.match(/^admin_approve_withdrawal_(\d+)$/);

  if (!match) {
    await ctx.answerCbQuery('❌ Неверный формат');
    return;
  }

  const withdrawalId = parseInt(match[1]);

  try {
    // Get withdrawal details
    const withdrawal = await withdrawalService.getWithdrawalById(withdrawalId);

    if (!withdrawal) {
      await ctx.answerCbQuery('❌ Заявка не найдена');
      return;
    }

    // For now, we'll simulate sending funds by generating a fake tx hash
    // In production, this should integrate with payment service
    const txHash = `0x${Math.random().toString(16).substring(2, 66)}`;

    const { success, error } = await withdrawalService.approveWithdrawal(withdrawalId, txHash);

    if (!success) {
      await ctx.answerCbQuery(`❌ Ошибка: ${error}`);
      return;
    }

    await ctx.answerCbQuery('✅ Заявка одобрена!');

    // Update message
    await ctx.editMessageText(
      `✅ **Заявка #${withdrawalId} одобрена**\n\n` +
      `💰 Сумма: ${parseFloat(withdrawal.amount).toFixed(2)} USDT\n` +
      `👤 Пользователь ID: ${withdrawal.user_id}\n` +
      `💳 Кошелек: \`${withdrawal.to_address}\`\n` +
      `🔗 TX: \`${txHash}\`\n\n` +
      `Средства отправлены пользователю.`,
      {
        parse_mode: 'Markdown',
        ...Markup.inlineKeyboard([
          [Markup.button.callback('📋 Список заявок', 'admin_pending_withdrawals')],
          [Markup.button.callback('◀️ Админ-панель', 'admin_panel')],
        ]),
      }
    );

    logAdminAction(ctx.from!.id, 'approve_withdrawal', {
      withdrawalId,
      userId: withdrawal.user_id,
      amount: withdrawal.amount,
    });
  } catch (error) {
    await ctx.answerCbQuery('❌ Ошибка при обработке');
    logger.error('Failed to approve withdrawal', {
      adminId: ctx.from!.id,
      withdrawalId,
      error: error instanceof Error ? error.message : String(error),
    });
  }
};

/**
 * Handle reject withdrawal (admin only)
 */
export const handleRejectWithdrawal = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery(ERROR_MESSAGES.ADMIN_ONLY);
    return;
  }

  // Extract withdrawal ID from callback data
  const callbackData = ctx.callbackQuery && 'data' in ctx.callbackQuery ? ctx.callbackQuery.data : '';
  const match = callbackData.match(/^admin_reject_withdrawal_(\d+)$/);

  if (!match) {
    await ctx.answerCbQuery('❌ Неверный формат');
    return;
  }

  const withdrawalId = parseInt(match[1]);

  try {
    // Get withdrawal details
    const withdrawal = await withdrawalService.getWithdrawalById(withdrawalId);

    if (!withdrawal) {
      await ctx.answerCbQuery('❌ Заявка не найдена');
      return;
    }

    const { success, error } = await withdrawalService.rejectWithdrawal(withdrawalId);

    if (!success) {
      await ctx.answerCbQuery(`❌ Ошибка: ${error}`);
      return;
    }

    await ctx.answerCbQuery('✅ Заявка отклонена');

    // Update message
    await ctx.editMessageText(
      `❌ **Заявка #${withdrawalId} отклонена**\n\n` +
      `💰 Сумма: ${parseFloat(withdrawal.amount).toFixed(2)} USDT\n` +
      `👤 Пользователь ID: ${withdrawal.user_id}\n` +
      `💳 Кошелек: \`${withdrawal.to_address}\`\n\n` +
      `Средства возвращены на баланс пользователя.`,
      {
        parse_mode: 'Markdown',
        ...Markup.inlineKeyboard([
          [Markup.button.callback('📋 Список заявок', 'admin_pending_withdrawals')],
          [Markup.button.callback('◀️ Админ-панель', 'admin_panel')],
        ]),
      }
    );

    logAdminAction(ctx.from!.id, 'reject_withdrawal', {
      withdrawalId,
      userId: withdrawal.user_id,
      amount: withdrawal.amount,
    });
  } catch (error) {
    await ctx.answerCbQuery('❌ Ошибка при обработке');
    logger.error('Failed to reject withdrawal', {
      adminId: ctx.from!.id,
      withdrawalId,
      error: error instanceof Error ? error.message : String(error),
    });
  }
};

export default {
  handleAdminPanel,
  handleAdminStats,
  handleStartBroadcast,
  handleBroadcastMessage,
  handleStartSendToUser,
  handleSendToUserMessage,
  handleStartBanUser,
  handleBanUserInput,
  handleStartUnbanUser,
  handleUnbanUserInput,
  handleStartPromoteAdmin,
  handlePromoteAdminInput,
  handlePendingWithdrawals,
  handleApproveWithdrawal,
  handleRejectWithdrawal,
};
