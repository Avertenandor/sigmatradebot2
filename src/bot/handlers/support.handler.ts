/**
 * User Support Handler
 * Handles user support ticket interactions
 */

import { Context, Markup } from 'telegraf';
import { AuthContext } from '../middlewares/auth.middleware';
import { AdminContext } from '../middlewares/admin.middleware';
import { SessionContext } from '../middlewares/session.middleware';
import { supportService } from '../../services/support.service';
import { notificationService } from '../../services/notification.service';
import { BotState } from '../../utils/constants';
import { getMainKeyboard } from '../keyboards/main.keyboard';
import type { SupportCategory } from '../../database/entities/SupportTicket.entity';

// Combined context type
type AppContext = AuthContext & SessionContext & AdminContext;

/**
 * Show support menu with category selection
 */
export async function handleSupportMenu(ctx: AppContext) {
  if (!ctx.user) return;

  // Check if user already has an active ticket
  const activeTicket = await supportService.getUserActiveTicket(ctx.user.id);

  if (activeTicket) {
    await ctx.editMessageText(
      `📝 У вас уже есть активное обращение #${activeTicket.id}\n\n` +
        `Категория: ${getCategoryName(activeTicket.category)}\n` +
        `Статус: ${getStatusName(activeTicket.status)}\n\n` +
        `Пожалуйста, дождитесь ответа администратора или закрытия обращения.`,
      getMainKeyboard(ctx.isAdmin)
    );
    return;
  }

  // Show category selection
  const keyboard = Markup.inlineKeyboard([
    [
      Markup.button.callback('💰 Платежи', 'support_cat_payments'),
      Markup.button.callback('💸 Выводы', 'support_cat_withdrawals'),
    ],
    [
      Markup.button.callback('🔑 Финпароль', 'support_cat_finpass'),
      Markup.button.callback('🤝 Рефералы', 'support_cat_referrals'),
    ],
    [
      Markup.button.callback('⚙️ Тех. вопрос', 'support_cat_tech'),
      Markup.button.callback('❓ Другое', 'support_cat_other'),
    ],
    [Markup.button.callback('◀️ Назад', 'main_menu')],
  ]);

  await ctx.editMessageText(
    '🆘 Техподдержка\n\n' +
      'Выберите категорию вашего обращения:',
    keyboard
  );
}

/**
 * Handle support category selection
 */
export async function handleSupportChooseCategory(ctx: AppContext) {
  if (!ctx.user || !ctx.callbackQuery || !('data' in ctx.callbackQuery)) return;

  const categoryMap: Record<string, SupportCategory> = {
    support_cat_payments: 'payments',
    support_cat_withdrawals: 'withdrawals',
    support_cat_finpass: 'finpass',
    support_cat_referrals: 'referrals',
    support_cat_tech: 'tech',
    support_cat_other: 'other',
  };

  const category = categoryMap[ctx.callbackQuery.data];
  if (!category) return;

  // Store category in session
  ctx.session.supportCategory = category;
  ctx.session.supportMessages = [];
  ctx.session.state = BotState.AWAITING_SUPPORT_INPUT;

  const keyboard = Markup.inlineKeyboard([
    [Markup.button.callback('📤 Отправить', 'support_submit')],
    [Markup.button.callback('❌ Отмена', 'main_menu')],
  ]);

  await ctx.editMessageText(
    `📝 Обращение: ${getCategoryName(category)}\n\n` +
      'Опишите вашу проблему. Вы можете отправить:\n' +
      '• Текстовое сообщение\n' +
      '• Фото\n' +
      '• Голосовое сообщение\n' +
      '• Аудио\n' +
      '• Документ\n\n' +
      'После того как вы добавите все необходимое, нажмите "📤 Отправить".',
    keyboard
  );
}

/**
 * Capture support input (text, photo, voice, audio, document)
 */
