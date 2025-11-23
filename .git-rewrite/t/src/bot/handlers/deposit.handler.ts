/**
 * Deposit Handler
 * Handles deposit-related actions
 */

import { Context } from 'telegraf';
import { AuthContext } from '../middlewares/auth.middleware';
import {
  getDepositLevelsKeyboard,
  getDepositInfoKeyboard,
  getDepositHistoryKeyboard,
  getBackButton,
} from '../keyboards';
import depositService from '../../services/deposit.service';
import { DEPOSIT_LEVELS, REQUIRED_REFERRALS_PER_LEVEL } from '../../utils/constants';
import { createLogger } from '../../utils/logger.util';
import { config } from '../../config';

const logger = createLogger('DepositHandler');

/**
 * Handle deposits menu
 */
export const handleDeposits = async (ctx: Context) => {
  const authCtx = ctx as AuthContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery('Пожалуйста, сначала зарегистрируйтесь');
    return;
  }

  // Get activated and available levels
  const activatedLevels = await depositService.getActivatedLevels(authCtx.user.id);
  const availableLevels = await depositService.getAvailableLevels(authCtx.user.id);

  const message = `
💰 **Депозитные планы**

**Ваши уровни:**
${activatedLevels.length > 0 ? activatedLevels.map((l) => `✅ Уровень ${l}: ${DEPOSIT_LEVELS[l as keyof typeof DEPOSIT_LEVELS]} USDT`).join('\n') : '❌ Нет активированных уровней'}

**Доступны для активации:**
${availableLevels.length > 0 ? availableLevels.map((l) => `💵 Уровень ${l}: ${DEPOSIT_LEVELS[l as keyof typeof DEPOSIT_LEVELS]} USDT`).join('\n') : 'Нет доступных уровней'}

📌 Активируйте уровни последовательно, снизу вверх.
  `.trim();

  const keyboard = getDepositLevelsKeyboard(activatedLevels, availableLevels);

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
    await ctx.answerCbQuery();
  }

  logger.debug('Deposits menu shown', {
    userId: authCtx.user.id,
    activatedLevels,
    availableLevels,
  });
};

/**
 * Handle deposit level info
 */
export const handleDepositLevel = async (ctx: Context) => {
  const authCtx = ctx as AuthContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery('Пожалуйста, сначала зарегистрируйтесь');
    return;
  }

  // Extract level from callback data (e.g., "deposit_level_1")
  const callbackData = ctx.callbackQuery && 'data' in ctx.callbackQuery ? ctx.callbackQuery.data : '';
  const level = parseInt(callbackData.split('_').pop() || '0', 10);

  if (level < 1 || level > 5) {
    await ctx.answerCbQuery('Неверный уровень');
    return;
  }

  // Get deposit info
  const depositInfo = depositService.getDepositInfo(level);
  if (!depositInfo) {
    await ctx.answerCbQuery('Ошибка получения информации');
    return;
  }

  // Check if can activate
  const { canActivate, reason } = await depositService.canActivateLevel(
    authCtx.user.id,
    level
  );

  // Check if already activated
  const activatedLevels = await depositService.getActivatedLevels(authCtx.user.id);
  const isActivated = activatedLevels.includes(level);

  // Get referral count
  const referralCount = await depositService.getDirectReferralCount(authCtx.user.id);

  const message = `
💰 **Уровень ${level}**

**Сумма:** ${depositInfo.amount} USDT
**Требуется рефералов:** ${depositInfo.requiredReferrals}
**У вас рефералов:** ${referralCount}

**Статус:** ${isActivated ? '✅ Активирован' : canActivate ? '💵 Доступен для активации' : '🔒 Заблокирован'}

${!canActivate && reason ? `❌ ${reason}` : ''}

${canActivate && !isActivated ? `
**Как активировать:**
1. Отправьте ${depositInfo.amount} USDT на адрес:
\`${config.blockchain.systemWalletAddress}\`

2. После отправки дождитесь 12 подтверждений в блокчейне

3. Уровень будет автоматически активирован

⚠️ **Важно:** Отправляйте точную сумму ${depositInfo.amount} USDT через сеть BSC (BEP-20)
` : ''}
  `.trim();

  await ctx.editMessageText(message, {
    parse_mode: 'Markdown',
    ...getDepositInfoKeyboard(level, canActivate && !isActivated),
  });

  await ctx.answerCbQuery();

  logger.debug('Deposit level info shown', {
    userId: authCtx.user.id,
    level,
    canActivate,
    isActivated,
  });
};

/**
 * Handle activate deposit
 */
export const handleActivateDeposit = async (ctx: Context) => {
  const authCtx = ctx as AuthContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery('Пожалуйста, сначала зарегистрируйтесь');
    return;
  }

  // Extract level from callback data
  const callbackData = ctx.callbackQuery && 'data' in ctx.callbackQuery ? ctx.callbackQuery.data : '';
  const level = parseInt(callbackData.split('_').pop() || '0', 10);

  if (level < 1 || level > 5) {
    await ctx.answerCbQuery('Неверный уровень');
    return;
  }

  const depositInfo = depositService.getDepositInfo(level);
  if (!depositInfo) {
    await ctx.answerCbQuery('Ошибка');
    return;
  }

  // Check if user can activate this level
  const { canActivate, reason } = await depositService.canActivateLevel(
    authCtx.user.id,
    level
  );

  if (!canActivate) {
    await ctx.answerCbQuery(reason || 'Невозможно активировать этот уровень');
    return;
  }

  // Create pending deposit in database
  const { deposit, error } = await depositService.createPendingDeposit({
    userId: authCtx.user.id,
    level,
    amount: depositInfo.amount,
  });

  if (error) {
    await ctx.answerCbQuery(error);
    return;
  }

  const message = `
