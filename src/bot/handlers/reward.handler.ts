/**
 * Reward Handler
 * Handles reward session management for admins
 */

import { Context, Markup } from 'telegraf';
import { AdminContext } from '../middlewares/admin.middleware';
import { SessionContext, updateSessionState } from '../middlewares/session.middleware';
import { BotState, ERROR_MESSAGES } from '../../utils/constants';
import rewardService from '../../services/reward.service';
import { createLogger, logAdminAction } from '../../utils/logger.util';
import { config } from '../../config';

const logger = createLogger('RewardHandler');

/**
 * Check if admin is authenticated (or is super admin from config)
 */
const requireAuthenticatedAdmin = async (ctx: Context): Promise<boolean> => {
  const adminCtx = ctx as AdminContext;

  if (adminCtx.isSuperAdmin && ctx.from?.id === config.telegram.superAdminId) {
    return true;
  }

  if (!adminCtx.isAuthenticated) {
    if (ctx.callbackQuery) {
      await ctx.answerCbQuery('🔐 Требуется вход. Используйте /admin_login', { show_alert: true });
    } else {
      await ctx.reply('🔐 Требуется аутентификация.\n\nИспользуйте команду /admin_login для входа с мастер-ключом.');
    }
    return false;
  }

  return true;
};

/**
 * Handle reward sessions list
 */
export const handleRewardSessions = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery(ERROR_MESSAGES.ADMIN_ONLY);
    return;
  }

  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  try {
    const sessions = await rewardService.getAllSessions();

    if (sessions.length === 0) {
      await ctx.editMessageText(
        '💰 **Сессии наград**\n\n' +
        'Нет созданных сессий.\n\n' +
        'Сессии наград позволяют настроить выплаты процентов от депозитов за определенный период.',
        {
          parse_mode: 'Markdown',
          ...Markup.inlineKeyboard([
            [Markup.button.callback('➕ Создать сессию', 'reward_create')],
            [Markup.button.callback('◀️ Админ-панель', 'admin_panel')],
          ]),
        }
      );
      await ctx.answerCbQuery();
      return;
    }

    let message = '💰 **Сессии наград**\n\n';

    for (const session of sessions.slice(0, 10)) {
      const statusEmoji = session.is_active ? '✅' : '❌';
      const currentEmoji = session.isCurrentlyActive ? '🔥' : '';

      const startDate = new Date(session.start_date).toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
      });

      const endDate = new Date(session.end_date).toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
      });

      message += `${statusEmoji} ${currentEmoji} **${session.name}**\n`;
      message += `• ID: ${session.id}\n`;
      message += `• Период: ${startDate} - ${endDate}\n`;
      message += `• Ставки: Ур.1=${parseFloat(session.reward_rate_level_1).toFixed(2)}%, `;
      message += `Ур.2=${parseFloat(session.reward_rate_level_2).toFixed(2)}%\n`;
      message += `\n`;
    }

    if (sessions.length > 10) {
      message += `\n_Показано 10 из ${sessions.length} сессий_\n`;
    }

    const buttons: any[][] = [];

    // Management buttons for first 5 sessions
    const displayCount = Math.min(sessions.length, 5);
    for (let i = 0; i < displayCount; i++) {
      const session = sessions[i];
      buttons.push([
        Markup.button.callback(`📊 Сессия #${session.id}`, `reward_stats_${session.id}`),
        Markup.button.callback(`⚙️ Настроить`, `reward_edit_${session.id}`),
      ]);
    }

    buttons.push([Markup.button.callback('➕ Создать сессию', 'reward_create')]);
    buttons.push([Markup.button.callback('◀️ Админ-панель', 'admin_panel')]);

    await ctx.editMessageText(message, {
      parse_mode: 'Markdown',
      ...Markup.inlineKeyboard(buttons),
    });

    await ctx.answerCbQuery();

    logAdminAction(ctx.from!.id, 'view_reward_sessions', { count: sessions.length });
  } catch (error) {
    await ctx.answerCbQuery('❌ Ошибка при загрузке сессий');
    logger.error('Failed to load reward sessions', {
      adminId: ctx.from!.id,
      error: error instanceof Error ? error.message : String(error),
    });
  }
};

/**
 * Handle reward session statistics
 */
