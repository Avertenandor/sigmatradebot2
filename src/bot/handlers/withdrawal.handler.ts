/**
 * Withdrawal Handler
 * Handles withdrawal requests
 */

import { Context } from 'telegraf';
import { Markup } from 'telegraf';
import { AuthContext } from '../middlewares/auth.middleware';
import { SessionContext, updateSessionState } from '../middlewares/session.middleware';
import { BotState } from '../../utils/constants';
import { getBackButton } from '../keyboards';
import userService from '../../services/user.service';
import withdrawalService from '../../services/withdrawal.service';
import { notificationService } from '../../services/notification.service';
import { createLogger } from '../../utils/logger.util';
import { formatUSDT } from '../../utils/money.util';

const logger = createLogger('WithdrawalHandler');

/**
 * Handle withdrawals menu
 */
export const handleWithdrawals = async (ctx: Context) => {
  const authCtx = ctx as AuthContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery('Пожалуйста, сначала зарегистрируйтесь');
    return;
  }

  // Get user balance
  const balance = await userService.getUserBalance(authCtx.user.id);

  const minAmount = withdrawalService.getMinWithdrawalAmount();

  const message = `
💸 **Вывод средств**

**Ваш баланс:**
💰 Доступно для вывода: **${formatUSDT(balance?.availableBalance || 0)} USDT**
⏳ В ожидании выплаты: ${formatUSDT(balance?.pendingEarnings || 0)} USDT
${balance && balance.pendingWithdrawals > 0 ? `🔒 Заблокировано в выводах: ${formatUSDT(balance.pendingWithdrawals)} USDT\n` : ''}
**Условия вывода:**
• Минимальная сумма: ${minAmount} USDT
• Вывод на ваш кошелек: \`${authCtx.user.wallet_address}\`
• Обработка: 15-30 минут

${balance && balance.availableBalance >= minAmount ? '✅ Вы можете запросить вывод' : '❌ Недостаточно средств для вывода'}
  `.trim();

  const buttons: any[][] = [];

  // Add request withdrawal button if balance is sufficient
  if (balance && balance.availableBalance >= minAmount) {
    buttons.push([
      Markup.button.callback('💸 Запросить вывод', 'request_withdrawal'),
    ]);
  }

  // Add withdrawal history button
  buttons.push([
    Markup.button.callback('📜 История выводов', 'withdrawal_history'),
  ]);

  // Add back button
  buttons.push([
    Markup.button.callback('🔙 Назад', 'main_menu'),
  ]);

  if (ctx.callbackQuery && 'message' in ctx.callbackQuery) {
    await ctx.editMessageText(message, {
      parse_mode: 'Markdown',
      ...Markup.inlineKeyboard(buttons),
    });
  } else {
    await ctx.reply(message, {
      parse_mode: 'Markdown',
      ...Markup.inlineKeyboard(buttons),
    });
  }

  if (ctx.callbackQuery) {
    await ctx.answerCbQuery();
  }

  logger.debug('Withdrawals menu shown', {
    userId: authCtx.user.id,
    availableBalance: balance?.availableBalance || 0,
  });
};

/**
 * Handle request withdrawal
 */
export const handleRequestWithdrawal = async (ctx: Context) => {
  const authCtx = ctx as AuthContext & SessionContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery('Пожалуйста, сначала зарегистрируйтесь');
    return;
  }

  // Get user balance
  const balance = await userService.getUserBalance(authCtx.user.id);
  const minAmount = withdrawalService.getMinWithdrawalAmount();

  if (!balance || balance.availableBalance < minAmount) {
    await ctx.answerCbQuery('Недостаточно средств для вывода');
    return;
  }

  // Update session state
  await updateSessionState(ctx.from!.id, BotState.AWAITING_WITHDRAWAL_AMOUNT);

  const message = `
💸 **Запрос на вывод**

Доступно для вывода: **${formatUSDT(balance.availableBalance)} USDT**
Минимальная сумма: ${minAmount} USDT

Укажите сумму для вывода (в USDT):
  `.trim();

  await ctx.editMessageText(message, {
    parse_mode: 'Markdown',
    ...Markup.inlineKeyboard([
      [Markup.button.callback('❌ Отмена', 'withdrawals')],
    ]),
  });

  await ctx.answerCbQuery();

  logger.debug('Withdrawal request started', {
    userId: authCtx.user.id,
  });
};

