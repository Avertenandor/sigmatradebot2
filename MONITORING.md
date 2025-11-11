# 📊 Monitoring & Alerting Guide - SigmaTrade Bot

**Last Updated:** 2025-11-11
**Version:** 1.0
**Status:** Production Ready

---

## 📋 Table of Contents

1. [Monitoring Stack](#monitoring-stack)
2. [Metrics Collection](#metrics-collection)
3. [Alert Rules](#alert-rules)
4. [Dashboards](#dashboards)
5. [Log Aggregation](#log-aggregation)
6. [Performance Monitoring](#performance-monitoring)
7. [Business Metrics](#business-metrics)
8. [Alert Channels](#alert-channels)
9. [On-Call Procedures](#on-call-procedures)

---

## 🏗 Monitoring Stack

### Components

```yaml
Metrics:
  - Prometheus (Time-series database)
  - Node Exporter (System metrics)
  - PostgreSQL Exporter (Database metrics)
  - Redis Exporter (Cache metrics)

Visualization:
  - Grafana (Dashboards)

Logging:
  - Winston (Application logging)
  - PM2 logs (Process management)
  - PostgreSQL logs (Database)

Alerting:
  - Prometheus Alertmanager
  - Telegram Bot (Notifications)
  - Email (Critical alerts)
  - PagerDuty (Optional)
```

---

## 📈 Metrics Collection

### Application Metrics (Custom)

#### File: `src/utils/metrics.util.ts`

```typescript
import { Registry, Counter, Histogram, Gauge } from 'prom-client';

// Create registry
export const register = new Registry();

// Bot metrics
export const botCommandsTotal = new Counter({
  name: 'sigmatrade_bot_commands_total',
  help: 'Total number of bot commands received',
  labelNames: ['command', 'status'],
  registers: [register]
});

export const depositProcessingDuration = new Histogram({
  name: 'sigmatrade_deposit_processing_seconds',
  help: 'Deposit processing time in seconds',
  labelNames: ['status'],
  buckets: [1, 5, 10, 30, 60, 120, 300],
  registers: [register]
});

export const activeUsers = new Gauge({
  name: 'sigmatrade_active_users',
  help: 'Number of active users in last hour',
  registers: [register]
});

export const pendingDeposits = new Gauge({
  name: 'sigmatrade_pending_deposits',
  help: 'Number of pending deposits',
  registers: [register]
});

export const dlqItems = new Gauge({
  name: 'sigmatrade_dlq_items',
  help: 'Number of items in Dead Letter Queue',
  registers: [register]
});

export const blockchainSyncLag = new Gauge({
  name: 'sigmatrade_blockchain_sync_lag_blocks',
  help: 'Number of blocks behind current blockchain height',
  registers: [register]
});

export const transactionErrors = new Counter({
  name: 'sigmatrade_transaction_errors_total',
  help: 'Total number of transaction errors',
  labelNames: ['type', 'error'],
  registers: [register]
});

export const referralRewards = new Counter({
  name: 'sigmatrade_referral_rewards_total',
  help: 'Total referral rewards distributed',
  labelNames: ['level'],
  registers: [register]
});

export const notificationFailures = new Counter({
  name: 'sigmatrade_notification_failures_total',
  help: 'Total notification failures',
  labelNames: ['priority'],
  registers: [register]
});

// Expose metrics endpoint
import express from 'express';
const metricsApp = express();

metricsApp.get('/metrics', async (req, res) => {
  res.set('Content-Type', register.contentType);
  res.end(await register.metrics());
});

metricsApp.listen(9090, () => {
  console.log('Metrics server listening on port 9090');
});
```

### Prometheus Configuration

#### File: `/etc/prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

# Alertmanager configuration
alerting:
  alertmanagers:
    - static_configs:
        - targets: ['localhost:9093']

# Load rules
rule_files:
  - "alerts.yml"

# Scrape configs
scrape_configs:
  # SigmaTrade Bot metrics
  - job_name: 'sigmatrade-bot'
    static_configs:
      - targets: ['localhost:9090']

  # System metrics
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']

  # PostgreSQL metrics
  - job_name: 'postgres'
    static_configs:
      - targets: ['localhost:9187']

  # Redis metrics
  - job_name: 'redis'
    static_configs:
      - targets: ['localhost:9121']
```

### PostgreSQL Exporter Setup

```bash
# Install postgres_exporter
wget https://github.com/prometheus-community/postgres_exporter/releases/download/v0.11.1/postgres_exporter-0.11.1.linux-amd64.tar.gz
tar xvfz postgres_exporter-0.11.1.linux-amd64.tar.gz
sudo mv postgres_exporter-0.11.1.linux-amd64/postgres_exporter /usr/local/bin/

# Create service
sudo tee /etc/systemd/system/postgres_exporter.service << EOF
[Unit]
Description=Prometheus PostgreSQL Exporter
After=network.target

[Service]
Type=simple
User=postgres
Environment="DATA_SOURCE_NAME=postgresql://botuser:password@localhost:5432/sigmatrade?sslmode=disable"
ExecStart=/usr/local/bin/postgres_exporter
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable postgres_exporter
sudo systemctl start postgres_exporter
```

### Redis Exporter Setup

```bash
# Install redis_exporter
wget https://github.com/oliver006/redis_exporter/releases/download/v1.45.0/redis_exporter-v1.45.0.linux-amd64.tar.gz
tar xvfz redis_exporter-v1.45.0.linux-amd64.tar.gz
sudo mv redis_exporter-v1.45.0.linux-amd64/redis_exporter /usr/local/bin/

# Create service
sudo tee /etc/systemd/system/redis_exporter.service << EOF
[Unit]
Description=Prometheus Redis Exporter
After=network.target

[Service]
Type=simple
User=redis
ExecStart=/usr/local/bin/redis_exporter
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable redis_exporter
sudo systemctl start redis_exporter
```

---

## 🚨 Alert Rules

### File: `/etc/prometheus/alerts.yml`

```yaml
groups:
  # Critical Alerts (P1)
  - name: critical_alerts
    interval: 30s
    rules:
      - alert: BotDown
        expr: up{job="sigmatrade-bot"} == 0
        for: 1m
        labels:
          severity: critical
          priority: P1
        annotations:
          summary: "SigmaTrade Bot is down"
          description: "Bot has been down for more than 1 minute"

      - alert: DatabaseDown
        expr: up{job="postgres"} == 0
        for: 1m
        labels:
          severity: critical
          priority: P1
        annotations:
          summary: "PostgreSQL database is down"
          description: "Database has been down for more than 1 minute"

      - alert: RedisDown
        expr: up{job="redis"} == 0
        for: 1m
        labels:
          severity: critical
          priority: P1
        annotations:
          summary: "Redis is down"
          description: "Redis has been down for more than 1 minute"

      - alert: HighErrorRate
        expr: rate(sigmatrade_transaction_errors_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
          priority: P1
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }} over the last 5 minutes"

      - alert: BlockchainSyncStuck
        expr: sigmatrade_blockchain_sync_lag_blocks > 100
        for: 10m
        labels:
          severity: critical
          priority: P1
        annotations:
          summary: "Blockchain sync is stuck"
          description: "Sync lag is {{ $value }} blocks behind"

  # High Priority Alerts (P2)
  - name: high_priority_alerts
    interval: 1m
    rules:
      - alert: HighDLQCount
        expr: sigmatrade_dlq_items > 5
        for: 15m
        labels:
          severity: high
          priority: P2
        annotations:
          summary: "High number of DLQ items"
          description: "{{ $value }} items in Dead Letter Queue"

      - alert: DepositProcessingSlow
        expr: histogram_quantile(0.95, rate(sigmatrade_deposit_processing_seconds_bucket[5m])) > 60
        for: 10m
        labels:
          severity: high
          priority: P2
        annotations:
          summary: "Deposit processing is slow"
          description: "95th percentile processing time is {{ $value }}s"

      - alert: HighPendingDeposits
        expr: sigmatrade_pending_deposits > 20
        for: 30m
        labels:
          severity: high
          priority: P2
        annotations:
          summary: "High number of pending deposits"
          description: "{{ $value }} deposits pending for >30 minutes"

      - alert: DatabaseConnectionsHigh
        expr: pg_stat_database_numbackends{datname="sigmatrade"} > 16
        for: 10m
        labels:
          severity: high
          priority: P2
        annotations:
          summary: "High database connections"
          description: "{{ $value }} active connections (max: 20)"

  # Medium Priority Alerts (P3)
  - name: medium_priority_alerts
    interval: 5m
    rules:
      - alert: HighMemoryUsage
        expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes > 0.85
        for: 10m
        labels:
          severity: medium
          priority: P3
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value | humanizePercentage }}"

      - alert: HighCPUUsage
        expr: 100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 15m
        labels:
          severity: medium
          priority: P3
        annotations:
          summary: "High CPU usage"
          description: "CPU usage is {{ $value | humanizePercentage }}"

      - alert: DiskSpaceLow
        expr: (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) < 0.15
        for: 10m
        labels:
          severity: medium
          priority: P3
        annotations:
          summary: "Disk space is low"
          description: "Only {{ $value | humanizePercentage }} disk space remaining"

      - alert: NotificationFailureSpike
        expr: rate(sigmatrade_notification_failures_total[5m]) > 0.1
        for: 10m
        labels:
          severity: medium
          priority: P3
        annotations:
          summary: "Notification failure spike"
          description: "High rate of notification failures: {{ $value }}/sec"

      - alert: RedisMemoryHigh
        expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.80
        for: 10m
        labels:
          severity: medium
          priority: P3
        annotations:
          summary: "Redis memory usage is high"
          description: "Redis using {{ $value | humanizePercentage }} of max memory"

  # Low Priority Alerts (P4)
  - name: low_priority_alerts
    interval: 15m
    rules:
      - alert: LowActiveUsers
        expr: sigmatrade_active_users < 5
        for: 1h
        labels:
          severity: low
          priority: P4
        annotations:
          summary: "Low active users"
          description: "Only {{ $value }} active users in last hour"

      - alert: DatabaseQueriesSlow
        expr: rate(pg_stat_statements_mean_time[5m]) > 100
        for: 30m
        labels:
          severity: low
          priority: P4
        annotations:
          summary: "Database queries are slow"
          description: "Average query time is {{ $value }}ms"
```

---

## 📊 Dashboards

### Grafana Dashboard Configuration

#### 1. Main Overview Dashboard

**Panels:**
1. Bot Status (Up/Down)
2. Active Users (Last 1h, 24h, 7d)
3. Commands per Minute
4. Deposit Processing Time (p50, p95, p99)
5. Pending Deposits Count
6. DLQ Items Count
7. Blockchain Sync Lag
8. Error Rate
9. Response Time

**JSON Export:**
```json
{
  "dashboard": {
    "title": "SigmaTrade Bot - Main Dashboard",
    "tags": ["sigmatrade", "bot"],
    "timezone": "browser",
    "panels": [
      {
        "title": "Bot Status",
        "type": "stat",
        "targets": [{
          "expr": "up{job='sigmatrade-bot'}",
          "legendFormat": "Status"
        }],
        "fieldConfig": {
          "defaults": {
            "mappings": [
              { "value": 1, "text": "UP", "color": "green" },
              { "value": 0, "text": "DOWN", "color": "red" }
            ]
          }
        }
      },
      {
        "title": "Active Users",
        "type": "graph",
        "targets": [{
          "expr": "sigmatrade_active_users",
          "legendFormat": "Active Users"
        }]
      },
      {
        "title": "Deposit Processing Time (p95)",
        "type": "graph",
        "targets": [{
          "expr": "histogram_quantile(0.95, rate(sigmatrade_deposit_processing_seconds_bucket[5m]))",
          "legendFormat": "p95"
        }]
      },
      {
        "title": "Error Rate",
        "type": "graph",
        "targets": [{
          "expr": "rate(sigmatrade_transaction_errors_total[5m])",
          "legendFormat": "{{type}}"
        }]
      }
    ]
  }
}
```

#### 2. Database Dashboard

**Panels:**
1. Active Connections
2. Transactions per Second
3. Query Duration (p50, p95, p99)
4. Table Sizes
5. Index Hit Rate
6. Locks
7. Deadlocks
8. Replication Lag (if applicable)

**Key Queries:**
```promql
# Active connections
pg_stat_database_numbackends{datname="sigmatrade"}

# Transactions per second
rate(pg_stat_database_xact_commit{datname="sigmatrade"}[5m])

# Query duration p95
histogram_quantile(0.95, rate(pg_stat_statements_total_time_bucket[5m]))

# Cache hit rate
pg_stat_database_blks_hit{datname="sigmatrade"} / (pg_stat_database_blks_hit{datname="sigmatrade"} + pg_stat_database_blks_read{datname="sigmatrade"})
```

#### 3. System Resources Dashboard

**Panels:**
1. CPU Usage (%)
2. Memory Usage (%)
3. Disk Usage (%)
4. Network I/O
5. Disk I/O
6. Process Count
7. Load Average

**Key Queries:**
```promql
# CPU usage
100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Memory usage
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100

# Disk usage
(node_filesystem_size_bytes{mountpoint="/"} - node_filesystem_avail_bytes{mountpoint="/"}) / node_filesystem_size_bytes{mountpoint="/"} * 100
```

#### 4. Business Metrics Dashboard

**Panels:**
1. Total Deposits (24h, 7d, 30d)
2. Total Volume (USDT)
3. New Users (24h, 7d, 30d)
4. Referral Rewards Paid
5. Average Deposit Size
6. Top Referrers
7. User Retention Rate

**Database Queries:**
```sql
-- Total deposits today
SELECT COUNT(*), SUM(amount)
FROM deposits
WHERE created_at >= CURRENT_DATE;

-- New users today
SELECT COUNT(*)
FROM users
WHERE created_at >= CURRENT_DATE;

-- Referral rewards today
SELECT SUM(amount)
FROM referral_earnings
WHERE created_at >= CURRENT_DATE;
```

---

## 📝 Log Aggregation

### Winston Logger Configuration

#### File: `src/utils/logger.util.ts`

```typescript
import winston from 'winston';

const logLevels = {
  error: 0,
  warn: 1,
  info: 2,
  http: 3,
  debug: 4,
};

const logColors = {
  error: 'red',
  warn: 'yellow',
  info: 'green',
  http: 'magenta',
  debug: 'blue',
};

winston.addColors(logColors);

// Console format
const consoleFormat = winston.format.combine(
  winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
  winston.format.colorize({ all: true }),
  winston.format.printf(
    (info) => `${info.timestamp} [${info.level}]: ${info.message}`
  )
);

// File format (JSON for parsing)
const fileFormat = winston.format.combine(
  winston.format.timestamp(),
  winston.format.errors({ stack: true }),
  winston.format.json()
);

// Create logger
export const logger = winston.createLogger({
  levels: logLevels,
  transports: [
    // Console output
    new winston.transports.Console({
      format: consoleFormat,
      level: process.env.NODE_ENV === 'production' ? 'info' : 'debug',
    }),

    // Error logs
    new winston.transports.File({
      filename: 'logs/error.log',
      level: 'error',
      format: fileFormat,
      maxsize: 10485760, // 10MB
      maxFiles: 10,
    }),

    // Combined logs
    new winston.transports.File({
      filename: 'logs/combined.log',
      format: fileFormat,
      maxsize: 10485760, // 10MB
      maxFiles: 30,
    }),

    // Critical errors (for alerting)
    new winston.transports.File({
      filename: 'logs/critical.log',
      level: 'error',
      format: fileFormat,
      maxsize: 5242880, // 5MB
      maxFiles: 10,
    }),
  ],
});

// Helper functions
export const logError = (context: string, error: Error, metadata?: any) => {
  logger.error(`[${context}] ${error.message}`, {
    error: {
      name: error.name,
      message: error.message,
      stack: error.stack,
    },
    ...metadata,
  });
};

export const logDeposit = (depositId: number, status: string, metadata?: any) => {
  logger.info(`Deposit ${depositId} - ${status}`, {
    depositId,
    status,
    ...metadata,
  });
};

export const logPaymentRetry = (retryId: number, attempt: number, status: string) => {
  logger.info(`Payment retry ${retryId} - Attempt ${attempt} - ${status}`, {
    retryId,
    attempt,
    status,
  });
};
```

### Log Rotation

```bash
# /etc/logrotate.d/sigmatrade

/home/bot/sigmatradebot/logs/*.log {
  daily
  rotate 30
  compress
  delaycompress
  notifempty
  create 0644 bot bot
  sharedscripts
  postrotate
    pm2 reloadLogs
  endscript
}
```

### Log Analysis Scripts

```bash
#!/bin/bash
# /home/bot/scripts/log-analysis.sh

# Error summary for today
echo "=== Error Summary ==="
grep -h "\"level\":\"error\"" logs/error.log | \
  jq -r '.message' | \
  sort | uniq -c | sort -rn | head -20

# Most active users today
echo -e "\n=== Most Active Users ==="
grep "telegram_id" logs/combined.log | \
  jq -r '.telegram_id' | \
  sort | uniq -c | sort -rn | head -10

# Slow deposits (>60s)
echo -e "\n=== Slow Deposits ==="
grep "Deposit.*confirmed" logs/combined.log | \
  jq -r 'select(.duration > 60) | "\(.depositId): \(.duration)s"' | \
  sort -t: -k2 -rn | head -10
```

---

## ⚡ Performance Monitoring

### Custom Performance Tracking

```typescript
// src/utils/performance.util.ts

import { performance } from 'perf_hooks';
import { logger } from './logger.util';

export class PerformanceMonitor {
  private timers: Map<string, number> = new Map();

  start(label: string): void {
    this.timers.set(label, performance.now());
  }

  end(label: string, logSlow: number = 1000): number {
    const startTime = this.timers.get(label);
    if (!startTime) {
      logger.warn(`Performance timer not found: ${label}`);
      return 0;
    }

    const duration = performance.now() - startTime;
    this.timers.delete(label);

    if (duration > logSlow) {
      logger.warn(`Slow operation: ${label} took ${duration.toFixed(2)}ms`);
    }

    return duration;
  }

  async measure<T>(
    label: string,
    fn: () => Promise<T>,
    logSlow: number = 1000
  ): Promise<T> {
    this.start(label);
    try {
      const result = await fn();
      this.end(label, logSlow);
      return result;
    } catch (error) {
      this.end(label, logSlow);
      throw error;
    }
  }
}

export const perfMonitor = new PerformanceMonitor();

// Usage example:
// const result = await perfMonitor.measure('deposit_processing', async () => {
//   return await processDeposit(depositId);
// });
```

### Database Query Performance

```sql
-- Enable pg_stat_statements
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Top 10 slowest queries
SELECT
  query,
  calls,
  total_time,
  mean_time,
  max_time,
  stddev_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- Queries with high total time
SELECT
  query,
  calls,
  total_time,
  mean_time
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 10;

-- Reset statistics
SELECT pg_stat_statements_reset();
```

---

## 💼 Business Metrics

### Daily Business Report

```sql
-- Daily business metrics report
SELECT
  CURRENT_DATE as report_date,
  (SELECT COUNT(*) FROM users WHERE created_at >= CURRENT_DATE) as new_users,
  (SELECT COUNT(*) FROM deposits WHERE created_at >= CURRENT_DATE) as deposits_count,
  (SELECT COALESCE(SUM(amount), 0) FROM deposits WHERE created_at >= CURRENT_DATE) as deposits_volume,
  (SELECT COUNT(*) FROM payment_retry WHERE status = 'success' AND created_at >= CURRENT_DATE) as withdrawals_count,
  (SELECT COALESCE(SUM(amount), 0) FROM payment_retry WHERE status = 'success' AND created_at >= CURRENT_DATE) as withdrawals_volume,
  (SELECT COALESCE(SUM(amount), 0) FROM referral_earnings WHERE created_at >= CURRENT_DATE) as referral_rewards,
  (SELECT COUNT(DISTINCT user_id) FROM user_actions WHERE created_at >= CURRENT_DATE) as active_users;
```

### Automated Business Report Email

```bash
#!/bin/bash
# /home/bot/scripts/daily-business-report.sh

DATE=$(date +%Y-%m-%d)

# Generate report
REPORT=$(psql -h localhost -U botuser -d sigmatrade -t -c "
SELECT
  '📊 Daily Business Report - ' || CURRENT_DATE || E'\n' ||
  E'\n👥 Users:' ||
  E'\n- New: ' || (SELECT COUNT(*) FROM users WHERE created_at >= CURRENT_DATE) ||
  E'\n- Active: ' || (SELECT COUNT(DISTINCT user_id) FROM user_actions WHERE created_at >= CURRENT_DATE) ||
  E'\n\n💰 Deposits:' ||
  E'\n- Count: ' || (SELECT COUNT(*) FROM deposits WHERE created_at >= CURRENT_DATE) ||
  E'\n- Volume: ' || (SELECT COALESCE(SUM(amount), 0) FROM deposits WHERE created_at >= CURRENT_DATE) || ' USDT' ||
  E'\n\n💸 Withdrawals:' ||
  E'\n- Count: ' || (SELECT COUNT(*) FROM payment_retry WHERE status = '\''success'\'' AND created_at >= CURRENT_DATE) ||
  E'\n- Volume: ' || (SELECT COALESCE(SUM(amount), 0) FROM payment_retry WHERE status = '\''success'\'' AND created_at >= CURRENT_DATE) || ' USDT' ||
  E'\n\n🔗 Referrals:' ||
  E'\n- Rewards Paid: ' || (SELECT COALESCE(SUM(amount), 0) FROM referral_earnings WHERE created_at >= CURRENT_DATE) || ' USDT' ||
  E'\n\n⚠️ Issues:' ||
  E'\n- DLQ Items: ' || (SELECT COUNT(*) FROM payment_retry WHERE status = '\''dlq'\'') ||
  E'\n- Pending Deposits: ' || (SELECT COUNT(*) FROM deposits WHERE status = '\''pending'\'')
")

# Send to Telegram admin channel
curl -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
  -d "chat_id=$ADMIN_CHAT_ID" \
  -d "text=$REPORT" \
  -d "parse_mode=HTML"

# Also save to file
echo "$REPORT" > /home/bot/reports/daily-$DATE.txt
```

---

## 📢 Alert Channels

### Alertmanager Configuration

#### File: `/etc/alertmanager/alertmanager.yml`

```yaml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'severity']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'telegram-critical'
  routes:
    - match:
        severity: critical
      receiver: 'telegram-critical'
      continue: true

    - match:
        severity: critical
      receiver: 'email-critical'

    - match:
        severity: high
      receiver: 'telegram-high'

    - match:
        severity: medium
      receiver: 'telegram-medium'

receivers:
  - name: 'telegram-critical'
    webhook_configs:
      - url: 'http://localhost:8080/telegram-webhook'
        send_resolved: true

  - name: 'telegram-high'
    webhook_configs:
      - url: 'http://localhost:8080/telegram-webhook'
        send_resolved: true

  - name: 'telegram-medium'
    webhook_configs:
      - url: 'http://localhost:8080/telegram-webhook'
        send_resolved: true

  - name: 'email-critical'
    email_configs:
      - to: 'oncall@example.com'
        from: 'alerts@sigmatrade.com'
        smarthost: 'smtp.gmail.com:587'
        auth_username: 'alerts@sigmatrade.com'
        auth_password: '$SMTP_PASSWORD'
        headers:
          Subject: '🚨 CRITICAL ALERT: {{ .GroupLabels.alertname }}'
```

### Telegram Webhook Handler

```typescript
// src/monitoring/telegram-alerts.ts

import express from 'express';
import axios from 'axios';

const app = express();
app.use(express.json());

const ADMIN_CHAT_ID = process.env.ADMIN_CHAT_ID!;
const BOT_TOKEN = process.env.BOT_TOKEN!;

app.post('/telegram-webhook', async (req, res) => {
  const alerts = req.body.alerts;

  for (const alert of alerts) {
    const emoji = getSeverityEmoji(alert.labels.severity);
    const status = alert.status === 'firing' ? '🔥 FIRING' : '✅ RESOLVED';

    const message = `
${emoji} ${status}

<b>${alert.labels.alertname}</b>

<b>Severity:</b> ${alert.labels.severity}
<b>Priority:</b> ${alert.labels.priority}

<b>Description:</b>
${alert.annotations.description}

<b>Started:</b> ${new Date(alert.startsAt).toLocaleString()}
    `.trim();

    await axios.post(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
      chat_id: ADMIN_CHAT_ID,
      text: message,
      parse_mode: 'HTML',
    });
  }

  res.sendStatus(200);
});

function getSeverityEmoji(severity: string): string {
  switch (severity) {
    case 'critical': return '🚨';
    case 'high': return '⚠️';
    case 'medium': return '⚡';
    case 'low': return 'ℹ️';
    default: return '📊';
  }
}

app.listen(8080, () => {
  console.log('Telegram webhook handler listening on port 8080');
});
```

---

## 📱 On-Call Procedures

### Alert Response Playbook

#### P1 - Critical (15 min response)
```markdown
1. Acknowledge alert in Telegram/PagerDuty
2. Check bot status: `pm2 status sigmatrade-bot`
3. Check recent errors: `pm2 logs sigmatrade-bot --err --lines 100`
4. Run health check: `./scripts/daily-check.sh`
5. If bot down: `pm2 restart sigmatrade-bot`
6. Monitor for 5 minutes
7. If issue persists, escalate to team lead
8. Document incident
```

#### P2 - High (1 hour response)
```markdown
1. Acknowledge alert
2. Investigate root cause using logs and metrics
3. Apply fix or workaround
4. Test fix in staging (if applicable)
5. Deploy fix to production
6. Monitor for 15 minutes
7. Update incident ticket
```

### Escalation Matrix

| Time | Action | Contact |
|------|--------|---------|
| 0 min | Alert fires | On-call engineer |
| 15 min | No response | Secondary on-call |
| 30 min | Still unresolved | Team lead |
| 1 hour | Critical issue persists | CTO/VP Engineering |

---

## 📊 Monitoring Checklist

### Daily
- [ ] Check dashboard for anomalies
- [ ] Review error logs
- [ ] Check DLQ items
- [ ] Verify blockchain sync status

### Weekly
- [ ] Review alert trends
- [ ] Check slow query report
- [ ] Analyze resource usage trends
- [ ] Review business metrics

### Monthly
- [ ] Review and tune alert thresholds
- [ ] Analyze incident patterns
- [ ] Capacity planning review
- [ ] Update dashboards

---

**Last Updated:** 2025-11-11
**Version:** 1.0
**Next Review:** 2025-12-11
