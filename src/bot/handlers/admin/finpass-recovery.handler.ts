/**
 * Admin Handlers for Financial Password Recovery
 *
 * Allows admins to:
 * - View pending recovery requests
 * - Review request details
 * - Approve and reset password (generates new password, sends to user)
 * - Reject requests
 */

import { Context, Markup } from 'telegraf';
import { AdminContext } from '../../middlewares/admin.middleware';
import { requireAuthenticatedAdmin } from './utils';
import { finpassRecoveryService } from '../../../services/finpass-recovery.service';
import { createLogger, logAdminAction } from '../../../utils/logger.util';

const logger = createLogger('AdminFinpassRecoveryHandler');

/**
 * List pending finpass recovery requests
 * Callback: 'admin_finpass_list'
 */
export const handleFinpassList = async (ctx: Context): Promise<void> => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery?.('Только для админов');
    return;
  }

  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  try {
    const list = await finpassRecoveryService.listPending(20);

    let message = '🔑 **Заявки на восстановление финпароля**\n\n';

    if (list.length === 0) {
      message += '✅ Нет ожидающих заявок';
      await ctx.editMessageText(message, {
        parse_mode: 'Markdown',
        ...Markup.inlineKeyboard([
          [Markup.button.callback('◀️ Админ-панель', 'admin_panel')],
        ]),
      });
      await ctx.answerCbQuery?.();
      return;
    }

    // Show first 10 requests
    for (const req of list.slice(0, 10)) {
      const user = req.user;
      const username = user?.username ? `@${user.username}` : '';
      const statusEmoji = {
        pending: '⏳',
        in_review: '👁',
        approved: '✅',
        rejected: '❌',
        sent: '📤',
      }[req.status] || '❓';

      message += `${statusEmoji} #${req.id} • user_id=${req.user_id} ${username} • ${req.status}\n`;
    }

    if (list.length > 10) {
      message += `\n_...и ещё ${list.length - 10} заявок_`;
    }

    // Action buttons for first 5 requests
    const buttons: any[][] = [];
    for (const req of list.slice(0, 5)) {
      buttons.push([
        Markup.button.callback(`👁 #${req.id}`, `admin_finpass_view_${req.id}`),
        Markup.button.callback(`✅ #${req.id}`, `admin_finpass_approve_${req.id}`),
        Markup.button.callback(`❌ #${req.id}`, `admin_finpass_reject_${req.id}`),
      ]);
    }

    buttons.push([Markup.button.callback('◀️ Админ-панель', 'admin_panel')]);

    await ctx.editMessageText(message, {
      parse_mode: 'Markdown',
      ...Markup.inlineKeyboard(buttons),
    });

    await ctx.answerCbQuery?.();

    logAdminAction(ctx.from!.id, 'view_finpass_requests', { count: list.length });
  } catch (error) {
    logger.error('Error listing finpass requests', { error });
    await ctx.answerCbQuery?.('❌ Ошибка загрузки заявок');
  }
};

/**
 * View single finpass recovery request details
 * Callback: 'admin_finpass_view_{id}'
 */
export const handleFinpassView = async (ctx: Context): Promise<void> => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery?.('Только для админов');
    return;
  }

  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  try {
    const data = 'data' in (ctx.callbackQuery || {}) ? (ctx.callbackQuery as any).data as string : '';
    const match = data.match(/^admin_finpass_view_(\d+)$/);
    if (!match) {
      await ctx.answerCbQuery?.('Неверный формат');
      return;
    }

    const requestId = parseInt(match[1], 10);
    const request = await finpassRecoveryService.getRequest(requestId);

    if (!request) {
      await ctx.answerCbQuery?.('❌ Заявка не найдена');
      return;
    }

    const user = request.user;
    const processedBy = request.processed_by_admin;

    const message = [
      `🔑 **Заявка #${request.id}**`,
      '',
      `👤 Пользователь: ID ${request.user_id} ${user?.username ? `(@${user.username})` : ''}`,
      `📅 Создана: ${request.created_at.toLocaleString('ru-RU')}`,
      `📊 Статус: ${request.status}`,
      '',
      `🎥 Видео требуется: ${request.video_required ? 'Да' : 'Нет'}`,
      `✓ Видео проверено: ${request.video_verified ? 'Да' : 'Нет'}`,
      '',
    ];

    if (processedBy) {
      message.push(`👨‍💼 Обработал: ${processedBy.telegram_id}`);
    }

    if (request.processed_at) {
      message.push(`⏰ Обработано: ${request.processed_at.toLocaleString('ru-RU')}`);
    }

    if (request.admin_comment) {
      message.push(`💬 Комментарий: ${request.admin_comment}`);
    }

    const buttons: any[][] = [];

    // Action buttons based on status
    if (request.status === 'pending' || request.status === 'in_review') {
      buttons.push([
        Markup.button.callback('✅ Одобрить', `admin_finpass_approve_${request.id}`),
        Markup.button.callback('❌ Отклонить', `admin_finpass_reject_${request.id}`),
      ]);
    }

    buttons.push([
      Markup.button.callback('📋 Список заявок', 'admin_finpass_list'),
      Markup.button.callback('◀️ Админ-панель', 'admin_panel'),
    ]);

    await ctx.editMessageText(message.join('\n'), {
      parse_mode: 'Markdown',
      ...Markup.inlineKeyboard(buttons),
    });

    await ctx.answerCbQuery?.();
  } catch (error) {
    logger.error('Error viewing finpass request', { error });
    await ctx.answerCbQuery?.('❌ Ошибка загрузки заявки');
  }
};

