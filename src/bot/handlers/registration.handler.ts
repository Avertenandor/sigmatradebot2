/**
 * Registration Handler
 * Handles user registration and verification process
 */

import { Context } from 'telegraf';
import { AuthContext } from '../middlewares/auth.middleware';
import { SessionContext, updateSessionState } from '../middlewares/session.middleware';
import { BotState, BOT_MESSAGES, ERROR_MESSAGES, SUCCESS_MESSAGES } from '../../utils/constants';
import { isValidBSCAddress, isValidEmail, isValidPhone, hasValidChecksum, normalizeWalletAddress } from '../../utils/validation.util';
import { getCancelButton, getMainKeyboard } from '../keyboards';
import userService from '../../services/user.service';
import referralService from '../../services/referral.service';
import { notificationService } from '../../services/notification.service';
import { createLogger } from '../../utils/logger.util';
import { Markup } from 'telegraf';
import Redis from 'ioredis';
import { config } from '../../config';
import { withTransaction, TRANSACTION_PRESETS } from '../../database/transaction.util';

const logger = createLogger('RegistrationHandler');

// Redis client for referral ID backup recovery (FIX #5)
const redis = new Redis({
  host: config.redis.host,
  port: config.redis.port,
  password: config.redis.password,
  db: config.redis.db,
});

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
    await ctx.reply(
      '❌ Неверный формат адреса кошелька.\n\n' +
      'Адрес должен:\n' +
      '• Начинаться с 0x\n' +
      '• Содержать 40 символов (итого 42 с префиксом)\n' +
      '• Иметь корректную контрольную сумму (EIP-55)\n\n' +
      'Пожалуйста, скопируйте адрес из вашего кошелька.'
    );
    return;
  }

  // FIX #15: Warn if checksum doesn't match (potential typo)
  if (!hasValidChecksum(walletAddress)) {
    const checksummedAddress = normalizeWalletAddress(walletAddress);

    // Store wallet address in session for confirmation callback
    authCtx.session.data = {
      ...authCtx.session.data,
      pendingWalletAddress: walletAddress,
    };

    await ctx.reply(
      '⚠️ **Предупреждение:** Регистр букв в адресе не соответствует контрольной сумме.\n\n' +
      'Это может указывать на опечатку, которая приведет к потере средств!\n\n' +
      '**Ваш адрес:**\n' +
      `\`${walletAddress}\`\n\n` +
      '**Правильный формат:**\n' +
      `\`${checksummedAddress}\`\n\n` +
      '❓ Продолжить с текущим адресом или ввести заново?',
      {
        parse_mode: 'Markdown',
        ...Markup.inlineKeyboard([
          [Markup.button.callback('✅ Продолжить', 'confirm_wallet_address')],
          [Markup.button.callback('🔄 Ввести заново', 'reenter_wallet_address')],
        ]),
      }
    );
    return;
  }

  // FIX #5: Get referrer ID with fallback mechanism
  let referrerId = authCtx.session.data?.referrerId;

  // If not in session, check Redis backup
  if (!referrerId) {
    const referralKey = `referral:pending:${ctx.from!.id}`;
    const storedReferrerId = await redis.get(referralKey);

    if (storedReferrerId) {
      referrerId = parseInt(storedReferrerId, 10);
      logger.info('Recovered referral ID from backup storage', {
        userId: ctx.from!.id,
        referrerId,
      });
    }
  }

  // FIX #9: WRAP ENTIRE REGISTRATION IN TRANSACTION
  // Ensures user + referral relationships created atomically
  let user;
  let plainPassword;

  try {
    const transactionResult = await withTransaction(async (manager) => {
      // Create user within transaction
      const userResult = await userService.createUser({
        telegramId: ctx.from!.id,
        username: ctx.from?.username,
        walletAddress,
        referrerId,
      }, manager);

      if (userResult.error || !userResult.user) {
        throw new Error(userResult.error || 'Failed to create user');
      }

      // Create referral relationships within same transaction
      if (referrerId) {
        const referralResult = await referralService.createReferralRelationships(
          userResult.user.id,
          referrerId,
          manager
        );

        if (!referralResult.success) {
          // NOW WE FAIL THE ENTIRE REGISTRATION if referrals can't be created
          throw new Error(referralResult.error || 'Failed to create referral relationships');
        }

        logger.info('Referral relationships created atomically', {
          userId: userResult.user.id,
          referrerId,
        });
      }

      return {
        user: userResult.user,
        plainPassword: (userResult.user as any).plainPassword,
      };
    }, TRANSACTION_PRESETS.FINANCIAL);

    user = transactionResult.user;
    plainPassword = transactionResult.plainPassword;

    logger.info('User registered successfully with atomic transaction', {
      userId: user.id,
      telegramId: user.telegram_id,
      hasReferrer: !!referrerId,
    });

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    logger.error('Registration transaction failed', {
      telegramId: ctx.from!.id,
      error: errorMessage,
    });

    await ctx.reply(`❌ Ошибка регистрации: ${errorMessage}`);
    await updateSessionState(ctx.from!.id, BotState.IDLE);
    return;
  }

  // Notify referrer about new referral (outside transaction - non-critical)
  if (referrerId) {
    const referrerUser = await userService.findById(referrerId);
    if (referrerUser) {
      await notificationService.notifyNewReferral(
        referrerUser.telegram_id,
        user.username
      ).catch((err) => {
        logger.error('Failed to notify referrer', {
          referrerId,
          error: err,
        });
      });
    }
  }

  // Success message with financial password
  const successMessage = `${SUCCESS_MESSAGES.REGISTRATION_COMPLETE}

Ваш кошелек: \`${user.maskedWallet}\`

🔐 **Ваш финансовый пароль:** \`${plainPassword}\`

⚠️ **ВАЖНО:** Сохраните этот пароль! Он понадобится для вывода средств и других операций. Мы больше не сможем его показать.

Теперь пройдите верификацию для активации аккаунта.`;

  await ctx.reply(successMessage, {
    parse_mode: 'Markdown',
    ...Markup.inlineKeyboard([
      [Markup.button.callback('✅ Пройти верификацию', 'start_verification')],
      [Markup.button.callback('🔐 Показать пароль ещё раз', 'show_password_again')],
    ]),
  });

  // FIX #5: Clean up backup storage after successful registration
  if (referrerId) {
    const referralKey = `referral:pending:${ctx.from!.id}`;
    await redis.del(referralKey);
    logger.debug('Cleaned up referral ID backup storage', {
      userId: ctx.from!.id,
      referrerId,
    });
  }

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

  // Get bot username for referral link
  const botInfo = await ctx.telegram.getMe();
  const referralLink = userService.generateReferralLink(
    authCtx.user.id,
    botInfo.username
  );

  const confirmMessage = `
✅ Контакты сохранены!

${phone ? `📞 Телефон: ${phone}` : ''}
${email ? `📧 Email: ${email}` : ''}

Добро пожаловать в SigmaTrade! 🎉

💰 **Зарабатывайте с реферальной программой!**

Ваша реферальная ссылка:
\`${referralLink}\`

**Вознаграждения:**
• 3% от депозитов прямых рефералов
• 2% от депозитов рефералов 2-го уровня
• 5% от депозитов рефералов 3-го уровня

Приглашайте друзей и зарабатывайте! 🚀
  `.trim();

  await ctx.reply(confirmMessage, {
    parse_mode: 'Markdown',
    ...getMainKeyboard(false),
  });

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

  // Get bot username for referral link
  const botInfo = await ctx.telegram.getMe();
  const referralLink = userService.generateReferralLink(
    authCtx.user.id,
    botInfo.username
  );

  const welcomeMessage = `
🎉 Регистрация завершена!

Добро пожаловать в SigmaTrade!

💰 **Зарабатывайте с реферальной программой!**

Ваша реферальная ссылка:
\`${referralLink}\`

**Вознаграждения:**
• 3% от депозитов прямых рефералов
• 2% от депозитов рефералов 2-го уровня
• 5% от депозитов рефералов 3-го уровня

Приглашайте друзей и зарабатывайте! 🚀

Используйте меню для навигации по системе.
  `.trim();

  await ctx.editMessageText(welcomeMessage, {
    parse_mode: 'Markdown',
    ...getMainKeyboard(false),
  });
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

