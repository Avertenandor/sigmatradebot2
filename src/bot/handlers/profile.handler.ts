/**
 * Profile Handler
 * Handles user profile display
 */

import { Context } from 'telegraf';
import { AuthContext } from '../middlewares/auth.middleware';
import { getBackButton } from '../keyboards';
import userService from '../../services/user.service';
import depositService from '../../services/deposit.service';
import { createLogger } from '../../utils/logger.util';
import { formatUSDT } from '../../utils/money.util';

const logger = createLogger('ProfileHandler');

/**
 * Handle profile view
 */
export const handleProfile = async (ctx: Context) => {
  const authCtx = ctx as AuthContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery('Пожалуйста, сначала зарегистрируйтесь');
    return;
  }

  const user = authCtx.user;

  // Get user stats
  const stats = await userService.getUserStats(user.id);

  // Get user balance
  const balance = await userService.getUserBalance(user.id);

  // Get ROI progress
  const roiProgress = await depositService.getLevel1RoiProgress(user.id);

  // Get referral link
  const botUsername = (await ctx.telegram.getMe()).username;
  const referralLink = userService.generateReferralLink(user.id, botUsername);

  // Create ROI progress bar
  const createProgressBar = (percent: number, length: number = 10): string => {
    const filled = Math.round((percent / 100) * length);
    const empty = length - filled;
    return '█'.repeat(filled) + '░'.repeat(empty);
  };

  // ROI section
  let roiSection = '';
  if (roiProgress.hasActiveDeposit && !roiProgress.isCompleted) {
    const progressBar = createProgressBar(roiProgress.roiPercent || 0);
    roiSection = `
**🎯 ROI Прогресс (Уровень 1):**
💵 Депозит: ${formatUSDT(roiProgress.depositAmount || 0)} USDT
📊 Прогресс: ${progressBar} ${roiProgress.roiPercent?.toFixed(1)}%
✅ Получено: ${formatUSDT(roiProgress.roiPaid || 0)} USDT
⏳ Осталось: ${formatUSDT(roiProgress.roiRemaining || 0)} USDT
🎯 Цель: ${formatUSDT(roiProgress.roiCap || 0)} USDT (500%)

`;
  } else if (roiProgress.hasActiveDeposit && roiProgress.isCompleted) {
    roiSection = `
**🎯 ROI Завершён (Уровень 1):**
✅ Достигнут максимум 500%!
💰 Получено: ${formatUSDT(roiProgress.roiPaid || 0)} USDT
📌 Создайте новый депозит 10 USDT чтобы продолжить

`;
  }

  // Format profile message
  const profileMessage = `
👤 **Ваш профиль**

**Основная информация:**
🆔 ID: \`${user.id}\`
👤 Username: ${user.username ? `@${user.username}` : 'Не указан'}
💳 Кошелек: \`${user.wallet_address}\`
${user.maskedWallet ? `(${user.maskedWallet})` : ''}

**Статус:**
${user.is_verified ? '✅' : '❌'} Верификация: ${user.is_verified ? 'Пройдена' : 'Не пройдена'}
${user.is_banned ? '🚫 Аккаунт заблокирован' : '✅ Аккаунт активен'}

**Баланс:**
💰 Доступно для вывода: **${formatUSDT(balance?.availableBalance || 0)} USDT**
💸 Всего заработано: ${formatUSDT(balance?.totalEarned || 0)} USDT
⏳ В ожидании выплаты: ${formatUSDT(balance?.pendingEarnings || 0)} USDT
${balance && balance.pendingWithdrawals > 0 ? `🔒 Заблокировано в выводах: ${formatUSDT(balance.pendingWithdrawals)} USDT\n` : ''}✅ Уже выплачено: ${formatUSDT(balance?.totalPaid || 0)} USDT

${roiSection}**Депозиты и рефералы:**
💰 Всего депозитов: ${formatUSDT(stats?.totalDeposits || 0)} USDT
👥 Рефералов: ${stats?.referralCount || 0}
📊 Активных уровней: ${stats?.activatedLevels.length || 0}/5

**Контакты:**
${user.phone ? `📞 ${user.phone}` : ''}
${user.email ? `📧 ${user.email}` : ''}

**Реферальная ссылка:**
\`${referralLink}\`

📅 Дата регистрации: ${new Date(user.created_at).toLocaleDateString('ru-RU')}
  `.trim();

  if (ctx.callbackQuery && 'message' in ctx.callbackQuery) {
    await ctx.editMessageText(profileMessage, {
      parse_mode: 'Markdown',
      ...getBackButton('main_menu'),
    });
  } else {
    await ctx.reply(profileMessage, {
      parse_mode: 'Markdown',
      ...getBackButton('main_menu'),
    });
  }

  if (ctx.callbackQuery) {
    await ctx.answerCbQuery();
  }

  logger.debug('Profile viewed', {
    userId: user.id,
    telegramId: user.telegram_id,
  });
};

export default {
  handleProfile,
};
