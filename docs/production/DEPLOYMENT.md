# 🚀 SigmaTrade Bot - Production Deployment Guide

Complete guide for deploying the SigmaTrade Telegram bot to production.

## 📋 Prerequisites

### System Requirements
- **OS**: Ubuntu 20.04+ or Debian 11+
- **Python**: 3.11 or higher
- **PostgreSQL**: 14 or higher
- **RAM**: Minimum 2GB, recommended 4GB
- **Storage**: Minimum 10GB free space

### Required Software
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11+
sudo apt install python3.11 python3.11-venv python3-pip -y

# Install PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# Install git
sudo apt install git -y
```

## 🔧 Installation Steps

### 1. Clone Repository
```bash
git clone <your-repo-url> /opt/sigmatradebot
cd /opt/sigmatradebot
```

### 2. Create Virtual Environment
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Database

#### Create PostgreSQL Database
```bash
sudo -u postgres psql

# In PostgreSQL shell:
CREATE DATABASE sigmatradebot;
CREATE USER botuser WITH ENCRYPTED PASSWORD 'YOUR_SECURE_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE sigmatradebot TO botuser;
\q
```

#### Test Database Connection
```bash
psql -h localhost -U botuser -d sigmatradebot -c "SELECT version();"
```

### 4. Environment Configuration

#### Copy and Edit .env
```bash
cp .env.example .env
nano .env
```

#### Required Environment Variables
```bash
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_BOT_USERNAME=your_bot_username

# Database
DATABASE_URL=postgresql+asyncpg://botuser:YOUR_SECURE_PASSWORD@localhost:5432/sigmatradebot
DATABASE_ECHO=false

# Admin IDs (comma-separated)
ADMIN_TELEGRAM_IDS=123456789,987654321

# Wallet (CRITICAL - SECURE THESE!)
WALLET_PRIVATE_KEY=your_wallet_private_key
WALLET_ADDRESS=0xYourWalletAddress
USDT_CONTRACT_ADDRESS=0xdAC17F958D2ee523a2206206994597C13D831ec7
RPC_URL=https://mainnet.infura.io/v3/YOUR_PROJECT_ID

# Security (Generate with: openssl rand -hex 32)
SECRET_KEY=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(openssl rand -hex 32)

# Environment
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
```

### 5. Database Migrations

#### Create Initial Migration
```bash
# Activate venv if not already
source venv/bin/activate

# Create initial migration
alembic revision --autogenerate -m "Initial schema"

# Review the migration file in alembic/versions/
# Then apply it:
alembic upgrade head
```

#### Verify Database Schema
```bash
psql -h localhost -U botuser -d sigmatradebot

# Check tables
\dt

# Should see: users, deposits, transactions, referrals, etc.
\q
```

### 6. Create Systemd Service

#### Create Service File
```bash
sudo nano /etc/systemd/system/sigmatradebot.service
```

#### Service Configuration
```ini
[Unit]
Description=SigmaTrade Telegram Bot
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=YOUR_USER
Group=YOUR_USER
WorkingDirectory=/opt/sigmatradebot
Environment="PATH=/opt/sigmatradebot/venv/bin"
ExecStart=/opt/sigmatradebot/venv/bin/python3 -m bot.main
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=sigmatradebot

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/sigmatradebot/logs

[Install]
WantedBy=multi-user.target
```

#### Enable and Start Service
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable sigmatradebot

# Start service
sudo systemctl start sigmatradebot

# Check status
sudo systemctl status sigmatradebot

# View logs
sudo journalctl -u sigmatradebot -f
```

## 🔒 Security Hardening

### 1. Secure .env File
```bash
# Set proper permissions
chmod 600 .env
chown YOUR_USER:YOUR_USER .env

# Never commit .env to git!
echo ".env" >> .gitignore
```

