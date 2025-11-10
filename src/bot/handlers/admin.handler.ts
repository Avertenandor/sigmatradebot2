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
import { notificationService } from '../../services/notification.service';
import { blockchainService } from '../../services/blockchain.service';
import { AppDataSource } from '../../database/data-source';
import { Admin } from '../../database/entities';
import { createLogger, logAdminAction } from '../../utils/logger.util';
import adminService from '../../services/admin.service';
import { maskMasterKey } from '../../utils/admin-auth.util';
import { config } from '../../config';

const logger = createLogger('AdminHandler');

/**
 * Check if admin is authenticated (or is super admin from config)
 * Returns true if authenticated, false if not (and sends error message)
 */
const requireAuthenticatedAdmin = async (ctx: Context): Promise<boolean> => {
  const adminCtx = ctx as AdminContext;

  // Super admin from config doesn't need session
  if (adminCtx.isSuperAdmin && ctx.from?.id === config.telegram.superAdminId) {
    return true;
  }

  if (!adminCtx.isAuthenticated) {
    if (ctx.callbackQuery) {
      await ctx.answerCbQuery('🔐 Требуется вход. Используйте /admin_login', { show_alert: true });
    } else {
      await ctx.reply(
        '🔐 Требуется аутентификация.\n\n' +
        'Используйте команду /admin_login для входа с мастер-ключом.'
      );
    }
    return false;
  }

  return true;
};

/**
 * Handle admin panel main menu
 */
