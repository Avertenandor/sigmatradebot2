/**
 * Transaction Utility
 *
 * Provides robust transaction handling with:
 * - Automatic retry on deadlock/serialization failures
 * - Exponential backoff for retries
 * - Configurable isolation levels
 * - Timeout protection
 * - Detailed logging and monitoring
 * - Request ID tracking integration
 *
 * Usage:
 * ```typescript
 * await withTransaction(async (manager) => {
 *   const user = await manager.findOne(User, { where: { id: userId } });
 *   user.balance += amount;
 *   await manager.save(user);
 *   return user;
 * }, {
 *   isolationLevel: 'SERIALIZABLE',
 *   maxRetries: 5,
 *   timeout: 30000
 * });
 * ```
 */

import { EntityManager, QueryRunner, IsolationLevel } from 'typeorm';
import { AppDataSource } from './data-source';
import { createLogger } from '../utils/logger.util';
import { measurePerformance, getRequestId } from '../utils/audit-logger.util';

const logger = createLogger('Transaction');

/**
 * Transaction options
 */
export interface TransactionOptions {
  /** Maximum number of retry attempts on transient failures (default: 3) */
  maxRetries?: number;

  /** Transaction timeout in milliseconds (default: 30000 = 30s) */
  timeout?: number;

  /** Database isolation level (default: READ COMMITTED) */
  isolationLevel?: IsolationLevel;

  /** Enable detailed logging for debugging (default: false) */
  enableDebugLogging?: boolean;

  /** Custom retry delay function (ms). Default: exponential backoff */
  retryDelayMs?: (attempt: number) => number;
}

/**
 * Transaction operation result
 */
export interface TransactionResult<T> {
  /** Operation result data */
  data: T;

  /** Number of attempts made */
  attempts: number;

  /** Total execution time in milliseconds */
  duration: number;

  /** Whether any retries occurred */
  hadRetries: boolean;
}

/**
 * Transaction error codes that should trigger retry
 */
const RETRIABLE_ERROR_CODES = new Set([
  '40001', // serialization_failure
  '40P01', // deadlock_detected
  '55P03', // lock_not_available
  '08003', // connection_does_not_exist
  '08006', // connection_failure
  '08001', // sqlclient_unable_to_establish_sqlconnection
  '08004', // sqlserver_rejected_establishment_of_sqlconnection
]);

/**
 * Check if error is retriable (deadlock, serialization failure, etc.)
 */
export function isRetriableError(error: any): boolean {
  if (!error) return false;

  // PostgreSQL error code
  if (error.code && RETRIABLE_ERROR_CODES.has(error.code)) {
    return true;
  }

  // Check error message for common patterns
  const message = (error.message || '').toLowerCase();
  const retriablePatterns = [
    'deadlock',
    'serialization failure',
    'could not serialize',
    'lock timeout',
    'connection',
    'econnrefused',
    'etimedout',
  ];

  return retriablePatterns.some(pattern => message.includes(pattern));
}

/**
 * Default exponential backoff with jitter
 */
function defaultRetryDelay(attempt: number): number {
  // Base: 100ms, 200ms, 400ms, 800ms, 1600ms
  const baseDelay = Math.pow(2, attempt) * 100;

  // Add jitter (random 0-25% of base delay) to prevent thundering herd
  const jitter = Math.random() * baseDelay * 0.25;

  return Math.min(baseDelay + jitter, 5000); // Cap at 5 seconds
}

/**
 * Delay execution for specified milliseconds
 */
function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Execute operation within a database transaction with automatic retry on transient failures
 *
 * Features:
 * - Automatic retry on deadlock/serialization errors
 * - Exponential backoff with jitter
 * - Configurable isolation levels
 * - Timeout protection
 * - Detailed logging
 * - Request ID tracking
 *
 * @param operation - Function to execute within transaction
 * @param options - Transaction configuration options
 * @returns Promise with operation result and metadata
 *
 * @example
 * ```typescript
 * const result = await withTransaction(async (manager) => {
 *   // Use manager for all database operations
 *   const user = await manager.findOne(User, { where: { id: 1 } });
 *   if (!user) throw new Error('User not found');
 *
 *   user.balance += 100;
 *   await manager.save(user);
 *
 *   return user;
 * }, {
 *   isolationLevel: 'REPEATABLE READ',
 *   maxRetries: 5
 * });
 *
 * console.log(`User updated after ${result.attempts} attempts`);
 * ```
 */
