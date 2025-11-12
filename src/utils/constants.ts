/**
 * Application Constants
 * Централизованное хранилище всех констант проекта
 */

// Deposit levels (in USDT)
export const DEPOSIT_LEVELS = {
  1: 10,
  2: 50,
  3: 100,
  4: 150,
  5: 300,
} as const;

export type DepositLevel = keyof typeof DEPOSIT_LEVELS;

// Referral commission rates
export const REFERRAL_RATES = {
  1: 0.03, // 3% - Level 1 (direct referrals)
  2: 0.02, // 2% - Level 2 (referrals of referrals)
  3: 0.05, // 5% - Level 3 (third level)
} as const;

export const REFERRAL_DEPTH = 3; // Maximum referral chain depth

// Required referrals per deposit level
// Level 1 = 0 referrals, Level 2 = 1 referral, etc.
export const REQUIRED_REFERRALS_PER_LEVEL: Record<DepositLevel, number> = {
  1: 0,
  2: 1,
  3: 2,
  4: 3,
  5: 4,
};

// BSC blockchain configuration
export const BSC_CONFIG = {
  CHAIN_ID: 56,
  NETWORK_NAME: 'Binance Smart Chain',
  RPC_URLS: ['https://bsc-dataseed.binance.org'],
  BLOCK_EXPLORER: 'https://bscscan.com',
  NATIVE_CURRENCY: {
    name: 'BNB',
    symbol: 'BNB',
    decimals: 18,
  },
  CONFIRMATION_BLOCKS: 12, // Wait for 12 confirmations
  BLOCK_TIME: 3000, // ~3 seconds per block
} as const;

// USDT BEP-20 Contract
export const USDT_CONTRACT = {
  ADDRESS: '0x55d398326f99059fF775485246999027B3197955',
  DECIMALS: 18,
  SYMBOL: 'USDT',
  ABI: [
    'function balanceOf(address owner) view returns (uint256)',
    'function transfer(address to, uint256 amount) returns (bool)',
    'function allowance(address owner, address spender) view returns (uint256)',
    'function approve(address spender, uint256 amount) returns (bool)',
    'event Transfer(address indexed from, address indexed to, uint256 value)',
  ],
} as const;

// Transaction statuses
export enum TransactionStatus {
  PENDING = 'pending',
  CONFIRMED = 'confirmed',
  FAILED = 'failed',
}

// Transaction types
export enum TransactionType {
  DEPOSIT = 'deposit',
  WITHDRAWAL = 'withdrawal',
  REFERRAL_REWARD = 'referral_reward',
  DEPOSIT_REWARD = 'deposit_reward',
  SYSTEM_PAYOUT = 'system_payout',
}

// User action types (для логирования)
export enum UserActionType {
  // Registration
  REGISTRATION_STARTED = 'registration_started',
  REGISTRATION_COMPLETED = 'registration_completed',
  VERIFICATION_COMPLETED = 'verification_completed',

  // Deposits
  DEPOSIT_VIEWED = 'deposit_viewed',
  DEPOSIT_INITIATED = 'deposit_initiated',
  DEPOSIT_CONFIRMED = 'deposit_confirmed',

  // Referrals
  REFERRAL_LINK_GENERATED = 'referral_link_generated',
  REFERRAL_STATS_VIEWED = 'referral_stats_viewed',

  // Profile
  PROFILE_VIEWED = 'profile_viewed',
  PROFILE_UPDATED = 'profile_updated',

  // Admin
  ADMIN_LOGIN = 'admin_login',
  ADMIN_BROADCAST = 'admin_broadcast',
  ADMIN_USER_BANNED = 'admin_user_banned',
  ADMIN_USER_UNBANNED = 'admin_user_unbanned',
}

// Rate limiting configuration
export const RATE_LIMITS = {
  USER: {
    WINDOW_MS: 60000, // 1 minute
    MAX_REQUESTS: 30,
    BAN_DURATION_MS: 300000, // 5 minutes
  },
  IP: {
    WINDOW_MS: 60000,
    MAX_REQUESTS: 100,
    BAN_DURATION_MS: 600000, // 10 minutes
  },
  REGISTRATION: {
    WINDOW_MS: 3600000, // 1 hour
    MAX_REQUESTS: 3,
  },
  DEPOSIT: {
    WINDOW_MS: 300000, // 5 minutes
    MAX_REQUESTS: 5,
  },
} as const;

