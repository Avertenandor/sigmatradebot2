/**
 * Admin Authentication Handler
 * Handles admin login, logout, and management
 */

import { Context, Markup } from 'telegraf';
import { AdminContext } from '../middlewares/admin.middleware';
import { SessionContext, updateSessionState } from '../middlewares/session.middleware';
import { BotState } from '../../utils/constants';
import adminService from '../../services/admin.service';
import { setAdminSession, clearAdminSession } from '../middlewares/admin.middleware';
import { createLogger, logAdminAction } from '../../utils/logger.util';
import { isValidMasterKeyFormat, maskMasterKey } from '../../utils/admin-auth.util';

const logger = createLogger('AdminAuthHandler');

/**
 * Handle /admin_login command
 */
export const handleAdminLogin = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isAdmin) {
    await ctx.reply('❌ У вас нет прав администратора.');
    return;
  }

  // Already authenticated
  if (adminCtx.isAuthenticated) {
    const remainingMinutes = adminCtx.adminSession?.remainingTimeMinutes || 0;
    await ctx.reply(
      `✅ Вы уже аутентифицированы.\n\n` +
      `Сессия истекает через: ${remainingMinutes} мин.\n\n` +
      `Используйте /admin_logout для выхода.`
    );
    return;
  }

  const message = `
🔐 **Вход в админ-панель**

Введите ваш мастер-ключ для входа.

Формат: XXXX-XXXX-XXXX-XXXX

Сессия будет активна 1 час с момента последней активности.

Для отмены используйте /cancel
  `.trim();

  await ctx.reply(message, {
    parse_mode: 'Markdown',
  });

  await updateSessionState(ctx.from!.id, BotState.AWAITING_ADMIN_MASTER_KEY);
};

/**
 * Handle master key input
 */
export const handleMasterKeyInput = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext & SessionContext;

  if (!adminCtx.isAdmin) {
    await ctx.reply('❌ У вас нет прав администратора.');
    return;
  }

  if (adminCtx.session?.state !== BotState.AWAITING_ADMIN_MASTER_KEY) {
    return;
  }

  const masterKey = ctx.text?.trim().toUpperCase();

  if (!masterKey) {
    await ctx.reply('❌ Пожалуйста, введите мастер-ключ.');
    return;
  }

  // Validate format
  if (!isValidMasterKeyFormat(masterKey)) {
    await ctx.reply(
      '❌ Неверный формат мастер-ключа.\n\n' +
      'Правильный формат: XXXX-XXXX-XXXX-XXXX\n\n' +
      'Попробуйте снова или используйте /cancel для отмены.'
    );
    return;
  }

  // Attempt login
  const { session, admin, error } = await adminService.login({
    telegramId: ctx.from!.id,
    masterKey,
  });

  if (error || !session || !admin) {
    await ctx.reply(`❌ ${error || 'Ошибка входа'}\n\nПопробуйте снова или используйте /cancel для отмены.`);

    logAdminAction(ctx.from!.id, 'failed_login', {
      error,
    });

    return;
  }

  // FIX #14: Store session token in Redis (now async)
  await setAdminSession(ctx.from!.id, session.session_token);

  await ctx.reply(
    `✅ **Вход выполнен успешно!**\n\n` +
    `Роль: ${admin.role === 'super_admin' ? 'Главный администратор' : 'Администратор'}\n` +
    `Сессия действует: 1 час\n\n` +
    `Используйте /admin_panel для доступа к панели управления.`,
    { parse_mode: 'Markdown' }
  );

  await updateSessionState(ctx.from!.id, BotState.IDLE);

  logAdminAction(ctx.from!.id, 'login', {
    adminId: admin.id,
    sessionId: session.id,
  });
};

/**
 * Handle /admin_logout command
 */
export const handleAdminLogout = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isAdmin) {
    await ctx.reply('❌ У вас нет прав администратора.');
    return;
  }

  if (!adminCtx.isAuthenticated || !adminCtx.adminSession) {
    await ctx.reply('ℹ️ Вы не аутентифицированы.');
    return;
  }

  const sessionToken = adminCtx.adminSession.session_token;

  await adminService.logout(sessionToken);
  // FIX #14: Clear session from Redis (now async)
  await clearAdminSession(ctx.from!.id);

  await ctx.reply('✅ Выход выполнен. Сессия завершена.');

  logAdminAction(ctx.from!.id, 'logout', {});
};

/**
 * Handle /admin_session command (check session status)
 */
export const handleAdminSession = async (ctx: Context) => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isAdmin) {
    await ctx.reply('❌ У вас нет прав администратора.');
    return;
  }

  if (!adminCtx.isAuthenticated || !adminCtx.adminSession) {
    await ctx.reply(
      '🔓 Вы не аутентифицированы.\n\n' +
      'Используйте /admin_login для входа.'
    );
    return;
  }

  const session = adminCtx.adminSession;
  const admin = adminCtx.admin!;

  await ctx.reply(
    `🔐 **Информация о сессии**\n\n` +
    `Администратор: ${admin.displayName}\n` +
    `Роль: ${admin.role === 'super_admin' ? 'Главный администратор' : 'Администратор'}\n` +
    `Статус: Активна\n` +
    `Осталось времени: ${session.remainingTimeMinutes} мин.\n\n` +
    `Используйте /admin_logout для выхода.`,
    { parse_mode: 'Markdown' }
  );
};

export default {
  handleAdminLogin,
  handleMasterKeyInput,
  handleAdminLogout,
  handleAdminSession,
};