/**
 * Approve finpass recovery request and send new password to user
 * Callback: 'admin_finpass_approve_{id}'
 */
export const handleFinpassApprove = async (ctx: Context): Promise<void> => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery?.('Только для админов');
    return;
  }

  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  try {
    const data = 'data' in (ctx.callbackQuery || {}) ? (ctx.callbackQuery as any).data as string : '';
    const match = data.match(/^admin_finpass_approve_(\d+)$/);
    if (!match) {
      await ctx.answerCbQuery?.('Неверный формат');
      return;
    }

    const requestId = parseInt(match[1], 10);
    const result = await finpassRecoveryService.approveAndReset(requestId, ctx.from!.id);

    if (!result.success) {
      await ctx.answerCbQuery?.(`❌ ${result.error}`, { show_alert: true });
      return;
    }

    await ctx.answerCbQuery('✅ Готово: новый финпароль отправлен пользователю');

    await ctx.editMessageText(
      `✅ **Заявка #${requestId} обработана**\n\n` +
      'Новый финансовый пароль сгенерирован и отправлен пользователю.\n\n' +
      '_Пароль доступен пользователю повторно в течение 1 часа_',
      {
        parse_mode: 'Markdown',
        ...Markup.inlineKeyboard([
          [Markup.button.callback('📋 Список заявок', 'admin_finpass_list')],
          [Markup.button.callback('◀️ Админ-панель', 'admin_panel')],
        ]),
      }
    );

    logger.info('Admin approved finpass recovery', {
      adminId: ctx.from!.id,
      requestId,
    });
  } catch (error) {
    logger.error('Error approving finpass request', { error });
    await ctx.answerCbQuery?.('❌ Ошибка при обработке заявки', { show_alert: true });
  }
};

/**
 * Reject finpass recovery request
 * Callback: 'admin_finpass_reject_{id}'
 */
export const handleFinpassReject = async (ctx: Context): Promise<void> => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery?.('Только для админов');
    return;
  }

  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  try {
    const data = 'data' in (ctx.callbackQuery || {}) ? (ctx.callbackQuery as any).data as string : '';
    const match = data.match(/^admin_finpass_reject_(\d+)$/);
    if (!match) {
      await ctx.answerCbQuery?.('Неверный формат');
      return;
    }

    const requestId = parseInt(match[1], 10);
    const success = await finpassRecoveryService.reject(requestId, ctx.from!.id);

    if (!success) {
      await ctx.answerCbQuery?.('❌ Ошибка при отклонении заявки', { show_alert: true });
      return;
    }

    await ctx.answerCbQuery('✅ Заявка отклонена');

    await ctx.editMessageText(
      `❌ **Заявка #${requestId} отклонена**`,
      {
        parse_mode: 'Markdown',
        ...Markup.inlineKeyboard([
          [Markup.button.callback('📋 Список заявок', 'admin_finpass_list')],
          [Markup.button.callback('◀️ Админ-панель', 'admin_panel')],
        ]),
      }
    );

    logger.info('Admin rejected finpass recovery', {
      adminId: ctx.from!.id,
      requestId,
    });
  } catch (error) {
    logger.error('Error rejecting finpass request', { error });
    await ctx.answerCbQuery?.('❌ Ошибка при отклонении заявки', { show_alert: true });
  }
};
