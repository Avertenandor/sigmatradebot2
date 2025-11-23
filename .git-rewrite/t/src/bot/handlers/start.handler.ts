/**
 * Start Handler
 * Handles /start command, welcomes users, processes referral links
 */

import { Context } from 'telegraf';
import { AuthContext } from '../middlewares/auth.middleware';
import { AdminContext } from '../middlewares/admin.middleware';
import { BOT_MESSAGES } from '../../utils/constants';
import { getMainKeyboard, getWelcomeKeyboard } from '../keyboards';
import userService from '../../services/user.service';
import { createLogger } from '../../utils/logger.util';

const logger = createLogger('StartHandler');

/**
 * Handle /start command
 */
export const handleStart = async (ctx: Context) => {
  const authCtx = ctx as AuthContext & AdminContext;
  const startPayload = ctx.text?.split(' ')[1]; // Get payload after /start

  // If user is already registered
  if (authCtx.isRegistered && authCtx.user) {
    const welcomeBack = `
👋 С возвращением, ${authCtx.user.displayName}!

Вы уже зарегистрированы в системе SigmaTrade.

Используйте меню ниже для навигации.
    `.trim();

    await ctx.reply(welcomeBack, getMainKeyboard(authCtx.isAdmin));
    return;
  }

  // New user - show welcome message
  let referrerId: number | undefined;

  // Parse referral code if present
  if (startPayload) {
    referrerId = userService.parseReferralCode(startPayload);

    if (referrerId) {
      logger.info('New user from referral', {
        referrerId,
        newUserTelegramId: ctx.from?.id,
      });
    }
  }

  // Store referrer ID in session for later use during registration
  if (ctx.session && referrerId) {
    ctx.session.data = { referrerId };
  }

  const welcomeMessage = `${BOT_MESSAGES.WELCOME}

Для начала работы нажмите кнопку ниже.`;

  await ctx.reply(welcomeMessage, getWelcomeKeyboard());
};

/**
 * Handle main menu callback
 */
export const handleMainMenu = async (ctx: Context) => {
  const authCtx = ctx as AuthContext & AdminContext;

  if (!authCtx.isRegistered) {
    await ctx.answerCbQuery('Пожалуйста, сначала зарегистрируйтесь');
    return;
  }

  const menuMessage = `
🏠 Главное меню

Выберите действие:
  `.trim();

  if (ctx.callbackQuery && 'message' in ctx.callbackQuery) {
    await ctx.editMessageText(menuMessage, getMainKeyboard(authCtx.isAdmin));
  } else {
    await ctx.reply(menuMessage, getMainKeyboard(authCtx.isAdmin));
  }

  await ctx.answerCbQuery();
};

/**
 * Handle help command
 */
export const handleHelp = async (ctx: Context) => {
  const helpMessage = `
❓ Помощь

**Основные команды:**
/start - Начать работу
/help - Показать это сообщение

**Как пользоваться ботом:**

1️⃣ **Регистрация**
Укажите адрес вашего кошелька BSC (BEP-20)

2️⃣ **Верификация**
Получите финансовый пароль и укажите контакты (опционально)

3️⃣ **Депозиты**
Активируйте уровни депозитов последовательно:
• Уровень 1: 10 USDT (без рефералов)
• Уровень 2: 50 USDT (нужен 1 реферал)
• Уровень 3: 100 USDT (нужно 2 реферала)
• Уровень 4: 150 USDT (нужно 3 реферала)
• Уровень 5: 300 USDT (нужно 4 реферала)

4️⃣ **Реферальная программа**
• Уровень 1: 3% от депозитов прямых партнеров
• Уровень 2: 2% от партнеров второго уровня
• Уровень 3: 5% от партнеров третьего уровня

**Поддержка:**
📧 Email: support@sigmatrade.org
🌐 Сайт: https://sigmatrade.org

💡 Используйте кнопки меню для навигации!
  `.trim();

  await ctx.reply(helpMessage, {
    parse_mode: 'Markdown',
    ...getMainKeyboard((ctx as AdminContext).isAdmin),
  });

  if (ctx.callbackQuery) {
    await ctx.answerCbQuery();
  }
};

export default {
  handleStart,
  handleMainMenu,
  handleHelp,
};