💳 **Активация уровня ${level}**

**Сумма:** ${depositInfo.amount} USDT

**Адрес для отправки:**
\`${config.blockchain.systemWalletAddress}\`

**Инструкция:**
1. Откройте ваш кошелек
2. Выберите сеть BSC (BEP-20)
3. Отправьте **точно ${depositInfo.amount} USDT**
4. Дождитесь 12 подтверждений

После отправки бот автоматически обнаружит транзакцию и активирует уровень.

⏱ Время обработки: 5-10 минут

✅ Депозит зарегистрирован в системе (ID: ${deposit?.id})
  `.trim();

  await ctx.editMessageText(message, {
    parse_mode: 'Markdown',
    ...getBackButton('deposits'),
  });

  await ctx.answerCbQuery('Скопируйте адрес и отправьте USDT');

  logger.info('Pending deposit created and instructions shown', {
    userId: authCtx.user.id,
    depositId: deposit?.id,
    level,
    amount: depositInfo.amount,
  });
};

/**
 * Handle check pending deposits status
 */
export const handleCheckPendingDeposits = async (ctx: Context) => {
  const authCtx = ctx as AuthContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery('Пожалуйста, сначала зарегистрируйтесь');
    return;
  }

  // Get pending deposits
  const pendingDeposits = await depositService.getPendingDeposits(authCtx.user.id);

  let message = `⏳ **Проверка статуса депозитов**\n\n`;

  if (pendingDeposits.length === 0) {
    message += 'У вас нет ожидающих подтверждения депозитов.';
  } else {
    message += `Найдено **${pendingDeposits.length}** ожидающих депозитов:\n\n`;

    pendingDeposits.forEach((deposit, index) => {
      const createdDate = new Date(deposit.created_at);
      const timeAgo = Math.floor((Date.now() - createdDate.getTime()) / 1000 / 60); // minutes

      const status = deposit.tx_hash
        ? `🔄 Ожидание ${config.blockchain.confirmationBlocks} подтверждений`
        : `⏳ Ожидание отправки средств`;

      message += `${index + 1}. **Уровень ${deposit.level}** - ${deposit.amountAsNumber} USDT\n`;
      message += `   Создан: ${timeAgo < 60 ? `${timeAgo} мин` : `${Math.floor(timeAgo / 60)} ч`} назад\n`;
      message += `   Статус: ${status}\n`;

      if (deposit.tx_hash) {
        message += `   TX: \`${deposit.tx_hash.substring(0, 10)}...${deposit.tx_hash.substring(deposit.tx_hash.length - 6)}\`\n`;
      }

      message += '\n';
    });

    message += `💡 Подтверждение обычно занимает 5-10 минут после отправки.`;
  }

  // Create buttons for cancelling deposits without tx_hash
  const buttons: any[][] = [];
  const cancelableDeposits = pendingDeposits.filter((d) => !d.tx_hash || d.tx_hash.length === 0);

  if (cancelableDeposits.length > 0) {
    cancelableDeposits.forEach((deposit) => {
      buttons.push([
        Markup.button.callback(
          `❌ Отменить депозит уровня ${deposit.level}`,
          `cancel_deposit_${deposit.id}`
        ),
      ]);
    });
  }

  buttons.push([Markup.button.callback('🔙 Назад', 'deposits')]);

  const keyboard = Markup.inlineKeyboard(buttons);

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
    await ctx.answerCbQuery();
  }

  logger.debug('Pending deposits status shown', {
    userId: authCtx.user.id,
    pendingCount: pendingDeposits.length,
    cancelableCount: cancelableDeposits.length,
  });
};

