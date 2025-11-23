/**
 * Notification Service
 * Handles sending notifications to users via Telegram
 * - Deposit confirmations
 * - Referral earnings
 * - Level activations
 * - System alerts
 */

import { Telegraf } from 'telegraf';
import { logger } from '../utils/logger.util';

export class NotificationService {
  private static instance: NotificationService;
  private bot?: Telegraf;

  private constructor() {}

  public static getInstance(): NotificationService {
    if (!NotificationService.instance) {
      NotificationService.instance = new NotificationService();
    }
    return NotificationService.instance;
  }

  /**
   * Set bot instance (called from bot initialization)
   */
  public setBot(bot: Telegraf): void {
    this.bot = bot;
  }

  /**
   * Send notification to user
   */
  private async sendNotification(
    telegramId: number,
    message: string,
    options?: { parse_mode?: 'Markdown' | 'HTML' }
  ): Promise<boolean> {
    if (!this.bot) {
      logger.error('Bot not initialized in NotificationService');
      return false;
    }

    try {
      await this.bot.telegram.sendMessage(telegramId, message, options);
      return true;
    } catch (error) {
      logger.error('Error sending notification', {
        telegramId,
        error: error instanceof Error ? error.message : String(error),
      });
      return false;
    }
  }

  /**
   * Notify user about deposit confirmation
   */
  public async notifyDepositConfirmed(
    telegramId: number,
    amount: number,
    level: number,
    txHash: string
  ): Promise<void> {
    const message = `
✅ **Депозит подтвержден!**

💰 Сумма: ${amount} USDT
📊 Уровень: ${level}
🔗 Транзакция: \`${txHash}\`

Ваш депозит успешно подтвержден в блокчейне BSC!
Уровень ${level} активирован. 🎉

[Посмотреть в BSCScan](https://bscscan.com/tx/${txHash})
    `.trim();

    await this.sendNotification(telegramId, message, { parse_mode: 'Markdown' });

    logger.info('Deposit confirmation notification sent', {
      telegramId,
      amount,
      level,
    });
  }

  /**
   * Notify user about referral earning
   */
  public async notifyReferralEarning(
    telegramId: number,
    amount: number,
    level: number,
    referredUsername?: string
  ): Promise<void> {
    const levelNames = {
      1: 'прямого реферала',
      2: 'реферала 2 уровня',
      3: 'реферала 3 уровня',
    };

    const referredInfo = referredUsername
      ? `от ${referredUsername}`
      : `уровня ${level}`;

    const message = `
💵 **Получено реферальное вознаграждение!**

💰 Сумма: ${amount} USDT
👥 От: ${levelNames[level as keyof typeof levelNames] || `уровня ${level}`}
${referredUsername ? `👤 Реферал: @${referredUsername}` : ''}

Вознаграждение будет выплачено на ваш кошелек автоматически.
    `.trim();

    await this.sendNotification(telegramId, message, { parse_mode: 'Markdown' });

    logger.info('Referral earning notification sent', {
      telegramId,
      amount,
      level,
    });
  }

  /**
   * Notify user about payment sent
   */
  public async notifyPaymentSent(
    telegramId: number,
    amount: number,
    txHash: string
  ): Promise<void> {
    const message = `
💸 **Выплата отправлена!**

💰 Сумма: ${amount} USDT
🔗 Транзакция: \`${txHash}\`

Реферальные вознаграждения отправлены на ваш кошелек!

[Посмотреть в BSCScan](https://bscscan.com/tx/${txHash})
    `.trim();

    await this.sendNotification(telegramId, message, { parse_mode: 'Markdown' });

    logger.info('Payment sent notification sent', {
      telegramId,
      amount,
    });
  }

  /**
   * Notify user about new referral
   */
  public async notifyNewReferral(
    telegramId: number,
    referralUsername?: string
  ): Promise<void> {
    const referralInfo = referralUsername
      ? `**@${referralUsername}**`
      : 'Новый пользователь';

    const message = `
🎉 **У вас новый реферал!**

👤 ${referralInfo} зарегистрировался по вашей ссылке!

Вы будете получать вознаграждения от его депозитов:
• 3% от прямых депозитов
• 2% от депозитов его рефералов
• 5% от депозитов рефералов 3 уровня

Продолжайте приглашать друзей! 💰
    `.trim();

    await this.sendNotification(telegramId, message, { parse_mode: 'Markdown' });

    logger.info('New referral notification sent', {
      telegramId,
      referralUsername,
    });
  }