### 2. Firewall Configuration
```bash
# Allow SSH
sudo ufw allow 22/tcp

# Allow PostgreSQL only from localhost
sudo ufw deny 5432/tcp

# Enable firewall
sudo ufw enable
sudo ufw status
```

### 3. PostgreSQL Security
```bash
sudo nano /etc/postgresql/14/main/pg_hba.conf

# Change to:
# local   all             all                                     scram-sha-256
# host    all             all             127.0.0.1/32            scram-sha-256

sudo systemctl restart postgresql
```

### 4. Secure Private Keys

**CRITICAL**: Never store private keys in plain text in production!

Use one of these methods:
- AWS Secrets Manager
- Google Cloud Secret Manager
- HashiCorp Vault
- Encrypted environment variables

## 📊 Monitoring & Logging

### View Bot Logs
```bash
# Real-time logs
sudo journalctl -u sigmatradebot -f

# Last 100 lines
sudo journalctl -u sigmatradebot -n 100

# Logs for specific date
sudo journalctl -u sigmatradebot --since "2024-01-01" --until "2024-01-02"
```

### Log Files
```bash
# Application logs
tail -f logs/bot.log

# Rotate logs (configure in main.py)
# - rotation="1 day"
# - retention="7 days"
```

### Health Checks
```bash
# Check if bot is running
sudo systemctl is-active sigmatradebot

# Check process
ps aux | grep "bot.main"

# Check database connection
psql -h localhost -U botuser -d sigmatradebot -c "SELECT COUNT(*) FROM users;"
```

### Health Check HTTP Endpoint

The bot provides a `/health` HTTP endpoint for external monitoring (nginx, UptimeRobot, etc.).

**URL:** `http://<bot-host>:8080/health`

**Response Codes:**
- `200`: All systems healthy
- `503`: One or more systems degraded/unhealthy

**Response Format (JSON):**
```json
{
  "status": "healthy",
  "checks": {
    "database": {
      "status": "healthy",
      "message": "Database connection successful"
    },
    "redis": {
      "status": "healthy",
      "message": "Redis connection successful"
    },
    "blockchain": {
      "status": "healthy",
      "message": "Blockchain connection successful (Chain ID: 56)",
      "chain_id": 56,
      "rpc_stats": {
        "requests_last_minute": 15,
        "avg_response_time_ms": 245.5,
        "error_count": 0,
        "total_requests": 1234
      }
    }
  }
}
```

**Configuration:**
- Port is configurable via `HEALTH_CHECK_PORT` environment variable (default: 8080)
- For Docker deployments, port is exposed in `docker-compose.python.yml`
- For systemd deployments, ensure port 8080 is accessible (firewall rules)

**Example Usage:**
```bash
# Test health endpoint
curl http://localhost:8080/health

# With jq for formatted output
curl -s http://localhost:8080/health | jq

# Check specific component
curl -s http://localhost:8080/health | jq '.checks.blockchain.status'
```

## 🔄 Updates & Maintenance

### Update Bot Code
```bash
cd /opt/sigmatradebot

# Pull latest code
git pull origin main

# Activate venv
source venv/bin/activate

# Update dependencies
pip install -r requirements.txt --upgrade

# Run new migrations
alembic upgrade head

# Restart service
sudo systemctl restart sigmatradebot

# Check status
sudo systemctl status sigmatradebot
```

### Database Backup

#### Option 1: Using the production backup script (Recommended)
```bash
# The script is located at scripts/backup-production.sh
# It includes:
# - Automatic compression
# - Backup verification
# - Rotation (keeps last 30 days + monthly archives)
# - Telegram notifications on failure

# Make it executable
chmod +x /opt/sigmatradebot/scripts/backup-production.sh

# Add to crontab (daily at 3 AM)
(crontab -l 2>/dev/null; echo "0 3 * * * cd /opt/sigmatradebot && ./scripts/backup-production.sh >> /var/log/sigmatrade-backup.log 2>&1") | crontab -

# Verify crontab
crontab -l
```