/**
 * Handle withdrawal amount input
 */
export const handleWithdrawalAmountInput = async (ctx: Context) => {
  const authCtx = ctx as AuthContext & SessionContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.reply('Пожалуйста, сначала зарегистрируйтесь');
    return;
  }

  // Check session state
  if (authCtx.session?.state !== BotState.AWAITING_WITHDRAWAL_AMOUNT) {
    return;
  }

  const input = ctx.text?.trim();
  if (!input) {
    await ctx.reply('Пожалуйста, укажите сумму');
    return;
  }

  // Parse amount
  const amount = parseFloat(input);

  // Validate amount (check for NaN, Infinity, negative, zero, too large)
  const MAX_AMOUNT = 1000000; // 1 million USDT max per withdrawal
  if (isNaN(amount) || !isFinite(amount) || amount <= 0 || amount > MAX_AMOUNT) {
    await ctx.reply(
      amount > MAX_AMOUNT
        ? `❌ Максимальная сумма вывода: ${MAX_AMOUNT.toLocaleString()} USDT`
        : '❌ Неверный формат суммы. Укажите число больше 0'
    );
    return;
  }

  // Limit decimal precision to 2 places
  const roundedAmount = Math.round(amount * 100) / 100;

  // Validate amount against balance
  const balance = await userService.getUserBalance(authCtx.user.id);
  const minAmount = withdrawalService.getMinWithdrawalAmount();

  if (!balance || balance.availableBalance < roundedAmount) {
    await ctx.reply(`❌ Недостаточно средств. Доступно: ${formatUSDT(balance?.availableBalance || 0)} USDT`, {
      ...Markup.inlineKeyboard([
        [Markup.button.callback('🔙 Назад', 'withdrawals')],
      ]),
    });
    await updateSessionState(ctx.from!.id, BotState.IDLE);
    return;
  }

  if (roundedAmount < minAmount) {
    await ctx.reply(`❌ Минимальная сумма вывода: ${minAmount} USDT`, {
      ...Markup.inlineKeyboard([
        [Markup.button.callback('🔙 Назад', 'withdrawals')],
      ]),
    });
    await updateSessionState(ctx.from!.id, BotState.IDLE);
    return;
  }

  // Store amount in session data and request financial password
  if (authCtx.session) {
    authCtx.session.data = { withdrawalAmount: roundedAmount };
  }

  await updateSessionState(ctx.from!.id, BotState.AWAITING_WITHDRAWAL_FINANCIAL_PASSWORD);

  const passwordMessage = `
🔐 **Подтверждение вывода**

💰 Сумма: ${formatUSDT(roundedAmount)} USDT
💳 Кошелек: \`${authCtx.user.wallet_address}\`

⚠️ **Для подтверждения операции введите ваш финансовый пароль:**

Этот пароль был выдан вам при регистрации.
  `.trim();

  await ctx.reply(passwordMessage, {
    parse_mode: 'Markdown',
    ...Markup.inlineKeyboard([
      [Markup.button.callback('❌ Отмена', 'withdrawals')],
    ]),
  });

  logger.debug('Withdrawal amount validated, requesting password', {
    userId: authCtx.user.id,
    amount,
  });
};

/**
 * Handle withdrawal financial password verification
 */
