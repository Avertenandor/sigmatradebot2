/**
 * Transaction History Handlers
 * Handlers for comprehensive transaction history
 */

import { Context } from 'telegraf';
import { Markup } from 'telegraf';
import transactionService from '../../services/transaction.service';
import { AuthContext } from '../middlewares/auth.middleware';
import { createLogger } from '../../utils/logger.util';
import { BUTTON_LABELS, TransactionStatus, TransactionType } from '../../utils/constants';

const logger = createLogger('TransactionHandler');

/**
 * Get emoji for transaction type
 */
function getTransactionTypeEmoji(type: TransactionType): string {
  switch (type) {
    case TransactionType.DEPOSIT:
      return '💰';
    case TransactionType.WITHDRAWAL:
      return '💸';
    case TransactionType.REFERRAL_REWARD:
      return '🎁';
    case TransactionType.SYSTEM_PAYOUT:
      return '💵';
    default:
      return '📝';
  }
}

/**
 * Get emoji for transaction status
 */
function getStatusEmoji(status: TransactionStatus): string {
  switch (status) {
    case TransactionStatus.CONFIRMED:
      return '✅';
    case TransactionStatus.PENDING:
      return '⏳';
    case TransactionStatus.FAILED:
      return '❌';
    default:
      return '❓';
  }
}

/**
 * Get status text
 */
function getStatusText(status: TransactionStatus): string {
  switch (status) {
    case TransactionStatus.CONFIRMED:
      return 'Подтверждено';
    case TransactionStatus.PENDING:
      return 'В обработке';
    case TransactionStatus.FAILED:
      return 'Отклонено';
    default:
      return 'Неизвестно';
  }
}

/**
 * Handle transaction history main view
 */
export const handleTransactionHistory = async (ctx: Context) => {
  const authCtx = ctx as AuthContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery('Пожалуйста, сначала зарегистрируйтесь');
    return;
  }

  // Parse page number from callback data
  let page = 0;
  if (ctx.callbackQuery && 'data' in ctx.callbackQuery) {
    const match = ctx.callbackQuery.data.match(/^transaction_history_(\d+)$/);
    if (match) {
      page = parseInt(match[1]);
    }
  }

  const limit = 10;
  const offset = page * limit;

  // Get transactions
  const { transactions, total, hasMore } = await transactionService.getAllTransactions(
    authCtx.user.id,
    { limit, offset }
  );

  // Get statistics
  const stats = await transactionService.getTransactionStats(authCtx.user.id);

  let message = `📊 **История транзакций**\n\n`;

  // Display statistics
  message += `**Общая статистика:**\n`;
  message += `💰 Всего депозитов: ${stats.totalDeposits.toFixed(2)} USDT (${stats.transactionCount.deposits} шт.)\n`;
  message += `💸 Всего выведено: ${stats.totalWithdrawals.toFixed(2)} USDT (${stats.transactionCount.withdrawals} шт.)\n`;
  message += `🎁 Реферальных доходов: ${stats.totalReferralEarnings.toFixed(2)} USDT (${stats.transactionCount.referralRewards} шт.)\n\n`;

  if (stats.pendingWithdrawals > 0 || stats.pendingEarnings > 0) {
    message += `**В обработке:**\n`;
    if (stats.pendingWithdrawals > 0) {
      message += `⏳ Вывод средств: ${stats.pendingWithdrawals.toFixed(2)} USDT\n`;
    }
    if (stats.pendingEarnings > 0) {
      message += `⏳ Реферальные доходы: ${stats.pendingEarnings.toFixed(2)} USDT\n`;
    }
    message += '\n';
  }

  message += `---\n\n`;

  // Display transactions
  if (transactions.length === 0) {
    message += 'У вас пока нет транзакций.';
  } else {
    message += `**Транзакции** (${offset + 1}-${offset + transactions.length} из ${total}):\n\n`;

    transactions.forEach((tx, index) => {
      const typeEmoji = getTransactionTypeEmoji(tx.type);
      const statusEmoji = getStatusEmoji(tx.status);
      const date = new Date(tx.createdAt).toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });

      message += `${index + 1}. ${typeEmoji} **${tx.description}**\n`;
      message += `   ${statusEmoji} ${getStatusText(tx.status)} | ${tx.amount.toFixed(2)} USDT\n`;
      message += `   📅 ${date}\n`;

      if (tx.txHash && tx.status === TransactionStatus.CONFIRMED) {
        const shortHash = `${tx.txHash.substring(0, 6)}...${tx.txHash.substring(tx.txHash.length - 4)}`;
        message += `   🔗 TX: \`${shortHash}\`\n`;
      }

      message += '\n';
    });
  }

  // Create keyboard with pagination
  const buttons: any[] = [];

  // Filter buttons
  const filterRow = [
    Markup.button.callback('💰 Депозиты', 'transaction_filter_deposit'),
    Markup.button.callback('💸 Выводы', 'transaction_filter_withdrawal'),
  ];
  buttons.push(filterRow);

  const filterRow2 = [
    Markup.button.callback('🎁 Рефералы', 'transaction_filter_referral'),
    Markup.button.callback('📊 Все', 'transaction_history'),
  ];
  buttons.push(filterRow2);

  // Pagination
  if (page > 0 || hasMore) {
    const paginationRow = [];
    if (page > 0) {
      paginationRow.push(Markup.button.callback('◀️ Назад', `transaction_history_${page - 1}`));
    }
    if (hasMore) {
      paginationRow.push(Markup.button.callback('Вперёд ▶️', `transaction_history_${page + 1}`));
    }
    buttons.push(paginationRow);
  }

  // Back button
  buttons.push([Markup.button.callback(BUTTON_LABELS.MAIN_MENU, 'main_menu')]);

  const keyboard = Markup.inlineKeyboard(buttons);

  if (ctx.callbackQuery && 'message' in ctx.callbackQuery) {
    await ctx.editMessageText(message, {
      parse_mode: 'Markdown',
      ...keyboard,
    });
    await ctx.answerCbQuery();
  } else {
    await ctx.reply(message, {
      parse_mode: 'Markdown',
      ...keyboard,
    });
  }

  logger.debug('Transaction history viewed', {
    userId: authCtx.user.id,
    page,
    total,
  });
};

