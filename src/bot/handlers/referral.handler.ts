/**
 * Referral Handler
 * Handles referral program actions
 */

import { Context, Markup } from 'telegraf';
import { AuthContext } from '../middlewares/auth.middleware';
import {
  getReferralMenuKeyboard,
  getReferralStatsKeyboard,
  getReferralEarningsKeyboard,
  getBackButton,
} from '../keyboards';
import referralService from '../../services/referral.service';
import userService from '../../services/user.service';
import { REFERRAL_RATES, BUTTON_LABELS } from '../../utils/constants';
import { createLogger } from '../../utils/logger.util';
import { formatUSDT } from '../../utils/money.util';

const logger = createLogger('ReferralHandler');

/**
 * Handle referrals menu
 */
export const handleReferrals = async (ctx: Context) => {
  const authCtx = ctx as AuthContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery('Пожалуйста, сначала зарегистрируйтесь');
    return;
  }

  // Get referral stats
  const stats = await referralService.getReferralStats(authCtx.user.id);

  const message = `
🤝 **Реферальная программа**

**Ваша статистика:**
👥 Прямые партнеры (Уровень 1): ${stats.directReferrals}
👥 Уровень 2: ${stats.level2Referrals}
👥 Уровень 3: ${stats.level3Referrals}

💰 **Доходы:**
💵 Всего заработано: ${formatUSDT(stats.totalEarned)} USDT
⏳ Ожидает выплаты: ${formatUSDT(stats.pendingEarnings)} USDT
✅ Выплачено: ${formatUSDT(stats.paidEarnings)} USDT

**Комиссии:**
• Уровень 1: ${REFERRAL_RATES[1] * 100}% от депозитов прямых партнеров
• Уровень 2: ${REFERRAL_RATES[2] * 100}% от партнеров второго уровня
• Уровень 3: ${REFERRAL_RATES[3] * 100}% от партнеров третьего уровня

📈 Чем больше ваша сеть, тем больше доход!
  `.trim();

  if (ctx.callbackQuery && 'message' in ctx.callbackQuery) {
    await ctx.editMessageText(message, {
      parse_mode: 'Markdown',
      ...getReferralMenuKeyboard(),
    });
  } else {
    await ctx.reply(message, {
      parse_mode: 'Markdown',
      ...getReferralMenuKeyboard(),
    });
  }

  if (ctx.callbackQuery) {
    await ctx.answerCbQuery();
  }

  logger.debug('Referrals menu shown', {
    userId: authCtx.user.id,
    stats,
  });
};

/**
 * Handle referral link
 */
export const handleReferralLink = async (ctx: Context) => {
  const authCtx = ctx as AuthContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery('Пожалуйста, сначала зарегистрируйтесь');
    return;
  }

  // Check if user is banned - referral link should be deactivated
  if (authCtx.user.is_banned) {
    await ctx.answerCbQuery('Реферальная ссылка деактивирована', { show_alert: true });
    await ctx.editMessageText(
      '🚫 **Реферальная ссылка деактивирована**\n\n' +
      'Ваша реферальная ссылка была деактивирована администратором.',
      {
        parse_mode: 'Markdown',
        ...getBackButton('referrals'),
      }
    );
    return;
  }

  // Get bot username
  const botInfo = await ctx.telegram.getMe();
  const referralLink = userService.generateReferralLink(
    authCtx.user.id,
    botInfo.username
  );

  const message = `
🔗 **Ваша реферальная ссылка**

\`${referralLink}\`

**Как использовать:**
1. Скопируйте ссылку
2. Поделитесь с друзьями
3. Получайте вознаграждения от их депозитов!

**Ваши комиссии:**
• ${REFERRAL_RATES[1] * 100}% от депозитов прямых партнеров
• ${REFERRAL_RATES[2] * 100}% от партнеров 2-го уровня
• ${REFERRAL_RATES[3] * 100}% от партнеров 3-го уровня

💡 Отправьте эту ссылку в соцсети, мессенджеры или на форумы!
  `.trim();

  await ctx.editMessageText(message, {
    parse_mode: 'Markdown',
    ...getBackButton('referrals'),
  });

  await ctx.answerCbQuery('Ссылка готова к отправке!');

  logger.debug('Referral link shown', {
    userId: authCtx.user.id,
  });
};