export async function withTransaction<T>(
  operation: (manager: EntityManager) => Promise<T>,
  options: TransactionOptions = {}
): Promise<TransactionResult<T>> {
  const {
    maxRetries = 3,
    timeout = 30000,
    isolationLevel = 'READ COMMITTED',
    enableDebugLogging = false,
    retryDelayMs = defaultRetryDelay,
  } = options;

  const requestId = getRequestId();
  const startTime = Date.now();
  let attempt = 0;
  let lastError: Error | null = null;

  if (enableDebugLogging) {
    logger.debug('Starting transaction', {
      requestId,
      isolationLevel,
      maxRetries,
      timeout,
    });
  }

  while (attempt < maxRetries) {
    attempt++;

    const attemptStart = Date.now();

    try {
      // Execute operation with performance tracking
      const data = await measurePerformance(
        'database_transaction',
        'database_query',
        async () => {
          return await executeWithTimeout(
            AppDataSource.transaction(isolationLevel, async (manager) => {
              return await operation(manager);
            }),
            timeout
          );
        }
      );

      const duration = Date.now() - startTime;
      const hadRetries = attempt > 1;

      if (hadRetries) {
        logger.info('Transaction succeeded after retries', {
          requestId,
          attempts: attempt,
          duration,
          isolationLevel,
        });
      } else if (enableDebugLogging) {
        logger.debug('Transaction succeeded on first attempt', {
          requestId,
          duration,
        });
      }

      return {
        data,
        attempts: attempt,
        duration,
        hadRetries,
      };

    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
      const attemptDuration = Date.now() - attemptStart;

      // Check if error is retriable
      const isRetriable = isRetriableError(error);
      const canRetry = attempt < maxRetries;

      if (isRetriable && canRetry) {
        const delayMs = retryDelayMs(attempt);

        logger.warn('Transaction failed with retriable error, will retry', {
          requestId,
          attempt,
          maxRetries,
          error: lastError.message,
          errorCode: (error as any).code,
          attemptDuration,
          nextRetryIn: delayMs,
          isolationLevel,
        });

        // Wait before retry (exponential backoff)
        await delay(delayMs);

        continue;
      } else {
        // Non-retriable error or max retries reached
        const errorType = isRetriable ? 'max retries reached' : 'non-retriable error';

        logger.error('Transaction failed permanently', {
          requestId,
          attempts: attempt,
          errorType,
          error: lastError.message,
          errorCode: (error as any).code,
          stack: lastError.stack,
          duration: Date.now() - startTime,
          isolationLevel,
        });

        throw lastError;
      }
    }
  }

  // Should never reach here, but TypeScript needs it
  throw lastError || new Error('Transaction failed after max retries');
}

/**
 * Execute operation with timeout
 */
async function executeWithTimeout<T>(
  promise: Promise<T>,
  timeoutMs: number
): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) =>
      setTimeout(
        () => reject(new Error(`Transaction timeout after ${timeoutMs}ms`)),
        timeoutMs
      )
    ),
  ]);
}

/**
 * Execute multiple operations in a single transaction
 * Useful for batch operations that must all succeed or fail together
 *
 * @param operations - Array of operations to execute
 * @param options - Transaction options
 * @returns Array of results in the same order as operations
 *
 * @example
 * ```typescript
 * const results = await withBatchTransaction([
 *   async (manager) => manager.save(User, user1),
 *   async (manager) => manager.save(User, user2),
 *   async (manager) => manager.save(Deposit, deposit),
 * ]);
 * ```
 */
export async function withBatchTransaction<T extends any[]>(
  operations: Array<(manager: EntityManager) => Promise<any>>,
  options: TransactionOptions = {}
): Promise<{ data: T; attempts: number; duration: number; hadRetries: boolean }> {
  return withTransaction(async (manager) => {
    const results: any[] = [];

    for (const operation of operations) {
      const result = await operation(manager);
      results.push(result);
    }

    return results as T;
  }, options);
}

