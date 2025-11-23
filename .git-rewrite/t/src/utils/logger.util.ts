/**
 * Logger Utility
 * Winston-based logging with daily rotation and multiple transports
 */

import winston from 'winston';
import DailyRotateFile from 'winston-daily-rotate-file';
import path from 'path';

// Log levels
const levels = {
  error: 0,
  warn: 1,
  info: 2,
  http: 3,
  debug: 4,
};

// Log colors
const colors = {
  error: 'red',
  warn: 'yellow',
  info: 'green',
  http: 'magenta',
  debug: 'blue',
};

winston.addColors(colors);

// Determine log level based on environment
const level = (): string => {
  const env = process.env.NODE_ENV || 'development';
  const isDevelopment = env === 'development';
  return isDevelopment ? 'debug' : process.env.LOG_LEVEL || 'info';
};

// Custom format for console output
const consoleFormat = winston.format.combine(
  winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
  winston.format.colorize({ all: true }),
  winston.format.printf((info) => {
    const { timestamp, level, message, ...meta } = info;

    let msg = `${timestamp} [${level}]: ${message}`;

    // Add metadata if present
    if (Object.keys(meta).length > 0) {
      msg += ` ${JSON.stringify(meta, null, 2)}`;
    }

    return msg;
  })
);

// Custom format for file output (JSON)
const fileFormat = winston.format.combine(
  winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
  winston.format.errors({ stack: true }),
  winston.format.json()
);

// Create transports
const transports: winston.transport[] = [];

// Console transport (always enabled in development)
if (process.env.NODE_ENV !== 'production') {
  transports.push(
    new winston.transports.Console({
      format: consoleFormat,
    })
  );
}

// File transports with daily rotation
const logsDir = path.join(process.cwd(), 'logs');

// All logs
transports.push(
  new DailyRotateFile({
    filename: path.join(logsDir, 'app-%DATE%.log'),
    datePattern: 'YYYY-MM-DD',
    maxSize: '20m',
    maxFiles: '14d',
    format: fileFormat,
    level: 'debug',
  })
);

// Error logs (separate file)
transports.push(
  new DailyRotateFile({
    filename: path.join(logsDir, 'error-%DATE%.log'),
    datePattern: 'YYYY-MM-DD',
    maxSize: '20m',
    maxFiles: '30d',
    format: fileFormat,
    level: 'error',
  })
);

// Combined logs (info and above)
transports.push(
  new DailyRotateFile({
    filename: path.join(logsDir, 'combined-%DATE%.log'),
    datePattern: 'YYYY-MM-DD',
    maxSize: '20m',
    maxFiles: '14d',
    format: fileFormat,
    level: 'info',
  })
);

// Create the logger instance
const logger = winston.createLogger({
  levels,
  level: level(),
  transports,
  exitOnError: false,
  // Handle uncaught exceptions and rejections
  exceptionHandlers: [
    new DailyRotateFile({
      filename: path.join(logsDir, 'exceptions-%DATE%.log'),
      datePattern: 'YYYY-MM-DD',
      maxSize: '20m',
      maxFiles: '30d',
      format: fileFormat,
    }),
  ],
  rejectionHandlers: [
    new DailyRotateFile({
      filename: path.join(logsDir, 'rejections-%DATE%.log'),
      datePattern: 'YYYY-MM-DD',
      maxSize: '20m',
      maxFiles: '30d',
      format: fileFormat,
    }),
  ],
});

// Helper functions for structured logging
export const createLogger = (context: string) => {
  return {
    error: (message: string, meta?: Record<string, any>) => {
      logger.error(message, { context, ...meta });
    },
    warn: (message: string, meta?: Record<string, any>) => {
      logger.warn(message, { context, ...meta });
    },
    info: (message: string, meta?: Record<string, any>) => {
      logger.info(message, { context, ...meta });
    },
    http: (message: string, meta?: Record<string, any>) => {
      logger.http(message, { context, ...meta });
    },
    debug: (message: string, meta?: Record<string, any>) => {
      logger.debug(message, { context, ...meta });
    },
  };
};

// Log user action helper
export const logUserAction = (
  userId: number,
  action: string,
  details?: Record<string, any>
) => {
  logger.info('User action', {
    context: 'UserAction',
    userId,
    action,
    ...details,
  });
};

// Log blockchain event helper
export const logBlockchainEvent = (
  event: string,
  details: Record<string, any>
) => {
  logger.info('Blockchain event', {
    context: 'Blockchain',
    event,
    ...details,
  });
};

// Log admin action helper
export const logAdminAction = (
  adminId: number,
  action: string,
  details?: Record<string, any>
) => {
  logger.warn('Admin action', {
    context: 'Admin',
    adminId,
    action,
    ...details,
  });
};

// Log security event helper
export const logSecurityEvent = (
  event: string,
  severity: 'low' | 'medium' | 'high' | 'critical',
  details: Record<string, any>
) => {
  const logMethod = severity === 'critical' || severity === 'high' ? 'error' : 'warn';
  logger[logMethod]('Security event', {
    context: 'Security',
    event,
    severity,
    ...details,
  });
};

// Log performance metric helper
export const logPerformance = (
  operation: string,
  duration: number,
  details?: Record<string, any>
) => {
  logger.debug('Performance metric', {
    context: 'Performance',
    operation,
    duration,
    ...details,
  });
};

export default logger;
