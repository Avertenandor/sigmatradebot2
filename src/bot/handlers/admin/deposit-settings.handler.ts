/**
 * Admin Deposit Settings Handler
 * Manages deposit level availability and ROI settings
 */

import { Context, Markup } from 'telegraf';
import { AdminContext } from '../../middlewares/admin.middleware';
import { ERROR_MESSAGES } from '../../../utils/constants';
import { settingsService } from '../../../services/settings.service';
import { logAdminAction } from '../../../utils/logger.util';
import { requireAuthenticatedAdmin } from './utils';

/**
 * Handle deposit settings menu
 * Shows current max open level and allows admin to change it
 */
export const handleDepositSettings = async (ctx: Context): Promise<void> => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery?.(ERROR_MESSAGES.ADMIN_ONLY);
    return;
  }

  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  const currentMaxLevel = await settingsService.getMaxOpenLevel();

  const message = `
⚙️ **Настройки депозитов**

**Текущий максимальный открытый уровень:** ${currentMaxLevel}

📌 **Описание:**
По умолчанию открыт только Уровень 1 (10 USDT).
Вы можете открыть уровни 2-5 для пользователей.

🔒 **Закрытые уровни:** Пользователи не видят их в списке доступных
✅ **Открытые уровни:** Пользователи могут их активировать

🎯 **ROI система (Уровень 1):**
• Максимальный доход: 500% (5x)
• Один активный депозит L1 на пользователя
• После 500% ROI нужен новый депозит

Выберите максимальный открытый уровень:
  `.trim();

  const keyboard = Markup.inlineKeyboard([
    [
      Markup.button.callback('1️⃣ Уровень 1', 'admin_set_max_level_1'),
      Markup.button.callback('2️⃣ Уровень 2', 'admin_set_max_level_2'),
    ],
    [
      Markup.button.callback('3️⃣ Уровень 3', 'admin_set_max_level_3'),
      Markup.button.callback('4️⃣ Уровень 4', 'admin_set_max_level_4'),
    ],
    [
      Markup.button.callback('5️⃣ Уровень 5', 'admin_set_max_level_5'),
    ],
    [Markup.button.callback('« Назад', 'admin_panel')],
  ]);

  if (ctx.callbackQuery && 'message' in ctx.callbackQuery) {
    await ctx.editMessageText(message, {
      parse_mode: 'Markdown',
      ...keyboard,
    });
  } else {
    await ctx.reply(message, {
      parse_mode: 'Markdown',
      ...keyboard,
    });
  }

  if (ctx.callbackQuery) {
    await ctx.answerCbQuery?.();
  }

  logAdminAction(ctx.from!.id, 'viewed_deposit_settings', { currentMaxLevel });
};

/**
 * Handle set max level
 * Updates the maximum open deposit level
 */
export const handleSetMaxLevel = async (ctx: Context): Promise<void> => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery?.(ERROR_MESSAGES.ADMIN_ONLY);
    return;
  }

  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  // Extract level from callback data (e.g., "admin_set_max_level_3")
  const callbackData =
    ctx.callbackQuery && 'data' in ctx.callbackQuery ? ctx.callbackQuery.data : '';
  const level = parseInt(callbackData.split('_').pop() || '1', 10);

  if (level < 1 || level > 5) {
    await ctx.answerCbQuery?.('Неверный уровень');
    return;
  }

  try {
    await settingsService.setMaxOpenLevel(level);

    const message = `
✅ **Настройки обновлены**

Максимальный открытый уровень: **${level}**

${level === 1 ? '🔒 Открыт только Уровень 1 (10 USDT)' : `✅ Открыты уровни 1-${level}`}

Пользователи теперь могут активировать депозиты до уровня ${level}.
    `.trim();

    await ctx.editMessageText(message, {
      parse_mode: 'Markdown',
      ...Markup.inlineKeyboard([
        [Markup.button.callback('« Назад к настройкам', 'admin_deposit_settings')],
        [Markup.button.callback('« Панель админа', 'admin_panel')],
      ]),
    });

    await ctx.answerCbQuery?.('Настройки сохранены ✅');

    logAdminAction(ctx.from!.id, 'set_max_open_level', { level });
  } catch (error) {
    await ctx.answerCbQuery?.('Ошибка сохранения настроек');
    logAdminAction(ctx.from!.id, 'set_max_open_level_failed', {
      level,
      error: error instanceof Error ? error.message : String(error),
    });
  }
};