// Bot messages
export const BOT_MESSAGES = {
  WELCOME: `
Здравствуйте — мы против километров текста.
Сначала ознакомьтесь с нашими продуктами на сайте, чтобы понимать как всё устроено и работает.
Потом возвращайтесь в бот и начинайте зарабатывать.
🌐 https://sigmatrade.org/index.html#exchange
  `.trim(),

  REGISTRATION_START: `
📝 Регистрация

Для регистрации укажите адрес вашего кошелька в сети Binance Smart Chain (BEP-20).

⚠️ Убедитесь, что адрес указан правильно! Этот адрес будет использоваться для всех операций.

Формат адреса: 0x...
  `.trim(),

  VERIFICATION_START: `
✅ Верификация

Ваша верификация пройдена успешно!

🔐 Ваш финансовый пароль: {password}

⚠️ ВАЖНО: Сохраните этот пароль в надежном месте! Он понадобится для важных операций.

📞 Желаете оставить контактные данные для обратной связи?
  `.trim(),

  DEPOSIT_INFO: `
💰 Депозитные планы

У нас действует 5 уровней депозитов:

1️⃣ Уровень 1: {level1} USDT
2️⃣ Уровень 2: {level2} USDT (требуется 1 реферал)
3️⃣ Уровень 3: {level3} USDT (требуется 2 реферала)
4️⃣ Уровень 4: {level4} USDT (требуется 3 реферала)
5️⃣ Уровень 5: {level5} USDT (требуется 4 реферала)

📌 Важно: активировать уровни можно только последовательно, снизу вверх.
  `.trim(),

  REFERRAL_INFO: `
🤝 Реферальная программа

Приглашайте друзей и зарабатывайте:

1️⃣ Уровень 1 (прямые партнеры): 3%
2️⃣ Уровень 2 (партнеры партнеров): 2%
3️⃣ Уровень 3 (третий уровень): 5%

Ваша реферальная ссылка:
{referralLink}

📊 Поделитесь ссылкой и начните зарабатывать!
  `.trim(),

  ADMIN_WELCOME: `
👑 Панель администратора

Добро пожаловать в админ-панель SigmaTrade Bot.
  `.trim(),
} as const;

// Keyboard button labels
export const BUTTON_LABELS = {
  // Main menu
  PROFILE: '👤 Профиль',
  DEPOSITS: '💰 Депозиты',
  WITHDRAWALS: '💸 Вывод средств',
  REFERRALS: '🤝 Рефералы',
  TRANSACTIONS: '📊 История транзакций',
  SUPPORT: '🆘 Техподдержка',
  HELP: '❓ Помощь',
  ADMIN_PANEL: '👑 Админ-панель',

  // Registration
  START_REGISTRATION: '📝 Начать регистрацию',
  VERIFY: '✅ Пройти верификацию',

  // Deposits
  DEPOSIT_LEVEL_1: `💵 ${DEPOSIT_LEVELS[1]} USDT`,
  DEPOSIT_LEVEL_2: `💵 ${DEPOSIT_LEVELS[2]} USDT`,
  DEPOSIT_LEVEL_3: `💵 ${DEPOSIT_LEVELS[3]} USDT`,
  DEPOSIT_LEVEL_4: `💵 ${DEPOSIT_LEVELS[4]} USDT`,
  DEPOSIT_LEVEL_5: `💵 ${DEPOSIT_LEVELS[5]} USDT`,
  DEPOSIT_HISTORY: '📜 История депозитов',

  // Referrals
  MY_REFERRAL_LINK: '🔗 Моя реферальная ссылка',
  REFERRAL_STATS: '📊 Статистика рефералов',
  REFERRAL_EARNINGS: '💸 Мои доходы',
  REFERRAL_LEADERBOARD: '🏆 Таблица лидеров',

  // Admin
  BROADCAST_MESSAGE: '📢 Рассылка всем',
  SEND_TO_USER: '✉️ Отправить пользователю',
  BAN_USER: '🚫 Забанить пользователя',
  UNBAN_USER: '✅ Разбанить пользователя',
  PROMOTE_ADMIN: '👑 Назначить админа',
  PENDING_WITHDRAWALS: '💸 Заявки на вывод',
  PLATFORM_STATS: '📊 Статистика платформы',

  // Navigation
  BACK: '◀️ Назад',
  CANCEL: '❌ Отмена',
  MAIN_MENU: '🏠 Главное меню',
} as const;

