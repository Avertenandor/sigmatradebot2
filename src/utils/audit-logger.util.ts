/**
 * Audit Logger Utility
 * Enhanced logging for critical financial operations and security events
 *
 * Features:
 * - Request ID tracking for tracing operations
 * - Separate audit trail file (immutable, long retention)
 * - Structured logging for money operations
 * - Performance metrics with alerting
 * - Automatic alerting on suspicious activity
 */

import winston from 'winston';
import DailyRotateFile from 'winston-daily-rotate-file';
import path from 'path';
import { v4 as uuidv4 } from 'uuid';

// ==================== REQUEST ID TRACKING ====================

/**
 * Thread-local storage for request ID (Node.js doesn't have true threads,
 * but we use AsyncLocalStorage for async context tracking)
 */
import { AsyncLocalStorage } from 'async_hooks';

const requestContext = new AsyncLocalStorage<Map<string, any>>();

/**
 * Generate new request ID
 */
export function generateRequestId(): string {
  return `req_${uuidv4()}`;
}

/**
 * Set request ID for current async context
 */
export function setRequestId(requestId: string): void {
  const store = requestContext.getStore();
  if (store) {
    store.set('requestId', requestId);
  }
}

/**
 * Get request ID from current async context
 */
export function getRequestId(): string | undefined {
  const store = requestContext.getStore();
  return store?.get('requestId');
}

/**
 * Run function with request context
 */
export function runWithRequestContext<T>(fn: () => T): T {
  const store = new Map<string, any>();
  const requestId = generateRequestId();
  store.set('requestId', requestId);

  return requestContext.run(store, () => {
    return fn();
  });
}

// ==================== AUDIT LOGGER ====================

/**
 * Audit log levels (higher severity than normal logs)
 */
const auditLevels = {
  critical: 0, // Immediate attention required
  security: 1, // Security-related events
  financial: 2, // Money operations
  admin: 3,    // Admin actions
  audit: 4,    // General audit trail
};

/**
 * Audit event categories
 */
export enum AuditCategory {
  // Financial operations
  DEPOSIT_CREATED = 'deposit_created',
  DEPOSIT_CONFIRMED = 'deposit_confirmed',
  DEPOSIT_FAILED = 'deposit_failed',
  WITHDRAWAL_REQUESTED = 'withdrawal_requested',
  WITHDRAWAL_APPROVED = 'withdrawal_approved',
  WITHDRAWAL_REJECTED = 'withdrawal_rejected',
  PAYMENT_SENT = 'payment_sent',
  PAYMENT_FAILED = 'payment_failed',
  REFERRAL_EARNING_CREATED = 'referral_earning_created',
  REWARD_CALCULATED = 'reward_calculated',

  // Balance changes
  BALANCE_INCREASED = 'balance_increased',
  BALANCE_DECREASED = 'balance_decreased',

  // User actions
  USER_REGISTERED = 'user_registered',
  USER_VERIFIED = 'user_verified',
  USER_BANNED = 'user_banned',
  USER_UNBANNED = 'user_unbanned',

  // Admin actions
  ADMIN_LOGIN = 'admin_login',
  ADMIN_LOGOUT = 'admin_logout',
  ADMIN_ACTION = 'admin_action',
  ADMIN_BROADCAST = 'admin_broadcast',

  // Security events
  SUSPICIOUS_ACTIVITY = 'suspicious_activity',
  RATE_LIMIT_EXCEEDED = 'rate_limit_exceeded',
  INVALID_ACCESS = 'invalid_access',
  PASSWORD_RESET = 'password_reset',

  // System events
  BLOCKCHAIN_DISCONNECT = 'blockchain_disconnect',
  BLOCKCHAIN_RECONNECT = 'blockchain_reconnect',
  DATABASE_ERROR = 'database_error',
  PAYMENT_RETRY = 'payment_retry',
}

/**
 * Audit event interface
 */
export interface AuditEvent {
  category: AuditCategory;
  severity: 'critical' | 'security' | 'financial' | 'admin' | 'audit';
  userId?: number;
  adminId?: number;
  requestId?: string;
  action: string;
  details: Record<string, any>;
  ipAddress?: string;
  userAgent?: string;

  // Financial fields
  amount?: number;
  currency?: string;
  balanceBefore?: number;
  balanceAfter?: number;

  // Metadata
  timestamp?: Date;
  success?: boolean;
  error?: string;
}

/**
 * Create audit logger instance (separate from main logger)
 */
const logsDir = path.join(process.cwd(), 'logs');