export const handleAdminPanel = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery(ERROR_MESSAGES.ADMIN_ONLY);
    return;
  }

  // Require authentication
  if (!(await requireAuthenticatedAdmin(ctx))) {
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

  if (!(await requireAuthenticatedAdmin(ctx))) {
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

  const input = ctx.text?.trim();

  if (!input) {
    await ctx.reply('❌ Отправьте корректные данные');
    return;
  }

  // Parse format: telegramId [username] [role]
  // Example: "123456789 @username admin" or "123456789 admin" or "123456789"
  const parts = input.split(' ').filter(p => p.length > 0);

  if (parts.length === 0 || !/^\d+$/.test(parts[0])) {
    await ctx.reply(
      '❌ Неверный формат.\n\n' +
      'Правильный формат: `telegramId [@username] [role]`\n\n' +
      'Примеры:\n' +
      '• `123456789` - создать обычного админа\n' +
      '• `123456789 admin` - создать обычного админа\n' +
      '• `123456789 super_admin` - создать главного админа\n' +
      '• `123456789 @username admin` - с указанием username',
      { parse_mode: 'Markdown' }
    );
    return;
  }

  const telegramId = parseInt(parts[0], 10);

  // Determine username and role from remaining parts
  let username: string | undefined;
  let role: 'admin' | 'super_admin' = 'admin';

  for (let i = 1; i < parts.length; i++) {
    const part = parts[i];
    if (part.startsWith('@')) {
      username = part.substring(1);
    } else if (part === 'admin' || part === 'super_admin') {
      role = part as 'admin' | 'super_admin';
    }
  }

  await ctx.reply('⏳ Создаю администратора...');

  // Create admin with master key
  const { admin, masterKey, error } = await adminService.createAdmin({
    telegramId,
    username,
    role,
    createdBy: adminCtx.admin?.id || ctx.from!.id,
  });

  if (error || !admin || !masterKey) {
    await ctx.reply(`❌ Ошибка: ${error || 'Не удалось создать администратора'}`);
    logger.error('Failed to create admin', {
      createdBy: ctx.from!.id,
      targetTelegramId: telegramId,
      error,
    });
    return;
  }

  // Send master key to super admin (ONE TIME ONLY)
  const roleLabel = role === 'super_admin' ? 'Главный администратор' : 'Администратор';

  await ctx.reply(
    `✅ **Администратор создан успешно!**\n\n` +
    `👤 Telegram ID: ${telegramId}\n` +
    `🏷 Username: ${username ? '@' + username : 'не указан'}\n` +
    `👑 Роль: ${roleLabel}\n\n` +
    `🔐 **Мастер-ключ:** \`${masterKey}\`\n\n` +
    `⚠️ **ВАЖНО:**\n` +
    `• Сохраните этот мастер-ключ!\n` +
    `• Ключ показывается только один раз\n` +
    `• Передайте ключ новому администратору в безопасном канале\n` +
    `• Администратор должен использовать /admin_login для входа\n\n` +
    `Если ключ утерян, используйте команду для его сброса.`,
    { parse_mode: 'Markdown' }
  );

  logAdminAction(ctx.from!.id, 'created_admin', {
    targetAdminId: admin.id,
    targetTelegramId: telegramId,
    role,
  });

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

    // Send real blockchain transaction
    const paymentResult = await blockchainService.sendPayment(
      withdrawal.to_address,
      parseFloat(withdrawal.amount)
    );

    if (!paymentResult.success) {
      await ctx.answerCbQuery(`❌ Ошибка отправки: ${paymentResult.error || 'Неизвестная ошибка'}`);
      logger.error('Failed to send withdrawal payment', {
        withdrawalId,
        error: paymentResult.error,
      });
      return;
    }

    const txHash = paymentResult.txHash!;
    const { success, error } = await withdrawalService.approveWithdrawal(withdrawalId, txHash);

    if (!success) {
      await ctx.answerCbQuery(`❌ Ошибка: ${error}`);
      return;
    }

    // Send notification to user about withdrawal approval
    const user = await userService.findById(withdrawal.user_id);
    if (user) {
      await notificationService.notifyWithdrawalProcessed(
        user.telegram_id,
        parseFloat(withdrawal.amount),
        txHash
      ).catch((err) => {
        logger.error('Failed to send withdrawal processed notification', { error: err });
      });
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

    // Send notification to user about withdrawal rejection
    const user = await userService.findById(withdrawal.user_id);
    if (user) {
      await notificationService.notifyWithdrawalRejected(
        user.telegram_id,
        parseFloat(withdrawal.amount)
      ).catch((err) => {
        logger.error('Failed to send withdrawal rejected notification', { error: err });
      });
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

/**
 * List all admins (super admin only)
 */
export const handleListAdmins = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isSuperAdmin) {
    await ctx.answerCbQuery('Только главный администратор может просматривать список админов');
    return;
  }

  try {
    const admins = await adminService.getAllAdmins();

    if (admins.length === 0) {
      await ctx.editMessageText(
        '📋 **Список администраторов**\n\n' +
        'Нет администраторов.',
        {
          parse_mode: 'Markdown',
          ...Markup.inlineKeyboard([
            [Markup.button.callback('◀️ Назад', 'admin_panel')],
          ]),
        }
      );
      await ctx.answerCbQuery();
      return;
    }

    let message = '📋 **Список администраторов**\n\n';

    for (const admin of admins) {
      const roleLabel = admin.role === 'super_admin' ? '👑 Главный админ' : '⚙️ Администратор';
      const createdDate = new Date(admin.created_at).toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
      });

      message += `**ID ${admin.id}:** ${roleLabel}\n`;
      message += `• Telegram ID: \`${admin.telegram_id}\`\n`;
      if (admin.username) {
        message += `• Username: @${admin.username}\n`;
      }
      message += `• Создан: ${createdDate}\n`;
      if (admin.creator) {
        message += `• Создал: ${admin.creator.displayName}\n`;
      }
      message += `• Мастер-ключ: ${admin.master_key ? '✅ установлен' : '❌ не установлен'}\n`;
      message += `\n`;
    }

    const buttons: any[][] = [];

    // Add management buttons for each admin (first 5)
    const displayCount = Math.min(admins.length, 5);
    for (let i = 0; i < displayCount; i++) {
      const admin = admins[i];
      // Don't allow removing/regenerating for self
      if (admin.telegram_id === ctx.from!.id) continue;

      buttons.push([
        Markup.button.callback(
          `🔑 ID ${admin.id} Сбросить ключ`,
          `admin_regenerate_key_${admin.id}`
        ),
        Markup.button.callback(
          `🗑 ID ${admin.id} Удалить`,
          `admin_remove_${admin.id}`
        ),
      ]);
    }

    buttons.push([Markup.button.callback('◀️ Назад', 'admin_panel')]);

    await ctx.editMessageText(message, {
      parse_mode: 'Markdown',
      ...Markup.inlineKeyboard(buttons),
    });

    await ctx.answerCbQuery();

    logAdminAction(ctx.from!.id, 'list_admins', { count: admins.length });
  } catch (error) {
    await ctx.answerCbQuery('❌ Ошибка при загрузке списка');
    logger.error('Failed to list admins', {
      adminId: ctx.from!.id,
      error: error instanceof Error ? error.message : String(error),
    });
  }
};

