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
import { AppDataSource } from '../database/data-source';
import { FailedNotification } from '../database/entities';
import { formatUSDT } from '../utils/money.util';

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
   * Send a custom message to a user
   * Public wrapper for sending arbitrary messages
   */
  public async sendCustomMessage(
    telegramId: number,
    message: string,
    options?: { parse_mode?: 'Markdown' | 'HTML' }
  ): Promise<boolean> {
    return this.sendNotification(telegramId, message, {
      parse_mode: options?.parse_mode,
      notificationType: 'custom_message',
    });
  }

  /**
   * Send photo message to user
   */
  public async sendPhotoMessage(
    telegramId: number,
    fileIdOrUrl: string,
    caption?: string,
    options?: { parse_mode?: 'Markdown' | 'HTML' }
  ): Promise<boolean> {
    if (!this.bot) {
      logger.error('Bot not initialized in NotificationService');
      return false;
    }

    try {
      await this.bot.telegram.sendPhoto(telegramId, fileIdOrUrl, {
        caption,
        parse_mode: options?.parse_mode,
      });
      return true;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);

      logger.error('Error sending photo message', {
        telegramId,
        error: errorMessage,
      });

      // Track failed notification
      try {
        const failedRepo = AppDataSource.getRepository(FailedNotification);
        await failedRepo.save({
          user_telegram_id: telegramId,
          notification_type: 'photo_message',
          message: `Photo: ${fileIdOrUrl}${caption ? ` | Caption: ${caption}` : ''}`,
          metadata: { fileIdOrUrl, caption },
          attempt_count: 1,
          last_error: errorMessage,
          last_attempt_at: new Date(),
          critical: false,
        });
      } catch (dbError) {
        logger.error('Failed to save failed photo notification', {
          telegramId,
          error: dbError instanceof Error ? dbError.message : String(dbError),
        });
      }

      return false;
    }
  }

  /**
   * Send voice message to user
   */
  public async sendVoiceMessage(
    telegramId: number,
    fileId: string,
    caption?: string,
    options?: { parse_mode?: 'Markdown' | 'HTML' }
  ): Promise<boolean> {
    if (!this.bot) {
      logger.error('Bot not initialized in NotificationService');
      return false;
    }

    try {
      await this.bot.telegram.sendVoice(telegramId, fileId, {
        caption,
        parse_mode: options?.parse_mode,
      });
      return true;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);

      logger.error('Error sending voice message', {
        telegramId,
        error: errorMessage,
      });

      // Track failed notification
      try {
        const failedRepo = AppDataSource.getRepository(FailedNotification);
        await failedRepo.save({
          user_telegram_id: telegramId,
          notification_type: 'voice_message',
          message: `Voice: ${fileId}${caption ? ` | Caption: ${caption}` : ''}`,
          metadata: { fileId, caption },
          attempt_count: 1,
          last_error: errorMessage,
          last_attempt_at: new Date(),
          critical: false,
        });
      } catch (dbError) {
        logger.error('Failed to save failed voice notification', {
          telegramId,
          error: dbError instanceof Error ? dbError.message : String(dbError),
        });
      }

      return false;
    }
  }

  /**
   * Send audio message to user
   */
  public async sendAudioMessage(
    telegramId: number,
    fileId: string,
    caption?: string,
    options?: { parse_mode?: 'Markdown' | 'HTML' }
  ): Promise<boolean> {
    if (!this.bot) {
      logger.error('Bot not initialized in NotificationService');
      return false;
    }

    try {
      await this.bot.telegram.sendAudio(telegramId, fileId, {
        caption,
        parse_mode: options?.parse_mode,
      });
      return true;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);

      logger.error('Error sending audio message', {
        telegramId,
        error: errorMessage,
      });

      // Track failed notification
      try {
        const failedRepo = AppDataSource.getRepository(FailedNotification);
        await failedRepo.save({
          user_telegram_id: telegramId,
          notification_type: 'audio_message',
          message: `Audio: ${fileId}${caption ? ` | Caption: ${caption}` : ''}`,
          metadata: { fileId, caption },
          attempt_count: 1,
          last_error: errorMessage,
          last_attempt_at: new Date(),
          critical: false,
        });
      } catch (dbError) {
        logger.error('Failed to save failed audio notification', {
          telegramId,
          error: dbError instanceof Error ? dbError.message : String(dbError),
        });
      }

      return false;
    }
  }

  /**
   * Send notification to user with failure tracking
   * FIX #17: Track and retry failed notifications
   */
  private async sendNotification(
    telegramId: number,
    message: string,
    options?: {
      parse_mode?: 'Markdown' | 'HTML';
      notificationType?: string;
      metadata?: Record<string, any>;
      critical?: boolean;
    }
  ): Promise<boolean> {
    if (!this.bot) {
      logger.error('Bot not initialized in NotificationService');
      return false;
    }

    try {
      await this.bot.telegram.sendMessage(telegramId, message, {
        parse_mode: options?.parse_mode,
      });
      return true;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);

      logger.error('Error sending notification', {
        telegramId,
        type: options?.notificationType,
        error: errorMessage,
      });

      // FIX #17: Store failed notification for retry
      try {
        const failedRepo = AppDataSource.getRepository(FailedNotification);
        await failedRepo.save({
          user_telegram_id: telegramId,
          notification_type: options?.notificationType || 'generic',
          message,
          metadata: options?.metadata || null,
          attempt_count: 1,
          last_error: errorMessage,
          last_attempt_at: new Date(),
          critical: options?.critical || false,
        });

        logger.info('Failed notification saved for retry', {
          telegramId,
          type: options?.notificationType,
        });

        // If critical, alert admin immediately
        if (options?.critical) {
          await this.alertAdminNotificationFailure(
            telegramId,
            options.notificationType || 'generic',
            errorMessage
          ).catch((err) => {
            logger.error('Failed to alert admin', { error: err });
          });
        }
      } catch (dbError) {
        logger.error('Failed to save failed notification', {
          telegramId,
          error: dbError instanceof Error ? dbError.message : String(dbError),
        });
      }

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
   * Notify user about deposit reward payment
   */
  public async notifyDepositRewardPayment(
    telegramId: number,
    amount: number,
    txHash: string
  ): Promise<void> {
    const message = `
💰 **Награда за депозит выплачена!**

💸 Сумма: ${formatUSDT(amount)} USDT
🔗 Транзакция: \`${txHash}\`

Ваша награда за депозиты отправлена на ваш кошелек!

[Посмотреть в BSCScan](https://bscscan.com/tx/${txHash})
    `.trim();

    await this.sendNotification(telegramId, message, { parse_mode: 'Markdown' });

    logger.info('Deposit reward payment notification sent', {
      telegramId,
      amount,
    });
  }

  /**
   * Notify user about ROI cap completion (500% reached)
   */
  public async notifyRoiCompleted(
    telegramId: number,
    level: number,
    capAmount: number
  ): Promise<void> {
    const message = `
🎯 **ROI достигнут 500%!**

📊 Уровень: ${level}
💰 Получено: ${formatUSDT(capAmount)} USDT
🔥 Доход: 500% (5x)

✅ Ваш депозит Уровня ${level} достиг максимального дохода 500%!

📌 **Что дальше?**
Чтобы продолжить получать доход, внесите новый депозит ${level === 1 ? '10 USDT' : ''}.

💡 Депозит не возвращается — это чистый доход от инвестиций!
    `.trim();

    await this.sendNotification(telegramId, message, { parse_mode: 'Markdown' });

    logger.info('ROI completion notification sent', {
      telegramId,
      level,
      capAmount,
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
   * Notify all admins about critical system event
   */
  public async notifyAllAdmins(
    title: string,
    message: string
  ): Promise<void> {
    try {
      // Import Admin entity dynamically to avoid circular dependency
      const { AppDataSource } = await import('../database/data-source');
      const { Admin } = await import('../database/entities');

      const adminRepo = AppDataSource.getRepository(Admin);
      const admins = await adminRepo.find({ select: ['telegram_id'] });

      if (admins.length === 0) {
        logger.warn('No admins found to send notification');
        return;
      }

      const fullMessage = `
🚨 **${title}**

${message}
    `.trim();

      // Send to all admins in parallel
      await Promise.allSettled(
        admins.map((admin) =>
          this.sendNotification(admin.telegram_id, fullMessage, {
            parse_mode: 'Markdown',
          })
        )
      );

      logger.info('Critical alert sent to all admins', {
        adminCount: admins.length,
        title,
      });
    } catch (error) {
      logger.error('Failed to notify admins', { error });
    }
  }

  /**
   * Alert admins about low payout wallet balance
   */
  public async alertLowPayoutBalance(
    currentBalance: number,
    threshold: number
  ): Promise<void> {
    await this.notifyAllAdmins(
      'Низкий баланс кошелька',
      `⚠️ Баланс платежного кошелька опустился до **${formatUSDT(currentBalance)} USDT**\n\n` +
      `Пороговое значение: ${threshold} USDT\n\n` +
      `Пополните кошелек для продолжения выплат.`
    );
  }

  /**
   * Alert admins about failed payment
   */
  public async alertPaymentFailed(
    userId: number,
    amount: number,
    error: string
  ): Promise<void> {
    await this.notifyAllAdmins(
      'Ошибка выплаты',
      `❌ Не удалось выполнить выплату:\n\n` +
      `👤 Пользователь ID: ${userId}\n` +
      `💰 Сумма: ${formatUSDT(amount)} USDT\n` +
      `📝 Ошибка: ${error}\n\n` +
      `Требуется ручная проверка.`
    );
  }

  /**
   * Alert admins about payment moved to DLQ (Dead Letter Queue)
   */
  public async alertPaymentMovedToDLQ(
    userId: number,
    amount: number,
    attemptCount: number,
    error: string
  ): Promise<void> {
    await this.notifyAllAdmins(
      'Выплата перемещена в DLQ',
      `🚨 **Критическое:** Выплата перемещена в очередь неудачных попыток (DLQ)\n\n` +
      `👤 Пользователь ID: ${userId}\n` +
      `💰 Сумма: ${formatUSDT(amount)} USDT\n` +
      `🔄 Попыток: ${attemptCount}\n` +
      `📝 Последняя ошибка: ${error}\n\n` +
      `Автоматические попытки исчерпаны. Требуется ручное вмешательство администратора.\n` +
      `Используйте команду /retry_dlq для повторной попытки.`
    );
  }

  /**
   * Alert admins about WebSocket disconnect
   */
  public async alertWebSocketDisconnect(
    attempts: number,
    maxAttempts: number
  ): Promise<void> {
    if (attempts >= maxAttempts) {
      await this.notifyAllAdmins(
        'WebSocket отключен',
        `🔴 **Критическое:** WebSocket соединение потеряно!\n\n` +
        `Попытки переподключения исчерпаны (${attempts}/${maxAttempts})\n\n` +
        `Мониторинг депозитов остановлен. Требуется перезапуск.`
      );
    } else if (attempts >= 5) {
      await this.notifyAllAdmins(
        'Проблемы с WebSocket',
        `⚠️ Множественные попытки переподключения WebSocket\n\n` +
        `Попытка ${attempts}/${maxAttempts}\n\n` +
        `Проверьте соединение с QuickNode.`
      );
    }
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

  /**
   * Notify user about withdrawal rejected
   */
  public async notifyWithdrawalRejected(
    telegramId: number,
    amount: number
  ): Promise<void> {
    const message = `
❌ **Заявка на вывод отклонена**

💰 Сумма: ${amount} USDT

К сожалению, ваша заявка на вывод была отклонена администратором.

Средства возвращены на ваш баланс.
Вы можете повторить запрос на вывод или обратиться в поддержку.
    `.trim();

    await this.sendNotification(telegramId, message, { parse_mode: 'Markdown' });

    logger.info('Withdrawal rejected notification sent', {
      telegramId,
      amount,
    });
  }

  /**
   * Alert admin about notification failure (FIX #17)
   */
  public async alertAdminNotificationFailure(
    userId: number,
    notificationType: string,
    error: string
  ): Promise<void> {
    const message = `
⚠️ **Уведомление не доставлено**

👤 Пользователь ID: ${userId}
📋 Тип: ${notificationType}
❌ Ошибка: ${error}

Уведомление сохранено для повторной попытки.
    `.trim();

    await this.notifyAllAdmins('Ошибка доставки уведомления', message);
  }

  /**
   * Alert admin that notification retry gave up (FIX #17)
   */
  public async alertNotificationGaveUp(
    userId: number,
    notificationType: string,
    originalMessage: string,
    lastError: string
  ): Promise<void> {
    const truncatedMessage =
      originalMessage.length > 200
        ? originalMessage.substring(0, 200) + '...'
        : originalMessage;

    const message = `
🚨 **Критическое: Уведомление не доставлено после 5 попыток**

👤 Пользователь ID: ${userId}
📋 Тип: ${notificationType}
❌ Последняя ошибка: ${lastError}

**Сообщение:**
${truncatedMessage}

Пользователь, вероятно, заблокировал бота или удалил аккаунт.
Требуется ручное вмешательство.
    `.trim();

    await this.notifyAllAdmins('Уведомление не доставлено', message);
  }
}

// Export singleton instance
export const notificationService = NotificationService.getInstance();
