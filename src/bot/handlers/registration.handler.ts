/**
 * Registration Handler
 * Handles user registration and verification process
 */

import { Context } from 'telegraf';
import { AuthContext } from '../middlewares/auth.middleware';
import { SessionContext, updateSessionState } from '../middlewares/session.middleware';
import { BotState, BOT_MESSAGES, ERROR_MESSAGES, SUCCESS_MESSAGES } from '../../utils/constants';
import { isValidBSCAddress, isValidEmail, isValidPhone } from '../../utils/validation.util';
import { getCancelButton, getMainKeyboard } from '../keyboards';
import userService from '../../services/user.service';
import referralService from '../../services/referral.service';
import { notificationService } from '../../services/notification.service';
import { createLogger } from '../../utils/logger.util';
import { Markup } from 'telegraf';

const logger = createLogger('RegistrationHandler');

/**
 * Start registration process
 */
export const handleStartRegistration = async (ctx: Context) => {
  const authCtx = ctx as AuthContext & SessionContext;

  // Check if already registered
  if (authCtx.isRegistered) {
    await ctx.answerCbQuery('Вы уже зарегистрированы');
    return;
  }

  // Update session state
  await updateSessionState(
    ctx.from!.id,
    BotState.AWAITING_WALLET_ADDRESS
  );

  const message = `${BOT_MESSAGES.REGISTRATION_START}

Пожалуйста, отправьте адрес вашего кошелька:`;

  if (ctx.callbackQuery && 'message' in ctx.callbackQuery) {
    await ctx.editMessageText(message, getCancelButton());
  } else {
    await ctx.reply(message, getCancelButton());
  }

  await ctx.answerCbQuery();
};

/**
 * Handle wallet address input
 */
export const handleWalletInput = async (ctx: Context) => {
  const authCtx = ctx as AuthContext & SessionContext;

  // Check if expecting wallet address
  if (authCtx.session.state !== BotState.AWAITING_WALLET_ADDRESS) {
    return;
  }

  const walletAddress = ctx.text?.trim();

  if (!walletAddress) {
    await ctx.reply(ERROR_MESSAGES.INVALID_INPUT);
    return;
  }

  // Validate wallet address
  if (!isValidBSCAddress(walletAddress)) {
    await ctx.reply(ERROR_MESSAGES.INVALID_WALLET_ADDRESS);
    return;
  }

  // Get referrer ID from session
  const referrerId = authCtx.session.data?.referrerId;

  // Create user
  const result = await userService.createUser({
    telegramId: ctx.from!.id,
    username: ctx.from?.username,
    walletAddress,
    referrerId,
  });

  if (result.error) {
    await ctx.reply(`❌ Ошибка регистрации: ${result.error}`);

    // Reset state
    await updateSessionState(ctx.from!.id, BotState.IDLE);
    return;
  }

  if (!result.user) {
    await ctx.reply(ERROR_MESSAGES.INTERNAL_ERROR);
    await updateSessionState(ctx.from!.id, BotState.IDLE);
    return;
  }

  logger.info('User registered successfully', {
    userId: result.user.id,
    telegramId: result.user.telegram_id,
    hasReferrer: !!referrerId,
  });

  // Create referral relationships if user was referred
  if (referrerId) {
    const referralResult = await referralService.createReferralRelationships(
      result.user.id,
      referrerId
    );

    if (!referralResult.success) {
      logger.error('Failed to create referral relationships', {
        userId: result.user.id,
        referrerId,
        error: referralResult.error,
      });
      // Don't fail registration, just log the error
    } else {
      logger.info('Referral relationships created', {
        userId: result.user.id,
        referrerId,
      });

      // Notify referrer about new referral
      const referrerUser = await userService.findById(referrerId);
      if (referrerUser) {
        await notificationService.notifyNewReferral(
          referrerUser.telegram_id,
          result.user.username
        );
      }
    }
  }

  // Get plain password (only available once)
  const plainPassword = (result.user as any).plainPassword;

  // Success message
  const successMessage = `${SUCCESS_MESSAGES.REGISTRATION_COMPLETE}

Ваш кошелек: \`${result.user.maskedWallet}\`

Теперь пройдите верификацию для активации аккаунта.`;

  await ctx.reply(successMessage, {
    parse_mode: 'Markdown',
    ...Markup.inlineKeyboard([
      [Markup.button.callback('✅ Пройти верификацию', 'start_verification')],
    ]),
  });

  // Reset session state
  await updateSessionState(ctx.from!.id, BotState.IDLE);
};

/**
 * Start verification process
 */