/**
 * Show password again (FIX #6)
 * Retrieves password from Redis backup if available
 */
export const handleShowPasswordAgain = async (ctx: Context) => {
  const authCtx = ctx as AuthContext & SessionContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery(ERROR_MESSAGES.USER_NOT_REGISTERED);
    return;
  }

  // Try to get password from Redis
  const plainPassword = await userService.getPlainPassword(authCtx.user.id);

  if (!plainPassword) {
    await ctx.answerCbQuery(
      '⏰ Время истекло! Пароль доступен только в течение 1 часа после регистрации.',
      { show_alert: true }
    );
    return;
  }

  // Send password as a separate message (more secure)
  const passwordMessage = `
🔐 **Ваш финансовый пароль:**

\`${plainPassword}\`

⚠️ **ВАЖНО:**
• Сохраните пароль в надежном месте
• Не передавайте его третьим лицам
• Пароль доступен только в течение 1 часа после регистрации

После истечения времени вы НЕ сможете восстановить этот пароль!
  `.trim();

  await ctx.reply(passwordMessage, {
    parse_mode: 'Markdown',
  });

  await ctx.answerCbQuery('Пароль отправлен вам в личные сообщения');

  logger.info('User retrieved password again from Redis', {
    userId: authCtx.user.id,
  });
};

