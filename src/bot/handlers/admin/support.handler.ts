/**
 * Admin Support Handler
 * Handles admin support ticket management
 */

import { Context, Markup } from 'telegraf';
import { AuthContext } from '../../middlewares/auth.middleware';
import { AdminContext } from '../../middlewares/admin.middleware';
import { SessionContext } from '../../middlewares/session.middleware';
import { supportService } from '../../../services/support.service';
import { notificationService } from '../../../services/notification.service';
import { BotState } from '../../../utils/constants';
import { getAdminPanelKeyboard } from '../../keyboards/admin.keyboard';
import type { SupportCategory, SupportStatus } from '../../../database/entities/SupportTicket.entity';

// Combined context type
type AppContext = AuthContext & SessionContext & AdminContext;

/**
 * Show admin support menu
 */
export async function handleAdminSupportMenu(ctx: AppContext) {
  if (!ctx.admin) return;

  const openTickets = await supportService.listOpen();

  let text = '🆘 Управление техподдержкой\n\n';
  text += `📊 Открытых обращений: ${openTickets.length}\n\n`;

  if (openTickets.length > 0) {
    text += 'Выберите действие:';
  } else {
    text += 'Нет открытых обращений.';
  }

  const keyboard = Markup.inlineKeyboard([
    [Markup.button.callback('📋 Список обращений', 'admin_support_list')],
    [Markup.button.callback('◀️ Назад', 'admin_panel')],
  ]);

  await ctx.editMessageText(text, keyboard);
}

/**
 * List all open support tickets
 */
export async function handleAdminSupportList(ctx: AppContext) {
  if (!ctx.admin) return;

  const tickets = await supportService.listOpen();

  if (tickets.length === 0) {
    await ctx.editMessageText(
      '📋 Список обращений\n\n' + 'Нет открытых обращений.',
      Markup.inlineKeyboard([[Markup.button.callback('◀️ Назад', 'admin_support')]])
    );
    return;
  }

  let text = '📋 Открытые обращения:\n\n';

  const buttons = tickets.map((ticket) => {
    const statusEmoji = getStatusEmoji(ticket.status);
    const categoryName = getCategoryName(ticket.category);
    const assignedInfo = ticket.assigned_admin_id
      ? ` [${ticket.assigned_admin?.username || ticket.assigned_admin_id}]`
      : '';

    return [
      Markup.button.callback(
        `${statusEmoji} #${ticket.id} - ${categoryName}${assignedInfo}`,
        `admin_support_view_${ticket.id}`
      ),
    ];
  });

  buttons.push([Markup.button.callback('◀️ Назад', 'admin_support')]);

  await ctx.editMessageText(text, Markup.inlineKeyboard(buttons));
}

/**
 * View specific support ticket
 */
export async function handleAdminSupportView(ctx: AppContext) {
  if (!ctx.admin || !ctx.callbackQuery || !('data' in ctx.callbackQuery)) return;

  const ticketId = parseInt(ctx.callbackQuery.data.replace('admin_support_view_', ''), 10);
  const ticket = await supportService.get(ticketId);

  if (!ticket) {
    await ctx.answerCbQuery('❌ Обращение не найдено');
    return;
  }

  let text = `🆘 Обращение #${ticket.id}\n\n`;
  text += `Пользователь: ${ticket.user.username || ticket.user.telegram_id}\n`;
  text += `Категория: ${getCategoryName(ticket.category)}\n`;
  text += `Статус: ${getStatusName(ticket.status)}\n`;
  text += `Создано: ${formatDate(ticket.created_at)}\n`;

  if (ticket.assigned_admin_id) {
    text += `Назначено: ${ticket.assigned_admin?.username || ticket.assigned_admin_id}\n`;
  }

  text += '\n━━━━━━━━━━━━━━━━━━\n\n';

  // Show messages
  if (ticket.messages && ticket.messages.length > 0) {
    for (const msg of ticket.messages) {
      const senderLabel =
        msg.sender === 'user' ? '👤 Пользователь' : msg.sender === 'admin' ? '👨‍💼 Админ' : '🤖 Система';

      text += `${senderLabel} (${formatDate(msg.created_at)}):\n`;

      if (msg.text) {
        text += `${msg.text}\n`;
      }

      if (msg.attachments && msg.attachments.length > 0) {
        text += `📎 Вложений: ${msg.attachments.length}\n`;
      }

      text += '\n';
    }
  } else {
    text += 'Нет сообщений.\n';
  }

  // Build action buttons
  const buttons: any[] = [];

  // Assign button (if not assigned or assigned to someone else)
  if (!ticket.assigned_admin_id || ticket.assigned_admin_id !== ctx.admin.id) {
    buttons.push([Markup.button.callback('✋ Взять в работу', `admin_support_assign_${ticketId}`)]);
  }

  // Reply button
  if (ticket.status !== 'closed') {
    buttons.push([Markup.button.callback('💬 Ответить', `admin_support_reply_${ticketId}`)]);
  }

  // Close/Reopen button
  if (ticket.status === 'closed') {
    buttons.push([Markup.button.callback('🔓 Переоткрыть', `admin_support_reopen_${ticketId}`)]);
  } else {
    buttons.push([Markup.button.callback('🔒 Закрыть', `admin_support_close_${ticketId}`)]);
  }

  buttons.push([Markup.button.callback('◀️ Назад к списку', 'admin_support_list')]);

  await ctx.editMessageText(text, Markup.inlineKeyboard(buttons));

  // Send attachments if any
  if (ticket.messages) {
    for (const msg of ticket.messages) {
      if (msg.attachments && msg.attachments.length > 0) {
        for (const att of msg.attachments) {
          try {
            switch (att.type) {
              case 'photo':
                await ctx.replyWithPhoto(att.file_id, { caption: att.caption });
                break;
              case 'voice':
                await ctx.replyWithVoice(att.file_id);
                break;
              case 'audio':
                await ctx.replyWithAudio(att.file_id, { caption: att.caption });
                break;
              case 'document':
                await ctx.replyWithDocument(att.file_id, { caption: att.caption });
                break;
            }
          } catch (error) {
            console.error('Error sending attachment:', error);
          }
        }
      }
    }
  }
}

