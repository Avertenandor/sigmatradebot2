/**
 * User Instructions Handler
 * Provides step-by-step deposit instructions for users
 *
 * FEATURES:
 * - Network and token information (BSC / USDT BEP-20)
 * - System wallet address (dynamically loaded from settings)
 * - Tolerance information (±5%)
 * - Common mistakes and troubleshooting
 * - Links to BscScan for verification
 */

import { Context, Markup } from 'telegraf';
import { settingsService } from '../../services/settings.service';
import { createLogger } from '../../utils/logger.util';

const logger = createLogger('InstructionsHandler');

/**
 * Show deposit instructions main menu
 */
export const handleInstructions = async (ctx: Context): Promise<void> => {
  try {
    // Get current system wallet address
    const systemWallet = await settingsService.getSystemWalletAddress();

    const message = `
📘 **Инструкция по пополнению**

🔸 **Сеть:** Binance Smart Chain (BSC / BEP-20)
🔸 **Токен:** USDT (BEP-20)
🔸 **Адрес для пополнения:**
\`${systemWallet}\`

⚙️ **Толеранс:** ±5% от суммы депозита
⛽ **Комиссия сети:** Оплачивается BNB (не USDT)

📝 **Пошаговая инструкция:**

1️⃣ Откройте ваш кошелёк (Trust Wallet, MetaMask, Binance и т.д.)

2️⃣ Выберите сеть **BSC (BEP-20)** и токен **USDT**

3️⃣ Скопируйте адрес выше и вставьте в поле получателя

4️⃣ Укажите сумму депозита: **10 USDT**

5️⃣ Подтвердите транзакцию и дождитесь 3-5 блоков

6️⃣ Ваш депозит будет зачислен автоматически

⚠️ **Важно:**
• Используйте только сеть BSC (BEP-20)
• Другие сети (ERC-20, TRC-20) не поддерживаются
• Сумма депозита: 10 USDT (±5% толеранс)
• Максимальная прибыль: до 500% от депозита
• **Депозит не возвращается** — работает на торговлю
• Комиссию сети оплачивайте в BNB

Выберите действие:
    `.trim();

    const keyboard = Markup.inlineKeyboard([
      [Markup.button.callback('📋 Скопировать адрес', 'user_instructions_copy_address')],
      [Markup.button.callback('🔎 Открыть на BscScan', 'user_instructions_bscscan')],
      [Markup.button.callback('⏳ Проверить статус депозита', 'user_instructions_check_status')],
      [Markup.button.callback('❗ Частые ошибки', 'user_instructions_common_mistakes')],
      [Markup.button.callback('« Назад', 'main_menu')],
    ]);

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
      await ctx.answerCbQuery?.();
    }

    logger.info('User viewed instructions', { userId: ctx.from?.id });
  } catch (error) {
    logger.error('Failed to load instructions', { error, userId: ctx.from?.id });
    await ctx.reply('Ошибка загрузки инструкции. Попробуйте позже.');
    if (ctx.callbackQuery) {
      await ctx.answerCbQuery?.();
    }
  }
};

/**
 * Copy address (show address in copyable format)
 */
export const handleCopyAddress = async (ctx: Context): Promise<void> => {
  try {
    const systemWallet = await settingsService.getSystemWalletAddress();

    const message = `
📋 **Адрес для пополнения:**

\`${systemWallet}\`

Нажмите на адрес выше, чтобы скопировать.

🔸 **Сеть:** BSC (BEP-20)
🔸 **Токен:** USDT
    `.trim();

    await ctx.editMessageText(message, {
      parse_mode: 'Markdown',
      ...Markup.inlineKeyboard([
        [Markup.button.callback('« Назад к инструкции', 'user_instructions')],
      ]),
    });

    if (ctx.callbackQuery) {
      await ctx.answerCbQuery?.('Адрес готов к копированию');
    }
  } catch (error) {
    await ctx.answerCbQuery?.('Ошибка загрузки адреса');
  }
};

/**
 * Open address on BscScan
 */