/**
 * Handle referral stats by level
 */
export const handleReferralStats = async (ctx: Context) => {
  const authCtx = ctx as AuthContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery('Пожалуйста, сначала зарегистрируйтесь');
    return;
  }

  // Get level from callback data
  const callbackData = ctx.callbackQuery && 'data' in ctx.callbackQuery ? ctx.callbackQuery.data : '';
  const level = parseInt(callbackData.split('_').pop() || '1', 10);

  if (level < 1 || level > 3) {
    await ctx.answerCbQuery('Неверный уровень');
    return;
  }

  // Get referrals for this level
  const { referrals, total } = await referralService.getReferralsByLevel(
    authCtx.user.id,
    level,
    { page: 1, limit: 5 }
  );

  let message = `
📊 **Рефералы: Уровень ${level}**

**Комиссия:** ${REFERRAL_RATES[level as keyof typeof REFERRAL_RATES] * 100}%

`;

  if (referrals.length === 0) {
    message += `У вас пока нет партнеров на уровне ${level}.`;
  } else {
    referrals.forEach((ref, index) => {
      const joinDate = new Date(ref.joinedAt).toLocaleDateString('ru-RU');
      message += `${index + 1}. ${ref.user.displayName}\n`;
      message += `   💰 Заработано: ${formatUSDT(ref.earned)} USDT\n`;
      message += `   📅 Присоединился: ${joinDate}\n\n`;
    });

    message += `\n👥 Всего партнеров: ${total}`;

    if (total > 5) {
      message += `\n📄 Показаны первые 5`;
    }
  }

  await ctx.editMessageText(message, {
    parse_mode: 'Markdown',
    ...getReferralStatsKeyboard(level),
  });

  await ctx.answerCbQuery();

  logger.debug('Referral stats shown', {
    userId: authCtx.user.id,
    level,
    totalReferrals: total,
  });
};

/**
 * Handle referral earnings
 */
export const handleReferralEarnings = async (ctx: Context) => {
  const authCtx = ctx as AuthContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery('Пожалуйста, сначала зарегистрируйтесь');
    return;
  }

  // Get page from callback data
  const callbackData = ctx.callbackQuery && 'data' in ctx.callbackQuery ? ctx.callbackQuery.data : '';
  const page = parseInt(callbackData.split('_').pop() || '1', 10);

  // Get pending earnings
  const { earnings, total, totalAmount, pages } = await referralService.getPendingEarnings(
    authCtx.user.id,
    { page, limit: 5 }
  );

  let message = `💸 **Ожидающие выплаты**\n\n`;

  if (earnings.length === 0) {
    message += 'У вас пока нет ожидающих выплат.';
  } else {
    earnings.forEach((earning, index) => {
      const date = new Date(earning.created_at).toLocaleDateString('ru-RU');
      const emoji = earning.paid ? '✅' : '⏳';

      message += `${emoji} ${formatUSDT(earning.amountAsNumber)} USDT\n`;
      message += `Дата: ${date}\n`;
      message += `Статус: ${earning.paid ? 'Выплачено' : 'Ожидает'}\n\n`;
    });

    message += `\n💰 Всего ожидает: ${formatUSDT(totalAmount)} USDT`;
    message += `\n📊 Всего записей: ${total}`;
  }

  const keyboard = getReferralEarningsKeyboard(page, pages);

  await ctx.editMessageText(message, {
    parse_mode: 'Markdown',
    ...keyboard,
  });

  await ctx.answerCbQuery();

  logger.debug('Referral earnings shown', {
    userId: authCtx.user.id,
    page,
    totalEarnings: total,
    totalAmount,
  });
};

/**
 * Handle referral leaderboard
 */