const auditLogger = winston.createLogger({
  levels: auditLevels,
  level: 'audit',
  format: winston.format.combine(
    winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss.SSS' }),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  transports: [
    // Audit trail file (LONG retention - 90 days)
    new DailyRotateFile({
      filename: path.join(logsDir, 'audit', 'audit-%DATE%.log'),
      datePattern: 'YYYY-MM-DD',
      maxSize: '50m',
      maxFiles: '90d', // Keep for 90 days (compliance)
      zippedArchive: true, // Compress rotated audit logs to save disk space
      level: 'audit',
    }),

    // Financial operations (VERY LONG retention - 365 days)
    new DailyRotateFile({
      filename: path.join(logsDir, 'audit', 'financial-%DATE%.log'),
      datePattern: 'YYYY-MM-DD',
      maxSize: '50m',
      maxFiles: '365d', // Keep for 1 year (financial records)
      zippedArchive: true, // Compress rotated audit logs to save disk space
      level: 'financial',
    }),

    // Security events (LONG retention - 180 days)
    new DailyRotateFile({
      filename: path.join(logsDir, 'audit', 'security-%DATE%.log'),
      datePattern: 'YYYY-MM-DD',
      maxSize: '50m',
      maxFiles: '180d', // Keep for 6 months
      zippedArchive: true, // Compress rotated audit logs to save disk space
      level: 'security',
    }),

    // Critical events (immediate attention)
    new DailyRotateFile({
      filename: path.join(logsDir, 'audit', 'critical-%DATE%.log'),
      datePattern: 'YYYY-MM-DD',
      maxSize: '50m',
      maxFiles: '365d',
      zippedArchive: true, // Compress rotated audit logs to save disk space
      level: 'critical',
    }),
  ],

  // Don't exit on error
  exitOnError: false,
});

// ==================== AUDIT LOGGING FUNCTIONS ====================

/**
 * Log audit event with full context
 */
export function logAuditEvent(event: AuditEvent): void {
  const enrichedEvent = {
    ...event,
    requestId: event.requestId || getRequestId(),
    timestamp: event.timestamp || new Date(),
  };

  // Determine log method based on severity
  const logMethod = event.severity || 'audit';

  auditLogger.log(logMethod, 'Audit Event', enrichedEvent);

  // If critical, also log to main logger and alert admins
  if (event.severity === 'critical') {
    const mainLogger = require('./logger.util').default;
    mainLogger.error('CRITICAL AUDIT EVENT', enrichedEvent);

    // Alert admins asynchronously (don't block)
    alertAdminsAsync(event);
  }
}

/**
 * Log financial operation (money in/out)
 */
export function logFinancialOperation(params: {
  category: AuditCategory;
  userId: number;
  action: string;
  amount: number;
  currency?: string;
  balanceBefore?: number;
  balanceAfter?: number;
  transactionId?: number;
  txHash?: string;
  success: boolean;
  error?: string;
  details?: Record<string, any>;
}): void {
  logAuditEvent({
    category: params.category,
    severity: 'financial',
    userId: params.userId,
    action: params.action,
    amount: params.amount,
    currency: params.currency || 'USDT',
    balanceBefore: params.balanceBefore,
    balanceAfter: params.balanceAfter,
    success: params.success,
    error: params.error,
    details: {
      transactionId: params.transactionId,
      txHash: params.txHash,
      ...params.details,
    },
  });

  // Alert if large amount or failed transaction
  if (!params.success || params.amount > 1000) {
    alertOnFinancialAnomaly(params);
  }
}

/**
 * Log balance change
 */
export function logBalanceChange(params: {
  userId: number;
  balanceBefore: number;
  balanceAfter: number;
  reason: string;
  transactionId?: number;
  details?: Record<string, any>;
}): void {
  const delta = params.balanceAfter - params.balanceBefore;
  const category = delta > 0 ? AuditCategory.BALANCE_INCREASED : AuditCategory.BALANCE_DECREASED;

  logAuditEvent({
    category,
    severity: 'financial',
    userId: params.userId,
    action: `Balance changed: ${params.reason}`,
    balanceBefore: params.balanceBefore,
    balanceAfter: params.balanceAfter,
    amount: Math.abs(delta),
    success: true,
    details: {
      delta,
      transactionId: params.transactionId,
      ...params.details,
    },
  });
}

/**
 * Log security event
 */
export function logSecurityAudit(params: {
  category: AuditCategory;
  severity?: 'critical' | 'security';
  userId?: number;
  action: string;
  success: boolean;
  ipAddress?: string;
  userAgent?: string;
  details?: Record<string, any>;
}): void {
  logAuditEvent({
    category: params.category,
    severity: params.severity || 'security',
    userId: params.userId,
    action: params.action,
    success: params.success,
    ipAddress: params.ipAddress,
    userAgent: params.userAgent,
    details: params.details || {},
  });
}

/**
 * Log admin action
 */
export function logAdminAudit(params: {
  adminId: number;
  action: string;
  targetUserId?: number;
  details?: Record<string, any>;
}): void {
  logAuditEvent({
    category: AuditCategory.ADMIN_ACTION,
    severity: 'admin',
    adminId: params.adminId,
    userId: params.targetUserId,
    action: params.action,
    success: true,
    details: params.details || {},
  });
}

// ==================== PERFORMANCE METRICS ====================

/**
 * Performance thresholds (in milliseconds)
 */
