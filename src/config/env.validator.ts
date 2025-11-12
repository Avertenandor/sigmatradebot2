import { z } from 'zod';
import { logger } from '../utils/logger.util';

/**
 * Схема валидации обязательных переменных окружения
 */
const envSchema = z
  .object({
    // Node environment
    NODE_ENV: z.enum(['development', 'production', 'test']).default('development'),

    // Telegram Bot
    BOT_TOKEN: z.string().min(30, 'BOT_TOKEN должен быть минимум 30 символов'),
    TELEGRAM_WEBHOOK_SECRET: z
      .string()
      .min(16, 'TELEGRAM_WEBHOOK_SECRET должен быть минимум 16 символов')
      .optional(),

    // Database
    DB_HOST: z.string().min(1, 'DB_HOST обязателен'),
    DB_PORT: z.string().regex(/^\d+$/, 'DB_PORT должен быть числом').default('5432'),
    DB_USER: z.string().min(1, 'DB_USER обязателен'),
    DB_PASSWORD: z.string().min(1, 'DB_PASSWORD обязателен'),
    DB_NAME: z.string().min(1, 'DB_NAME обязателен'),

    // Redis
    REDIS_HOST: z.string().min(1, 'REDIS_HOST обязателен'),
    REDIS_PORT: z.string().regex(/^\d+$/, 'REDIS_PORT должен быть числом').default('6379'),
    REDIS_PASSWORD: z.string().optional(),

    // Blockchain (QuickNode)
    QUICKNODE_HTTPS_URL: z.string().url('QUICKNODE_HTTPS_URL должен быть валидным URL'),
    QUICKNODE_WSS_URL: z.string().url('QUICKNODE_WSS_URL должен быть валидным URL'),

    // System Wallet (for receiving deposits)
    SYSTEM_WALLET_ADDRESS: z
      .string()
      .regex(/^0x[a-fA-F0-9]{40}$/, 'SYSTEM_WALLET_ADDRESS должен быть валидным Ethereum адресом'),
    SYSTEM_WALLET_PRIVATE_KEY: z
      .string()
      .regex(/^(0x)?[a-fA-F0-9]{64}$/, 'SYSTEM_WALLET_PRIVATE_KEY должен быть валидным приватным ключом'),

    // USDT Contract Address (BSC)
    USDT_CONTRACT_ADDRESS: z
      .string()
      .regex(/^0x[a-fA-F0-9]{40}$/, 'USDT_CONTRACT_ADDRESS должен быть валидным адресом контракта')
      .default('0x55d398326f99059fF775485246999027B3197955'),

    // Encryption key for PII (optional in dev, required in production)
    ENCRYPTION_KEY: z
      .string()
      .regex(/^[a-fA-F0-9]{64}$/, 'ENCRYPTION_KEY должен быть 64 hex символа (32 байта)')
      .optional(),

    // Optional: BSCScan API Key
    BSCSCAN_API_KEY: z.string().optional(),

    // Optional: Admin Telegram IDs (comma-separated)
    ADMIN_TELEGRAM_IDS: z.string().optional(),

    // Optional: Deposit tolerance in USDT (default: 0.01)
    DEPOSIT_AMOUNT_TOLERANCE: z
      .string()
      .regex(/^\d+(\.\d+)?$/, 'DEPOSIT_AMOUNT_TOLERANCE должен быть числом')
      .default('0.01'),

    // Optional: Monitoring
    PROMETHEUS_PORT: z.string().regex(/^\d+$/).default('9090'),
    HEALTH_CHECK_PORT: z.string().regex(/^\d+$/).default('3000'),
  })
  .refine(
    (data) => {
      // В production TELEGRAM_WEBHOOK_SECRET обязателен
      if (data.NODE_ENV === 'production' && !data.TELEGRAM_WEBHOOK_SECRET) {
        return false;
      }
      return true;
    },
    {
      message:
        'TELEGRAM_WEBHOOK_SECRET обязателен в production окружении для защиты webhook от подделки',
      path: ['TELEGRAM_WEBHOOK_SECRET'],
    }
  )
  .refine(
    (data) => {
      // В production ENCRYPTION_KEY обязателен
      if (data.NODE_ENV === 'production' && !data.ENCRYPTION_KEY) {
        return false;
      }
      return true;
    },
    {
      message:
        'ENCRYPTION_KEY обязателен в production окружении для шифрования персональных данных (GDPR compliance)',
      path: ['ENCRYPTION_KEY'],
    }
  );