/**
 * FIX #15: Confirm wallet address despite checksum warning
 * User chose to proceed with the wallet address even though checksum doesn't match
 */
export const handleConfirmWalletAddress = async (ctx: Context) => {
  const authCtx = ctx as AuthContext & SessionContext;

  // Get pending wallet address from session
  const walletAddress = authCtx.session.data?.pendingWalletAddress;

  if (!walletAddress) {
    await ctx.answerCbQuery('Ошибка: адрес не найден. Пожалуйста, введите заново.');
    await updateSessionState(ctx.from!.id, BotState.AWAITING_WALLET_ADDRESS);
    return;
  }

  // Clear pending address from session
  delete authCtx.session.data.pendingWalletAddress;

  await ctx.answerCbQuery('Продолжаем регистрацию...');

  // Proceed with registration (same logic as handleWalletInput after validation)
  // FIX #5: Get referrer ID with fallback mechanism
  let referrerId = authCtx.session.data?.referrerId;

  // If not in session, check Redis backup
  if (!referrerId) {
    const referralKey = `referral:pending:${ctx.from!.id}`;
    const storedReferrerId = await redis.get(referralKey);

    if (storedReferrerId) {
      referrerId = parseInt(storedReferrerId, 10);
      logger.info('Recovered referral ID from backup storage', {
        userId: ctx.from!.id,
        referrerId,
      });
    }
  }

  // FIX #9: WRAP ENTIRE REGISTRATION IN TRANSACTION
  let user;
  let plainPassword;

  try {
    const transactionResult = await withTransaction(async (manager) => {
      // Create user within transaction
      const userResult = await userService.createUser({
        telegramId: ctx.from!.id,
        username: ctx.from?.username,
        walletAddress,
        referrerId,
      }, manager);

      if (userResult.error || !userResult.user) {
        throw new Error(userResult.error || 'Failed to create user');
      }

      // Create referral relationships within same transaction
      if (referrerId) {
        const referralResult = await referralService.createReferralRelationships(
          userResult.user.id,
          referrerId,
          manager
        );

        if (!referralResult.success) {
          throw new Error(referralResult.error || 'Failed to create referral relationships');
        }
      }

      return {
        user: userResult.user,
        plainPassword: (userResult.user as any).plainPassword,
      };
    }, TRANSACTION_PRESETS.FINANCIAL);

    user = transactionResult.user;
    plainPassword = transactionResult.plainPassword;

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    await ctx.editMessageText(`❌ Ошибка регистрации: ${errorMessage}`);
    await updateSessionState(ctx.from!.id, BotState.IDLE);
    return;
  }

  // Send success message with password
  const successMessage = `${SUCCESS_MESSAGES.REGISTRATION_COMPLETE}

🔐 **Ваш финансовый пароль:**

\`${plainPassword}\`

⚠️ **ОЧЕНЬ ВАЖНО:**
• Сохраните этот пароль в надежном месте
• Пароль нужен для подтверждения финансовых операций
• Мы НЕ можем восстановить ваш пароль
• Не передавайте пароль третьим лицам

💡 Пароль также доступен в течение 1 часа через кнопку ниже.`;

  await ctx.editMessageText(successMessage, {
    parse_mode: 'Markdown',
    ...Markup.inlineKeyboard([
      [Markup.button.callback('✅ Пройти верификацию', 'start_verification')],
      [Markup.button.callback('🔐 Показать пароль ещё раз', 'show_password_again')],
    ]),
  });

  await updateSessionState(ctx.from!.id, BotState.IDLE);

  // Notify user about successful registration
  await notificationService.notifyUserRegistered(user.telegram_id, user.username || 'Пользователь');

  logger.info('User confirmed wallet address with checksum warning', {
    userId: user.id,
    telegramId: user.telegram_id,
    walletAddress,
  });
};

/**
 * FIX #15: Re-enter wallet address after checksum warning
 */
export const handleReenterWalletAddress = async (ctx: Context) => {
  const authCtx = ctx as AuthContext & SessionContext;

  // Clear pending address from session
  if (authCtx.session.data?.pendingWalletAddress) {
    delete authCtx.session.data.pendingWalletAddress;
  }

  await updateSessionState(ctx.from!.id, BotState.AWAITING_WALLET_ADDRESS);

  await ctx.editMessageText(
    '🔄 Хорошо, введите адрес кошелька заново.\n\n' +
    '📋 Рекомендуем скопировать адрес непосредственно из вашего кошелька, ' +
    'чтобы избежать ошибок в регистре символов.'
  );

  await ctx.answerCbQuery('Введите адрес заново');
};

export default {
  handleStartRegistration,
  handleWalletInput,
  handleConfirmWalletAddress,
  handleReenterWalletAddress,
  handleStartVerification,
  handleAddContactInfo,
  handleContactInfoInput,
  handleSkipContactInfo,
  handleCancelRegistration,
  handleShowPasswordAgain,
};
