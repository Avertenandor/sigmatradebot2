import Bottleneck from 'bottleneck';
import { ethers } from 'ethers';
import { logger } from '../utils/logger.util';
import { getEnvConfig } from '../config/env.validator';

/**
 * RPC Rate Limiter для QuickNode
 *
 * Защищает от превышения лимитов QuickNode API:
 * - $49/месяц план: ~300 requests/second
 * - Оптимизирует расход через батчинг и кеширование
 * - Автоматический retry с exponential backoff
 */

/**
 * Конфигурация rate limiting для QuickNode
 */
interface RateLimitConfig {
  // Максимум одновременных запросов
  maxConcurrent: number;

  // Минимальное время между запросами (ms)
  minTime: number;

  // Максимум запросов в резервуаре (burst capacity)
  reservoir: number;

  // Скорость восстановления резервуара (requests per interval)
  reservoirRefreshAmount: number;

  // Интервал восстановления резервуара (ms)
  reservoirRefreshInterval: number;
}

/**
 * Предустановленные конфигурации для разных планов QuickNode
 */
export const QUICKNODE_PLANS: Record<string, RateLimitConfig> = {
  // Free tier: ~25 req/sec
  free: {
    maxConcurrent: 5,
    minTime: 40, // 25 req/sec
    reservoir: 100,
    reservoirRefreshAmount: 25,
    reservoirRefreshInterval: 1000,
  },

  // $49/month: ~300 req/sec
  build: {
    maxConcurrent: 20,
    minTime: 10, // 100 req/sec (консервативно)
    reservoir: 500,
    reservoirRefreshAmount: 100,
    reservoirRefreshInterval: 1000,
  },

  // $299/month: ~1000 req/sec
  scale: {
    maxConcurrent: 50,
    minTime: 5, // 200 req/sec (консервативно)
    reservoir: 1000,
    reservoirRefreshAmount: 200,
    reservoirRefreshInterval: 1000,
  },

  // Custom plan
  custom: {
    maxConcurrent: 10,
    minTime: 20,
    reservoir: 200,
    reservoirRefreshAmount: 50,
    reservoirRefreshInterval: 1000,
  },
};

/**
 * RPC Rate Limiter класс
 */
export class RPCRateLimiter {
  private limiter: Bottleneck;
  private provider: ethers.JsonRpcProvider;
  private wsProvider?: ethers.WebSocketProvider;
  private config: RateLimitConfig;

  // Метрики
  private stats = {
    totalRequests: 0,
    successfulRequests: 0,
    failedRequests: 0,
    retriedRequests: 0,
    averageLatency: 0,
    lastError: null as Error | null,
  };

  constructor(plan: keyof typeof QUICKNODE_PLANS = 'build') {
    this.config = QUICKNODE_PLANS[plan];

    // Создаём Bottleneck limiter
    this.limiter = new Bottleneck({
      maxConcurrent: this.config.maxConcurrent,
      minTime: this.config.minTime,
      reservoir: this.config.reservoir,
      reservoirRefreshAmount: this.config.reservoirRefreshAmount,
      reservoirRefreshInterval: this.config.reservoirRefreshInterval,

      // Retry стратегия
      retryOptions: {
        maxRetries: 3,
        minDelay: 1000,
        maxDelay: 10000,
        factor: 2,
      },
    });

    // Event listeners для мониторинга
    this.setupEventListeners();

    // Инициализация providers
    const envConfig = getEnvConfig();
    this.provider = new ethers.JsonRpcProvider(envConfig.QUICKNODE_HTTPS_URL);

    if (envConfig.QUICKNODE_WSS_URL) {
      this.wsProvider = new ethers.WebSocketProvider(envConfig.QUICKNODE_WSS_URL);
    }

    logger.info(`RPC Rate Limiter initialized with plan: ${plan}`, {
      maxConcurrent: this.config.maxConcurrent,
      minTime: this.config.minTime,
    });
  }

  /**
   * Настройка event listeners для метрик
   */
  private setupEventListeners(): void {
    this.limiter.on('failed', (error, jobInfo) => {
      this.stats.failedRequests++;
      this.stats.lastError = error;

      logger.warn('RPC request failed', {
        error: error.message,
        retryCount: jobInfo.retryCount,
      });
    });

    this.limiter.on('retry', (error, jobInfo) => {
      this.stats.retriedRequests++;

      logger.info('Retrying RPC request', {
        error: error.message,
        retryCount: jobInfo.retryCount,
      });
    });

    this.limiter.on('done', (info) => {
      this.stats.successfulRequests++;

      // Обновляем среднюю latency
      const latency = Date.now() - info.options.startTime;
      this.stats.averageLatency =
        (this.stats.averageLatency * (this.stats.successfulRequests - 1) + latency) /
        this.stats.successfulRequests;
    });
  }

  /**
   * Обёртка для rate-limited RPC вызовов
   */
  private async rateLimited<T>(fn: () => Promise<T>): Promise<T> {
    this.stats.totalRequests++;

    return this.limiter.schedule({ startTime: Date.now() }, fn);
  }

  // ==================== Provider Methods ====================

  /**
   * Получить текущий номер блока
   */
  async getBlockNumber(): Promise<number> {
    return this.rateLimited(() => this.provider.getBlockNumber());
  }

