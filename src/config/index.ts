/**
 * Main Configuration Module
 * Centralizes all application configuration
 */

import dotenv from 'dotenv';
import path from 'path';

// Load environment variables
dotenv.config({ path: path.join(__dirname, '../../.env') });

// Validate required environment variables
const requiredEnvVars = [
  'TELEGRAM_BOT_TOKEN',
  'DB_HOST',
  'DB_PORT',
  'DB_USERNAME',
  'DB_PASSWORD',
  'DB_DATABASE',
  'REDIS_HOST',
  'REDIS_PORT',
  'QUICKNODE_HTTPS_URL',
  'QUICKNODE_WSS_URL',
  'SYSTEM_WALLET_ADDRESS',
  'PAYOUT_WALLET_ADDRESS',
];

const missingEnvVars = requiredEnvVars.filter((envVar) => !process.env[envVar]);

if (missingEnvVars.length > 0) {
  throw new Error(
    `Missing required environment variables: ${missingEnvVars.join(', ')}`
  );
}

// Application configuration
export const config = {
  // Environment
  env: process.env.NODE_ENV || 'development',
  isDevelopment: process.env.NODE_ENV === 'development',
  isProduction: process.env.NODE_ENV === 'production',
  port: parseInt(process.env.PORT || '3000', 10),

  // Logging
  logLevel: process.env.LOG_LEVEL || 'info',

  // Telegram Bot
  telegram: {
    botToken: process.env.TELEGRAM_BOT_TOKEN!,
    webhookUrl: process.env.TELEGRAM_WEBHOOK_URL,
    webhookSecret: process.env.TELEGRAM_WEBHOOK_SECRET,
    superAdminId: parseInt(process.env.SUPER_ADMIN_TELEGRAM_ID || '0', 10),
  },

  // Database (PostgreSQL)
  database: {
    host: process.env.DB_HOST!,
    port: parseInt(process.env.DB_PORT!, 10),
    username: process.env.DB_USERNAME!,
    password: process.env.DB_PASSWORD!,
    database: process.env.DB_DATABASE!,
    logging: process.env.DB_LOGGING === 'true',
    synchronize: process.env.DB_SYNCHRONIZE === 'true', // NEVER true in production!
  },

  // Redis
  redis: {
    host: process.env.REDIS_HOST!,
    port: parseInt(process.env.REDIS_PORT!, 10),
    password: process.env.REDIS_PASSWORD || undefined,
    db: parseInt(process.env.REDIS_DB || '0', 10),
    tls: process.env.REDIS_TLS === 'true' ? {} : undefined,
  },

  // Blockchain (BSC)
  blockchain: {
    quicknodeHttpsUrl: process.env.QUICKNODE_HTTPS_URL!,
    quicknodeWssUrl: process.env.QUICKNODE_WSS_URL!,
    chainId: parseInt(process.env.BSC_CHAIN_ID || '56', 10),
    network: process.env.BSC_NETWORK || 'mainnet',
    usdtContractAddress: process.env.USDT_CONTRACT_ADDRESS || '0x55d398326f99059fF775485246999027B3197955',
    systemWalletAddress: process.env.SYSTEM_WALLET_ADDRESS!,
    payoutWalletAddress: process.env.PAYOUT_WALLET_ADDRESS!,
    payoutWalletPrivateKey: process.env.PAYOUT_WALLET_PRIVATE_KEY || '', // Empty in dev
    startBlock: process.env.BLOCKCHAIN_START_BLOCK || 'latest',
    confirmationBlocks: parseInt(process.env.BLOCKCHAIN_CONFIRMATION_BLOCKS || '12', 10),
    pollIntervalMs: parseInt(process.env.BLOCKCHAIN_POLL_INTERVAL_MS || '3000', 10),
  },

  // Deposit Levels
  deposits: {
    level1: parseFloat(process.env.DEPOSIT_LEVEL_1 || '10'),
    level2: parseFloat(process.env.DEPOSIT_LEVEL_2 || '50'),
    level3: parseFloat(process.env.DEPOSIT_LEVEL_3 || '100'),
    level4: parseFloat(process.env.DEPOSIT_LEVEL_4 || '150'),
    level5: parseFloat(process.env.DEPOSIT_LEVEL_5 || '300'),
  },

  // Referral Rates
  referrals: {
    level1Rate: parseFloat(process.env.REFERRAL_RATE_LEVEL_1 || '0.03'),
    level2Rate: parseFloat(process.env.REFERRAL_RATE_LEVEL_2 || '0.02'),
    level3Rate: parseFloat(process.env.REFERRAL_RATE_LEVEL_3 || '0.05'),
  },

  // Security
  security: {
    jwtSecret: process.env.JWT_SECRET || 'change-me-in-production',
    sessionSecret: process.env.SESSION_SECRET || 'change-me-in-production',
    bcryptRounds: parseInt(process.env.FINANCIAL_PASSWORD_BCRYPT_ROUNDS || '12', 10),
  },

  // Rate Limiting
  rateLimiting: {
    windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS || '60000', 10),
    maxRequestsPerUser: parseInt(process.env.RATE_LIMIT_MAX_REQUESTS_PER_USER || '30', 10),
    maxRequestsPerIp: parseInt(process.env.RATE_LIMIT_MAX_REQUESTS_PER_IP || '100', 10),
    banDurationMs: parseInt(process.env.RATE_LIMIT_BAN_DURATION_MS || '300000', 10),
  },

  // Background Jobs
  jobs: {
    blockchainMonitor: {
      enabled: process.env.JOB_BLOCKCHAIN_MONITOR_ENABLED !== 'false',
    },
    paymentProcessor: {
      enabled: process.env.JOB_PAYMENT_PROCESSOR_ENABLED !== 'false',
    },
    paymentRetryProcessor: {
      enabled: process.env.JOB_PAYMENT_RETRY_PROCESSOR_ENABLED !== 'false',
    },
    rewardCalculator: {
      enabled: process.env.JOB_REWARD_CALCULATOR_ENABLED !== 'false',
      intervalMinutes: parseInt(process.env.JOB_REWARD_CALCULATOR_INTERVAL_MINUTES || '60', 10),
    },
    backup: {
      enabled: process.env.JOB_BACKUP_ENABLED !== 'false',
      cron: process.env.JOB_BACKUP_CRON || '0 4 * * *',
    },
    logCleanup: {
      enabled: process.env.JOB_LOG_CLEANUP_ENABLED !== 'false',
      cron: process.env.JOB_LOG_CLEANUP_CRON || '0 3 * * 0',
    },
  },

  // Backup
  backup: {
    enabled: process.env.BACKUP_ENABLED !== 'false',
    dir: process.env.BACKUP_DIR || './backups',
    retentionDays: parseInt(process.env.BACKUP_RETENTION_DAYS || '90', 10),
    gitRemote: process.env.BACKUP_GIT_REMOTE || 'origin',
    gitBranch: process.env.BACKUP_GIT_BRANCH || 'main',
    gcsBackupBucket: process.env.GCS_BACKUP_BUCKET,
  },

  // Admin
  admin: {
    panelEnabled: process.env.ADMIN_PANEL_ENABLED !== 'false',
  },

  // Google Cloud Platform
  gcp: {
    projectId: process.env.GCP_PROJECT_ID,
    region: process.env.GCP_REGION || 'us-central1',
    secretManagerEnabled: process.env.GCP_SECRET_MANAGER_ENABLED === 'true',
  },

  // Monitoring & Alerting
  monitoring: {
    sentryDsn: process.env.SENTRY_DSN,
    alertEmail: process.env.ALERT_EMAIL,
    alertTelegramChatId: process.env.ALERT_TELEGRAM_CHAT_ID,
  },

  // Feature Flags
  features: {
    registration: process.env.FEATURE_REGISTRATION_ENABLED !== 'false',
    deposits: process.env.FEATURE_DEPOSITS_ENABLED !== 'false',
    withdrawals: process.env.FEATURE_WITHDRAWALS_ENABLED !== 'false',
    referrals: process.env.FEATURE_REFERRALS_ENABLED !== 'false',
    adminPanel: process.env.FEATURE_ADMIN_PANEL_ENABLED !== 'false',
  },

  // Development flags (DANGEROUS - only for testing!)
  dev: {
    skipBlockchainVerification: process.env.DEV_SKIP_BLOCKCHAIN_VERIFICATION === 'true',
    mockPayments: process.env.DEV_MOCK_PAYMENTS === 'true',
    resetDbOnStart: process.env.DEV_RESET_DB_ON_START === 'true',
  },
} as const;

// Type export for TypeScript
export type AppConfig = typeof config;

export default config;
