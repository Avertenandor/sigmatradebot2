/**
 * Performance Monitor Utility
 * Tracks execution time and resource usage of critical operations
 * Provides automatic alerting when thresholds are exceeded
 */

import { measurePerformance } from './audit-logger.util';
import { createLogger } from './logger.util';

const logger = createLogger('PerformanceMonitor');

/**
 * Performance categories with thresholds
 */
export const PerformanceCategory = {
  DATABASE_QUERY: 'database_query',
  BLOCKCHAIN_CALL: 'blockchain_call',
  API_REQUEST: 'api_request',
  PAYMENT_PROCESSING: 'payment_processing',
  REWARD_CALCULATION: 'reward_calculation',
  REFERRAL_CHAIN: 'referral_chain',
  USER_REGISTRATION: 'user_registration',
} as const;

/**
 * Decorator for automatic performance tracking
 * Usage: @trackPerformance('operation_name', 'category')
 */
export function trackPerformance(operation: string, category: string) {
  return function (
    _target: any,
    _propertyKey: string,
    descriptor: PropertyDescriptor
  ) {
    const originalMethod = descriptor.value;

    descriptor.value = async function (...args: any[]) {
      return await measurePerformance(
        operation,
        category,
        () => originalMethod.apply(this, args)
      );
    };

    return descriptor;
  };
}

/**
 * Manual performance tracking for functions
 * Use when decorator is not applicable
 */
export async function withPerformanceTracking<T>(
  operation: string,
  category: string,
  fn: () => Promise<T>
): Promise<T> {
  return await measurePerformance(operation, category, fn);
}

/**
 * Track database query performance
 */
export async function trackDatabaseQuery<T>(
  queryName: string,
  query: () => Promise<T>
): Promise<T> {
  return await measurePerformance(
    queryName,
    PerformanceCategory.DATABASE_QUERY,
    query
  );
}

/**
 * Track blockchain call performance
 */
export async function trackBlockchainCall<T>(
  operation: string,
  call: () => Promise<T>
): Promise<T> {
  return await measurePerformance(
    operation,
    PerformanceCategory.BLOCKCHAIN_CALL,
    call
  );
}

/**
 * Performance statistics collector
 */
class PerformanceStats {
  private stats = new Map<string, {
    count: number;
    totalDuration: number;
    minDuration: number;
    maxDuration: number;
    failures: number;
  }>();

  /**
   * Record metric
   */
  record(operation: string, duration: number, success: boolean): void {
    const existing = this.stats.get(operation);

    if (!existing) {
      this.stats.set(operation, {
        count: 1,
        totalDuration: duration,
        minDuration: duration,
        maxDuration: duration,
        failures: success ? 0 : 1,
      });
    } else {
      existing.count += 1;
      existing.totalDuration += duration;
      existing.minDuration = Math.min(existing.minDuration, duration);
      existing.maxDuration = Math.max(existing.maxDuration, duration);
      if (!success) existing.failures += 1;
    }
  }

  /**
   * Get statistics for operation
   */
  getStats(operation: string) {
    const stats = this.stats.get(operation);

    if (!stats) {
      return null;
    }

    return {
      operation,
      count: stats.count,
      avgDuration: stats.totalDuration / stats.count,
      minDuration: stats.minDuration,
      maxDuration: stats.maxDuration,
      successRate: ((stats.count - stats.failures) / stats.count) * 100,
      failures: stats.failures,
    };
  }

  /**
   * Get all statistics
   */
  getAllStats() {
    const allStats = [];

    for (const [operation, _] of this.stats) {
      allStats.push(this.getStats(operation));
    }

    return allStats.sort((a, b) => {
      if (!a || !b) return 0;
      return b.count - a.count; // Sort by most frequent
    });
  }

  /**
   * Clear statistics
   */
  clear(): void {
    this.stats.clear();
  }

  /**
   * Log statistics summary
   */
  logSummary(): void {
    const allStats = this.getAllStats();

    if (allStats.length === 0) {
      logger.info('No performance statistics available');
      return;
    }

    logger.info('Performance Statistics Summary', {
      totalOperations: allStats.length,
      stats: allStats.slice(0, 10), // Top 10
    });
  }
}

// Singleton instance
export const performanceStats = new PerformanceStats();

/**
 * Start periodic performance reporting (every hour)
 */
let reportingInterval: NodeJS.Timeout | null = null;

export function startPerformanceReporting(intervalMs: number = 60 * 60 * 1000): void {
  if (reportingInterval) {
    logger.warn('Performance reporting already started');
    return;
  }

  reportingInterval = setInterval(() => {
    performanceStats.logSummary();
  }, intervalMs);

  logger.info('Performance reporting started', { intervalMs });
}

/**
 * Stop performance reporting
 */
export function stopPerformanceReporting(): void {
  if (reportingInterval) {
    clearInterval(reportingInterval);
    reportingInterval = null;
    logger.info('Performance reporting stopped');
  }
}

/**
 * Memory usage monitor
 */
export function logMemoryUsage(): void {
  const usage = process.memoryUsage();

  logger.debug('Memory usage', {
    rss: `${Math.round(usage.rss / 1024 / 1024)} MB`, // Resident Set Size
    heapTotal: `${Math.round(usage.heapTotal / 1024 / 1024)} MB`,
    heapUsed: `${Math.round(usage.heapUsed / 1024 / 1024)} MB`,
    external: `${Math.round(usage.external / 1024 / 1024)} MB`,
  });

  // Alert if memory usage is high (> 1GB)
  if (usage.heapUsed > 1024 * 1024 * 1024) {
    logger.warn('High memory usage detected', {
      heapUsed: `${Math.round(usage.heapUsed / 1024 / 1024)} MB`,
    });
  }
}

/**
 * Start memory monitoring (every 5 minutes)
 */
let memoryInterval: NodeJS.Timeout | null = null;

export function startMemoryMonitoring(intervalMs: number = 5 * 60 * 1000): void {
  if (memoryInterval) {
    logger.warn('Memory monitoring already started');
    return;
  }

  memoryInterval = setInterval(() => {
    logMemoryUsage();
  }, intervalMs);

  logger.info('Memory monitoring started', { intervalMs });
}

/**
 * Stop memory monitoring
 */
export function stopMemoryMonitoring(): void {
  if (memoryInterval) {
    clearInterval(memoryInterval);
    memoryInterval = null;
    logger.info('Memory monitoring stopped');
  }
}

export default {
  trackPerformance,
  withPerformanceTracking,
  trackDatabaseQuery,
  trackBlockchainCall,
  performanceStats,
  startPerformanceReporting,
  stopPerformanceReporting,
  logMemoryUsage,
  startMemoryMonitoring,
  stopMemoryMonitoring,
};