export const handleRewardStats = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery(ERROR_MESSAGES.ADMIN_ONLY);
    return;
  }

  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  const callbackData = ctx.callbackQuery && 'data' in ctx.callbackQuery ? ctx.callbackQuery.data : '';
  const match = callbackData.match(/^reward_stats_(\d+)$/);

  if (!match) {
    await ctx.answerCbQuery('❌ Неверный формат');
    return;
  }

  const sessionId = parseInt(match[1]);

  try {
    const session = await rewardService.getSessionById(sessionId);

    if (!session) {
      await ctx.answerCbQuery('❌ Сессия не найдена');
      return;
    }

    const stats = await rewardService.getSessionStatistics(sessionId);

    const startDate = new Date(session.start_date).toLocaleDateString('ru-RU');
    const endDate = new Date(session.end_date).toLocaleDateString('ru-RU');

    const statusEmoji = session.is_active ? '✅ Активна' : '❌ Неактивна';
    const currentEmoji = session.isCurrentlyActive ? ' 🔥 (В процессе)' : '';

    let message = `📊 **Статистика сессии #${session.id}**\n\n`;
    message += `**${session.name}**\n`;
    message += `Статус: ${statusEmoji}${currentEmoji}\n`;
    message += `Период: ${startDate} - ${endDate}\n\n`;

    message += `**Ставки вознаграждения:**\n`;
    message += `• Уровень 1: ${parseFloat(session.reward_rate_level_1).toFixed(4)}%\n`;
    message += `• Уровень 2: ${parseFloat(session.reward_rate_level_2).toFixed(4)}%\n`;
    message += `• Уровень 3: ${parseFloat(session.reward_rate_level_3).toFixed(4)}%\n`;
    message += `• Уровень 4: ${parseFloat(session.reward_rate_level_4).toFixed(4)}%\n`;
    message += `• Уровень 5: ${parseFloat(session.reward_rate_level_5).toFixed(4)}%\n\n`;

    message += `**Статистика выплат:**\n`;
    message += `💰 Всего начислено: ${stats.totalRewards} наград на ${stats.totalAmount.toFixed(2)} USDT\n`;
    message += `✅ Выплачено: ${stats.paidRewards} наград на ${stats.paidAmount.toFixed(2)} USDT\n`;
    message += `⏳ Ожидает: ${stats.pendingRewards} наград на ${stats.pendingAmount.toFixed(2)} USDT\n`;

    await ctx.editMessageText(message, {
      parse_mode: 'Markdown',
      ...Markup.inlineKeyboard([
        [Markup.button.callback('🔄 Пересчитать награды', `reward_calculate_${sessionId}`)],
        [
          Markup.button.callback(session.is_active ? '❌ Деактивировать' : '✅ Активировать', `reward_toggle_${sessionId}`),
          Markup.button.callback('🗑 Удалить', `reward_delete_${sessionId}`),
        ],
        [Markup.button.callback('◀️ К списку', 'reward_sessions')],
      ]),
    });

    await ctx.answerCbQuery();

    logAdminAction(ctx.from!.id, 'view_reward_stats', { sessionId });
  } catch (error) {
    await ctx.answerCbQuery('❌ Ошибка при загрузке статистики');
    logger.error('Failed to load reward stats', {
      adminId: ctx.from!.id,
      sessionId,
      error: error instanceof Error ? error.message : String(error),
    });
  }
};

/**
 * Handle manual reward calculation
 */
export const handleCalculateRewards = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isSuperAdmin) {
    await ctx.answerCbQuery('Только главный администратор может запускать расчет наград');
    return;
  }

  const callbackData = ctx.callbackQuery && 'data' in ctx.callbackQuery ? ctx.callbackQuery.data : '';
  const match = callbackData.match(/^reward_calculate_(\d+)$/);

  if (!match) {
    await ctx.answerCbQuery('❌ Неверный формат');
    return;
  }

  const sessionId = parseInt(match[1]);

  await ctx.answerCbQuery('⏳ Начинаю расчет наград...');

  try {
    const result = await rewardService.calculateRewardsForSession(sessionId);

    if (!result.success) {
      await ctx.reply(`❌ Ошибка: ${result.error}`);
      return;
    }

    await ctx.reply(
      `✅ **Расчет наград завершен**\n\n` +
      `Начислено наград: ${result.rewardsCalculated}\n` +
      `Общая сумма: ${result.totalRewardAmount?.toFixed(2)} USDT\n\n` +
      `Награды добавлены в систему и ожидают выплаты.`,
      { parse_mode: 'Markdown' }
    );

    logAdminAction(ctx.from!.id, 'calculate_rewards', {
      sessionId,
      rewardsCalculated: result.rewardsCalculated,
      totalAmount: result.totalRewardAmount,
    });
  } catch (error) {
    await ctx.reply('❌ Ошибка при расчете наград');
    logger.error('Failed to calculate rewards', {
      adminId: ctx.from!.id,
      sessionId,
      error: error instanceof Error ? error.message : String(error),
    });
  }
};