/**
 * Handle transaction history with filter
 */
export const handleTransactionHistoryFilter = async (ctx: Context) => {
  const authCtx = ctx as AuthContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery('Пожалуйста, сначала зарегистрируйтесь');
    return;
  }

  if (!ctx.callbackQuery || !('data' in ctx.callbackQuery)) {
    return;
  }

  // Parse filter type
  const data = ctx.callbackQuery.data;
  let filterType: TransactionType | undefined;
  let filterName = 'Все транзакции';

  if (data === 'transaction_filter_deposit') {
    filterType = TransactionType.DEPOSIT;
    filterName = 'Депозиты';
  } else if (data === 'transaction_filter_withdrawal') {
    filterType = TransactionType.WITHDRAWAL;
    filterName = 'Выводы средств';
  } else if (data === 'transaction_filter_referral') {
    filterType = TransactionType.REFERRAL_REWARD;
    filterName = 'Реферальные доходы';
  }

  const limit = 10;
  const offset = 0;

  // Get filtered transactions
  const { transactions, total, hasMore } = await transactionService.getAllTransactions(
    authCtx.user.id,
    { limit, offset, type: filterType }
  );

  let message = `📊 **${filterName}**\n\n`;

  if (transactions.length === 0) {
    message += `У вас пока нет транзакций типа "${filterName}".`;
  } else {
    message += `Найдено: **${total}** транзакций\n\n`;

    transactions.forEach((tx, index) => {
      const typeEmoji = getTransactionTypeEmoji(tx.type);
      const statusEmoji = getStatusEmoji(tx.status);
      const date = new Date(tx.createdAt).toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });

      message += `${index + 1}. ${typeEmoji} **${tx.description}**\n`;
      message += `   ${statusEmoji} ${getStatusText(tx.status)} | ${tx.amount.toFixed(2)} USDT\n`;
      message += `   📅 ${date}\n`;

      if (tx.txHash && tx.status === TransactionStatus.CONFIRMED) {
        const shortHash = `${tx.txHash.substring(0, 6)}...${tx.txHash.substring(tx.txHash.length - 4)}`;
        message += `   🔗 TX: \`${shortHash}\`\n`;
      }

      message += '\n';
    });
  }

  // Create keyboard
  const buttons: any[] = [];

  // Back to all transactions
  buttons.push([
    Markup.button.callback('◀️ Все транзакции', 'transaction_history'),
  ]);

  // Back to main menu
  buttons.push([
    Markup.button.callback(BUTTON_LABELS.MAIN_MENU, 'main_menu'),
  ]);

  const keyboard = Markup.inlineKeyboard(buttons);

  await ctx.editMessageText(message, {
    parse_mode: 'Markdown',
    ...keyboard,
  });

  await ctx.answerCbQuery();

  logger.debug('Transaction history filtered', {
    userId: authCtx.user.id,
    filterType,
    total,
  });
};

export default {
  handleTransactionHistory,
  handleTransactionHistoryFilter,
};