export const handleOpenBscScan = async (ctx: Context): Promise<void> => {
  try {
    const systemWallet = await settingsService.getSystemWalletAddress();
    const bscscanUrl = `https://bscscan.com/address/${systemWallet}`;

    const message = `
🔎 **Просмотр на BscScan**

Вы можете проверить баланс и транзакции системного кошелька на BscScan:

🔗 [Открыть ${systemWallet.substring(0, 10)}... на BscScan](${bscscanUrl})

На BscScan вы сможете:
• Просмотреть баланс кошелька
• Увидеть историю транзакций
• Проверить статус вашей транзакции
• Убедиться в корректности адреса
    `.trim();

    await ctx.editMessageText(message, {
      parse_mode: 'Markdown',
      link_preview_options: { is_disabled: true },
      ...Markup.inlineKeyboard([
        [Markup.button.url('🔗 Открыть на BscScan', bscscanUrl)],
        [Markup.button.callback('« Назад к инструкции', 'user_instructions')],
      ]),
    });

    if (ctx.callbackQuery) {
      await ctx.answerCbQuery?.();
    }
  } catch (error) {
    await ctx.answerCbQuery?.('Ошибка загрузки ссылки');
  }
};

/**
 * Check deposit status
 */
export const handleCheckStatus = async (ctx: Context): Promise<void> => {
  const message = `
⏳ **Проверка статуса депозита**

Ваш депозит обрабатывается автоматически:

1️⃣ **Отправлено** → Транзакция отправлена из вашего кошелька

2️⃣ **В обработке** → Ожидание подтверждений (3-5 блоков)

3️⃣ **Подтверждено** → Депозит зачислен, награды начисляются

⏱️ **Обычное время:** 1-5 минут

Если депозит не зачислился в течение 10 минут:
• Проверьте, что использовали сеть **BSC (BEP-20)**
• Проверьте статус транзакции на BscScan
• Обратитесь в техподдержку с хешем транзакции

Проверить свои депозиты: /deposits
  `.trim();

  await ctx.editMessageText(message, {
    parse_mode: 'Markdown',
    ...Markup.inlineKeyboard([
      [Markup.button.callback('💰 Мои депозиты', 'deposits')],
      [Markup.button.callback('« Назад к инструкции', 'user_instructions')],
    ]),
  });

  if (ctx.callbackQuery) {
    await ctx.answerCbQuery?.();
  }
};

/**
 * Common mistakes and troubleshooting
 */
export const handleCommonMistakes = async (ctx: Context): Promise<void> => {
  const message = `
❗ **Частые ошибки и как их избежать**

❌ **Неправильная сеть**
Используйте только **BSC (BEP-20)**, а не ERC-20 или TRC-20.
Если отправили в другой сети — средства могут быть потеряны.

❌ **Неправильный токен**
Отправляйте только **USDT**, а не BNB, BUSD или другие токены.

❌ **Недостаточно BNB для комиссии**
Комиссия сети оплачивается в BNB. Убедитесь, что на балансе есть ~0.001 BNB для комиссии.

❌ **Неправильная сумма**
Депозит должен быть 10 USDT (±5% толеранс: 9.5-10.5 USDT).
Другие суммы не будут зачислены автоматически.

❌ **Копипаста с ошибкой**
Дважды проверьте адрес перед отправкой.
Используйте кнопку "Скопировать адрес" в инструкции.

✅ **Как избежать проблем:**
• Используйте кнопку "Скопировать адрес"
• Проверьте сеть (BSC) и токен (USDT)
• Убедитесь в наличии BNB для комиссии
• Отправляйте точную сумму депозита

🆘 **Нужна помощь?**
Обратитесь в техподдержку: /support
  `.trim();

  await ctx.editMessageText(message, {
    parse_mode: 'Markdown',
    ...Markup.inlineKeyboard([
      [Markup.button.callback('🆘 Техподдержка', 'support')],
      [Markup.button.callback('« Назад к инструкции', 'user_instructions')],
    ]),
  });

  if (ctx.callbackQuery) {
    await ctx.answerCbQuery?.();
  }
};
