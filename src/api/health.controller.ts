import express, { Request, Response } from 'express';
import { DataSource } from 'typeorm';
import Redis from 'ioredis';
import { logger } from '../utils/logger.util';
import { getEnvConfig } from '../config/env.validator';

export interface HealthCheckResult {
  status: 'ok' | 'degraded' | 'down';
  message?: string;
  responseTime?: number;
  details?: any;
}

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  uptime: number;
  checks: {
    database: HealthCheckResult;
    redis: HealthCheckResult;
    bot: HealthCheckResult;
    blockchain?: HealthCheckResult;
  };
  version?: string;
  environment?: string;
}

/**
 * Health Check Controller
 * Предоставляет эндпоинты для проверки здоровья приложения
 */
export class HealthController {
  private dataSource: DataSource;
  private redis: Redis;
  private bot: any;
  private startTime: number;

  constructor(dataSource: DataSource, redis: Redis, bot?: any) {
    this.dataSource = dataSource;
    this.redis = redis;
    this.bot = bot;
    this.startTime = Date.now();
  }

  /**
   * Проверка подключения к базе данных
   */
  async checkDatabase(): Promise<HealthCheckResult> {
    const start = Date.now();

    try {
      // Простой query для проверки подключения
      await this.dataSource.query('SELECT 1');

      const responseTime = Date.now() - start;

      return {
        status: responseTime < 100 ? 'ok' : 'degraded',
        message:
          responseTime < 100
            ? 'Database connection healthy'
            : 'Database responding slowly',
        responseTime,
      };
    } catch (error) {
      logger.error('Database health check failed:', error);

      return {
        status: 'down',
        message: 'Database connection failed',
        responseTime: Date.now() - start,
        details: {
          error: error instanceof Error ? error.message : String(error),
        },
      };
    }
  }

  /**
   * Проверка подключения к Redis
   */
  async checkRedis(): Promise<HealthCheckResult> {
    const start = Date.now();

    try {
      // PING команда для проверки подключения
      const result = await this.redis.ping();

      const responseTime = Date.now() - start;

      if (result !== 'PONG') {
        return {
          status: 'down',
          message: 'Redis not responding correctly',
          responseTime,
        };
      }

      return {
        status: responseTime < 50 ? 'ok' : 'degraded',
        message:
          responseTime < 50 ? 'Redis connection healthy' : 'Redis responding slowly',
        responseTime,
      };
    } catch (error) {
      logger.error('Redis health check failed:', error);

      return {
        status: 'down',
        message: 'Redis connection failed',
        responseTime: Date.now() - start,
        details: {
          error: error instanceof Error ? error.message : String(error),
        },
      };
    }
  }

  /**
   * Проверка Telegram Bot API
   */
  async checkBot(): Promise<HealthCheckResult> {
    const start = Date.now();

    if (!this.bot) {
      return {
        status: 'down',
        message: 'Bot not initialized',
        responseTime: 0,
      };
    }

    try {
      // Получаем информацию о боте через API
      const botInfo = await this.bot.telegram.getMe();

      const responseTime = Date.now() - start;

      return {
        status: responseTime < 500 ? 'ok' : 'degraded',
        message:
          responseTime < 500
            ? 'Bot API connection healthy'
            : 'Bot API responding slowly',
        responseTime,
        details: {
          username: botInfo.username,
          id: botInfo.id,
        },
      };
    } catch (error) {
      logger.error('Bot health check failed:', error);

      return {
        status: 'down',
        message: 'Bot API connection failed',
        responseTime: Date.now() - start,
        details: {
          error: error instanceof Error ? error.message : String(error),
        },
      };
    }
  }

  /**
   * Проверка подключения к блокчейн ноде (опционально)
   */
  async checkBlockchain(): Promise<HealthCheckResult> {
    const start = Date.now();

    try {
      const config = getEnvConfig();
      const { ethers } = await import('ethers');
      const provider = new ethers.JsonRpcProvider(config.QUICKNODE_HTTPS_URL);

      // Получаем текущий номер блока
      const blockNumber = await provider.getBlockNumber();

      const responseTime = Date.now() - start;

      return {
        status: responseTime < 1000 ? 'ok' : 'degraded',
        message:
          responseTime < 1000
            ? 'Blockchain connection healthy'
            : 'Blockchain responding slowly',
        responseTime,
        details: {
          currentBlock: blockNumber,
        },
      };
    } catch (error) {
      logger.error('Blockchain health check failed:', error);

      return {
        status: 'down',
        message: 'Blockchain connection failed',
        responseTime: Date.now() - start,
        details: {
          error: error instanceof Error ? error.message : String(error),
        },
      };
    }
  }

