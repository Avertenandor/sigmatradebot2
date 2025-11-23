# SigmaTrade DeFi Telegram Bot - Архитектурный План

## 📋 Содержание
1. [Обзор проекта](#обзор-проекта)
2. [Технологический стек](#технологический-стек)
3. [Архитектура системы](#архитектура-системы)
4. [База данных](#база-данных)
5. [Безопасность и DDoS защита](#безопасность-и-ddos-защита)
6. [Блокчейн интеграция](#блокчейн-интеграция)
7. [План разработки](#план-разработки)
8. [Деплоймент на Google Cloud](#деплоймент-на-google-cloud)
9. [Риски и митигация](#риски-и-митигация)

---

## 🎯 Обзор проекта

### Назначение
DeFi Telegram бот для управления депозитами в USDT (BEP-20) с многоуровневой реферальной системой и автоматическим мониторингом блокчейна.

### Ключевые функции
- ✅ Регистрация пользователей с BSC адресом
- ✅ Система депозитов (10, 50, 100, 150, 300 USDT)
- ✅ 3-уровневая реферальная программа (3%, 2%, 5%)
- ✅ Автоматический мониторинг BSC блокчейна через QuickNode
- ✅ Автоматические выплаты реферальных вознаграждений
- ✅ Админ-панель
- ✅ Защита от DDoS атак

---

## 🛠 Технологический стек

### Backend
```yaml
Runtime: Node.js 20 LTS
Language: TypeScript 5.x
Bot Framework: telegraf 4.x
Blockchain: ethers.js 6.x
ORM: TypeORM 0.3.x
API: Express.js 4.x
Queue: Bull 4.x (Redis-based)
Scheduler: node-cron 3.x
Validation: joi 17.x
Logging: winston 3.x
```

### Database & Cache
```yaml
Primary DB: PostgreSQL 15
Cache/Rate Limiting: Redis 7
Backup: pg_dump + git
```

### Infrastructure
```yaml
Containerization: Docker + Docker Compose
Process Manager: PM2
Reverse Proxy: nginx
Cloud Provider: Google Cloud Platform
  - Compute Engine (VM)
  - Cloud SQL (PostgreSQL)
  - Memorystore (Redis)
  - Cloud Storage (backups)
  - Cloud Scheduler (cron jobs)
```

### Blockchain
```yaml
Network: Binance Smart Chain (BSC)
Node Provider: QuickNode (WebSocket + HTTP)
Token: USDT BEP-20 (0x55d398326f99059fF775485246999027B3197955)
Libraries: ethers.js 6.x, web3-utils
```

---

## 🏗 Архитектура системы

### Микросервисная архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    NGINX (Reverse Proxy)                     │
│              Rate Limiting + DDoS Protection                 │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼────────┐  ┌─────────▼────────┐  ┌────────▼────────┐
│  Telegram Bot  │  │ Blockchain       │  │  Admin API      │
│    Service     │  │   Monitor        │  │   Service       │
│   (telegraf)   │  │  (WebSocket)     │  │  (Express)      │
└───────┬────────┘  └─────────┬────────┘  └────────┬────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   Business Logic   │
                    │      Layer         │
                    │  - User Service    │
                    │  - Deposit Service │
                    │  - Referral Calc   │
                    │  - Payment Proc    │
                    └─────────┬──────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼────────┐  ┌─────────▼────────┐  ┌────────▼────────┐
│  PostgreSQL    │  │     Redis         │  │   Bull Queue    │
│   Database     │  │  Cache + Rate     │  │  (Background    │
│                │  │    Limiting       │  │     Jobs)       │
└────────────────┘  └───────────────────┘  └─────────────────┘
```

### Модульная структура проекта

```
sigmatradebot/
├── src/
│   ├── bot/                      # Telegram bot
│   │   ├── handlers/             # Обработчики команд и кнопок
│   │   │   ├── start.handler.ts
│   │   │   ├── registration.handler.ts
│   │   │   ├── verification.handler.ts
│   │   │   ├── deposit.handler.ts
│   │   │   ├── referral.handler.ts
│   │   │   └── admin.handler.ts
│   │   ├── keyboards/            # Клавиатуры
│   │   │   ├── main.keyboard.ts
│   │   │   ├── admin.keyboard.ts
│   │   │   └── deposit.keyboard.ts
│   │   ├── middlewares/          # Middleware для бота
│   │   │   ├── auth.middleware.ts
│   │   │   ├── admin.middleware.ts
│   │   │   ├── rate-limit.middleware.ts
│   │   │   └── logger.middleware.ts
│   │   └── index.ts              # Bot entry point
│   │
│   ├── blockchain/               # Blockchain интеграция
│   │   ├── monitor.service.ts    # Мониторинг блоков BSC
│   │   ├── transaction.service.ts # Работа с транзакциями
│   │   ├── wallet.service.ts     # Управление кошельками
│   │   └── usdt.contract.ts      # USDT BEP-20 контракт
│   │
│   ├── services/                 # Бизнес-логика
│   │   ├── user.service.ts       # Управление пользователями
│   │   ├── deposit.service.ts    # Логика депозитов
│   │   ├── referral.service.ts   # Реферальная система
│   │   ├── payment.service.ts    # Платежный процессор
│   │   ├── admin.service.ts      # Админ функции
│   │   └── backup.service.ts     # Бэкапы
│   │
│   ├── database/                 # Database layer
│   │   ├── entities/             # TypeORM entities
│   │   │   ├── User.entity.ts
│   │   │   ├── Wallet.entity.ts
│   │   │   ├── Deposit.entity.ts
│   │   │   ├── Transaction.entity.ts
│   │   │   ├── Referral.entity.ts
│   │   │   ├── UserAction.entity.ts
│   │   │   └── Admin.entity.ts
│   │   ├── repositories/         # Custom repositories
│   │   ├── migrations/           # DB migrations
│   │   └── data-source.ts        # TypeORM config
│   │
│   ├── jobs/                     # Background jobs (Bull)
│   │   ├── blockchain-monitor.job.ts
│   │   ├── payment-processor.job.ts
│   │   ├── referral-calculator.job.ts
│   │   ├── backup.job.ts
│   │   └── log-cleanup.job.ts
│   │
│   ├── utils/                    # Утилиты
│   │   ├── validation.util.ts    # Валидация данных
│   │   ├── crypto.util.ts        # Криптография
│   │   ├── logger.util.ts        # Логирование
│   │   └── constants.ts          # Константы
│   │
│   ├── config/                   # Конфигурация
│   │   ├── bot.config.ts
│   │   ├── database.config.ts
│   │   ├── blockchain.config.ts
│   │   └── security.config.ts
│   │
│   └── index.ts                  # Main entry point
│
├── tests/                        # Тесты
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── docker/                       # Docker конфигурация
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── nginx.conf
│   └── .dockerignore
│
├── scripts/                      # Скрипты
│   ├── deploy.sh
│   ├── backup.sh
│   └── migrate.sh
│
├── backups/                      # Локальные бэкапы (git)
│   └── .gitkeep
│
├── .env.example                  # Пример env файла
├── .gitignore
├── package.json
├── tsconfig.json
├── README.md
└── ARCHITECTURE.md
```

---

## 🗄 База данных

### PostgreSQL Schema

#### Постоянные таблицы (хранятся вечно)

**users** - Основная таблица пользователей
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    wallet_address VARCHAR(42) UNIQUE NOT NULL,
    financial_password VARCHAR(255) NOT NULL,  -- bcrypt hashed
    phone VARCHAR(20),
    email VARCHAR(255),
    referrer_id INTEGER REFERENCES users(id),
    is_verified BOOLEAN DEFAULT FALSE,
    is_banned BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_users_wallet ON users(wallet_address);
CREATE INDEX idx_users_referrer ON users(referrer_id);
```

**deposits** - История депозитов
```sql
CREATE TABLE deposits (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    level INTEGER NOT NULL CHECK (level BETWEEN 1 AND 5),
    amount DECIMAL(18, 8) NOT NULL,
    tx_hash VARCHAR(66) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- pending, confirmed, failed
    block_number BIGINT,
    confirmed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_deposits_user ON deposits(user_id);
CREATE INDEX idx_deposits_tx_hash ON deposits(tx_hash);
CREATE INDEX idx_deposits_level ON deposits(level);
```

**transactions** - Все транзакции (входящие и исходящие)
```sql
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    tx_hash VARCHAR(66) UNIQUE NOT NULL,
    type VARCHAR(20) NOT NULL, -- deposit, referral_reward, system_payout
    amount DECIMAL(18, 8) NOT NULL,
    from_address VARCHAR(42),
    to_address VARCHAR(42),
    block_number BIGINT,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_transactions_user ON transactions(user_id);
CREATE INDEX idx_transactions_type ON transactions(type);
CREATE INDEX idx_transactions_tx_hash ON transactions(tx_hash);
```

**referrals** - Реферальная структура
```sql
CREATE TABLE referrals (
    id SERIAL PRIMARY KEY,
    referrer_id INTEGER NOT NULL REFERENCES users(id),
    referral_id INTEGER NOT NULL REFERENCES users(id),
    level INTEGER NOT NULL CHECK (level BETWEEN 1 AND 3),
    total_earned DECIMAL(18, 8) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(referrer_id, referral_id)
);

CREATE INDEX idx_referrals_referrer ON referrals(referrer_id);
CREATE INDEX idx_referrals_referral ON referrals(referral_id);
```

**referral_earnings** - История реферальных выплат
```sql
CREATE TABLE referral_earnings (
    id SERIAL PRIMARY KEY,
    referral_id INTEGER NOT NULL REFERENCES referrals(id),
    amount DECIMAL(18, 8) NOT NULL,
    source_transaction_id INTEGER REFERENCES transactions(id),
    tx_hash VARCHAR(66),
    paid BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**admins** - Администраторы
```sql
CREATE TABLE admins (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    role VARCHAR(20) DEFAULT 'admin', -- admin, super_admin
    created_by INTEGER REFERENCES admins(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Временные таблицы (ротация 7 дней)

**user_actions** - Действия пользователей (TTL: 7 дней)
```sql
CREATE TABLE user_actions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action_type VARCHAR(50) NOT NULL,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_user_actions_created ON user_actions(created_at);
CREATE INDEX idx_user_actions_user ON user_actions(user_id);

-- Автоматическое удаление старых записей
CREATE OR REPLACE FUNCTION delete_old_user_actions()
RETURNS void AS $$
BEGIN
    DELETE FROM user_actions WHERE created_at < NOW() - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;
```

**rate_limit_log** - Логи rate limiting (TTL: 7 дней)
```sql
CREATE TABLE rate_limit_log (
    id SERIAL PRIMARY KEY,
    identifier VARCHAR(255) NOT NULL, -- IP or telegram_id
    endpoint VARCHAR(100),
    attempts INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rate_limit_created ON rate_limit_log(created_at);
```

### Redis Структура

```javascript
// Rate Limiting
`rate_limit:user:${telegramId}` // TTL: 1 minute
`rate_limit:ip:${ipAddress}` // TTL: 1 minute

// Session management
`session:${telegramId}` // User state in conversation flow

// Cache
`user:${userId}` // User data cache, TTL: 5 minutes
`deposit:levels:${userId}` // User deposit levels, TTL: 5 minutes
`referrals:${userId}` // Referral count, TTL: 5 minutes

// Blockchain monitoring
`last_processed_block` // Last processed block number
`pending_deposits:${txHash}` // Pending deposit verification

// Admin sessions
`admin:session:${telegramId}` // Admin action state
```

---

## 🔒 Безопасность и DDoS защита

### Многоуровневая защита

#### 1. Network Layer (L3/L4)
```yaml
Google Cloud Armor:
  - IP-based rate limiting
  - Geo-blocking (опционально)
  - DDoS protection rules
  - Adaptive protection (auto-scaling)

nginx:
  - Connection limiting
  - Request rate limiting
  - Timeout configuration
```

#### 2. Application Layer (L7)
```typescript
// Rate Limiting Strategy
const rateLimitConfig = {
  // Per user (Telegram ID)
  user: {
    windowMs: 60000,        // 1 minute
    maxRequests: 30,        // 30 requests per minute
    blockDuration: 300000   // 5 minutes ban
  },

  // Per IP address
  ip: {
    windowMs: 60000,
    maxRequests: 100,
    blockDuration: 600000   // 10 minutes ban
  },

  // Registration endpoint
  registration: {
    windowMs: 3600000,      // 1 hour
    maxRequests: 3,         // 3 registrations per hour
  },

  // Deposit operations
  deposit: {
    windowMs: 300000,       // 5 minutes
    maxRequests: 5,         // 5 deposit checks per 5 min
  }
};
```

#### 3. Bot-specific Protection
```typescript
// Anti-spam middleware
- Flood protection (max messages per second)
- Command cooldown (delay between commands)
- Captcha для новых пользователей (опционально)
- Honeypot techniques (fake commands)
```

#### 4. Database Protection
```typescript
// Connection pooling
maxConnections: 20
minConnections: 5
acquireTimeout: 30000

// Query timeout
queryTimeout: 10000

// Prepared statements (защита от SQL injection)
- TypeORM parameterized queries
```

#### 5. Blockchain Protection
```typescript
// QuickNode rate limiting awareness
- Queue blockchain requests
- Batch processing
- Exponential backoff on failures
- Failover to backup node
```

### Валидация входных данных

```typescript
// Wallet address validation
const walletSchema = Joi.string()
  .pattern(/^0x[a-fA-F0-9]{40}$/)
  .required();

// Financial password validation
const passwordSchema = Joi.string()
  .min(8)
  .max(32)
  .pattern(/^[a-zA-Z0-9!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]*$/);

// Email validation
const emailSchema = Joi.string().email();

// Phone validation
const phoneSchema = Joi.string().pattern(/^\+?[1-9]\d{1,14}$/);
```

### Безопасное хранение секретов

```yaml
Secrets Management:
  Private Keys:
    - Google Cloud Secret Manager
    - Encrypted at rest
    - Rotation policy: 90 days

  API Keys:
    - Environment variables
    - Never committed to git
    - Separate keys for dev/staging/prod

  Database Credentials:
    - Cloud SQL IAM authentication
    - Automatic credential rotation

  Financial Passwords:
    - bcrypt hashing (cost factor: 12)
    - Salted hashes
```

---

## ⛓ Блокчейн интеграция

### QuickNode Configuration

```typescript
// WebSocket для real-time мониторинга
const wsProvider = new ethers.WebSocketProvider(
  process.env.QUICKNODE_WSS_URL
);

// HTTP для отправки транзакций
const httpProvider = new ethers.JsonRpcProvider(
  process.env.QUICKNODE_HTTPS_URL
);

// Failover configuration
const providers = [
  quicknodeProvider,
  backupProvider1, // BSC public RPC
  backupProvider2  // Alternative provider
];
```

### Мониторинг блокчейна

```typescript
/**
 * Алгоритм мониторинга:
 * 1. Подписка на новые блоки через WebSocket
 * 2. Для каждого блока получаем все транзакции
 * 3. Фильтруем транзакции по:
 *    - To address = наш системный кошелек
 *    - Token = USDT BEP-20
 * 4. Проверяем sender в нашей БД
 * 5. Валидируем сумму (10/50/100/150/300 USDT)
 * 6. Создаем запись deposit в БД
 * 7. Начисляем реферальные вознаграждения
 * 8. Отправляем уведомление пользователю
 */

interface BlockMonitor {
  startBlock: number;
  systemWallet: string;
  usdtContract: string;

  onNewBlock(block: Block): Promise<void>;
  processTransaction(tx: Transaction): Promise<void>;
  verifyDeposit(deposit: DepositData): Promise<boolean>;
  creditReferralRewards(userId: number, amount: number): Promise<void>;
}
```

### USDT BEP-20 Contract Interface

```typescript
const USDT_ABI = [
  "function balanceOf(address owner) view returns (uint256)",
  "function transfer(address to, uint256 amount) returns (bool)",
  "event Transfer(address indexed from, address indexed to, uint256 value)"
];

const usdtContract = new ethers.Contract(
  "0x55d398326f99059fF775485246999027B3197955",
  USDT_ABI,
  signer
);
```

### Обработка депозитов

```typescript
// Допустимые суммы депозитов (в USDT)
const DEPOSIT_AMOUNTS = {
  1: 10,
  2: 50,
  3: 100,
  4: 150,
  5: 300
};

// Проверка условий для активации уровня
async function canActivateLevel(
  userId: number,
  level: number
): Promise<boolean> {
  // 1. Проверяем что предыдущие уровни активированы
  const previousLevels = await depositRepo.findActivatedLevels(userId);
  if (level > 1 && !previousLevels.includes(level - 1)) {
    return false;
  }

  // 2. Проверяем количество рефералов
  const referralCount = await referralRepo.countDirectReferrals(userId);
  const requiredReferrals = level - 1; // Уровень 2 = 1 реферал, и т.д.

  if (level > 1 && referralCount < requiredReferrals) {
    return false;
  }

  return true;
}
```

### Реферальные выплаты

```typescript
// Комиссии по уровням
const REFERRAL_RATES = {
  1: 0.03,  // 3%
  2: 0.02,  // 2%
  3: 0.05   // 5%
};

async function processReferralRewards(
  userId: number,
  depositAmount: number
): Promise<void> {
  // Получаем всех рефереров до 3 уровня
  const referrers = await getReferralChain(userId, 3);

  for (let level = 1; level <= 3 && level <= referrers.length; level++) {
    const referrer = referrers[level - 1];
    const rewardAmount = depositAmount * REFERRAL_RATES[level];

    // Создаем запись о заработке
    await createReferralEarning(referrer.id, userId, rewardAmount, level);

    // Добавляем в очередь на выплату
    await paymentQueue.add('referral_payout', {
      referrerId: referrer.id,
      amount: rewardAmount,
      level: level
    });
  }
}
```

---

## 📅 План разработки

### Фаза 1: Инфраструктура и Основа (3-5 дней)
- [x] Инициализация проекта
- [ ] Настройка TypeScript + ESLint + Prettier
- [ ] Docker конфигурация (PostgreSQL + Redis)
- [ ] TypeORM setup + entities
- [ ] Database migrations
- [ ] Logger setup (winston)
- [ ] Environment configuration

### Фаза 2: Telegram Bot Core (4-6 дней)
- [ ] Telegraf setup
- [ ] Базовые хендлеры (start, help)
- [ ] Клавиатуры (main, navigation)
- [ ] Middleware (auth, logging, rate-limit)
- [ ] Регистрация пользователя
- [ ] Верификация + генерация финансового пароля
- [ ] Реферальная система (генерация ссылок)

### Фаза 3: Депозитная система (5-7 дней)
- [ ] Логика уровней депозитов
- [ ] Проверка условий активации
- [ ] UI для выбора депозита
- [ ] Отображение требований (рефералы)
- [ ] История депозитов пользователя

### Фаза 4: Blockchain Integration (7-10 дней)
- [ ] QuickNode connection (WebSocket + HTTP)
- [ ] USDT contract integration
- [ ] Block monitor service
- [ ] Transaction detection
- [ ] Deposit verification
- [ ] Event handling (Transfer events)
- [ ] Wallet management
- [ ] Payment processor (реферальные выплаты)

### Фаза 5: Реферальная система (3-5 дней)
- [ ] Расчет реферальных вознаграждений
- [ ] Многоуровневая структура (3 уровня)
- [ ] Автоматические выплаты
- [ ] Статистика рефералов
- [ ] UI для просмотра рефералов

### Фаза 6: Админ панель (4-5 дней)
- [ ] Admin middleware
- [ ] Массовая рассылка
- [ ] Отправка сообщения конкретному пользователю
- [ ] Бан/разбан пользователей
- [ ] Назначение администраторов
- [ ] Статистика платформы
- [ ] Логи действий

### Фаза 7: Безопасность и DDoS защита (5-7 дней)
- [ ] Rate limiting (Redis-based)
- [ ] Input validation (joi)
- [ ] Anti-spam middleware
- [ ] nginx configuration
- [ ] Security headers (helmet)
- [ ] Secrets management
- [ ] Audit logging

### Фаза 8: Background Jobs (3-4 дня)
- [ ] Bull queue setup
- [ ] Blockchain monitor job
- [ ] Payment processor job
- [ ] Referral calculator job
- [ ] Backup job (ежедневный)
- [ ] Log cleanup job (еженедельный)

### Фаза 9: Testing (5-7 дней)
- [ ] Unit tests (services)
- [ ] Integration tests (database)
- [ ] E2E tests (bot flow)
- [ ] Blockchain mocks
- [ ] Load testing (k6 или Artillery)

### Фаза 10: Deployment (5-7 дней)
- [ ] Google Cloud setup
- [ ] Cloud SQL configuration
- [ ] Memorystore Redis
- [ ] Compute Engine VM
- [ ] Cloud Armor (DDoS protection)
- [ ] CI/CD pipeline
- [ ] Monitoring (Cloud Monitoring)
- [ ] Alerting setup

**Общий срок разработки: 7-10 недель**

---

## ☁️ Деплоймент на Google Cloud

### Архитектура GCP

```
┌─────────────────────────────────────────────────────┐
│            Cloud Load Balancer                       │
│         (with Cloud Armor DDoS protection)           │
└─────────────────┬───────────────────────────────────┘
                  │
         ┌────────▼──────────┐
         │  Compute Engine   │
         │  (n1-standard-2)  │
         │                   │
         │  - nginx          │
         │  - Node.js app    │
         │  - PM2            │
         └────────┬──────────┘
                  │
    ┌─────────────┼──────────────┐
    │             │              │
┌───▼──────┐  ┌──▼────────┐  ┌──▼──────────┐
│ Cloud    │  │Memorystore│  │Cloud Storage│
│ SQL      │  │  Redis    │  │   Backups   │
│PostgreSQL│  │           │  │             │
└──────────┘  └───────────┘  └─────────────┘
```

### Конфигурация ресурсов

#### Compute Engine
```yaml
Instance:
  Name: sigmatrade-bot-prod
  Type: n1-standard-2 (2 vCPU, 7.5 GB RAM)
  OS: Ubuntu 22.04 LTS
  Disk: 50 GB SSD
  Region: us-central1 (или ближайший к целевой аудитории)

Auto-scaling (опционально):
  Min instances: 1
  Max instances: 3
  CPU threshold: 70%
```

#### Cloud SQL
```yaml
Database:
  Type: PostgreSQL 15
  Tier: db-f1-micro (dev) → db-n1-standard-1 (prod)
  Storage: 10 GB SSD (auto-resize enabled)
  Backups:
    - Automated daily backups
    - Point-in-time recovery enabled
    - Retention: 7 days
  High Availability: Enabled (for production)
```

#### Memorystore Redis
```yaml
Redis:
  Type: Basic (dev) → Standard (prod)
  Memory: 1 GB (dev) → 5 GB (prod)
  Version: 7.0
  High Availability: Enabled (Standard tier)
```

#### Cloud Storage
```yaml
Bucket:
  Name: sigmatrade-backups
  Location: us-central1
  Storage class: Standard
  Lifecycle:
    - Delete after 90 days (rotating logs)
    - Keep permanent backups forever
```

### Security Configuration

#### Cloud Armor (DDoS Protection)
```yaml
Security Policy:
  Rules:
    - Adaptive Protection: Enabled
    - Rate Limiting:
        - 100 requests per minute per IP
        - 1000 requests per minute per region
    - Geo-blocking: Optional (restrict to specific countries)
    - Bot detection: Enabled
    - Custom rules:
        - Block known attack signatures
        - Allow Google/Telegram IPs
```

#### VPC Network
```yaml
Network:
  Name: sigmatrade-vpc
  Subnets:
    - name: app-subnet
      region: us-central1
      cidr: 10.0.1.0/24

Firewall Rules:
  - Allow SSH (from your IP only)
  - Allow HTTP/HTTPS (from Cloud Load Balancer)
  - Allow internal communication
  - Block all other traffic
```

#### Secret Manager
```yaml
Secrets:
  - telegram-bot-token
  - database-password
  - quicknode-api-key
  - wallet-private-key (CRITICAL!)
  - jwt-secret

Access Control:
  - Service account: sigmatrade-bot@project.iam
  - Permissions: secretmanager.secretAccessor
```

### Deployment Process

#### 1. Initial Setup
```bash
# Create GCP project
gcloud projects create sigmatrade-bot --name="SigmaTrade Bot"
gcloud config set project sigmatrade-bot

# Enable required APIs
gcloud services enable compute.googleapis.com
gcloud services enable sqladmin.googleapis.com
gcloud services enable redis.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable cloudscheduler.googleapis.com

# Create service account
gcloud iam service-accounts create sigmatrade-bot \
  --display-name="SigmaTrade Bot Service Account"
```

#### 2. Database Setup
```bash
# Create Cloud SQL instance
gcloud sql instances create sigmatrade-db \
  --database-version=POSTGRES_15 \
  --tier=db-n1-standard-1 \
  --region=us-central1 \
  --backup \
  --backup-start-time=03:00

# Create database
gcloud sql databases create sigmatrade \
  --instance=sigmatrade-db

# Create user
gcloud sql users create botuser \
  --instance=sigmatrade-db \
  --password=[STRONG_PASSWORD]
```

#### 3. Redis Setup
```bash
# Create Memorystore instance
gcloud redis instances create sigmatrade-redis \
  --size=5 \
  --region=us-central1 \
  --tier=standard
```

#### 4. Compute Engine Setup
```bash
# Create VM instance
gcloud compute instances create sigmatrade-bot-prod \
  --zone=us-central1-a \
  --machine-type=n1-standard-2 \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=50GB \
  --boot-disk-type=pd-ssd \
  --service-account=sigmatrade-bot@project.iam.gserviceaccount.com \
  --scopes=cloud-platform

# SSH into instance
gcloud compute ssh sigmatrade-bot-prod --zone=us-central1-a
```

#### 5. Application Deployment
```bash
# On VM: Install dependencies
sudo apt update
sudo apt install -y docker.io docker-compose nodejs npm nginx

# Clone repository
git clone https://github.com/your-org/sigmatradebot.git
cd sigmatradebot

# Setup environment
cp .env.example .env
# Edit .env with production values

# Build and run
docker-compose up -d

# Setup nginx
sudo cp docker/nginx.conf /etc/nginx/sites-available/default
sudo systemctl restart nginx
```

#### 6. CI/CD Pipeline (GitHub Actions)
```yaml
# .github/workflows/deploy.yml
name: Deploy to GCP

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Cloud SDK
        uses: google-github-actions/setup-gcloud@v1
        with:
          service_account_key: ${{ secrets.GCP_SA_KEY }}
          project_id: sigmatrade-bot

      - name: Build Docker image
        run: docker build -t gcr.io/sigmatrade-bot/app:${{ github.sha }} .

      - name: Push to Container Registry
        run: docker push gcr.io/sigmatrade-bot/app:${{ github.sha }}

      - name: Deploy to Compute Engine
        run: |
          gcloud compute ssh sigmatrade-bot-prod --zone=us-central1-a \
            --command="cd /home/bot/sigmatradebot && \
                       git pull && \
                       docker-compose pull && \
                       docker-compose up -d"
```

### Monitoring & Alerting

#### Cloud Monitoring
```yaml
Dashboards:
  - Bot Metrics:
      - Active users
      - Messages per minute
      - Error rate
      - Response time

  - Blockchain Metrics:
      - Blocks processed
      - Pending deposits
      - Failed transactions

  - System Metrics:
      - CPU usage
      - Memory usage
      - Disk usage
      - Network traffic

Alerts:
  - High error rate (> 5% for 5 minutes)
  - CPU usage > 80% for 10 minutes
  - Database connections > 80%
  - Blockchain sync lag > 10 blocks
  - Disk space < 10 GB
```

#### Logging
```yaml
Cloud Logging:
  Log Sinks:
    - All errors → email notification
    - Critical errors → SMS + email
    - Admin actions → audit log

  Log Retention:
    - Application logs: 30 days
    - Audit logs: 365 days
    - Blockchain events: 90 days
```

### Backup Strategy

#### Database Backups
```bash
# Automated (Cloud SQL)
- Daily automated backups at 3:00 AM UTC
- 7-day retention
- Point-in-time recovery enabled

# Manual backup to git (via cron)
0 4 * * * /home/bot/scripts/backup.sh
```

#### Application Backups
```bash
#!/bin/bash
# scripts/backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/bot/sigmatradebot/backups"

# Export critical tables
pg_dump -h $DB_HOST -U $DB_USER -t users -t deposits \
  -t transactions -t referrals > $BACKUP_DIR/db_$DATE.sql

# Compress
gzip $BACKUP_DIR/db_$DATE.sql

# Commit to git
cd $BACKUP_DIR
git add .
git commit -m "Backup $DATE"
git push origin main

# Upload to Cloud Storage (redundancy)
gsutil cp $BACKUP_DIR/db_$DATE.sql.gz \
  gs://sigmatrade-backups/daily/db_$DATE.sql.gz

# Cleanup old local backups (keep 14 days)
find $BACKUP_DIR -name "*.sql.gz" -mtime +14 -delete
```

### Disaster Recovery Plan

#### RTO (Recovery Time Objective): 1 hour
#### RPO (Recovery Point Objective): 24 hours

```yaml
Scenario 1: Database corruption
  1. Stop application
  2. Restore from latest Cloud SQL automated backup
  3. Apply transaction logs from backup repository
  4. Restart application
  5. Verify data integrity

Scenario 2: VM failure
  1. Create new VM from snapshot (if available)
  2. Or provision new VM and deploy from git
  3. Restore database connection
  4. Update DNS/Load Balancer
  5. Verify functionality

Scenario 3: Complete GCP region failure
  1. Failover to backup region (requires multi-region setup)
  2. Restore database from Cloud Storage backup
  3. Update QuickNode endpoint
  4. Update Telegram webhook
  5. Resume operations
```

### Cost Estimation (Monthly)

```yaml
Compute Engine (n1-standard-2): $50
Cloud SQL (db-n1-standard-1): $35
Memorystore Redis (5GB Standard): $45
Cloud Storage (backups): $2
Cloud Load Balancer: $18
Data Transfer: ~$10
Cloud Armor: $0 (первый policy бесплатно)

Total: ~$160/month (production)
```

---

## ⚠️ Риски и митигация

### Технические риски

#### 1. QuickNode Rate Limiting
**Риск:** Превышение лимитов API при высокой нагрузке
**Митигация:**
- Использовать WebSocket для мониторинга (меньше запросов)
- Батчинг запросов
- Кеширование в Redis
- Failover на публичные BSC RPC

#### 2. Blockchain Reorganization
**Риск:** Отмена подтвержденных транзакций из-за reorg
**Митигация:**
- Ждать N подтверждений (рекомендуется 12 блоков для BSC)
- Мониторинг chain reorg events
- Логирование всех подтверждений

#### 3. Smart Contract Bug (USDT)
**Риск:** Уязвимость в USDT контракте
**Митигация:**
- Использовать официальный контракт
- Мониторинг событий pause/upgrade
- Возможность переключения на другой stablecoin

#### 4. Private Key Compromise
**Риск:** Кража приватного ключа выплатного кошелька
**Митигация:**
- Google Cloud Secret Manager с rotation
- Мультиподпись (multi-sig wallet)
- Limit на максимальную выплату за транзакцию
- Daily withdrawal limits

#### 5. Database Performance Degradation
**Риск:** Медленные запросы при росте данных
**Митигация:**
- Правильная индексация
- Партиционирование больших таблиц
- Регулярный VACUUM и ANALYZE
- Read replicas для аналитики

### Бизнес риски

#### 1. Регуляторные риски
**Риск:** Изменение законодательства о криптовалютах
**Митигация:**
- KYC/AML процедуры (опционально)
- Юридическая консультация
- Geo-blocking для запрещенных юрисдикций

#### 2. Telegram Ban
**Риск:** Блокировка бота Telegram
**Митигация:**
- Соблюдение ToS Telegram
- Backup plan (Web app, другие мессенджеры)
- Экспорт пользовательских данных

#### 3. Liquidity Risk
**Риск:** Недостаточно средств для реферальных выплат
**Митигация:**
- Мониторинг баланса кошелька
- Алерты при низком балансе
- Автоматическая пауза выплат

### Операционные риски

#### 1. Key Person Dependency
**Риск:** Зависимость от одного разработчика
**Митигация:**
- Документация кода
- Code reviews
- Knowledge sharing sessions

#### 2. Monitoring Gaps
**Риск:** Незамеченные проблемы в production
**Митигация:**
- Comprehensive monitoring
- Automated alerts
- On-call rotation

---

## 📚 Дополнительные рекомендации

### Оптимизации производительности

1. **Database Query Optimization**
   - Use indexes wisely
   - Avoid N+1 queries
   - Use connection pooling
   - Implement read replicas for reporting

2. **Caching Strategy**
   - User data (5 min TTL)
   - Deposit levels (5 min TTL)
   - Referral counts (10 min TTL)
   - Blockchain data (1 block time)

3. **Asynchronous Processing**
   - Use Bull queues for heavy operations
   - Defer non-critical tasks
   - Batch database updates

### Масштабирование

#### Вертикальное (Vertical Scaling)
- Upgrade VM type (более мощный CPU/RAM)
- Upgrade database tier
- Увеличить Redis memory

#### Горизонтальное (Horizontal Scaling)
```yaml
Multi-instance setup:
  - Load balancer → Multiple bot instances
  - Shared Redis (session management)
  - Shared PostgreSQL
  - Single blockchain monitor (leader election)
```

### Compliance & Legal

```yaml
Рекомендации:
  - Terms of Service
  - Privacy Policy
  - GDPR compliance (если есть EU users)
  - AML/KYC процедуры (опционально)
  - Налоговая отчетность
  - Лицензирование (зависит от юрисдикции)
```

### Future Enhancements

- [ ] Multi-language support (i18n)
- [ ] Web dashboard (React/Next.js)
- [ ] Mobile app
- [ ] Другие блокчейны (Ethereum, Polygon)
- [ ] Другие токены (BUSD, DAI)
- [ ] NFT integration
- [ ] Gamification (badges, leaderboard)
- [ ] AI-powered support (ChatGPT integration)

---

## 🎓 Обучающие ресурсы

### Для команды разработки
- TypeScript Best Practices
- Telegraf Documentation
- ethers.js Documentation
- PostgreSQL Performance Tuning
- Google Cloud Platform Training

### Security
- OWASP Top 10
- Blockchain Security Best Practices
- Smart Contract Auditing

---

## 📞 Контакты и Поддержка

```yaml
Escalation Path:
  L1 (Basic issues): Bot автоответы
  L2 (Technical): Админ в Telegram
  L3 (Critical): Email + Phone
  L4 (Emergency): On-call engineer

Response Times:
  Critical (system down): 15 minutes
  High (major function broken): 1 hour
  Medium (minor issue): 4 hours
  Low (enhancement): 24 hours
```

---

**Версия документа:** 1.0
**Дата создания:** 2025-11-10
**Автор:** Claude (Anthropic)
**Статус:** Draft для review
