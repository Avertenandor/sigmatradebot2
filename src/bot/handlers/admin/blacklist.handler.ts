/**
 * Admin Blacklist Handler
 * Manages pre-registration ban list (blacklist)
 * Allows admins to add/remove users from blacklist
 */

import { Context, Markup } from 'telegraf';
import { AdminContext } from '../../middlewares/admin.middleware';
import { SessionContext, updateSessionState } from '../../middlewares/session.middleware';
import { BotState } from '../../../utils/constants';
import { getCancelButton } from '../../keyboards';
import { requireAuthenticatedAdmin } from './utils';
import { createLogger } from '../../../utils/logger.util';
import blacklistService from '../../../services/blacklist.service';

const logger = createLogger('AdminBlacklistHandler');

/**
 * Show blacklist management menu
 */
export const handleBlacklistMenu = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery?.('Только для админов');
    return;
  }

  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  const message = `
🛑 **Чёрный список (pre-ban)**

Здесь вы можете запретить регистрацию пользователю по его Telegram ID
или убрать его из предрегистрационного списка.

**Что это даёт:**
• Пользователи из чёрного списка не смогут пройти регистрацию
• Они получат отказ с текстом о решении сообщества
• Это работает ДО регистрации (pre-ban)

Выберите действие:
  `.trim();

  const keyboard = Markup.inlineKeyboard([
    [Markup.button.callback('➕ Добавить по Telegram ID', 'admin_blacklist_add')],
    [Markup.button.callback('➖ Удалить по Telegram ID', 'admin_blacklist_remove')],
    [Markup.button.callback('◀️ Админ-панель', 'admin_panel')],
  ]);

  if (ctx.callbackQuery && 'message' in ctx.callbackQuery) {
    await ctx.editMessageText(message, { parse_mode: 'Markdown', ...keyboard });
    await ctx.answerCbQuery?.();
  } else {
    await ctx.reply(message, { parse_mode: 'Markdown', ...keyboard });
  }

  logger.debug('Blacklist menu shown', { adminId: ctx.from!.id });
};

/**
 * Start adding user to blacklist
 */
export const handleStartBlacklistAdd = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext & SessionContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery?.('Только для админов');
    return;
  }

  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  await updateSessionState(ctx.from!.id, BotState.AWAITING_ADMIN_BLACKLIST_ADD);

  const msg = `
➕ **Добавить в чёрный список**

Отправьте Telegram ID и опционально причину блокировки.

**Примеры:**
\`123456789\`
\`123456789 спам и фишинг\`
\`987654321 мошенничество\`

После добавления пользователь не сможет зарегистрироваться в боте.
  `.trim();

  await ctx.editMessageText(msg, { parse_mode: 'Markdown', ...getCancelButton() });
  await ctx.answerCbQuery?.();

  logger.debug('Blacklist add started', { adminId: ctx.from!.id });
};

/**
 * Handle blacklist add input (Telegram ID + optional reason)
 */
export const handleBlacklistAddInput = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext & SessionContext;

  if (!adminCtx.isAdmin) {
    return;
  }

  if (adminCtx.session.state !== BotState.AWAITING_ADMIN_BLACKLIST_ADD) {
    return;
  }

  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  const input = ctx.message && 'text' in ctx.message ? (ctx.message.text || '').trim() : '';

  if (!input) {
    await ctx.reply('❌ Укажите Telegram ID (и опционально причину через пробел)');
    return;
  }

  // Parse input: first part is ID, rest is reason
  const parts = input.split(' ');
  const idPart = parts[0];

  if (!/^\d+$/.test(idPart)) {
    await ctx.reply('❌ Неверный формат Telegram ID. Используйте только цифры.');
    return;
  }

  const telegramId = parseInt(idPart, 10);
  const reason = parts.slice(1).join(' ').trim() || undefined;

  // Add to blacklist
  const { success, error } = await blacklistService.add(telegramId, ctx.from!.id, reason);

  if (!success) {
    await ctx.reply(`❌ Ошибка: ${error || 'не удалось добавить'}`);
    logger.error('Failed to add to blacklist', { adminId: ctx.from!.id, telegramId, error });
    return;
  }

  await ctx.reply(
    `✅ **Добавлено в чёрный список**\n\n` +
    `👤 Telegram ID: \`${telegramId}\`\n` +
    `${reason ? `📝 Причина: ${reason}\n` : ''}` +
    `\nПользователь не сможет зарегистрироваться.`,
    { parse_mode: 'Markdown' }
  );

  await updateSessionState(ctx.from!.id, BotState.IDLE);

  logger.info('User added to blacklist', {
    adminId: ctx.from!.id,
    telegramId,
    reason,
  });
};

/**
 * Start removing user from blacklist
 */
export const handleStartBlacklistRemove = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext & SessionContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery?.('Только для админов');
    return;
  }

  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  await updateSessionState(ctx.from!.id, BotState.AWAITING_ADMIN_BLACKLIST_REMOVE);

  const msg = `
➖ **Удалить из чёрного списка**

Отправьте Telegram ID пользователя, которого нужно убрать из чёрного списка.

**Пример:**
\`123456789\`

После удаления пользователь сможет зарегистрироваться в боте.
  `.trim();

  await ctx.editMessageText(msg, { parse_mode: 'Markdown', ...getCancelButton() });
  await ctx.answerCbQuery?.();

  logger.debug('Blacklist remove started', { adminId: ctx.from!.id });
};

/**
 * Handle blacklist remove input (Telegram ID)
 */
export const handleBlacklistRemoveInput = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext & SessionContext;

  if (!adminCtx.isAdmin) {
    return;
  }

  if (adminCtx.session.state !== BotState.AWAITING_ADMIN_BLACKLIST_REMOVE) {
    return;
  }

  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  const input = ctx.message && 'text' in ctx.message ? (ctx.message.text || '').trim() : '';

  if (!/^\d+$/.test(input)) {
    await ctx.reply('❌ Неверный формат Telegram ID. Используйте только цифры.');
    return;
  }

  const telegramId = parseInt(input, 10);

  // Check if exists before removing (for better UX)
  const entry = await blacklistService.getEntry(telegramId);

  if (!entry) {
    await ctx.reply(
      `⚠️ Telegram ID \`${telegramId}\` не найден в чёрном списке.`,
      { parse_mode: 'Markdown' }
    );
    await updateSessionState(ctx.from!.id, BotState.IDLE);
    return;
  }

  // Remove from blacklist
  const { success, error } = await blacklistService.remove(telegramId, ctx.from!.id);

  if (!success) {
    await ctx.reply(`❌ Ошибка: ${error || 'не удалось удалить'}`);
    logger.error('Failed to remove from blacklist', { adminId: ctx.from!.id, telegramId, error });
    return;
  }

  await ctx.reply(
    `✅ **Удалён из чёрного списка**\n\n` +
    `👤 Telegram ID: \`${telegramId}\`\n` +
    `${entry.reason ? `📝 Была причина: ${entry.reason}\n` : ''}` +
    `\nПользователь теперь может зарегистрироваться.`,
    { parse_mode: 'Markdown' }
  );

  await updateSessionState(ctx.from!.id, BotState.IDLE);

  logger.info('User removed from blacklist', {
    adminId: ctx.from!.id,
    telegramId,
  });
};

export default {
  handleBlacklistMenu,
  handleStartBlacklistAdd,
  handleBlacklistAddInput,
  handleStartBlacklistRemove,
  handleBlacklistRemoveInput,
};
