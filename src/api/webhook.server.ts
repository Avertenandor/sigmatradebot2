/**
 * Telegram Webhook Server
 * Handles incoming webhook requests from Telegram in production
 */

import express from 'express';
import { Telegraf } from 'telegraf';
import { logger } from '../utils/logger.util';
import { webhookSecretMiddleware } from '../bot/middleware/webhook-secret.middleware';

/**
 * Создать и запустить webhook сервер для Telegram
 *
 * CRITICAL для production:
 * - Trust proxy для правильного определения IP за GCP LB
 * - Webhook secret validation для защиты от поддельных запросов
 * - Rate limiting на уровне middleware
 * - Body size limit для защиты от DoS
 */
export async function startWebhookServer(
  bot: Telegraf,
  port: number,
  webhookPath: string = '/telegram/webhook'
): Promise<express.Application> {
  const app = express();

  // CRITICAL: Trust proxy for GCP Load Balancer / Cloud Run
  // Without this, req.ip will be internal LB IP (10.x.x.x), not real client IP
  // This is required for:
  // - Correct IP-based rate limiting
  // - Accurate logging of client IPs
  // - IP whitelist validation (if used)
  app.set('trust proxy', true);

  logger.info('🔒 Trust proxy enabled for GCP Load Balancer');

  // Body parser for JSON (Telegram sends JSON)
  // Limit body size to prevent DoS attacks
  app.use(express.json({ limit: '256kb' }));

  // Health check endpoint (lightweight, no auth needed)
  app.get('/health', (req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
  });

  // Telegram webhook endpoint
  // Order matters: middleware runs before handler
  app.post(
    webhookPath,
    webhookSecretMiddleware,  // Validates X-Telegram-Bot-Api-Secret-Token
    bot.webhookCallback(webhookPath)  // Telegraf handles the update
  );

  // 404 handler for unknown routes
  app.use((req, res) => {
    logger.warn('Unknown route accessed', {
      method: req.method,
      path: req.path,
      ip: req.ip,
      userAgent: req.get('user-agent'),
    });
    res.status(404).json({ error: 'Not Found' });
  });

  // Error handler
  app.use((err: Error, req: express.Request, res: express.Response, next: express.NextFunction) => {
    logger.error('Webhook server error', {
      error: err.message,
      stack: err.stack,
      method: req.method,
      path: req.path,
      ip: req.ip,
    });

    res.status(500).json({
      error: 'Internal Server Error',
      message: process.env.NODE_ENV === 'production' ? undefined : err.message,
    });
  });

  // Start server
  const server = app.listen(port, () => {
    logger.info(`🚀 Telegram webhook server listening on port ${port}`);
    logger.info(`📥 Webhook endpoint: POST ${webhookPath}`);
    logger.info(`🔒 Webhook secret validation: enabled`);
    logger.info(`🌐 Trust proxy: enabled (GCP-ready)`);
  });

  // Graceful shutdown
  const shutdown = async () => {
    logger.info('Shutting down webhook server...');
    server.close(() => {
      logger.info('Webhook server closed');
    });
  };

  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);

  return app;
}

/**
 * Конфигурация для Cloud Run / GCP deployment
 *
 * Example environment variables:
 * - PORT=8080  (Cloud Run automatically sets this)
 * - TELEGRAM_WEBHOOK_SECRET=<your-secret>
 * - TELEGRAM_WEBHOOK_URL=https://your-app.run.app/telegram/webhook
 */
export function getWebhookConfig() {
  const port = parseInt(process.env.PORT || process.env.WEBHOOK_PORT || '8080', 10);
  const path = process.env.WEBHOOK_PATH || '/telegram/webhook';
  const url = process.env.TELEGRAM_WEBHOOK_URL;

  if (!url) {
    throw new Error('TELEGRAM_WEBHOOK_URL is required for webhook mode');
  }

  return {
    port,
    path,
    url,
  };
}