/**
 * Assign ticket to admin
 */
export async function handleAdminSupportAssign(ctx: AppContext) {
  if (!ctx.admin || !ctx.callbackQuery || !('data' in ctx.callbackQuery)) return;

  const ticketId = parseInt(ctx.callbackQuery.data.replace('admin_support_assign_', ''), 10);

  try {
    await supportService.assignToSelf(ticketId, ctx.admin.id);
    await ctx.answerCbQuery('✅ Обращение назначено на вас');

    // Refresh view
    ctx.callbackQuery.data = `admin_support_view_${ticketId}`;
    await handleAdminSupportView(ctx);
  } catch (error: any) {
    await ctx.answerCbQuery(`❌ ${error.message || 'Ошибка'}`);
  }
}

/**
 * Close support ticket
 */
export async function handleAdminSupportClose(ctx: AppContext) {
  if (!ctx.admin || !ctx.callbackQuery || !('data' in ctx.callbackQuery)) return;

  const ticketId = parseInt(ctx.callbackQuery.data.replace('admin_support_close_', ''), 10);
  const ticket = await supportService.get(ticketId);

  if (!ticket) {
    await ctx.answerCbQuery('❌ Обращение не найдено');
    return;
  }

  try {
    await supportService.close(ticketId);
    await supportService.addSystemMessage(ticketId, 'Обращение закрыто администратором.');

    // Notify user
    await notificationService.notifyUser(
      ticket.user_id,
      `🔒 Ваше обращение #${ticketId} закрыто.\n\n` +
        'Если у вас остались вопросы, вы можете создать новое обращение через меню Техподдержка.'
    );

    await ctx.answerCbQuery('✅ Обращение закрыто');

    // Refresh view
    ctx.callbackQuery.data = `admin_support_view_${ticketId}`;
    await handleAdminSupportView(ctx);
  } catch (error: any) {
    await ctx.answerCbQuery(`❌ ${error.message || 'Ошибка'}`);
  }
}

/**
 * Reopen closed support ticket
 */
export async function handleAdminSupportReopen(ctx: AppContext) {
  if (!ctx.admin || !ctx.callbackQuery || !('data' in ctx.callbackQuery)) return;

  const ticketId = parseInt(ctx.callbackQuery.data.replace('admin_support_reopen_', ''), 10);
  const ticket = await supportService.get(ticketId);

  if (!ticket) {
    await ctx.answerCbQuery('❌ Обращение не найдено');
    return;
  }

  try {
    await supportService.reopen(ticketId);
    await supportService.addSystemMessage(ticketId, 'Обращение переоткрыто администратором.');

    // Notify user
    await notificationService.notifyUser(
      ticket.user_id,
      `🔓 Ваше обращение #${ticketId} переоткрыто.\n\n` + 'Администратор продолжит работу над вашим вопросом.'
    );

    await ctx.answerCbQuery('✅ Обращение переоткрыто');

    // Refresh view
    ctx.callbackQuery.data = `admin_support_view_${ticketId}`;
    await handleAdminSupportView(ctx);
  } catch (error: any) {
    await ctx.answerCbQuery(`❌ ${error.message || 'Ошибка'}`);
  }
}