export const handleWithdrawalPasswordInput = async (ctx: Context) => {
  const authCtx = ctx as AuthContext & SessionContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.reply('Пожалуйста, сначала зарегистрируйтесь');
    return;
  }

  // Check session state
  if (authCtx.session?.state !== BotState.AWAITING_WITHDRAWAL_FINANCIAL_PASSWORD) {
    return;
  }

  // Get amount from session
  const amount = authCtx.session?.data?.withdrawalAmount;
  if (!amount) {
    await ctx.reply('❌ Ошибка: сумма не найдена. Начните процесс вывода заново.', {
      ...Markup.inlineKeyboard([
        [Markup.button.callback('🔙 Назад', 'withdrawals')],
      ]),
    });
    await updateSessionState(ctx.from!.id, BotState.IDLE);
    return;
  }

  const password = ctx.text?.trim();
  if (!password) {
    await ctx.reply('Пожалуйста, введите финансовый пароль');
    return;
  }

  // Verify financial password
  const { success, error } = await userService.verifyFinancialPassword(
    authCtx.user.id,
    password
  );

  if (!success) {
    await ctx.reply(`❌ ${error || 'Неверный пароль'}. Попробуйте снова или отмените операцию.`, {
      ...Markup.inlineKeyboard([
        [Markup.button.callback('❌ Отмена', 'withdrawals')],
      ]),
    });
    logger.warn('Failed withdrawal password attempt', {
      userId: authCtx.user.id,
    });
    return;
  }

  // Password verified, create withdrawal request
  const { transaction, error: withdrawalError } = await withdrawalService.requestWithdrawal({
    userId: authCtx.user.id,
    amount,
  });

  if (withdrawalError) {
    await ctx.reply(`❌ Ошибка: ${withdrawalError}`, {
      ...Markup.inlineKeyboard([
        [Markup.button.callback('🔙 Назад', 'withdrawals')],
      ]),
    });
    await updateSessionState(ctx.from!.id, BotState.IDLE);
    return;
  }

  // Send notification to user about withdrawal request
  await notificationService.notifyWithdrawalReceived(
    authCtx.user.telegram_id,
    amount
  ).catch((err) => {
    logger.error('Failed to send withdrawal received notification', { error: err });
  });

  const successMessage = `
✅ **Заявка на вывод создана!**

💰 Сумма: ${formatUSDT(amount)} USDT
🆔 ID заявки: ${transaction?.id}
💳 Кошелек: \`${authCtx.user.wallet_address}\`

Заявка принята в обработку.
Средства будут отправлены в течение 15-30 минут.

Вы получите уведомление когда вывод будет выполнен.
  `.trim();

  await ctx.reply(successMessage, {
    parse_mode: 'Markdown',
    ...Markup.inlineKeyboard([
      [Markup.button.callback('📜 История выводов', 'withdrawal_history')],
      [Markup.button.callback('🔙 Главное меню', 'main_menu')],
    ]),
  });

  // Clear session data and reset state
  if (authCtx.session) {
    authCtx.session.data = {};
  }
  await updateSessionState(ctx.from!.id, BotState.IDLE);

  logger.info('Withdrawal request created after password verification', {
    userId: authCtx.user.id,
    transactionId: transaction?.id,
    amount,
  });
};

/**
 * Handle withdrawal history
 */