/**
 * Handle deposit history
 */
export const handleDepositHistory = async (ctx: Context) => {
  const authCtx = ctx as AuthContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery('Пожалуйста, сначала зарегистрируйтесь');
    return;
  }

  // Get page from callback data (e.g., "deposit_history_2")
  const callbackData = ctx.callbackQuery && 'data' in ctx.callbackQuery ? ctx.callbackQuery.data : '';
  const page = parseInt(callbackData.split('_').pop() || '1', 10);

  // Get deposit history
  const { deposits, total, pages } = await depositService.getDepositHistory(
    authCtx.user.id,
    { page, limit: 5 }
  );

  let message = `📜 **История депозитов**\n\n`;

  if (deposits.length === 0) {
    message += 'У вас пока нет депозитов.';
  } else {
    deposits.forEach((deposit, index) => {
      const emoji = deposit.isConfirmed ? '✅' : deposit.isPending ? '⏳' : '❌';
      const date = new Date(deposit.created_at).toLocaleDateString('ru-RU');

      message += `${emoji} **Уровень ${deposit.level}** - ${deposit.amountAsNumber} USDT\n`;
      message += `Дата: ${date}\n`;
      message += `Статус: ${deposit.status}\n`;
      message += `TX: \`${deposit.tx_hash.substring(0, 10)}...${deposit.tx_hash.substring(deposit.tx_hash.length - 6)}\`\n\n`;
    });

    message += `📊 Всего депозитов: ${total}`;
  }

  const keyboard = getDepositHistoryKeyboard(page, pages);

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
    await ctx.answerCbQuery();
  }

  logger.debug('Deposit history shown', {
    userId: authCtx.user.id,
    page,
    totalDeposits: total,
  });
};

/**
 * Handle cancel pending deposit
 */
export const handleCancelDeposit = async (ctx: Context) => {
  const authCtx = ctx as AuthContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery('Пожалуйста, сначала зарегистрируйтесь');
    return;
  }

  // Extract deposit ID from callback data
  const callbackData = ctx.callbackQuery && 'data' in ctx.callbackQuery ? ctx.callbackQuery.data : '';
  const match = callbackData.match(/^cancel_deposit_(\d+)$/);

  if (!match) {
    await ctx.answerCbQuery('❌ Неверный формат');
    return;
  }

  const depositId = parseInt(match[1]);

  try {
    const { success, error } = await depositService.cancelPendingDeposit(
      authCtx.user.id,
      depositId
    );

    if (!success) {
      await ctx.answerCbQuery(`❌ ${error}`);
      return;
    }

    await ctx.answerCbQuery('✅ Депозит отменён');

    // Update message to show success
    await ctx.editMessageText(
      `✅ **Депозит отменён**\n\n` +
      `Запрос на депозит был успешно отменён.\n` +
      `Вы можете создать новый запрос на депозит в любое время.`,
      {
        parse_mode: 'Markdown',
        ...Markup.inlineKeyboard([
          [Markup.button.callback('💰 Депозиты', 'deposits')],
          [Markup.button.callback('🏠 Главное меню', 'main_menu')],
        ]),
      }
    );

    logger.info('Deposit cancelled by user', {
      userId: authCtx.user.id,
      depositId,
    });
  } catch (error) {
    await ctx.answerCbQuery('❌ Ошибка при отмене');
    logger.error('Failed to cancel deposit', {
      userId: authCtx.user.id,
      depositId,
      error: error instanceof Error ? error.message : String(error),
    });
  }
};

export default {
  handleDeposits,
  handleDepositLevel,
  handleActivateDeposit,
  handleCheckPendingDeposits,
  handleDepositHistory,
  handleCancelDeposit,
};