// Error messages
export const ERROR_MESSAGES = {
  INVALID_WALLET_ADDRESS: '❌ Неверный формат адреса кошелька. Адрес должен начинаться с 0x и содержать 42 символа.',
  WALLET_ALREADY_REGISTERED: '❌ Этот кошелек уже зарегистрирован.',
  USER_NOT_REGISTERED: '❌ Вы не зарегистрированы. Используйте /start для регистрации.',
  USER_NOT_VERIFIED: '❌ Пожалуйста, пройдите верификацию.',
  USER_BANNED: 'Здравствуйте. Мы обнаружили, что вы нарушаете правила нашего сообщества и политику безопасности, в связи с чем мы терминируем ваш аккаунт и деактивируем вашу реферальную ссылку.',
  INSUFFICIENT_REFERRALS: '❌ Недостаточно рефералов для активации этого уровня.',
  PREVIOUS_LEVEL_NOT_ACTIVATED: '❌ Сначала активируйте предыдущий уровень депозита.',
  DEPOSIT_ALREADY_ACTIVATED: '❌ Этот уровень депозита уже активирован.',
  RATE_LIMIT_EXCEEDED: '❌ Слишком много запросов. Пожалуйста, подождите.',
  INTERNAL_ERROR: '❌ Внутренняя ошибка. Пожалуйста, попробуйте позже.',
  ADMIN_ONLY: '❌ Эта команда доступна только администраторам.',
  INVALID_INPUT: '❌ Неверный формат данных.',
} as const;

// Success messages
export const SUCCESS_MESSAGES = {
  REGISTRATION_COMPLETE: '✅ Регистрация завершена успешно!',
  VERIFICATION_COMPLETE: '✅ Верификация пройдена!',
  DEPOSIT_DETECTED: '✅ Депозит обнаружен и обрабатывается.',
  DEPOSIT_CONFIRMED: '✅ Депозит подтвержден! Уровень {level} активирован.',
  REFERRAL_REWARD_SENT: '✅ Реферальное вознаграждение отправлено.',
  USER_BANNED: '✅ Пользователь заблокирован.',
  USER_UNBANNED: '✅ Пользователь разблокирован.',
  ADMIN_PROMOTED: '✅ Пользователь назначен администратором.',
  BROADCAST_SENT: '✅ Сообщение отправлено всем пользователям.',
} as const;

// Database TTL configuration
export const DB_TTL = {
  USER_ACTIONS: 7 * 24 * 60 * 60 * 1000, // 7 days in milliseconds
  RATE_LIMIT_LOG: 7 * 24 * 60 * 60 * 1000, // 7 days
} as const;

// Backup configuration
export const BACKUP_CONFIG = {
  RETENTION_DAYS: 90,
  CRON_SCHEDULE: '0 4 * * *', // Daily at 4 AM
  GIT_COMMIT_MESSAGE: (timestamp: string) => `Automated backup ${timestamp}`,
} as const;

// Log cleanup configuration
export const LOG_CLEANUP_CONFIG = {
  CRON_SCHEDULE: '0 3 * * 0', // Weekly on Sunday at 3 AM
} as const;

// Regex patterns
export const REGEX_PATTERNS = {
  BSC_ADDRESS: /^0x[a-fA-F0-9]{40}$/,
  TRANSACTION_HASH: /^0x[a-fA-F0-9]{64}$/,
  EMAIL: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
  PHONE: /^\+?[1-9]\d{1,14}$/,
  TELEGRAM_USERNAME: /^@?[a-zA-Z0-9_]{5,32}$/,
} as const;

