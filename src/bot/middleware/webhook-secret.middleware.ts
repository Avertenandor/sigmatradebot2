import { Request, Response, NextFunction } from 'express';
import { getEnvConfig } from '../../config/env.validator';
import { logger } from '../../utils/logger.util';

/**
 * Middleware для проверки секрета Telegram webhook
 *
 * Защищает от поддельных webhook запросов от неавторизованных источников
 *
 * Требования:
 * 1. При setWebhook() указать secret_token
 * 2. Установить переменную TELEGRAM_WEBHOOK_SECRET в .env
 * 3. Telegram будет отправлять заголовок X-Telegram-Bot-Api-Secret-Token
 *
 * @see https://core.telegram.org/bots/api#setwebhook
 */
export function webhookSecretMiddleware(
  req: Request,
  res: Response,
  next: NextFunction
): void {
  const config = getEnvConfig();

  // Если секрет не настроен
  if (!config.TELEGRAM_WEBHOOK_SECRET) {
    // В production это критичная ошибка (хотя env.validator должен был уже заблокировать старт)
    if (config.NODE_ENV === 'production') {
      logger.error('КРИТИЧНО: TELEGRAM_WEBHOOK_SECRET не настроен в production окружении');
      return res.status(503).json({
        error: 'Service Unavailable',
        message: 'Webhook security not configured',
      });
    }

    // В development - предупреждение и пропуск
    logger.warn(
      'TELEGRAM_WEBHOOK_SECRET не настроен - webhook не защищён от подделки. ' +
        'Установите TELEGRAM_WEBHOOK_SECRET в .env для production.'
    );
    return next();
  }

  // Получаем заголовок с секретом от Telegram
  const secretHeader = req.headers['x-telegram-bot-api-secret-token'];

  // Проверяем наличие заголовка
  if (!secretHeader) {
    logger.warn('Получен webhook запрос без заголовка X-Telegram-Bot-Api-Secret-Token', {
      ip: req.ip,
      userAgent: req.headers['user-agent'],
      path: req.path,
    });

    return res.status(403).json({
      error: 'Forbidden',
      message: 'Missing webhook secret',
    });
  }

  // Проверяем совпадение секрета
  if (secretHeader !== config.TELEGRAM_WEBHOOK_SECRET) {
    logger.error('Получен webhook запрос с неверным секретом - возможная атака!', {
      ip: req.ip,
      userAgent: req.headers['user-agent'],
      path: req.path,
      providedSecret: String(secretHeader).substring(0, 8) + '...',
    });

    return res.status(403).json({
      error: 'Forbidden',
      message: 'Invalid webhook secret',
    });
  }

  // Секрет валиден - пропускаем запрос
  next();
}

/**
 * Middleware для проверки IP адресов Telegram
 *
 * Дополнительная защита: проверяем, что запрос пришёл с известных IP Telegram
 *
 * Telegram webhook IP ranges (по состоянию на 2024):
 * - 149.154.160.0/20
 * - 91.108.4.0/22
 *
 * ВАЖНО: IP могут измениться, поэтому это дополнительная, а не основная защита
 * Основная защита - webhook secret выше
 */
export function webhookIpWhitelistMiddleware(
  req: Request,
  res: Response,
  next: NextFunction
): void {
  const clientIp = req.ip || req.socket.remoteAddress || '';

  // Известные IP диапазоны Telegram (обновить при необходимости)
  const telegramIpRanges = [
    // Основные диапазоны
    '149.154.160.',
    '149.154.161.',
    '149.154.162.',
    '149.154.163.',
    '149.154.164.',
    '149.154.165.',
    '149.154.166.',
    '149.154.167.',
    '149.154.168.',
    '149.154.169.',
    '149.154.170.',
    '149.154.171.',
    '149.154.172.',
    '149.154.173.',
    '149.154.174.',
    '149.154.175.',
    '91.108.4.',
    '91.108.5.',
    '91.108.6.',
    '91.108.7.',
  ];

  // Локальные IP для разработки
  const developmentIps = ['127.0.0.1', '::1', '::ffff:127.0.0.1', 'localhost'];

  // В development режиме пропускаем локальные запросы
  if (process.env.NODE_ENV === 'development' && developmentIps.includes(clientIp)) {
    return next();
  }

  // Проверяем IP в whitelist
  const isAllowed = telegramIpRanges.some((range) => clientIp.startsWith(range));

  if (!isAllowed) {
    logger.warn('Получен webhook запрос с неизвестного IP адреса', {
      ip: clientIp,
      userAgent: req.headers['user-agent'],
      path: req.path,
    });

    return res.status(403).json({
      error: 'Forbidden',
      message: 'IP not whitelisted',
    });
  }

  next();
}

/**
 * Комбинированный middleware: проверяет и секрет, и IP
 * Используйте этот middleware для максимальной защиты webhook
 */
export function webhookSecurityMiddleware(
  req: Request,
  res: Response,
  next: NextFunction
): void {
  // Сначала проверяем секрет (основная защита)
  webhookSecretMiddleware(req, res, (secretError) => {
    if (secretError) {
      return next(secretError);
    }

    // Затем проверяем IP (дополнительная защита)
    webhookIpWhitelistMiddleware(req, res, next);
  });
}

/**
 * Helper для установки webhook с секретом
 *
 * Использование:
 * await setupSecureWebhook(bot, 'https://your-domain.com/webhook');
 */
export async function setupSecureWebhook(
  bot: any,
  webhookUrl: string
): Promise<void> {
  const config = getEnvConfig();

  const options: any = {
    url: webhookUrl,
    drop_pending_updates: true,
    allowed_updates: [
      'message',
      'callback_query',
      'inline_query',
      'chosen_inline_result',
    ],
  };

  // Добавляем секрет, если настроен
  if (config.TELEGRAM_WEBHOOK_SECRET) {
    options.secret_token = config.TELEGRAM_WEBHOOK_SECRET;
    logger.info('Устанавливаем webhook с секретом для защиты');
  } else {
    logger.warn(
      'TELEGRAM_WEBHOOK_SECRET не настроен - webhook будет без дополнительной защиты'
    );
  }

  try {
    await bot.telegram.setWebhook(options.url, {
      drop_pending_updates: options.drop_pending_updates,
      allowed_updates: options.allowed_updates,
      secret_token: options.secret_token,
    });

    logger.info(`✅ Webhook установлен: ${webhookUrl}`);
  } catch (error) {
    logger.error('❌ Ошибка установки webhook:', error);
    throw error;
  }
}