export async function captureSupportInput(ctx: AppContext, next: () => Promise<void>) {
  // Only capture if user is in support input state
  if (!ctx.user || ctx.session.state !== BotState.AWAITING_SUPPORT_INPUT) {
    return next();
  }

  if (!ctx.session.supportMessages) {
    ctx.session.supportMessages = [];
  }

  const message = ctx.message;
  if (!message) return;

  // Handle text
  if ('text' in message && message.text && !message.text.startsWith('/')) {
    ctx.session.supportMessages.push({
      type: 'text',
      text: message.text,
    });

    await ctx.reply(
      '✅ Сообщение добавлено.\n\n' +
        'Вы можете добавить ещё информации или нажать "📤 Отправить" для отправки обращения.',
      Markup.inlineKeyboard([
        [Markup.button.callback('📤 Отправить', 'support_submit')],
        [Markup.button.callback('❌ Отмена', 'main_menu')],
      ])
    );
  }

  // Handle photo
  else if ('photo' in message && message.photo && message.photo.length > 0) {
    const photo = message.photo[message.photo.length - 1]; // Largest size
    ctx.session.supportMessages.push({
      type: 'photo',
      file_id: photo.file_id,
      caption: message.caption,
    });

    await ctx.reply(
      '✅ Фото добавлено.\n\n' +
        'Вы можете добавить ещё информации или нажать "📤 Отправить".',
      Markup.inlineKeyboard([
        [Markup.button.callback('📤 Отправить', 'support_submit')],
        [Markup.button.callback('❌ Отмена', 'main_menu')],
      ])
    );
  }

  // Handle voice
  else if ('voice' in message && message.voice) {
    ctx.session.supportMessages.push({
      type: 'voice',
      file_id: message.voice.file_id,
    });

    await ctx.reply(
      '✅ Голосовое сообщение добавлено.\n\n' +
        'Вы можете добавить ещё информации или нажать "📤 Отправить".',
      Markup.inlineKeyboard([
        [Markup.button.callback('📤 Отправить', 'support_submit')],
        [Markup.button.callback('❌ Отмена', 'main_menu')],
      ])
    );
  }

  // Handle audio
  else if ('audio' in message && message.audio) {
    ctx.session.supportMessages.push({
      type: 'audio',
      file_id: message.audio.file_id,
      caption: message.caption,
    });

    await ctx.reply(
      '✅ Аудио добавлено.\n\n' +
        'Вы можете добавить ещё информации или нажать "📤 Отправить".',
      Markup.inlineKeyboard([
        [Markup.button.callback('📤 Отправить', 'support_submit')],
        [Markup.button.callback('❌ Отмена', 'main_menu')],
      ])
    );
  }

  // Handle document
  else if ('document' in message && message.document) {
    ctx.session.supportMessages.push({
      type: 'document',
      file_id: message.document.file_id,
      caption: message.caption,
    });

    await ctx.reply(
      '✅ Документ добавлен.\n\n' +
        'Вы можете добавить ещё информации или нажать "📤 Отправить".',
      Markup.inlineKeyboard([
        [Markup.button.callback('📤 Отправить', 'support_submit')],
        [Markup.button.callback('❌ Отмена', 'main_menu')],
      ])
    );
  }
}

/**
 * Submit support ticket
 */
export async function handleSupportSubmit(ctx: AppContext) {
  if (!ctx.user) return;

  const { supportCategory, supportMessages } = ctx.session;

  if (!supportCategory || !supportMessages || supportMessages.length === 0) {
    await ctx.answerCbQuery('❌ Пожалуйста, опишите вашу проблему перед отправкой.');
    return;
  }

  try {
    // Combine all text messages into one
    const textMessages = supportMessages.filter((m) => m.type === 'text');
    const combinedText = textMessages.map((m) => m.text).join('\n\n');

    // Collect all attachments
    const attachments = supportMessages
      .filter((m) => m.type !== 'text')
      .map((m) => ({
        type: m.type,
        file_id: m.file_id!,
        caption: m.caption,
      }));

    // Create ticket
    const ticket = await supportService.createTicket({
      userId: ctx.user.id,
      category: supportCategory,
      initialMessage: combinedText || undefined,
      attachments: attachments.length > 0 ? attachments : undefined,
    });

    // Clear session
    ctx.session.state = BotState.IDLE;
    ctx.session.supportCategory = undefined;
    ctx.session.supportMessages = undefined;

    // Notify user
    await ctx.editMessageText(
      `✅ Ваше обращение #${ticket.id} успешно создано!\n\n` +
        `Категория: ${getCategoryName(ticket.category)}\n\n` +
        'Администратор ответит вам в ближайшее время. Вы получите уведомление, когда придёт ответ.',
      getMainKeyboard(ctx.isAdmin)
    );

    // Find on-duty admin and notify
    const onDutyAdminId = await supportService.findOnDutyAdmin();

    if (onDutyAdminId) {
      // Notify specific on-duty admin and assign to them
      await supportService.assignToSelf(ticket.id, onDutyAdminId);

      await notificationService.notifyAdmin(
        onDutyAdminId,
        `🆘 Новое обращение #${ticket.id}\n\n` +
          `От: ${ctx.user.username || ctx.user.telegram_id}\n` +
          `Категория: ${getCategoryName(ticket.category)}\n\n` +
          `Обращение автоматически назначено на вас (вы на дежурстве).\n\n` +
          `Используйте /admin → Техподдержка для ответа.`
      );
    } else {
      // Notify all admins
      await notificationService.notifyAllAdmins(
        `🆘 Новое обращение #${ticket.id}\n\n` +
          `От: ${ctx.user.username || ctx.user.telegram_id}\n` +
          `Категория: ${getCategoryName(ticket.category)}\n\n` +
          `Используйте /admin → Техподдержка для ответа.`
      );
    }
  } catch (error: any) {
    await ctx.editMessageText(
      `❌ ${error.message || 'Ошибка при создании обращения. Попробуйте позже.'}`,
      getMainKeyboard(ctx.isAdmin)
    );
  }
}

/**
 * Get human-readable category name
 */
function getCategoryName(category: SupportCategory): string {
  const names: Record<SupportCategory, string> = {
    payments: '💰 Платежи',
    withdrawals: '💸 Выводы',
    finpass: '🔑 Финпароль',
    referrals: '🤝 Рефералы',
    tech: '⚙️ Технический вопрос',
    other: '❓ Другое',
  };
  return names[category] || category;
}

/**
 * Get human-readable status name
 */
function getStatusName(status: string): string {
  const names: Record<string, string> = {
    open: '🔵 Открыто',
    in_progress: '🟡 В работе',
    answered: '🟢 Отвечено',
    closed: '⚫ Закрыто',
  };
  return names[status] || status;
}