#### Option 2: Simple backup script
```bash
# Create backup script
cat > /opt/sigmatradebot/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups/sigmatradebot"
mkdir -p $BACKUP_DIR
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump -h localhost -U botuser -d sigmatradebot > "$BACKUP_DIR/backup_$DATE.sql"
# Keep only last 30 days
find $BACKUP_DIR -name "backup_*.sql" -mtime +30 -delete
echo "Backup completed: $BACKUP_DIR/backup_$DATE.sql"
EOF

chmod +x /opt/sigmatradebot/backup.sh

# Add to crontab (daily at 3 AM)
(crontab -l 2>/dev/null; echo "0 3 * * * /opt/sigmatradebot/backup.sh") | crontab -
```

#### Option 3: Using Docker (if using docker-compose)
```bash
# Backup from Docker container
cat > /opt/sigmatradebot/backup-docker.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups/sigmatradebot"
mkdir -p $BACKUP_DIR
DATE=$(date +%Y%m%d_%H%M%S)
docker exec sigmatrade-postgres pg_dump -U sigmatrade sigmatrade > "$BACKUP_DIR/backup_$DATE.sql"
find $BACKUP_DIR -name "backup_*.sql" -mtime +30 -delete
EOF

chmod +x /opt/sigmatradebot/backup-docker.sh

# Add to crontab
(crontab -l 2>/dev/null; echo "0 3 * * * /opt/sigmatradebot/backup-docker.sh") | crontab -
```

#### Verify cron is working
```bash
# Check cron service
sudo systemctl status cron

# View cron logs
sudo tail -f /var/log/syslog | grep CRON

# Test backup manually
/opt/sigmatradebot/scripts/backup-production.sh
```

### Database Restore
```bash
# Stop bot
sudo systemctl stop sigmatradebot

# Restore from backup
psql -h localhost -U botuser -d sigmatradebot < /opt/backups/sigmatradebot/backup_YYYYMMDD_HHMMSS.sql

# Start bot
sudo systemctl start sigmatradebot
```

## 🐛 Troubleshooting

### Bot Won't Start
```bash
# Check logs for errors
sudo journalctl -u sigmatradebot -n 50

# Common issues:
# 1. Database connection - check DATABASE_URL
# 2. Bot token - check TELEGRAM_BOT_TOKEN
# 3. Missing dependencies - run: pip install -r requirements.txt
# 4. Permissions - check file ownership
```

### Database Connection Errors
```bash
# Test PostgreSQL
sudo systemctl status postgresql

# Test connection
psql -h localhost -U botuser -d sigmatradebot

# Check PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-14-main.log
```

### High Memory Usage
```bash
# Check memory
free -h

# Check bot process
ps aux | grep python | grep bot.main

# Restart bot
sudo systemctl restart sigmatradebot
```

## 📞 Support

For issues:
1. Check logs: `sudo journalctl -u sigmatradebot -f`
2. Review error messages
3. Check database connectivity
4. Verify environment variables
5. Consult documentation

## ✅ Production Checklist

Before going live:

- [ ] PostgreSQL database created and secured
- [ ] .env file configured with production values
- [ ] All secret keys generated and secured
- [ ] Database migrations applied
- [ ] Systemd service configured and enabled
- [ ] Firewall rules configured
- [ ] Backup script configured
- [ ] Bot tested with test transactions
- [ ] Admin users configured
- [ ] Monitoring/alerting set up
- [ ] Documentation reviewed
- [ ] Private keys secured (NOT in .env)

## 🎉 Quick Start (Development)

For development/testing:

```bash
# Clone and setup
git clone <repo> && cd sigmatradebot
cp .env.example .env
nano .env  # Configure

# Create venv and install
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Setup database
createdb sigmatradebot
alembic upgrade head

# Run bot
./run.sh
# or
python3 -m bot.main
```

---

**SECURITY WARNING**: Never commit `.env`, private keys, or secrets to git!