  /**
   * Получить блок по номеру или хешу
   */
  async getBlock(
    blockHashOrNumber: string | number,
    prefetchTxs?: boolean
  ): Promise<ethers.Block | null> {
    return this.rateLimited(() => this.provider.getBlock(blockHashOrNumber, prefetchTxs));
  }

  /**
   * Получить транзакцию по хешу
   */
  async getTransaction(txHash: string): Promise<ethers.TransactionResponse | null> {
    return this.rateLimited(() => this.provider.getTransaction(txHash));
  }

  /**
   * Получить receipt транзакции
   */
  async getTransactionReceipt(txHash: string): Promise<ethers.TransactionReceipt | null> {
    return this.rateLimited(() => this.provider.getTransactionReceipt(txHash));
  }

  /**
   * Получить баланс адреса
   */
  async getBalance(address: string, blockTag?: string | number): Promise<bigint> {
    return this.rateLimited(() => this.provider.getBalance(address, blockTag));
  }

  /**
   * Вызвать read-only метод контракта
   */
  async call(transaction: ethers.TransactionRequest): Promise<string> {
    return this.rateLimited(() => this.provider.call(transaction));
  }

  /**
   * Отправить транзакцию
   */
  async sendTransaction(signedTx: string): Promise<ethers.TransactionResponse> {
    return this.rateLimited(() => this.provider.broadcastTransaction(signedTx));
  }

  /**
   * Получить логи (events)
   */
  async getLogs(filter: ethers.Filter): Promise<ethers.Log[]> {
    return this.rateLimited(() => this.provider.getLogs(filter));
  }

  /**
   * Батч запрос нескольких getLogs (оптимизация)
   */
  async getBatchLogs(filters: ethers.Filter[]): Promise<ethers.Log[][]> {
    // Обрабатываем батчами по 5 запросов
    const BATCH_SIZE = 5;
    const results: ethers.Log[][] = [];

    for (let i = 0; i < filters.length; i += BATCH_SIZE) {
      const batch = filters.slice(i, i + BATCH_SIZE);

      // Параллельно выполняем батч через rate limiter
      const batchResults = await Promise.all(batch.map((filter) => this.getLogs(filter)));

      results.push(...batchResults);
    }

    return results;
  }

  /**
   * Оценить gas для транзакции
   */
  async estimateGas(transaction: ethers.TransactionRequest): Promise<bigint> {
    return this.rateLimited(() => this.provider.estimateGas(transaction));
  }

  /**
   * Получить gas price
   */
  async getFeeData(): Promise<ethers.FeeData> {
    return this.rateLimited(() => this.provider.getFeeData());
  }

  // ==================== WebSocket Methods ====================

  /**
   * Подписаться на новые блоки (через WebSocket)
   * Не проходит через rate limiter (WebSocket - отдельный лимит)
   */
  onBlock(callback: (blockNumber: number) => void): void {
    if (!this.wsProvider) {
      logger.warn('WebSocket provider not configured, falling back to polling');
      // Fallback to polling
      this.provider.on('block', callback);
      return;
    }

    this.wsProvider.on('block', callback);
  }

  /**
   * Подписаться на события контракта (через WebSocket)
   */
  onLogs(filter: ethers.Filter, callback: (log: ethers.Log) => void): void {
    if (!this.wsProvider) {
      logger.warn('WebSocket provider not configured');
      return;
    }

    this.wsProvider.on(filter, callback);
  }

  // ==================== Metrics & Management ====================

  /**
   * Получить статистику использования
   */
  getStats() {
    return {
      ...this.stats,
      queueSize: this.limiter.counts().QUEUED,
      runningJobs: this.limiter.counts().RUNNING,
      successRate:
        this.stats.totalRequests > 0
          ? (this.stats.successfulRequests / this.stats.totalRequests) * 100
          : 0,
    };
  }

  /**
   * Очистить очередь (для экстренных случаев)
   */
  async clearQueue(): Promise<void> {
    await this.limiter.stop({ dropWaitingJobs: true });
    logger.warn('RPC queue cleared');
  }

  /**
   * Получить raw provider (для прямого доступа без rate limiting)
   * ВНИМАНИЕ: Используйте осторожно!
   */
  getRawProvider(): ethers.JsonRpcProvider {
    logger.warn('Getting raw provider - rate limiting bypassed!');
    return this.provider;
  }

  /**
   * Закрыть соединения
   */
  async disconnect(): Promise<void> {
    await this.limiter.stop();

    if (this.wsProvider) {
      await this.wsProvider.destroy();
    }

    logger.info('RPC Rate Limiter disconnected');
  }
}

/**
 * Singleton instance
 */
let rateLimiterInstance: RPCRateLimiter | null = null;

/**
 * Получить глобальный инстанс rate limiter
 */
export function getRPCRateLimiter(
  plan: keyof typeof QUICKNODE_PLANS = 'build'
): RPCRateLimiter {
  if (!rateLimiterInstance) {
    rateLimiterInstance = new RPCRateLimiter(plan);
  }

  return rateLimiterInstance;
}

/**
 * Закрыть глобальный инстанс
 */
export async function disconnectRPCRateLimiter(): Promise<void> {
  if (rateLimiterInstance) {
    await rateLimiterInstance.disconnect();
    rateLimiterInstance = null;
  }
}