export const handleReferralLeaderboard = async (ctx: Context) => {
  const authCtx = ctx as AuthContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery('Пожалуйста, сначала зарегистрируйтесь');
    return;
  }

  // Parse view type from callback data
  let viewType: 'referrals' | 'earnings' = 'referrals';
  if (ctx.callbackQuery && 'data' in ctx.callbackQuery) {
    if (ctx.callbackQuery.data === 'referral_leaderboard_earnings') {
      viewType = 'earnings';
    }
  }

  // Get leaderboard data
  const leaderboard = await referralService.getReferralLeaderboard({ limit: 10 });
  const userPosition = await referralService.getUserLeaderboardPosition(authCtx.user.id);

  let message = `🏆 **Таблица лидеров**\n\n`;

  if (viewType === 'referrals') {
    message += `**Топ по количеству рефералов:**\n\n`;

    if (leaderboard.byReferrals.length === 0) {
      message += 'Пока нет рефералов в системе.\n\n';
    } else {
      leaderboard.byReferrals.forEach((leader) => {
        const medal = leader.rank === 1 ? '🥇' : leader.rank === 2 ? '🥈' : leader.rank === 3 ? '🥉' : `${leader.rank}.`;
        const username = leader.username ? `@${leader.username}` : `Пользователь #${leader.telegramId}`;
        const isCurrentUser = leader.userId === authCtx.user.id;

        message += `${medal} ${username}${isCurrentUser ? ' **(вы)**' : ''}\n`;
        message += `   👥 Рефералов: **${leader.referralCount}**\n`;
        message += `   💰 Заработано: ${formatUSDT(leader.totalEarnings)} USDT\n\n`;
      });
    }

    // Show user's position if not in top 10
    if (userPosition.referralRank && userPosition.referralRank > 10) {
      message += `---\n\n`;
      message += `**Ваша позиция:**\n`;
      message += `📊 Место: ${userPosition.referralRank} из ${userPosition.totalUsers}\n\n`;
    } else if (!userPosition.referralRank && userPosition.totalUsers > 0) {
      message += `---\n\n`;
      message += `**Ваша позиция:**\n`;
      message += `У вас пока нет рефералов. Начните приглашать друзей! 🚀\n\n`;
    }
  } else {
    message += `**Топ по заработку:**\n\n`;

    if (leaderboard.byEarnings.length === 0) {
      message += 'Пока нет доходов в системе.\n\n';
    } else {
      leaderboard.byEarnings.forEach((leader) => {
        const medal = leader.rank === 1 ? '🥇' : leader.rank === 2 ? '🥈' : leader.rank === 3 ? '🥉' : `${leader.rank}.`;
        const username = leader.username ? `@${leader.username}` : `Пользователь #${leader.telegramId}`;
        const isCurrentUser = leader.userId === authCtx.user.id;

        message += `${medal} ${username}${isCurrentUser ? ' **(вы)**' : ''}\n`;
        message += `   💰 Заработано: **${formatUSDT(leader.totalEarnings)} USDT**\n`;
        message += `   👥 Рефералов: ${leader.referralCount}\n\n`;
      });
    }

    // Show user's position if not in top 10
    if (userPosition.earningsRank && userPosition.earningsRank > 10) {
      message += `---\n\n`;
      message += `**Ваша позиция:**\n`;
      message += `📊 Место: ${userPosition.earningsRank} из ${userPosition.totalUsers}\n\n`;
    } else if (!userPosition.earningsRank && userPosition.totalUsers > 0) {
      message += `---\n\n`;
      message += `**Ваша позиция:**\n`;
      message += `У вас пока нет реферального дохода. Продолжайте приглашать! 🚀\n\n`;
    }
  }

  message += `💡 Приглашайте больше друзей и поднимайтесь в рейтинге!`;

  // Create keyboard with view switcher
  const buttons: any[] = [];

  // View switcher
  const switcherRow = [
    Markup.button.callback(
      viewType === 'referrals' ? '✅ По рефералам' : 'По рефералам',
      'referral_leaderboard_referrals'
    ),
    Markup.button.callback(
      viewType === 'earnings' ? '✅ По заработку' : 'По заработку',
      'referral_leaderboard_earnings'
    ),
  ];
  buttons.push(switcherRow);

  // Back button
  buttons.push([Markup.button.callback(BUTTON_LABELS.BACK, 'referrals')]);

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

  logger.debug('Referral leaderboard viewed', {
    userId: authCtx.user.id,
    viewType,
  });
};

export default {
  handleReferrals,
  handleReferralLink,
  handleReferralStats,
  handleReferralEarnings,
  handleReferralLeaderboard,
};
