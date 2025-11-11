/**
 * Unit Tests for Transaction Utility
 * Tests retry logic, error handling, and transaction features
 */

import {
  withTransaction,
  isRetriableError,
  TransactionOptions,
  TransactionResult,
  TRANSACTION_PRESETS,
  withBatchTransaction,
  TransactionStats,
} from '../../src/database/transaction.util';

// Mock dependencies
jest.mock('../../src/database/data-source', () => ({
  AppDataSource: {
    transaction: jest.fn(),
    createQueryRunner: jest.fn(),
  },
}));

jest.mock('../../src/utils/logger.util', () => ({
  createLogger: jest.fn(() => ({
    debug: jest.fn(),
    info: jest.fn(),
    warn: jest.fn(),
    error: jest.fn(),
  })),
}));

jest.mock('../../src/utils/audit-logger.util', () => ({
  measurePerformance: jest.fn(async (name, category, fn) => await fn()),
  getRequestId: jest.fn(() => 'test-request-id'),
}));

import { AppDataSource } from '../../src/database/data-source';

describe('Transaction Utility', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    TransactionStats.reset();
  });

  describe('isRetriableError', () => {
    it('should identify deadlock error as retriable', () => {
      const error = {
        code: '40P01', // deadlock_detected
        message: 'deadlock detected',
      };

      expect(isRetriableError(error)).toBe(true);
    });

    it('should identify serialization failure as retriable', () => {
      const error = {
        code: '40001', // serialization_failure
        message: 'could not serialize access',
      };

      expect(isRetriableError(error)).toBe(true);
    });

    it('should identify lock timeout as retriable', () => {
      const error = {
        code: '55P03', // lock_not_available
        message: 'lock timeout',
      };

      expect(isRetriableError(error)).toBe(true);
    });

    it('should identify connection errors as retriable', () => {
      const errors = [
        { code: '08003', message: 'connection does not exist' },
        { code: '08006', message: 'connection failure' },
        { message: 'ECONNREFUSED' },
        { message: 'ETIMEDOUT' },
      ];

      errors.forEach(error => {
        expect(isRetriableError(error)).toBe(true);
      });
    });

    it('should identify non-retriable errors', () => {
      const errors = [
        { code: '23505', message: 'duplicate key value' }, // unique violation
        { code: '23503', message: 'foreign key violation' },
        { message: 'invalid input syntax' },
        { message: 'division by zero' },
      ];

      errors.forEach(error => {
        expect(isRetriableError(error)).toBe(false);
      });
    });

    it('should handle null/undefined errors', () => {
      expect(isRetriableError(null)).toBe(false);
      expect(isRetriableError(undefined)).toBe(false);
    });
  });

  describe('withTransaction', () => {
    it('should execute operation successfully on first attempt', async () => {
      const mockResult = { id: 1, name: 'Test' };

      (AppDataSource.transaction as jest.Mock).mockImplementation(
        async (isolationLevel, callback) => {
          const mockManager: any = {};
          return await callback(mockManager);
        }
      );

      const result = await withTransaction(async (manager) => {
        return mockResult;
      });

      expect(result.data).toEqual(mockResult);
      expect(result.attempts).toBe(1);
      expect(result.hadRetries).toBe(false);
      expect(AppDataSource.transaction).toHaveBeenCalledTimes(1);
    });

    it('should retry on deadlock error', async () => {
      const mockResult = { id: 1, name: 'Test' };
      let attemptCount = 0;

      (AppDataSource.transaction as jest.Mock).mockImplementation(
        async (isolationLevel, callback) => {
          attemptCount++;

          if (attemptCount < 3) {
            const error: any = new Error('deadlock detected');
            error.code = '40P01';
            throw error;
          }

          const mockManager: any = {};
          return await callback(mockManager);
        }
      );

      const result = await withTransaction(
        async (manager) => {
          return mockResult;
        },
        { maxRetries: 5 }
      );

      expect(result.data).toEqual(mockResult);
      expect(result.attempts).toBe(3);
      expect(result.hadRetries).toBe(true);
      expect(AppDataSource.transaction).toHaveBeenCalledTimes(3);
    });

    it('should throw after max retries exceeded', async () => {
      const deadlockError: any = new Error('deadlock detected');
      deadlockError.code = '40P01';

      (AppDataSource.transaction as jest.Mock).mockImplementation(async () => {
        throw deadlockError;
      });

      await expect(
        withTransaction(
          async (manager) => {
            return {};
          },
          { maxRetries: 3 }
        )
      ).rejects.toThrow('deadlock detected');

      expect(AppDataSource.transaction).toHaveBeenCalledTimes(3);
    });

    it('should not retry on non-retriable error', async () => {
      const uniqueViolationError: any = new Error('duplicate key value');
      uniqueViolationError.code = '23505';

      (AppDataSource.transaction as jest.Mock).mockImplementation(async () => {
        throw uniqueViolationError;
      });

      await expect(
        withTransaction(
          async (manager) => {
            return {};
          },
          { maxRetries: 5 }
        )
      ).rejects.toThrow('duplicate key value');

      // Should fail immediately without retries
      expect(AppDataSource.transaction).toHaveBeenCalledTimes(1);
    });

    it('should use custom isolation level', async () => {
      const mockResult = { id: 1 };

      (AppDataSource.transaction as jest.Mock).mockImplementation(
        async (isolationLevel, callback) => {
          const mockManager: any = {};
          return await callback(mockManager);
        }
      );

      await withTransaction(
        async (manager) => mockResult,
        { isolationLevel: 'SERIALIZABLE' }
      );

      expect(AppDataSource.transaction).toHaveBeenCalledWith(
        'SERIALIZABLE',
        expect.any(Function)
      );
    });

    it('should use default READ COMMITTED isolation level', async () => {
      const mockResult = { id: 1 };

      (AppDataSource.transaction as jest.Mock).mockImplementation(
        async (isolationLevel, callback) => {
          const mockManager: any = {};
          return await callback(mockManager);
        }
      );

      await withTransaction(async (manager) => mockResult);

      expect(AppDataSource.transaction).toHaveBeenCalledWith(
        'READ COMMITTED',
        expect.any(Function)
      );
    });

    it('should timeout long-running transactions', async () => {
      (AppDataSource.transaction as jest.Mock).mockImplementation(
        async (isolationLevel, callback) => {
          // Simulate long-running operation
          await new Promise(resolve => setTimeout(resolve, 200));
          const mockManager: any = {};
          return await callback(mockManager);
        }
      );

      await expect(
        withTransaction(async (manager) => ({ id: 1 }), { timeout: 50 })
      ).rejects.toThrow(/timeout/i);
    });

    it('should apply exponential backoff between retries', async () => {
      const mockResult = { id: 1 };
      const delays: number[] = [];
      let attemptCount = 0;

      (AppDataSource.transaction as jest.Mock).mockImplementation(
        async (isolationLevel, callback) => {
          attemptCount++;

          if (attemptCount < 3) {
            const error: any = new Error('deadlock');
            error.code = '40P01';
            throw error;
          }

          const mockManager: any = {};
          return await callback(mockManager);
        }
      );

      const startTime = Date.now();

      await withTransaction(
        async (manager) => mockResult,
        {
          maxRetries: 5,
          retryDelayMs: (attempt) => {
            const delay = Math.pow(2, attempt) * 100;
            delays.push(delay);
            return delay;
          },
        }
      );

      const duration = Date.now() - startTime;

      // Should have 2 delays (attempts 1 and 2 failed)
      expect(delays.length).toBe(2);

      // Delays should increase exponentially: 200ms, 400ms
      expect(delays[0]).toBe(200); // 2^1 * 100
      expect(delays[1]).toBe(400); // 2^2 * 100

      // Total time should be at least the sum of delays
      expect(duration).toBeGreaterThanOrEqual(delays.reduce((a, b) => a + b, 0));
    });
  });

  describe('withBatchTransaction', () => {
    it('should execute multiple operations in single transaction', async () => {
      const results = [{ id: 1 }, { id: 2 }, { id: 3 }];
      let operationIndex = 0;

      (AppDataSource.transaction as jest.Mock).mockImplementation(
        async (isolationLevel, callback) => {
          const mockManager: any = {};
          return await callback(mockManager);
        }
      );

      const result = await withBatchTransaction([
        async (manager) => results[0],
        async (manager) => results[1],
        async (manager) => results[2],
      ]);

      expect(result.data).toEqual(results);
      expect(AppDataSource.transaction).toHaveBeenCalledTimes(1);
    });

    it('should rollback all operations if one fails', async () => {
      (AppDataSource.transaction as jest.Mock).mockImplementation(
        async (isolationLevel, callback) => {
          const mockManager: any = {};
          return await callback(mockManager);
        }
      );

      await expect(
        withBatchTransaction([
          async (manager) => ({ id: 1 }),
          async (manager) => {
            throw new Error('Operation 2 failed');
          },
          async (manager) => ({ id: 3 }),
        ])
      ).rejects.toThrow('Operation 2 failed');
    });
  });

  describe('Transaction Presets', () => {
    it('should have DEFAULT preset with standard settings', () => {
      expect(TRANSACTION_PRESETS.DEFAULT).toEqual({
        maxRetries: 3,
        timeout: 30000,
        isolationLevel: 'READ COMMITTED',
      });
    });

    it('should have FINANCIAL preset with stricter settings', () => {
      expect(TRANSACTION_PRESETS.FINANCIAL).toEqual({
        maxRetries: 5,
        timeout: 60000,
        isolationLevel: 'REPEATABLE READ',
      });
    });

    it('should have CRITICAL preset with maximum consistency', () => {
      expect(TRANSACTION_PRESETS.CRITICAL).toEqual({
        maxRetries: 10,
        timeout: 120000,
        isolationLevel: 'SERIALIZABLE',
      });
    });

    it('should have READ_ONLY preset for read operations', () => {
      expect(TRANSACTION_PRESETS.READ_ONLY).toEqual({
        maxRetries: 2,
        timeout: 10000,
        isolationLevel: 'READ COMMITTED',
      });
    });

    it('should have BULK preset for large operations', () => {
      expect(TRANSACTION_PRESETS.BULK).toEqual({
        maxRetries: 3,
        timeout: 300000,
        isolationLevel: 'READ COMMITTED',
      });
    });
  });

  describe('TransactionStats', () => {
    it('should track successful transactions', () => {
      TransactionStats.recordSuccess(1, 100);
      TransactionStats.recordSuccess(1, 200);

      const stats = TransactionStats.getStats();

      expect(stats.total).toBe(2);
      expect(stats.successful).toBe(2);
      expect(stats.failed).toBe(0);
      expect(stats.retried).toBe(0);
      expect(stats.successRate).toBe(100);
      expect(stats.avgDuration).toBe(150);
    });

    it('should track failed transactions', () => {
      TransactionStats.recordSuccess(1, 100);
      TransactionStats.recordFailure();

      const stats = TransactionStats.getStats();

      expect(stats.total).toBe(2);
      expect(stats.successful).toBe(1);
      expect(stats.failed).toBe(1);
      expect(stats.successRate).toBe(50);
    });

    it('should track retried transactions', () => {
      TransactionStats.recordSuccess(1, 100); // No retries
      TransactionStats.recordSuccess(3, 500); // 2 retries (total 3 attempts)

      const stats = TransactionStats.getStats();

      expect(stats.total).toBe(2);
      expect(stats.retried).toBe(1);
      expect(stats.retryRate).toBe(50);
      expect(stats.avgAttemptsPerTransaction).toBe(2); // (1 + 3) / 2
    });

    it('should reset stats', () => {
      TransactionStats.recordSuccess(1, 100);
      TransactionStats.recordSuccess(1, 100);
      TransactionStats.recordFailure();

      TransactionStats.reset();

      const stats = TransactionStats.getStats();

      expect(stats.total).toBe(0);
      expect(stats.successful).toBe(0);
      expect(stats.failed).toBe(0);
      expect(stats.retried).toBe(0);
    });
  });

  describe('Error Scenarios', () => {
    it('should handle Error objects', async () => {
      const error = new Error('Test error');

      (AppDataSource.transaction as jest.Mock).mockImplementation(async () => {
        throw error;
      });

      await expect(
        withTransaction(async (manager) => ({}))
      ).rejects.toThrow('Test error');
    });

    it('should handle non-Error objects as errors', async () => {
      (AppDataSource.transaction as jest.Mock).mockImplementation(async () => {
        throw 'string error';
      });

      await expect(
        withTransaction(async (manager) => ({}))
      ).rejects.toThrow('string error');
    });

    it('should preserve error stack trace', async () => {
      const error = new Error('Test error');
      error.stack = 'original stack trace';

      (AppDataSource.transaction as jest.Mock).mockRejectedValue(error);

      try {
        await withTransaction(async (manager) => ({}));
      } catch (caught) {
        expect((caught as Error).stack).toContain('original stack trace');
      }
    });
  });

  describe('Performance', () => {
    it('should track transaction duration', async () => {
      const mockResult = { id: 1 };

      (AppDataSource.transaction as jest.Mock).mockImplementation(
        async (isolationLevel, callback) => {
          await new Promise(resolve => setTimeout(resolve, 50));
          const mockManager: any = {};
          return await callback(mockManager);
        }
      );

      const result = await withTransaction(async (manager) => mockResult);

      expect(result.duration).toBeGreaterThanOrEqual(50);
    });

    it('should handle rapid successive transactions', async () => {
      (AppDataSource.transaction as jest.Mock).mockImplementation(
        async (isolationLevel, callback) => {
          const mockManager: any = {};
          return await callback(mockManager);
        }
      );

      const promises = Array.from({ length: 10 }, (_, i) =>
        withTransaction(async (manager) => ({ id: i }))
      );

      const results = await Promise.all(promises);

      expect(results).toHaveLength(10);
      results.forEach((result, i) => {
        expect(result.data.id).toBe(i);
      });
    });
  });
});