  /**
   * Выполнить все проверки здоровья
   */
  async performHealthCheck(includeBlockchain: boolean = false): Promise<HealthStatus> {
    const checks = {
      database: await this.checkDatabase(),
      redis: await this.checkRedis(),
      bot: await this.checkBot(),
      ...(includeBlockchain && { blockchain: await this.checkBlockchain() }),
    };

    // Определяем общий статус
    const allChecks = Object.values(checks);
    const hasDown = allChecks.some((check) => check.status === 'down');
    const hasDegraded = allChecks.some((check) => check.status === 'degraded');

    let overallStatus: 'healthy' | 'degraded' | 'unhealthy';
    if (hasDown) {
      overallStatus = 'unhealthy';
    } else if (hasDegraded) {
      overallStatus = 'degraded';
    } else {
      overallStatus = 'healthy';
    }

    const config = getEnvConfig();

    return {
      status: overallStatus,
      timestamp: new Date().toISOString(),
      uptime: Math.floor((Date.now() - this.startTime) / 1000), // seconds
      checks,
      version: process.env.npm_package_version || '1.0.0',
      environment: config.NODE_ENV,
    };
  }

  /**
   * Простой liveness probe (просто проверяет, что процесс жив)
   */
  async liveness(req: Request, res: Response): Promise<void> {
    res.status(200).json({
      status: 'alive',
      timestamp: new Date().toISOString(),
    });
  }

  /**
   * Readiness probe (проверяет, что приложение готово принимать трафик)
   */
  async readiness(req: Request, res: Response): Promise<void> {
    try {
      // Проверяем только критичные зависимости
      const dbCheck = await this.checkDatabase();
      const redisCheck = await this.checkRedis();

      const ready = dbCheck.status !== 'down' && redisCheck.status !== 'down';

      if (ready) {
        res.status(200).json({
          status: 'ready',
          timestamp: new Date().toISOString(),
        });
      } else {
        res.status(503).json({
          status: 'not_ready',
          timestamp: new Date().toISOString(),
          checks: {
            database: dbCheck,
            redis: redisCheck,
          },
        });
      }
    } catch (error) {
      logger.error('Readiness check failed:', error);
      res.status(503).json({
        status: 'error',
        message: 'Readiness check failed',
        timestamp: new Date().toISOString(),
      });
    }
  }

  /**
   * Полный health check endpoint
   */
  async health(req: Request, res: Response): Promise<void> {
    try {
      const includeBlockchain = req.query.blockchain === 'true';
      const health = await this.performHealthCheck(includeBlockchain);

      // HTTP статус код зависит от общего статуса
      const statusCode = health.status === 'healthy' ? 200 : health.status === 'degraded' ? 200 : 503;

      res.status(statusCode).json(health);
    } catch (error) {
      logger.error('Health check failed:', error);
      res.status(500).json({
        status: 'unhealthy',
        timestamp: new Date().toISOString(),
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }
}

/**
 * Создать Express router с health check эндпоинтами
 */
export function createHealthRouter(
  dataSource: DataSource,
  redis: Redis,
  bot?: any
): express.Router {
  const router = express.Router();
  const controller = new HealthController(dataSource, redis, bot);

  // Kubernetes-style health checks
  router.get('/livez', controller.liveness.bind(controller));
  router.get('/readyz', controller.readiness.bind(controller));

  // Полная проверка здоровья
  router.get('/healthz', controller.health.bind(controller));
  router.get('/health', controller.health.bind(controller)); // Альтернативный путь

  return router;
}

/**
 * Запустить standalone health check сервер
 * Используется для отделения health checks от основного приложения
 */
export async function startHealthCheckServer(
  port: number,
  dataSource: DataSource,
  redis: Redis,
  bot?: any
): Promise<express.Application> {
  const app = express();

  // CRITICAL: Trust proxy for GCP Load Balancer
  // Without this, req.ip will show internal LB IP (10.x.x.x), not client IP
  app.set('trust proxy', true);

  const healthRouter = createHealthRouter(dataSource, redis, bot);

  app.use(healthRouter);

  // Простой корневой endpoint
  app.get('/', (req, res) => {
    res.json({
      name: 'SigmaTrade Bot Health Check',
      version: process.env.npm_package_version || '1.0.0',
      endpoints: ['/livez', '/readyz', '/healthz', '/health'],
    });
  });

  app.listen(port, () => {
    logger.info(`🏥 Health check server listening on port ${port}`);
  });

  return app;
}
