# 🤖 SigmaTrade Bot - Telegram DeFi Investment Platform (Python)

High-performance Telegram bot for DeFi investment platform with multi-level referral system, automated ROI distribution, and blockchain integration.

> **Note**: This is the Python version. TypeScript version documentation is in README.typescript.md

## 🎯 Features

### Core Functionality
- **Multi-Level Deposits**: 5 investment levels ($10, $50, $100, $150, $300)
- **Automated ROI**: 2% daily returns up to 500% cap
- **3-Tier Referral System**: 3%, 2%, 5% commission structure
- **Blockchain Integration**: USDT (BSC) deposits and withdrawals
- **Real-time Transaction Monitoring**: Automated deposit confirmations

### Admin Features
- **User Management**: Ban/unban users, view statistics
- **Broadcast System**: Mass messaging with multimedia support (15 msg/sec rate limit)
- **Withdrawal Approvals**: Manual withdrawal review and approval
- **Analytics Dashboard**: Platform-wide statistics and insights

### Security
- **Financial Password**: Additional security for withdrawals
- **Request ID Tracking**: Unique ID for every request
- **Rate Limiting**: Anti-spam protection
- **Admin Authentication**: Separate admin verification system

## 🏗️ Technology Stack

- **Framework**: aiogram 3.x (async Telegram bot framework)
- **Database**: PostgreSQL 14+ with SQLAlchemy 2.0 (async ORM)
- **Blockchain**: Web3.py for BSC/USDT integration
- **Migrations**: Alembic for database versioning
- **Logging**: Loguru for structured logging
- **Settings**: Pydantic Settings for environment config

## 📁 Project Structure

```
sigmatradebot/
├── app/
│   ├── config/          # Configuration (settings, database)
│   ├── models/          # SQLAlchemy models
│   ├── repositories/    # Data access layer
│   └── services/        # Business logic layer
├── bot/
│   ├── handlers/        # Telegram command/callback handlers
│   ├── keyboards/       # Inline/reply keyboards
│   ├── middlewares/     # Request processing middleware
│   ├── states/          # FSM state definitions
│   └── main.py          # Bot entry point
├── alembic/             # Database migrations
├── logs/                # Application logs
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables
├── docs/               # Documentation (see docs/INDEX.md)
└── run.sh               # Startup script
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 14+
- Telegram Bot Token (from @BotFather)
- BSC Wallet with USDT

### Installation

```bash
# 1. Clone repository
git clone <repository-url>
cd sigmatradebot

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
nano .env  # Edit with your configuration

# 5. Setup database
createdb sigmatradebot
alembic upgrade head

# 6. Start bot
./run.sh
```

### Required Environment Variables
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/sigmatradebot
ADMIN_TELEGRAM_IDS=123456789
WALLET_PRIVATE_KEY=your_private_key
WALLET_ADDRESS=0xYourAddress
SECRET_KEY=your_secret_key
ENCRYPTION_KEY=your_encryption_key
```

## 📖 Documentation

- **[docs/INDEX.md](docs/INDEX.md)**: Complete documentation index
- **[docs/production/DEPLOYMENT.md](docs/production/DEPLOYMENT.md)**: Complete production deployment guide
- **[docs/migration/](docs/migration/)**: Migration documentation

## 🏃 Production Deployment

See [docs/production/DEPLOYMENT.md](docs/production/DEPLOYMENT.md) for complete production setup including:
- Systemd service configuration
- Database setup and security
- Firewall configuration
- Backup strategies
- Monitoring and logging
- Security hardening

## 🔐 Security

**CRITICAL**: Never commit secrets to git!

- Store private keys in Secret Manager (AWS/GCP/Vault)
- Use strong database passwords
- Enable firewall (UFW)
- Regular automated backups
- Monitor logs for suspicious activity

## 🧪 Development

### Database Migrations
```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Testing
```bash
# Run all tests
pytest

# Run specific test types
pytest tests/unit/ -v              # Unit tests
pytest tests/integration/ -v       # Integration tests
pytest tests/e2e/ -v              # End-to-end tests
pytest tests/load/ -v -m load     # Load tests

# With coverage
pytest --cov=app --cov=bot --cov-report=html

# Linting (Ruff)
ruff check .
```

**Testing Documentation:**

- **[tests/TESTING_SYSTEM_DOCUMENTATION.md](tests/TESTING_SYSTEM_DOCUMENTATION.md)**: Complete testing system
- **[tests/LOAD_TESTING_SCENARIOS.md](tests/LOAD_TESTING_SCENARIOS.md)**: Load testing scenarios
- **[tests/TEST_COVERAGE_MAP.md](tests/TEST_COVERAGE_MAP.md)**: Coverage map
- **[tests/README.md](tests/README.md)**: Quick start guide

## 📊 Key Components

### Middleware Chain (Order Critical!)

1. RequestIDMiddleware - Unique request tracking
2. DatabaseMiddleware - Database session management
3. AuthMiddleware - User authentication

### Models

- User, Deposit, Transaction, Referral, ReferralEarning
- PaymentRetry, FailedNotification (PART5)
- SupportTicket, SupportMessage

### Services

- UserService, DepositService, ReferralService
- WithdrawalService, NotificationService
- TransactionService, SupportService

## 🐛 Troubleshooting

### Bot won't start

```bash
# Check logs
sudo journalctl -u sigmatradebot -f

# Verify .env file
cat .env | grep TELEGRAM_BOT_TOKEN

# Test database
psql -h localhost -U botuser -d sigmatradebot
```

### Database errors

```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Run migrations
alembic upgrade head
```

See [docs/guides/TROUBLESHOOTING.md](docs/guides/TROUBLESHOOTING.md) for more troubleshooting tips.

## 📝 License

[Your License]

## 👥 Support

- Check documentation
- Review logs: `./logs/bot.log`
- Open GitHub issue

---

**⚠️ WARNING**: This bot handles real cryptocurrency. Test thoroughly!