export type EnvConfig = z.infer<typeof envSchema>;

/**
 * Валидирует переменные окружения при старте приложения
 * При отсутствии обязательных переменных - завершает процесс с ошибкой
 */
export function validateEnv(): EnvConfig {
  console.log('🔍 Валидация переменных окружения...');

  try {
    const validated = envSchema.parse(process.env);

    console.log('✅ Все обязательные переменные окружения присутствуют');
    console.log(`📦 Окружение: ${validated.NODE_ENV}`);
    console.log(`🗄️  База данных: ${validated.DB_HOST}:${validated.DB_PORT}/${validated.DB_NAME}`);
    console.log(`🔴 Redis: ${validated.REDIS_HOST}:${validated.REDIS_PORT}`);
    console.log(`⛓️  QuickNode: ${validated.QUICKNODE_HTTPS_URL.substring(0, 30)}...`);
    console.log(`💼 System Wallet: ${validated.SYSTEM_WALLET_ADDRESS}`);

    // Предупреждения только для development окружения
    const isProduction = validated.NODE_ENV === 'production';

    if (!isProduction) {
      if (!validated.TELEGRAM_WEBHOOK_SECRET) {
        console.warn(
          '⚠️  TELEGRAM_WEBHOOK_SECRET не установлен - webhook не будет защищён от подделки'
        );
      }

      if (!validated.ENCRYPTION_KEY) {
        console.warn(
          '⚠️  ENCRYPTION_KEY не установлен - PII данные (телефон, email) не будут зашифрованы'
        );
      }
    } else {
      // В production эти переменные обязательны (проверено в refine)
      console.log('🔒 Webhook security: enabled');
      console.log('🔐 PII encryption: enabled');
    }

    if (!validated.ADMIN_TELEGRAM_IDS) {
      console.warn('⚠️  ADMIN_TELEGRAM_IDS не установлен - админ-функции будут недоступны');
    }

    return validated;
  } catch (error) {
    if (error instanceof z.ZodError) {
      console.error('\n❌ ОШИБКА: Отсутствуют или невалидны обязательные переменные окружения:\n');

      error.errors.forEach((err) => {
        const path = err.path.join('.');
        console.error(`  • ${path}: ${err.message}`);
      });

      console.error('\n📝 Проверьте файл .env и убедитесь, что все переменные заполнены корректно.');
      console.error('📖 Пример: .env.example\n');

      // Завершаем процесс с ошибкой
      process.exit(1);
    }

    // Неожиданная ошибка
    console.error('❌ Неожиданная ошибка при валидации окружения:', error);
    process.exit(1);
  }
}

/**
 * Получить валидированную конфигурацию окружения
 * Использовать после вызова validateEnv()
 */
let cachedConfig: EnvConfig | null = null;

export function getEnvConfig(): EnvConfig {
  if (!cachedConfig) {
    cachedConfig = validateEnv();
  }
  return cachedConfig;
}

/**
 * Проверить, является ли окружение production
 */
export function isProduction(): boolean {
  return getEnvConfig().NODE_ENV === 'production';
}

/**
 * Проверить, является ли окружение development
 */
export function isDevelopment(): boolean {
  return getEnvConfig().NODE_ENV === 'development';
}

/**
 * Получить список админских Telegram ID
 */
export function getAdminTelegramIds(): number[] {
  const config = getEnvConfig();
  if (!config.ADMIN_TELEGRAM_IDS) {
    return [];
  }

  return config.ADMIN_TELEGRAM_IDS.split(',')
    .map((id) => parseInt(id.trim(), 10))
    .filter((id) => !isNaN(id));
}