// Financial password configuration
export const FINANCIAL_PASSWORD_CONFIG = {
  LENGTH: 12,
  CHARSET: 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%^&*',
  BCRYPT_ROUNDS: 12,
} as const;

// Session states (для FSM в боте)
export enum BotState {
  IDLE = 'idle',
  AWAITING_WALLET_ADDRESS = 'awaiting_wallet_address',
  AWAITING_CONTACT_INFO = 'awaiting_contact_info',
  AWAITING_WITHDRAWAL_AMOUNT = 'awaiting_withdrawal_amount',
  AWAITING_WITHDRAWAL_FINANCIAL_PASSWORD = 'awaiting_withdrawal_financial_password',
  AWAITING_ADMIN_BROADCAST_MESSAGE = 'awaiting_admin_broadcast_message',
  AWAITING_ADMIN_USER_MESSAGE = 'awaiting_admin_user_message',
  AWAITING_ADMIN_USER_TO_BAN = 'awaiting_admin_user_to_ban',
  AWAITING_ADMIN_USER_TO_UNBAN = 'awaiting_admin_user_to_unban',
  AWAITING_ADMIN_USER_TO_PROMOTE = 'awaiting_admin_user_to_promote',
  AWAITING_ADMIN_MASTER_KEY = 'awaiting_admin_master_key',
  AWAITING_REWARD_SESSION_DATA = 'awaiting_reward_session_data',
  AWAITING_ADMIN_BLACKLIST_ADD = 'awaiting_admin_blacklist_add',
  AWAITING_ADMIN_BLACKLIST_REMOVE = 'awaiting_admin_blacklist_remove',
  AWAITING_SUPPORT_CATEGORY = 'awaiting_support_category',
  AWAITING_SUPPORT_INPUT = 'awaiting_support_input',
  AWAITING_ADMIN_SUPPORT_REPLY = 'awaiting_admin_support_reply',
}

// Cache TTL (Redis)
export const CACHE_TTL = {
  USER_DATA: 300, // 5 minutes
  DEPOSIT_LEVELS: 300, // 5 minutes
  REFERRAL_COUNT: 600, // 10 minutes
  LAST_PROCESSED_BLOCK: 60, // 1 minute
} as const;

// Job configuration
export const JOB_CONFIG = {
  BLOCKCHAIN_MONITOR: {
    ENABLED: true,
    CONCURRENCY: 1, // Single instance
  },
  PAYMENT_PROCESSOR: {
    ENABLED: true,
    CONCURRENCY: 3, // Process 3 payments simultaneously
    RETRY_ATTEMPTS: 3,
    RETRY_DELAY: 5000, // 5 seconds
  },
  REFERRAL_CALCULATOR: {
    ENABLED: true,
    CONCURRENCY: 2,
  },
  BACKUP: {
    ENABLED: true,
    CONCURRENCY: 1,
  },
  LOG_CLEANUP: {
    ENABLED: true,
    CONCURRENCY: 1,
  },
} as const;

// Gas configuration for BSC
export const GAS_CONFIG = {
  PRICE_GWEI: 5, // Default gas price in Gwei
  LIMIT_TRANSFER: 100000, // Gas limit for USDT transfer
  PRICE_MULTIPLIER: 1.1, // Multiply gas price by 10% for faster confirmation
} as const;

// Health check endpoints
export const HEALTH_CHECK = {
  PATH: '/health',
  TIMEOUT: 5000,
} as const;

// Export all as a single object for convenience
export const CONSTANTS = {
  DEPOSIT_LEVELS,
  REFERRAL_RATES,
  REFERRAL_DEPTH,
  REQUIRED_REFERRALS_PER_LEVEL,
  BSC_CONFIG,
  USDT_CONTRACT,
  RATE_LIMITS,
  BOT_MESSAGES,
  BUTTON_LABELS,
  ERROR_MESSAGES,
  SUCCESS_MESSAGES,
  DB_TTL,
  BACKUP_CONFIG,
  LOG_CLEANUP_CONFIG,
  REGEX_PATTERNS,
  FINANCIAL_PASSWORD_CONFIG,
  CACHE_TTL,
  JOB_CONFIG,
  GAS_CONFIG,
  HEALTH_CHECK,
} as const;