/**
 * Start replying to ticket
 */
export async function handleAdminSupportReplyStart(ctx: AppContext) {
  if (!ctx.admin || !ctx.callbackQuery || !('data' in ctx.callbackQuery)) return;

  const ticketId = parseInt(ctx.callbackQuery.data.replace('admin_support_reply_', ''), 10);
  const ticket = await supportService.get(ticketId);

  if (!ticket) {
    await ctx.answerCbQuery('❌ Обращение не найдено');
    return;
  }

  // Set state
  ctx.session.state = BotState.AWAITING_ADMIN_SUPPORT_REPLY;
  ctx.session.supportReplyTicketId = ticketId;
  ctx.session.supportReplyMessages = [];

  await ctx.editMessageText(
    `💬 Ответ на обращение #${ticketId}\n\n` +
      'Отправьте ваш ответ пользователю. Вы можете отправить:\n' +
      '• Текстовое сообщение\n' +
      '• Фото\n' +
      '• Голосовое сообщение\n' +
      '• Аудио\n' +
      '• Документ\n\n' +
      'После того как вы добавите всё необходимое, нажмите "📤 Отправить".',
    Markup.inlineKeyboard([
      [Markup.button.callback('📤 Отправить', `admin_support_send_reply_${ticketId}`)],
      [Markup.button.callback('❌ Отмена', `admin_support_view_${ticketId}`)],
    ])
  );
}

/**
 * Capture admin reply input (text, photo, voice, audio, document)
 */
export async function handleAdminSupportReplyInput(ctx: AppContext, next: () => Promise<void>) {
  // Only capture if admin is in reply state
  if (!ctx.admin || ctx.session.state !== BotState.AWAITING_ADMIN_SUPPORT_REPLY) {
    return next();
  }

  if (!ctx.session.supportReplyMessages) {
    ctx.session.supportReplyMessages = [];
  }

  const message = ctx.message;
  if (!message) return;

  const ticketId = ctx.session.supportReplyTicketId;

  // Handle text
  if ('text' in message && message.text && !message.text.startsWith('/')) {
    ctx.session.supportReplyMessages.push({
      type: 'text',
      text: message.text,
    });

    await ctx.reply(
      '✅ Сообщение добавлено.\n\n' + 'Вы можете добавить ещё информации или нажать "📤 Отправить".',
      Markup.inlineKeyboard([
        [Markup.button.callback('📤 Отправить', `admin_support_send_reply_${ticketId}`)],
        [Markup.button.callback('❌ Отмена', `admin_support_view_${ticketId}`)],
      ])
    );
  }

  // Handle photo
  else if ('photo' in message && message.photo && message.photo.length > 0) {
    const photo = message.photo[message.photo.length - 1];
    ctx.session.supportReplyMessages.push({
      type: 'photo',
      file_id: photo.file_id,
      caption: message.caption,
    });

    await ctx.reply(
      '✅ Фото добавлено.',
      Markup.inlineKeyboard([
        [Markup.button.callback('📤 Отправить', `admin_support_send_reply_${ticketId}`)],
        [Markup.button.callback('❌ Отмена', `admin_support_view_${ticketId}`)],
      ])
    );
  }

  // Handle voice
  else if ('voice' in message && message.voice) {
    ctx.session.supportReplyMessages.push({
      type: 'voice',
      file_id: message.voice.file_id,
    });

    await ctx.reply(
      '✅ Голосовое сообщение добавлено.',
      Markup.inlineKeyboard([
        [Markup.button.callback('📤 Отправить', `admin_support_send_reply_${ticketId}`)],
        [Markup.button.callback('❌ Отмена', `admin_support_view_${ticketId}`)],
      ])
    );
  }

  // Handle audio
  else if ('audio' in message && message.audio) {
    ctx.session.supportReplyMessages.push({
      type: 'audio',
      file_id: message.audio.file_id,
      caption: message.caption,
    });

    await ctx.reply(
      '✅ Аудио добавлено.',
      Markup.inlineKeyboard([
        [Markup.button.callback('📤 Отправить', `admin_support_send_reply_${ticketId}`)],
        [Markup.button.callback('❌ Отмена', `admin_support_view_${ticketId}`)],
      ])
    );
  }

  // Handle document
  else if ('document' in message && message.document) {
    ctx.session.supportReplyMessages.push({
      type: 'document',
      file_id: message.document.file_id,
      caption: message.caption,
    });

    await ctx.reply(
      '✅ Документ добавлен.',
      Markup.inlineKeyboard([
        [Markup.button.callback('📤 Отправить', `admin_support_send_reply_${ticketId}`)],
        [Markup.button.callback('❌ Отмена', `admin_support_view_${ticketId}`)],
      ])
    );
  }
}

