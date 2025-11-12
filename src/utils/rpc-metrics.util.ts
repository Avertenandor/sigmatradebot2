/**
 * RPC Metrics Util
 * Exports RPC rate limiter metrics in Prometheus text format
 *
 * OPTIMIZATION: Provides observability for QuickNode API usage
 * - Tracks request rates and success rates
 * - Monitors queue sizes and latency
 * - Helps prevent rate limit violations
 */

import { RPCRateLimiter } from '../blockchain/rpc-limiter';
import { logger } from './logger.util';

/**
 * Convert RPC stats to Prometheus text format
 * https://prometheus.io/docs/instrumenting/exposition_formats/
 *
 * @param rateLimiter - RPC rate limiter instance
 * @returns Prometheus-formatted metrics string
 */
export function getRPCMetricsPrometheus(rateLimiter: RPCRateLimiter): string {
  const stats = rateLimiter.getStats();
  const timestamp = Date.now();

  const metrics: string[] = [];

  // HELP and TYPE declarations
  metrics.push('# HELP rpc_requests_total Total number of RPC requests made');
  metrics.push('# TYPE rpc_requests_total counter');
  metrics.push(`rpc_requests_total ${stats.totalRequests} ${timestamp}`);
  metrics.push('');

  metrics.push('# HELP rpc_requests_successful Number of successful RPC requests');
  metrics.push('# TYPE rpc_requests_successful counter');
  metrics.push(`rpc_requests_successful ${stats.successfulRequests} ${timestamp}`);
  metrics.push('');

  metrics.push('# HELP rpc_requests_failed Number of failed RPC requests');
  metrics.push('# TYPE rpc_requests_failed counter');
  metrics.push(`rpc_requests_failed ${stats.failedRequests} ${timestamp}`);
  metrics.push('');

  metrics.push('# HELP rpc_requests_retried Number of retried RPC requests');
  metrics.push('# TYPE rpc_requests_retried counter');
  metrics.push(`rpc_requests_retried ${stats.retriedRequests} ${timestamp}`);
  metrics.push('');

  metrics.push('# HELP rpc_latency_avg_ms Average RPC request latency in milliseconds');
  metrics.push('# TYPE rpc_latency_avg_ms gauge');
  metrics.push(`rpc_latency_avg_ms ${stats.averageLatency.toFixed(2)} ${timestamp}`);
  metrics.push('');

  metrics.push('# HELP rpc_queue_size Number of RPC requests waiting in queue');
  metrics.push('# TYPE rpc_queue_size gauge');
  metrics.push(`rpc_queue_size ${stats.queueSize} ${timestamp}`);
  metrics.push('');

  metrics.push('# HELP rpc_running_jobs Number of currently running RPC requests');
  metrics.push('# TYPE rpc_running_jobs gauge');
  metrics.push(`rpc_running_jobs ${stats.runningJobs} ${timestamp}`);
  metrics.push('');

  metrics.push('# HELP rpc_success_rate_percent RPC request success rate (0-100)');
  metrics.push('# TYPE rpc_success_rate_percent gauge');
  metrics.push(`rpc_success_rate_percent ${stats.successRate.toFixed(2)} ${timestamp}`);
  metrics.push('');

  // Derived metrics
  const utilizationPercent = stats.totalRequests > 0
    ? ((stats.queueSize + stats.runningJobs) / stats.totalRequests * 100)
    : 0;
  metrics.push('# HELP rpc_utilization_percent Percentage of rate limit capacity in use');
  metrics.push('# TYPE rpc_utilization_percent gauge');
  metrics.push(`rpc_utilization_percent ${utilizationPercent.toFixed(2)} ${timestamp}`);
  metrics.push('');

  return metrics.join('\n');
}

/**
 * Log RPC metrics for monitoring
 * Called periodically by performance monitor
 *
 * @param rateLimiter - RPC rate limiter instance
 */
export function logRPCMetrics(rateLimiter: RPCRateLimiter): void {
  const stats = rateLimiter.getStats();

  logger.info('📊 RPC Metrics', {
    totalRequests: stats.totalRequests,
    successfulRequests: stats.successfulRequests,
    failedRequests: stats.failedRequests,
    retriedRequests: stats.retriedRequests,
    successRate: `${stats.successRate.toFixed(2)}%`,
    averageLatency: `${stats.averageLatency.toFixed(2)}ms`,
    queueSize: stats.queueSize,
    runningJobs: stats.runningJobs,
  });

  // ALERT: High failure rate
  if (stats.totalRequests > 100 && stats.successRate < 95) {
    logger.warn('⚠️  RPC success rate below 95%', {
      successRate: stats.successRate.toFixed(2),
      failedRequests: stats.failedRequests,
      totalRequests: stats.totalRequests,
    });
  }

  // ALERT: High queue size (potential rate limit saturation)
  if (stats.queueSize > 50) {
    logger.warn('⚠️  RPC queue size high', {
      queueSize: stats.queueSize,
      runningJobs: stats.runningJobs,
    });
  }

  // ALERT: High latency (potential network/QuickNode issues)
  if (stats.averageLatency > 2000) {
    logger.warn('⚠️  RPC average latency high', {
      averageLatency: `${stats.averageLatency.toFixed(2)}ms`,
    });
  }
}

/**
 * Calculate RPC utilization percentage
 * ALERT if approaching rate limits (>70%)
 *
 * @param rateLimiter - RPC rate limiter instance
 * @returns Utilization percentage (0-100)
 */
export function getRPCUtilization(rateLimiter: RPCRateLimiter): number {
  const stats = rateLimiter.getStats();

  if (stats.totalRequests === 0) {
    return 0;
  }

  // Simple utilization: (queue + running) / total capacity
  // This is an approximation - real calculation would need reservoir size
  const utilizationPercent = ((stats.queueSize + stats.runningJobs) / 100) * 100;

  if (utilizationPercent > 70) {
    logger.warn('⚠️  RPC utilization high - approaching rate limits', {
      utilization: `${utilizationPercent.toFixed(2)}%`,
      queueSize: stats.queueSize,
      runningJobs: stats.runningJobs,
    });
  }

  return utilizationPercent;
}