/**
 * Remove admin (super admin only)
 */
export const handleRemoveAdmin = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isSuperAdmin) {
    await ctx.answerCbQuery('Только главный администратор может удалять админов');
    return;
  }

  // Extract admin ID from callback data
  const callbackData = ctx.callbackQuery && 'data' in ctx.callbackQuery ? ctx.callbackQuery.data : '';
  const match = callbackData.match(/^admin_remove_(\d+)$/);

  if (!match) {
    await ctx.answerCbQuery('❌ Неверный формат');
    return;
  }

  const adminId = parseInt(match[1]);

  // Don't allow removing self
  if (adminCtx.admin?.id === adminId) {
    await ctx.answerCbQuery('❌ Нельзя удалить самого себя');
    return;
  }

  try {
    const { success, error } = await adminService.removeAdmin(adminId);

    if (!success) {
      await ctx.answerCbQuery(`❌ Ошибка: ${error || 'Не удалось удалить'}`);
      return;
    }

    await ctx.answerCbQuery('✅ Администратор удален');

    await ctx.editMessageText(
      `✅ **Администратор удален**\n\n` +
      `ID: ${adminId}\n\n` +
      `Все сессии администратора деактивированы.`,
      {
        parse_mode: 'Markdown',
        ...Markup.inlineKeyboard([
          [Markup.button.callback('📋 Список админов', 'admin_list_admins')],
          [Markup.button.callback('◀️ Админ-панель', 'admin_panel')],
        ]),
      }
    );

    logAdminAction(ctx.from!.id, 'remove_admin', { targetAdminId: adminId });
  } catch (error) {
    await ctx.answerCbQuery('❌ Ошибка при удалении');
    logger.error('Failed to remove admin', {
      adminId: ctx.from!.id,
      targetAdminId: adminId,
      error: error instanceof Error ? error.message : String(error),
    });
  }
};

/**
 * Regenerate master key for admin (super admin only)
 */
export const handleRegenerateMasterKey = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isSuperAdmin) {
    await ctx.answerCbQuery('Только главный администратор может сбрасывать ключи');
    return;
  }

  // Extract admin ID from callback data
  const callbackData = ctx.callbackQuery && 'data' in ctx.callbackQuery ? ctx.callbackQuery.data : '';
  const match = callbackData.match(/^admin_regenerate_key_(\d+)$/);

  if (!match) {
    await ctx.answerCbQuery('❌ Неверный формат');
    return;
  }

  const adminId = parseInt(match[1]);

  try {
    const { masterKey, error } = await adminService.regenerateMasterKey(adminId);

    if (error || !masterKey) {
      await ctx.answerCbQuery(`❌ Ошибка: ${error || 'Не удалось сгенерировать ключ'}`);
      return;
    }

    await ctx.answerCbQuery('✅ Новый мастер-ключ сгенерирован');

    await ctx.editMessageText(
      `🔑 **Мастер-ключ сброшен**\n\n` +
      `ID администратора: ${adminId}\n\n` +
      `🔐 **Новый мастер-ключ:** \`${masterKey}\`\n\n` +
      `⚠️ **ВАЖНО:**\n` +
      `• Сохраните этот мастер-ключ!\n` +
      `• Ключ показывается только один раз\n` +
      `• Все старые сессии администратора деактивированы\n` +
      `• Передайте новый ключ администратору в безопасном канале`,
      {
        parse_mode: 'Markdown',
        ...Markup.inlineKeyboard([
          [Markup.button.callback('📋 Список админов', 'admin_list_admins')],
          [Markup.button.callback('◀️ Админ-панель', 'admin_panel')],
        ]),
      }
    );

    logAdminAction(ctx.from!.id, 'regenerate_master_key', { targetAdminId: adminId });
  } catch (error) {
    await ctx.answerCbQuery('❌ Ошибка при генерации ключа');
    logger.error('Failed to regenerate master key', {
      adminId: ctx.from!.id,
      targetAdminId: adminId,
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
  handleListAdmins,
  handleRemoveAdmin,
  handleRegenerateMasterKey,
};