/**
 * Send admin reply to ticket
 */
export async function handleAdminSupportSendReply(ctx: AppContext) {
  if (!ctx.admin || !ctx.callbackQuery || !('data' in ctx.callbackQuery)) return;

  const ticketId = parseInt(ctx.callbackQuery.data.replace('admin_support_send_reply_', ''), 10);
  const { supportReplyMessages } = ctx.session;

  if (!supportReplyMessages || supportReplyMessages.length === 0) {
    await ctx.answerCbQuery('❌ Пожалуйста, добавьте сообщение для отправки.');
    return;
  }

  const ticket = await supportService.get(ticketId);
  if (!ticket) {
    await ctx.answerCbQuery('❌ Обращение не найдено');
    return;
  }

  try {
    // Combine all text messages
    const textMessages = supportReplyMessages.filter((m) => m.type === 'text');
    const combinedText = textMessages.map((m) => m.text).join('\n\n');

    // Collect attachments
    const attachments = supportReplyMessages
      .filter((m) => m.type !== 'text')
      .map((m) => ({
        type: m.type,
        file_id: m.file_id!,
        caption: m.caption,
      }));

    // Add admin message
    await supportService.addAdminMessage({
      ticketId,
      sender: 'admin',
      adminId: ctx.admin.id,
      text: combinedText || undefined,
      attachments: attachments.length > 0 ? attachments : undefined,
    });

    // Clear session
    ctx.session.state = BotState.IDLE;
    ctx.session.supportReplyTicketId = undefined;
    ctx.session.supportReplyMessages = undefined;

    // Notify user
    let notificationText = `💬 Новый ответ на ваше обращение #${ticketId}\n\n`;
    if (combinedText) {
      notificationText += combinedText;
    }

    await notificationService.notifyUser(ticket.user_id, notificationText);

    // Send attachments to user
    if (attachments.length > 0) {
      for (const att of attachments) {
        try {
          switch (att.type) {
            case 'photo':
              await ctx.telegram.sendPhoto(ticket.user.telegram_id, att.file_id, { caption: att.caption });
              break;
            case 'voice':
              await ctx.telegram.sendVoice(ticket.user.telegram_id, att.file_id);
              break;
            case 'audio':
              await ctx.telegram.sendAudio(ticket.user.telegram_id, att.file_id, { caption: att.caption });
              break;
            case 'document':
              await ctx.telegram.sendDocument(ticket.user.telegram_id, att.file_id, { caption: att.caption });
              break;
          }
        } catch (error) {
          console.error('Error sending attachment to user:', error);
        }
      }
    }

    await ctx.answerCbQuery('✅ Ответ отправлен пользователю');

    // Refresh view
    ctx.callbackQuery.data = `admin_support_view_${ticketId}`;
    await handleAdminSupportView(ctx);
  } catch (error: any) {
    await ctx.answerCbQuery(`❌ ${error.message || 'Ошибка при отправке ответа'}`);
  }
}

/**
 * Get category name
 */
function getCategoryName(category: SupportCategory): string {
  const names: Record<SupportCategory, string> = {
    payments: '💰 Платежи',
    withdrawals: '💸 Выводы',
    finpass: '🔑 Финпароль',
    referrals: '🤝 Рефералы',
    tech: '⚙️ Тех. вопрос',
    other: '❓ Другое',
  };
  return names[category] || category;
}

/**
 * Get status name
 */
function getStatusName(status: SupportStatus): string {
  const names: Record<SupportStatus, string> = {
    open: '🔵 Открыто',
    in_progress: '🟡 В работе',
    answered: '🟢 Отвечено',
    closed: '⚫ Закрыто',
  };
  return names[status] || status;
}

/**
 * Get status emoji
 */
function getStatusEmoji(status: SupportStatus): string {
  const emojis: Record<SupportStatus, string> = {
    open: '🔵',
    in_progress: '🟡',
    answered: '🟢',
    closed: '⚫',
  };
  return emojis[status] || '⚪';
}

/**
 * Format date
 */
function formatDate(date: Date): string {
  return new Date(date).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