  /**
   * Notify user about level activation
   */
  public async notifyLevelActivated(
    telegramId: number,
    level: number
  ): Promise<void> {
    const message = `
🎊 **Уровень ${level} активирован!**

Поздравляем! Вы успешно активировали уровень ${level}.

${level < 5 ? `Следующий уровень: ${level + 1}\nТребуется рефералов: ${level}` : 'Вы достигли максимального уровня! 🏆'}
    `.trim();

    await this.sendNotification(telegramId, message, { parse_mode: 'Markdown' });

    logger.info('Level activation notification sent', {
      telegramId,
      level,
    });
  }

  /**
   * Notify admin about system event
   */
  public async notifyAdmin(
    adminTelegramId: number,
    title: string,
    message: string
  ): Promise<void> {
    const fullMessage = `
🔔 **${title}**

${message}
    `.trim();

    await this.sendNotification(adminTelegramId, fullMessage, {
      parse_mode: 'Markdown',
    });

    logger.info('Admin notification sent', {
      adminTelegramId,
      title,
    });
  }

  /**
   * Notify user about deposit pending
   */
  public async notifyDepositPending(
    telegramId: number,
    amount: number,
    level: number,
    txHash: string
  ): Promise<void> {
    const message = `
⏳ **Депозит обнаружен!**

💰 Сумма: ${amount} USDT
📊 Уровень: ${level}
🔗 Транзакция: \`${txHash}\`

Ожидаем подтверждение в блокчейне (12 блоков).
Обычно это занимает 1-2 минуты.

[Отследить транзакцию](https://bscscan.com/tx/${txHash})
    `.trim();

    await this.sendNotification(telegramId, message, { parse_mode: 'Markdown' });

    logger.info('Deposit pending notification sent', {
      telegramId,
      amount,
      level,
    });
  }

  /**
   * Notify user about deposit timeout
   */
  public async notifyDepositTimeout(
    telegramId: number,
    amount: number,
    level: number
  ): Promise<void> {
    const message = `
⏱️ **Время ожидания депозита истекло**

💰 Сумма: ${amount} USDT
📊 Уровень: ${level}

К сожалению, мы не обнаружили депозит в течение 24 часов.

Возможные причины:
• Транзакция не была отправлена
• Неправильный адрес или сеть
• Недостаточная сумма для покрытия комиссии

Если вы отправили средства, свяжитесь с поддержкой.
    `.trim();

    await this.sendNotification(telegramId, message, { parse_mode: 'Markdown' });

    logger.info('Deposit timeout notification sent', {
      telegramId,
      amount,
      level,
    });
  }

  /**
   * Notify user about withdrawal request received
   */
  public async notifyWithdrawalReceived(
    telegramId: number,
    amount: number
  ): Promise<void> {
    const message = `
📤 **Заявка на вывод получена**

💰 Сумма: ${amount} USDT

Ваша заявка принята в обработку.
Обычно вывод занимает 15-30 минут.

Мы уведомим вас, когда средства будут отправлены.
    `.trim();

    await this.sendNotification(telegramId, message, { parse_mode: 'Markdown' });

    logger.info('Withdrawal received notification sent', {
      telegramId,
      amount,
    });
  }

  /**
   * Notify user about withdrawal processed
   */
  public async notifyWithdrawalProcessed(
    telegramId: number,
    amount: number,
    txHash: string
  ): Promise<void> {
    const message = `
✅ **Вывод выполнен!**

💰 Сумма: ${amount} USDT
🔗 Транзакция: \`${txHash}\`

Средства отправлены на ваш кошелек!

[Посмотреть в BSCScan](https://bscscan.com/tx/${txHash})
    `.trim();

    await this.sendNotification(telegramId, message, { parse_mode: 'Markdown' });

    logger.info('Withdrawal processed notification sent', {
      telegramId,
      amount,
    });
  }
}

// Export singleton instance
export const notificationService = NotificationService.getInstance();