/**
 * Toggle session active status
 */
export const handleToggleSession = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isSuperAdmin) {
    await ctx.answerCbQuery('Только главный администратор может изменять статус сессий');
    return;
  }

  const callbackData = ctx.callbackQuery && 'data' in ctx.callbackQuery ? ctx.callbackQuery.data : '';
  const match = callbackData.match(/^reward_toggle_(\d+)$/);

  if (!match) {
    await ctx.answerCbQuery('❌ Неверный формат');
    return;
  }

  const sessionId = parseInt(match[1]);

  try {
    const session = await rewardService.getSessionById(sessionId);

    if (!session) {
      await ctx.answerCbQuery('❌ Сессия не найдена');
      return;
    }

    const newStatus = !session.is_active;

    const result = await rewardService.updateSession(sessionId, {
      isActive: newStatus,
    });

    if (!result.success) {
      await ctx.answerCbQuery(`❌ ${result.error}`);
      return;
    }

    await ctx.answerCbQuery(`✅ Сессия ${newStatus ? 'активирована' : 'деактивирована'}`);

    // Refresh stats view
    await handleRewardStats(ctx);

    logAdminAction(ctx.from!.id, 'toggle_reward_session', {
      sessionId,
      newStatus,
    });
  } catch (error) {
    await ctx.answerCbQuery('❌ Ошибка при изменении статуса');
    logger.error('Failed to toggle session', {
      adminId: ctx.from!.id,
      sessionId,
      error: error instanceof Error ? error.message : String(error),
    });
  }
};

/**
 * Delete session
 */
export const handleDeleteSession = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isSuperAdmin) {
    await ctx.answerCbQuery('Только главный администратор может удалять сессии');
    return;
  }

  const callbackData = ctx.callbackQuery && 'data' in ctx.callbackQuery ? ctx.callbackQuery.data : '';
  const match = callbackData.match(/^reward_delete_(\d+)$/);

  if (!match) {
    await ctx.answerCbQuery('❌ Неверный формат');
    return;
  }

  const sessionId = parseInt(match[1]);

  try {
    const result = await rewardService.deleteSession(sessionId);

    if (!result.success) {
      await ctx.answerCbQuery(result.error || 'Не удалось удалить', { show_alert: true });
      return;
    }

    await ctx.answerCbQuery('✅ Сессия удалена');

    await ctx.editMessageText(
      `✅ **Сессия #${sessionId} удалена**\n\n` +
      `Сессия успешно удалена из системы.`,
      {
        parse_mode: 'Markdown',
        ...Markup.inlineKeyboard([
          [Markup.button.callback('📋 К списку сессий', 'reward_sessions')],
          [Markup.button.callback('◀️ Админ-панель', 'admin_panel')],
        ]),
      }
    );

    logAdminAction(ctx.from!.id, 'delete_reward_session', { sessionId });
  } catch (error) {
    await ctx.answerCbQuery('❌ Ошибка при удалении');
    logger.error('Failed to delete session', {
      adminId: ctx.from!.id,
      sessionId,
      error: error instanceof Error ? error.message : String(error),
    });
  }
};

/**
 * Start reward session creation
 */
