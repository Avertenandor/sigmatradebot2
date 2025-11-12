/**
 * Financial Password Recovery Handler (User Side)
 *
 * Allows users to request manual password reset
 * SLA: 3-5 business days for admin processing
 */

import { Context, Markup } from 'telegraf';
import { AuthContext } from '../middlewares/auth.middleware';
import { createLogger } from '../../utils/logger.util';
import { finpassRecoveryService } from '../../services/finpass-recovery.service';
import { updateSessionState } from '../middlewares/session.middleware';
import { BotState } from '../../utils/constants';

const logger = createLogger('FinpassRecoveryHandler');

/**
 * Handle user request to recover financial password
 * Triggered by callback: 'recover_finpass'
 */
export const handleRequestFinpassRecovery = async (ctx: Context) => {
  const authCtx = ctx as AuthContext;

  // Must be registered
  if (!authCtx.isRegistered || !authCtx.user) {
    if (ctx.callbackQuery) {
      await ctx.answerCbQuery('Сначала зарегистрируйтесь');
    } else {
      await ctx.reply('Сначала зарегистрируйтесь');
    }
    return;
  }

  try {
    // Create recovery request
    const { success, error, requestId } = await finpassRecoveryService.createRequest(authCtx.user.id);

    if (!success) {
      await ctx.reply(`❌ Не удалось создать заявку: ${error || 'попробуйте позже'}`);
      return;
    }

    const message = [
      '🔑 **Заявка на восстановление финпароля создана**',
      '',
      `🆔 Номер заявки: #${requestId}`,
      '',
      '⏳ **Срок обработки: 3–5 рабочих дней**',
      '',
      '👨‍💼 Заявку вручную проверит администратор',
      '🎥 Может потребоваться видеоверификация',
      '',
      'ℹ️ Вы получите уведомление в этом чате, когда новый пароль будет готов',
    ].join('\n');

    const keyboard = Markup.inlineKeyboard([
      [Markup.button.callback('🏠 Главное меню', 'main_menu')],
    ]);

    if (ctx.callbackQuery && 'message' in ctx.callbackQuery) {
      await ctx.editMessageText(message, {
        parse_mode: 'Markdown',
        ...keyboard,
      });
      await ctx.answerCbQuery('✅ Заявка создана');
    } else {
      await ctx.reply(message, {
        parse_mode: 'Markdown',
        ...keyboard,
      });
    }

    await updateSessionState(ctx.from!.id, BotState.IDLE);

    logger.info('User requested finpass recovery', {
      userId: authCtx.user.id,
      requestId,
    });
  } catch (error) {
    logger.error('Error handling finpass recovery request', {
      userId: authCtx.user?.id,
      error,
    });
    await ctx.reply('❌ Произошла ошибка. Попробуйте позже.');
  }
};