/**
 * Create a transaction runner for more fine-grained control
 * Use when you need to control when to commit/rollback manually
 *
 * @returns Query runner with helper methods
 *
 * @example
 * ```typescript
 * const runner = createTransactionRunner();
 * try {
 *   await runner.startTransaction('SERIALIZABLE');
 *
 *   const user = await runner.manager.findOne(User, { where: { id: 1 } });
 *   user.balance += 100;
 *   await runner.manager.save(user);
 *
 *   await runner.commitTransaction();
 * } catch (error) {
 *   await runner.rollbackTransaction();
 *   throw error;
 * } finally {
 *   await runner.release();
 * }
 * ```
 */
export function createTransactionRunner(): QueryRunner {
  return AppDataSource.createQueryRunner();
}

/**
 * Wrap a function to automatically run it in a transaction
 * Useful for service methods that should always run in a transaction
 *
 * @param fn - Function to wrap
 * @param options - Default transaction options
 * @returns Wrapped function
 *
 * @example
 * ```typescript
 * class UserService {
 *   // This method will always run in a transaction
 *   updateBalance = transactional(async (userId: number, amount: number, manager: EntityManager) => {
 *     const user = await manager.findOne(User, { where: { id: userId } });
 *     if (!user) throw new Error('User not found');
 *
 *     user.balance += amount;
 *     return await manager.save(user);
 *   }, { isolationLevel: 'REPEATABLE READ' });
 * }
 * ```
 */
export function transactional<Args extends any[], Result>(
  fn: (manager: EntityManager, ...args: Args) => Promise<Result>,
  options: TransactionOptions = {}
): (...args: Args) => Promise<TransactionResult<Result>> {
  return async (...args: Args) => {
    return withTransaction(
      async (manager) => fn(manager, ...args),
      options
    );
  };
}

/**
 * Retry configuration for specific operation types
 */
export const TRANSACTION_PRESETS = {
  /** Default settings for most operations */
  DEFAULT: {
    maxRetries: 3,
    timeout: 30000,
    isolationLevel: 'READ COMMITTED' as IsolationLevel,
  },

  /** Settings for financial operations (deposits, withdrawals, payments) */
  FINANCIAL: {
    maxRetries: 5,
    timeout: 60000,
    isolationLevel: 'REPEATABLE READ' as IsolationLevel,
  },

  /** Settings for critical operations requiring highest consistency */
  CRITICAL: {
    maxRetries: 10,
    timeout: 120000,
    isolationLevel: 'SERIALIZABLE' as IsolationLevel,
  },

  /** Settings for read-only operations */
  READ_ONLY: {
    maxRetries: 2,
    timeout: 10000,
    isolationLevel: 'READ COMMITTED' as IsolationLevel,
  },

  /** Settings for bulk operations */
  BULK: {
    maxRetries: 3,
    timeout: 300000, // 5 minutes
    isolationLevel: 'READ COMMITTED' as IsolationLevel,
  },
} as const;

/**
 * Transaction statistics collector
 * Useful for monitoring and debugging
 */
export class TransactionStats {
  private static stats = {
    total: 0,
    successful: 0,
    failed: 0,
    retried: 0,
    totalDuration: 0,
    totalAttempts: 0,
  };

  static recordSuccess(attempts: number, duration: number): void {
    this.stats.total++;
    this.stats.successful++;
    this.stats.totalDuration += duration;
    this.stats.totalAttempts += attempts;

    if (attempts > 1) {
      this.stats.retried++;
    }
  }

  static recordFailure(): void {
    this.stats.total++;
    this.stats.failed++;
  }

  static getStats() {
    const { total, successful, failed, retried, totalDuration, totalAttempts } = this.stats;

    return {
      total,
      successful,
      failed,
      retried,
      successRate: total > 0 ? (successful / total) * 100 : 0,
      retryRate: total > 0 ? (retried / total) * 100 : 0,
      avgDuration: successful > 0 ? totalDuration / successful : 0,
      avgAttemptsPerTransaction: successful > 0 ? totalAttempts / successful : 0,
    };
  }

  static reset(): void {
    this.stats = {
      total: 0,
      successful: 0,
      failed: 0,
      retried: 0,
      totalDuration: 0,
      totalAttempts: 0,
    };
  }
}

// Export types
export type { IsolationLevel };