const PERFORMANCE_THRESHOLDS = {
  database_query: 1000, // 1 second
  blockchain_call: 5000, // 5 seconds
  api_request: 2000, // 2 seconds
  payment_processing: 10000, // 10 seconds
};

/**
 * Performance metric interface
 */
export interface PerformanceMetric {
  operation: string;
  category: string;
  duration: number;
  success: boolean;
  details?: Record<string, any>;
}

/**
 * Log performance metric
 */
export function logPerformanceMetric(metric: PerformanceMetric): void {
  const threshold = PERFORMANCE_THRESHOLDS[metric.category as keyof typeof PERFORMANCE_THRESHOLDS];
  const isSlow = threshold && metric.duration > threshold;

  // Log to main logger
  const mainLogger = require('./logger.util').default;
  const logMethod = isSlow ? 'warn' : 'debug';

  mainLogger[logMethod]('Performance metric', {
    context: 'Performance',
    ...metric,
    threshold,
    isSlow,
    requestId: getRequestId(),
  });

  // If slow, log to audit trail
  if (isSlow) {
    logAuditEvent({
      category: AuditCategory.ADMIN_ACTION, // Use admin category for visibility
      severity: 'audit',
      action: `Slow operation detected: ${metric.operation}`,
      success: metric.success,
      details: {
        ...metric,
        threshold,
        exceedBy: metric.duration - threshold,
      },
    });
  }
}

/**
 * Measure and log execution time
 */
export async function measurePerformance<T>(
  operation: string,
  category: string,
  fn: () => Promise<T>
): Promise<T> {
  const startTime = Date.now();
  let success = true;
  let error: any;

  try {
    const result = await fn();
    return result;
  } catch (err) {
    success = false;
    error = err;
    throw err;
  } finally {
    const duration = Date.now() - startTime;

    logPerformanceMetric({
      operation,
      category,
      duration,
      success,
      details: error ? { error: error.message } : undefined,
    });
  }
}

// ==================== ALERTING ====================

/**
 * Alert admins about critical event (async, non-blocking)
 * TODO: Integrate with Telegram notification service when bot instance is available
 */
async function alertAdminsAsync(event: AuditEvent): Promise<void> {
  // Run in background, don't block
  setImmediate(async () => {
    try {
      const message = formatAlertMessage(event);

      // For now, just log critical alerts to main logger
      // TODO: Send Telegram notification to super admin
      const mainLogger = require('./logger.util').default;
      mainLogger.error('CRITICAL ALERT', {
        message,
        event,
      });
    } catch (error) {
      // Don't throw - alerting failure shouldn't break operations
      const mainLogger = require('./logger.util').default;
      mainLogger.error('Failed to process admin alert', { error });
    }
  });
}

/**
 * Alert on financial anomaly
 */
function alertOnFinancialAnomaly(params: {
  action: string;
  amount: number;
  success: boolean;
  error?: string;
  userId?: number;
}): void {
  // Only alert on failures or large amounts
  if (params.success && params.amount < 1000) {
    return;
  }

  const event: AuditEvent = {
    category: AuditCategory.SUSPICIOUS_ACTIVITY,
    severity: 'critical',
    userId: params.userId,
    action: params.action,
    amount: params.amount,
    success: params.success,
    error: params.error,
    details: {
      reason: params.success ? 'Large amount' : 'Transaction failed',
    },
  };

  alertAdminsAsync(event);
}

/**
 * Format alert message for admins
 */
function formatAlertMessage(event: AuditEvent): string {
  let emoji = '🚨';

  if (event.severity === 'critical') emoji = '🔴';
  if (event.severity === 'security') emoji = '🔒';
  if (event.severity === 'financial') emoji = '💰';

  let message = `${emoji} **ALERT: ${event.category}**\n\n`;
  message += `**Action:** ${event.action}\n`;
  message += `**Severity:** ${event.severity}\n`;
  message += `**Time:** ${new Date().toISOString()}\n`;

  if (event.userId) {
    message += `**User ID:** ${event.userId}\n`;
  }

  if (event.amount !== undefined) {
    message += `**Amount:** ${event.amount} ${event.currency || 'USDT'}\n`;
  }

  if (event.success === false) {
    message += `**Status:** ❌ FAILED\n`;
    if (event.error) {
      message += `**Error:** ${event.error}\n`;
    }
  }

  if (event.requestId) {
    message += `**Request ID:** ${event.requestId}\n`;
  }

  if (Object.keys(event.details).length > 0) {
    message += `\n**Details:**\n\`\`\`json\n${JSON.stringify(event.details, null, 2)}\n\`\`\``;
  }

  return message;
}

// ==================== EXPORTS ====================

export default {
  logAuditEvent,
  logFinancialOperation,
  logBalanceChange,
  logSecurityAudit,
  logAdminAudit,
  logPerformanceMetric,
  measurePerformance,
  generateRequestId,
  setRequestId,
  getRequestId,
  runWithRequestContext,
};
