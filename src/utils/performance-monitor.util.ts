/**
 * Performance Monitoring Utilities
 * Track and monitor application performance metrics
 */

import { createLogger } from './logger.util';

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

export default {
  measureAsync,
  recordMetric,
  getMemoryUsage,
};