export const handleStartVerification = async (ctx: Context) => {
  const authCtx = ctx as AuthContext & SessionContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery(ERROR_MESSAGES.USER_NOT_REGISTERED);
    return;
  }

  if (authCtx.user.is_verified) {
    await ctx.answerCbQuery('Вы уже верифицированы');
    return;
  }

  // Verify user (without contact info first)
  const result = await userService.verifyUser(authCtx.user.id);

  if (!result.success) {
    await ctx.answerCbQuery(`Ошибка: ${result.error}`);
    return;
  }

  // Get plain password from user object (should be stored temporarily)
  const plainPassword = (authCtx.user as any).plainPassword || 'Пароль был отправлен ранее';

  const verificationMessage = BOT_MESSAGES.VERIFICATION_START.replace(
    '{password}',
    `\`${plainPassword}\``
  );

  await ctx.editMessageText(
    verificationMessage,
    {
      parse_mode: 'Markdown',
      ...Markup.inlineKeyboard([
        [Markup.button.callback('📧 Указать контакты', 'add_contact_info')],
        [Markup.button.callback('⏭️ Пропустить', 'skip_contact_info')],
      ]),
    }
  );

  await ctx.answerCbQuery(SUCCESS_MESSAGES.VERIFICATION_COMPLETE);

  logger.info('User verified', {
    userId: authCtx.user.id,
    telegramId: authCtx.user.telegram_id,
  });
};

/**
 * Handle adding contact info
 */
export const handleAddContactInfo = async (ctx: Context) => {
  const authCtx = ctx as AuthContext & SessionContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery(ERROR_MESSAGES.USER_NOT_REGISTERED);
    return;
  }

  // Update session state
  await updateSessionState(
    ctx.from!.id,
    BotState.AWAITING_CONTACT_INFO
  );

  const message = `
📞 Контактная информация

Вы можете указать ваши контактные данные для связи:

• Телефон (международный формат, например: +79991234567)
• Email (например: user@example.com)

Отправьте контакты в формате:
\`+79991234567\`
или
\`user@example.com\`

Или отправьте оба через пробел:
\`+79991234567 user@example.com\`
  `.trim();

  await ctx.editMessageText(message, {
    parse_mode: 'Markdown',
    ...getCancelButton(),
  });

  await ctx.answerCbQuery();
};

/**
 * Handle contact info input
 */
export const handleContactInfoInput = async (ctx: Context) => {
  const authCtx = ctx as AuthContext & SessionContext;

  if (authCtx.session.state !== BotState.AWAITING_CONTACT_INFO) {
    return;
  }

  if (!authCtx.user) {
    return;
  }

  const input = ctx.text?.trim();

  if (!input) {
    await ctx.reply(ERROR_MESSAGES.INVALID_INPUT);
    return;
  }

  const parts = input.split(/\s+/);
  let phone: string | undefined;
  let email: string | undefined;

  // Parse input
  for (const part of parts) {
    if (isValidEmail(part)) {
      email = part;
    } else if (isValidPhone(part)) {
      phone = part;
    }
  }

  if (!phone && !email) {
    await ctx.reply('❌ Не удалось распознать контактные данные. Проверьте формат.');
    return;
  }

  // Update user with contact info
  const result = await userService.verifyUser(authCtx.user.id, { phone, email });

  if (!result.success) {
    await ctx.reply(`❌ Ошибка: ${result.error}`);
    return;
  }

  const confirmMessage = `
✅ Контакты сохранены!

${phone ? `📞 Телефон: ${phone}` : ''}
${email ? `📧 Email: ${email}` : ''}

Добро пожаловать в SigmaTrade! 🎉
  `.trim();

  await ctx.reply(confirmMessage, getMainKeyboard(false));

  // Reset session
  await updateSessionState(ctx.from!.id, BotState.IDLE);

  logger.info('Contact info added', {
    userId: authCtx.user.id,
    hasPhone: !!phone,
    hasEmail: !!email,
  });
};

/**
 * Skip contact info
 */
export const handleSkipContactInfo = async (ctx: Context) => {
  const authCtx = ctx as AuthContext & SessionContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery(ERROR_MESSAGES.USER_NOT_REGISTERED);
    return;
  }

  const welcomeMessage = `
🎉 Регистрация завершена!

Добро пожаловать в SigmaTrade!

Используйте меню для навигации по системе.
  `.trim();

  await ctx.editMessageText(welcomeMessage, getMainKeyboard(false));
  await ctx.answerCbQuery('Контакты пропущены');

  // Reset session
  await updateSessionState(ctx.from!.id, BotState.IDLE);
};

/**
 * Cancel registration/verification
 */
export const handleCancelRegistration = async (ctx: Context) => {
  await updateSessionState(ctx.from!.id, BotState.IDLE);

  await ctx.editMessageText(
    '❌ Действие отменено',
    Markup.inlineKeyboard([
      [Markup.button.callback('🔙 Вернуться', 'main_menu')],
    ])
  );

  await ctx.answerCbQuery('Отменено');
};

export default {
  handleStartRegistration,
  handleWalletInput,
  handleStartVerification,
  handleAddContactInfo,
  handleContactInfoInput,
  handleSkipContactInfo,
  handleCancelRegistration,
};
