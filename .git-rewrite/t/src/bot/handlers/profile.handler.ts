/**
 * Profile Handler
 * Handles user profile display
 */

import { Context } from 'telegraf';
import { AuthContext } from '../middlewares/auth.middleware';
import { getBackButton } from '../keyboards';
import userService from '../../services/user.service';
import { createLogger } from '../../utils/logger.util';
import { config } from '../../config';

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

  // Get referral link
  const botUsername = (await ctx.telegram.getMe()).username;
  const referralLink = userService.generateReferralLink(user.id, botUsername);

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
💰 Доступно для вывода: **${balance?.availableBalance.toFixed(2) || 0} USDT**
💸 Всего заработано: ${balance?.totalEarned.toFixed(2) || 0} USDT
⏳ В ожидании выплаты: ${balance?.pendingEarnings.toFixed(2) || 0} USDT
✅ Уже выплачено: ${balance?.totalPaid.toFixed(2) || 0} USDT

**Депозиты и рефералы:**
💰 Всего депозитов: ${stats?.totalDeposits.toFixed(2) || 0} USDT
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
