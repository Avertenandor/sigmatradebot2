/**
 * Performance Monitoring Utilities
 * Track and monitor application performance metrics
 */

import { createLogger } from './logger.util';
import type { RPCRateLimiter } from '../blockchain/rpc-limiter';

const logger = createLogger('PerformanceMonitor');

/**
 * Performance metrics storage
 */
interface PerformanceMetric {
  name: string;
  duration: number;
  timestamp: number;
  metadata?: Record<string, any>;
}

const metrics: PerformanceMetric[] = [];
const MAX_METRICS_STORED = 1000; // Keep last 1000 metrics

/**
 * Measure execution time of async function
 */
export const measureAsync = async <T>(
  name: string,
  fn: () => Promise<T>,
  metadata?: Record<string, any>
): Promise<T> => {
  const startTime = Date.now();

  try {
    const result = await fn();
    const duration = Date.now() - startTime;

    recordMetric(name, duration, metadata);

    // Log slow operations (> 1 second)
    if (duration > 1000) {
      logger.warn('Slow operation detected', { name, duration, metadata });
    }

    return result;
  } catch (error) {
    const duration = Date.now() - startTime;
    recordMetric(name, duration, { ...metadata, error: true });
    throw error;
  }
};

/**
 * Record a performance metric
 */
export const recordMetric = (
  name: string,
  duration: number,
  metadata?: Record<string, any>
): void => {
  const metric: PerformanceMetric = {
    name,
    duration,
    timestamp: Date.now(),
    metadata,
  };

  metrics.push(metric);

  // Keep only last N metrics
  if (metrics.length > MAX_METRICS_STORED) {
    metrics.shift();
  }
};

/**
 * Get memory usage
 */
export const getMemoryUsage = (): {
  rss: number;
  heapTotal: number;
  heapUsed: number;
  heapUsedPercentage: number;
} => {
  const usage = process.memoryUsage();

  return {
    rss: Math.round(usage.rss / 1024 / 1024), // MB
    heapTotal: Math.round(usage.heapTotal / 1024 / 1024), // MB
    heapUsed: Math.round(usage.heapUsed / 1024 / 1024), // MB
    heapUsedPercentage: Math.round((usage.heapUsed / usage.heapTotal) * 100),
  };
};

// Performance reporting intervals
let performanceInterval: NodeJS.Timeout | null = null;
let memoryInterval: NodeJS.Timeout | null = null;
let rpcRateLimiter: RPCRateLimiter | null = null;

/**
 * Set RPC rate limiter instance for monitoring
 * Call this after initializing the rate limiter
 */
export const setRPCRateLimiter = (limiter: RPCRateLimiter): void => {
  rpcRateLimiter = limiter;
  logger.info('RPC rate limiter registered for monitoring');
};

/**
 * Start performance reporting (hourly)
 * Reports memory usage, metrics, and RPC stats
 */
export const startPerformanceReporting = (): void => {
  if (performanceInterval) {
    logger.warn('Performance reporting already started');
    return;
  }

  const reportInterval = 60 * 60 * 1000; // 1 hour

  performanceInterval = setInterval(() => {
    try {
      const memory = getMemoryUsage();

      logger.info('📊 Performance Report', {
        memory,
        metricsStored: metrics.length,
      });

      // Report RPC metrics if available
      if (rpcRateLimiter) {
        const { logRPCMetrics, getRPCUtilization } = require('./rpc-metrics.util');
        logRPCMetrics(rpcRateLimiter);

        const utilization = getRPCUtilization(rpcRateLimiter);
        if (utilization > 70) {
          logger.warn('⚠️  RPC capacity utilization high', {
            utilization: `${utilization.toFixed(2)}%`,
          });
        }
      }

      // Check DLQ thresholds (failed/stuck jobs)
      try {
        const { checkDLQThresholds } = require('../jobs/queue.config');
        await checkDLQThresholds();
      } catch (error) {
        logger.error('Error checking DLQ thresholds', { error });
      }

      // Alert on high memory usage
      if (memory.heapUsedPercentage > 90) {
        logger.warn('⚠️  High memory usage detected', {
          heapUsedPercentage: memory.heapUsedPercentage,
          heapUsed: `${memory.heapUsed}MB`,
          heapTotal: `${memory.heapTotal}MB`,
        });
      }
    } catch (error) {
      logger.error('Error in performance reporting', { error });
    }
  }, reportInterval);

  logger.info('✅ Performance reporting started (hourly)');
};

/**
 * Stop performance reporting
 */
export const stopPerformanceReporting = (): void => {
  if (performanceInterval) {
    clearInterval(performanceInterval);
    performanceInterval = null;
    logger.info('Performance reporting stopped');
  }
};

/**
 * Start memory monitoring (every 5 minutes)
 * Logs memory usage for tracking trends
 */
export const startMemoryMonitoring = (): void => {
  if (memoryInterval) {
    logger.warn('Memory monitoring already started');
    return;
  }

  const monitorInterval = 5 * 60 * 1000; // 5 minutes

  memoryInterval = setInterval(() => {
    try {
      const memory = getMemoryUsage();

      logger.debug('💾 Memory Usage', {
        rss: `${memory.rss}MB`,
        heapUsed: `${memory.heapUsed}MB`,
        heapTotal: `${memory.heapTotal}MB`,
        heapUsedPercentage: `${memory.heapUsedPercentage}%`,
      });

      // Alert on memory leaks (heap usage keeps growing)
      if (memory.heapUsedPercentage > 95) {
        logger.error('🚨 CRITICAL: Memory usage at 95%+', {
          heapUsed: `${memory.heapUsed}MB`,
          heapTotal: `${memory.heapTotal}MB`,
        });
      }
    } catch (error) {
      logger.error('Error in memory monitoring', { error });
    }
  }, monitorInterval);

  logger.info('✅ Memory monitoring started (5 minutes)');
};

/**
 * Stop memory monitoring
 */
export const stopMemoryMonitoring = (): void => {
  if (memoryInterval) {
    clearInterval(memoryInterval);
    memoryInterval = null;
    logger.info('Memory monitoring stopped');
  }
};

export default {
  measureAsync,
  recordMetric,
  getMemoryUsage,
  startPerformanceReporting,
  stopPerformanceReporting,
  startMemoryMonitoring,
  stopMemoryMonitoring,
  setRPCRateLimiter,
};