export const handleStartCreateSession = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext & SessionContext;

  if (!adminCtx.isSuperAdmin) {
    await ctx.answerCbQuery('Только главный администратор может создавать сессии');
    return;
  }

  const message = `
➕ **Создание сессии наград**

Отправьте данные сессии в следующем формате:

\`\`\`
Название | Начало | Конец | Ур1% | Ур2% | Ур3% | Ур4% | Ур5%
\`\`\`

**Пример:**
\`Июль 2024 | 01.07.2024 | 31.07.2024 | 1.117 | 1.5 | 2.0 | 2.5 | 3.0\`

**Где:**
• Название - название сессии
• Начало/Конец - даты в формате ДД.ММ.ГГГГ
• Ур1%-Ур5% - процентные ставки для уровней депозитов 1-5

Для отмены используйте /cancel
  `.trim();

  await ctx.editMessageText(message, {
    parse_mode: 'Markdown',
    ...Markup.inlineKeyboard([[Markup.button.callback('❌ Отмена', 'reward_sessions')]]),
  });

  await updateSessionState(ctx.from!.id, BotState.AWAITING_REWARD_SESSION_DATA);

  await ctx.answerCbQuery();
};

/**
 * Handle reward session data input
 */
export const handleRewardSessionInput = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext & SessionContext;

  if (!adminCtx.isSuperAdmin) {
    return;
  }

  if (adminCtx.session.state !== BotState.AWAITING_REWARD_SESSION_DATA) {
    return;
  }

  const input = ctx.text?.trim();

  if (!input) {
    await ctx.reply('❌ Пожалуйста, отправьте данные сессии');
    return;
  }

  // Parse format: Name | StartDate | EndDate | Rate1 | Rate2 | Rate3 | Rate4 | Rate5
  const parts = input.split('|').map(p => p.trim());

  if (parts.length !== 8) {
    await ctx.reply(
      '❌ Неверный формат данных.\n\n' +
      'Используйте: `Название | Начало | Конец | Ур1% | Ур2% | Ур3% | Ур4% | Ур5%`\n\n' +
      'Пример: `Июль 2024 | 01.07.2024 | 31.07.2024 | 1.117 | 1.5 | 2.0 | 2.5 | 3.0`',
      { parse_mode: 'Markdown' }
    );
    return;
  }

  const [name, startDateStr, endDateStr, rate1, rate2, rate3, rate4, rate5] = parts;

  // Parse dates
  const parseDate = (dateStr: string): Date | null => {
    const match = dateStr.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
    if (!match) return null;

    const [, day, month, year] = match;
    return new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
  };

  const startDate = parseDate(startDateStr);
  const endDate = parseDate(endDateStr);

  if (!startDate || !endDate) {
    await ctx.reply('❌ Неверный формат дат. Используйте ДД.ММ.ГГГГ (например, 01.07.2024)');
    return;
  }

  // Parse rates
  const rates = [rate1, rate2, rate3, rate4, rate5].map(r => parseFloat(r));

  if (rates.some(r => isNaN(r) || r < 0)) {
    await ctx.reply('❌ Неверный формат процентных ставок. Используйте числа (например, 1.117)');
    return;
  }

  await ctx.reply('⏳ Создаю сессию наград...');

  try {
    const result = await rewardService.createSession({
      name,
      rewardRates: {
        1: rates[0],
        2: rates[1],
        3: rates[2],
        4: rates[3],
        5: rates[4],
      },
      startDate,
      endDate,
      createdBy: adminCtx.admin?.id || ctx.from!.id,
    });

    if (result.error || !result.session) {
      await ctx.reply(`❌ Ошибка: ${result.error || 'Не удалось создать сессию'}`);
      return;
    }

    await ctx.reply(
      `✅ **Сессия создана успешно!**\n\n` +
      `ID: ${result.session.id}\n` +
      `Название: ${result.session.name}\n` +
      `Период: ${startDate.toLocaleDateString('ru-RU')} - ${endDate.toLocaleDateString('ru-RU')}\n\n` +
      `Сессия активна и готова к расчету наград.`,
      { parse_mode: 'Markdown' }
    );

    logAdminAction(ctx.from!.id, 'create_reward_session', {
      sessionId: result.session.id,
      name: result.session.name,
    });
  } catch (error) {
    await ctx.reply('❌ Ошибка при создании сессии');
    logger.error('Failed to create reward session', {
      adminId: ctx.from!.id,
      error: error instanceof Error ? error.message : String(error),
    });
  }

  await updateSessionState(ctx.from!.id, BotState.IDLE);
};

export default {
  handleRewardSessions,
  handleRewardStats,
  handleCalculateRewards,
  handleToggleSession,
  handleDeleteSession,
  handleStartCreateSession,
  handleRewardSessionInput,
};