export const handleWithdrawalHistory = async (ctx: Context) => {
  const authCtx = ctx as AuthContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery('Пожалуйста, сначала зарегистрируйтесь');
    return;
  }

  // Get page from callback data
  const callbackData = ctx.callbackQuery && 'data' in ctx.callbackQuery ? ctx.callbackQuery.data : '';
  const page = parseInt(callbackData.split('_').pop() || '1', 10);

  // Get withdrawal history
  const { withdrawals, total, pages } = await withdrawalService.getUserWithdrawals(
    authCtx.user.id,
    { page, limit: 5 }
  );

  let message = `📜 **История выводов**\n\n`;

  if (withdrawals.length === 0) {
    message += 'У вас пока нет выводов.';
  } else {
    withdrawals.forEach((withdrawal, index) => {
      const emoji =
        withdrawal.status === 'confirmed'
          ? '✅'
          : withdrawal.status === 'pending'
          ? '⏳'
          : '❌';
      const date = new Date(withdrawal.created_at).toLocaleDateString('ru-RU');

      message += `${emoji} **${formatUSDT(parseFloat(withdrawal.amount))} USDT**\n`;
      message += `Дата: ${date}\n`;
      message += `Статус: ${withdrawal.status}\n`;

      if (withdrawal.tx_hash) {
        message += `TX: \`${withdrawal.tx_hash.substring(0, 10)}...${withdrawal.tx_hash.substring(withdrawal.tx_hash.length - 6)}\`\n`;
      }

      message += '\n';
    });

    message += `📊 Всего выводов: ${total}`;
  }

  const buttons: any[][] = [];

  // Add cancel buttons for pending withdrawals
  const pendingWithdrawals = withdrawals.filter(w => w.status === 'pending');
  if (pendingWithdrawals.length > 0) {
    pendingWithdrawals.forEach((withdrawal) => {
      buttons.push([
        Markup.button.callback(
          `❌ Отменить вывод ${formatUSDT(parseFloat(withdrawal.amount))} USDT`,
          `cancel_withdrawal_${withdrawal.id}`
        ),
      ]);
    });
  }

  // Add pagination if needed
  if (pages > 1) {
    const navButtons = [];
    if (page > 1) {
      navButtons.push(
        Markup.button.callback('⬅️ Назад', `withdrawal_history_${page - 1}`)
      );
    }
    navButtons.push(
      Markup.button.callback(`${page}/${pages}`, 'noop')
    );
    if (page < pages) {
      navButtons.push(
        Markup.button.callback('Вперед ➡️', `withdrawal_history_${page + 1}`)
      );
    }
    buttons.push(navButtons);
  }

  buttons.push([
    Markup.button.callback('🔙 Назад', 'withdrawals'),
  ]);

  if (ctx.callbackQuery && 'message' in ctx.callbackQuery) {
    await ctx.editMessageText(message, {
      parse_mode: 'Markdown',
      ...Markup.inlineKeyboard(buttons),
    });
  } else {
    await ctx.reply(message, {
      parse_mode: 'Markdown',
      ...Markup.inlineKeyboard(buttons),
    });
  }

  if (ctx.callbackQuery) {
    await ctx.answerCbQuery();
  }

  logger.debug('Withdrawal history shown', {
    userId: authCtx.user.id,
    page,
    totalWithdrawals: total,
  });
};

/**
 * Handle cancel withdrawal
 */
export const handleCancelWithdrawal = async (ctx: Context) => {
  const authCtx = ctx as AuthContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery('Пожалуйста, сначала зарегистрируйтесь');
    return;
  }

  // Extract withdrawal ID from callback data (e.g., "cancel_withdrawal_123")
  const callbackData = ctx.callbackQuery && 'data' in ctx.callbackQuery ? ctx.callbackQuery.data : '';
  const match = callbackData.match(/^cancel_withdrawal_(\d+)$/);

  if (!match) {
    await ctx.answerCbQuery('❌ Ошибка: неверный формат');
    return;
  }

  const withdrawalId = parseInt(match[1], 10);

  // Cancel withdrawal
  const { success, error } = await withdrawalService.cancelWithdrawal(
    withdrawalId,
    authCtx.user.id
  );

  if (!success) {
    await ctx.answerCbQuery(`❌ ${error}`);
    return;
  }

  await ctx.answerCbQuery('✅ Вывод отменен, средства возвращены на баланс');

  // Update message to show success
  await ctx.editMessageText(
    `✅ **Вывод отменён**\n\n` +
    `Заявка на вывод была успешно отменена.\n` +
    `Средства возвращены на ваш баланс и доступны для использования.`,
    {
      parse_mode: 'Markdown',
      ...Markup.inlineKeyboard([
        [Markup.button.callback('📜 История выводов', 'withdrawal_history')],
        [Markup.button.callback('🔙 Назад', 'withdrawals')],
      ]),
    }
  );

  logger.info('Withdrawal cancelled by user', {
    userId: authCtx.user.id,
    withdrawalId,
  });
};

export default {
  handleWithdrawals,
  handleRequestWithdrawal,
  handleWithdrawalAmountInput,
  handleWithdrawalPasswordInput,
  handleWithdrawalHistory,
  handleCancelWithdrawal,
};
