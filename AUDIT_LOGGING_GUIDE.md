# 🔍 Audit Logging & Performance Monitoring Guide

Complete guide for using the enhanced audit logging and performance monitoring system.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Request ID Tracking](#request-id-tracking)
3. [Audit Logging](#audit-logging)
4. [Financial Operations Logging](#financial-operations-logging)
5. [Performance Monitoring](#performance-monitoring)
6. [Integration Examples](#integration-examples)
7. [Log Files & Retention](#log-files--retention)
8. [Alerting](#alerting)

---

## 🎯 Overview

The audit system provides:
- **Request ID tracking** - Trace operations end-to-end
- **Immutable audit trail** - Long-term retention for compliance
- **Financial operation logging** - All money movements tracked
- **Performance metrics** - Automatic slow operation detection
- **Admin action logging** - Full accountability
- **Security event tracking** - Suspicious activity detection
- **Automatic alerting** - Critical events notify admins

---

## 🔗 Request ID Tracking

### Automatic Tracking (Bot Requests)

Request IDs are automatically generated for all bot interactions:

```typescript
// In bot middleware chain (already configured)
import { requestIdMiddleware } from './middlewares/request-id.middleware';

bot.use(requestIdMiddleware); // Must be FIRST middleware
```

### Manual Tracking (Background Jobs)

For background jobs, wrap in request context:

```typescript
import { withRequestContext } from './middlewares/request-id.middleware';

// Background job
async function processPayments() {
  await withRequestContext(async () => {
    // All logs inside will have same request ID
    await payment Service.processPendingPayments();
  });
}
```

### Accessing Request ID

```typescript
import { getRequestId } from './utils/audit-logger.util';

const requestId = getRequestId(); // Returns current request ID
console.log('Processing request:', requestId);
```

---

## 📝 Audit Logging

### Basic Audit Event

```typescript
import { logAuditEvent, AuditCategory } from './utils/audit-logger.util';

logAuditEvent({
  category: AuditCategory.USER_REGISTERED,
  severity: 'audit',
  userId: user.id,
  action: 'User completed registration',
  success: true,
  details: {
    username: user.username,
    walletAddress: user.wallet_address,
    referrerId: user.referrer_id,
  },
});
```

### Audit Categories

```typescript
export enum AuditCategory {
  // Financial
  DEPOSIT_CREATED = 'deposit_created',
  DEPOSIT_CONFIRMED = 'deposit_confirmed',
  PAYMENT_SENT = 'payment_sent',
  PAYMENT_FAILED = 'payment_failed',
  REFERRAL_EARNING_CREATED = 'referral_earning_created',

  // Balance changes
  BALANCE_INCREASED = 'balance_increased',
  BALANCE_DECREASED = 'balance_decreased',

  // User actions
  USER_REGISTERED = 'user_registered',
  USER_VERIFIED = 'user_verified',
  USER_BANNED = 'user_banned',

  // Admin actions
  ADMIN_LOGIN = 'admin_login',
  ADMIN_ACTION = 'admin_action',
  ADMIN_BROADCAST = 'admin_broadcast',

  // Security
  SUSPICIOUS_ACTIVITY = 'suspicious_activity',
  RATE_LIMIT_EXCEEDED = 'rate_limit_exceeded',
  INVALID_ACCESS = 'invalid_access',

  // System
  BLOCKCHAIN_DISCONNECT = 'blockchain_disconnect',
  DATABASE_ERROR = 'database_error',
}
```

### Severity Levels

```typescript
severity: 'critical'   // Immediate attention, alerts admins
severity: 'security'   // Security-related events
severity: 'financial'  // Money operations (long retention)
severity: 'admin'      // Admin actions
severity: 'audit'      // General audit trail
```

---

## 💰 Financial Operations Logging

### Log Deposit Creation

```typescript
import { logFinancialOperation, AuditCategory } from './utils/audit-logger.util';

// When deposit is created
logFinancialOperation({
  category: AuditCategory.DEPOSIT_CREATED,
  userId: user.id,
  action: 'Deposit request created',
  amount: deposit.amount,
  balanceBefore: currentBalance,
  balanceAfter: currentBalance, // No change yet
  transactionId: deposit.id,
  success: true,
  details: {
    level: deposit.level,
    walletAddress: user.wallet_address,
  },
});
```

### Log Deposit Confirmation

```typescript
// When deposit is confirmed on blockchain
logFinancialOperation({
  category: AuditCategory.DEPOSIT_CONFIRMED,
  userId: user.id,
  action: 'Deposit confirmed on blockchain',
  amount: deposit.amount,
  balanceBefore: balanceBefore,
  balanceAfter: balanceAfter,
  transactionId: deposit.id,
  txHash: deposit.tx_hash,
  success: true,
  details: {
    level: deposit.level,
    blockNumber: deposit.block_number,
    confirmations: confirmations,
  },
});
```

### Log Payment Sent

```typescript
// When payment is sent to user
logFinancialOperation({
  category: AuditCategory.PAYMENT_SENT,
  userId: user.id,
  action: 'Referral reward payment sent',
  amount: totalAmount,
  balanceBefore: 0, // Pending balance
  balanceAfter: 0,
  txHash: paymentResult.txHash,
  success: true,
  details: {
    earningIds: earnings.map(e => e.id),
    recipientAddress: user.wallet_address,
  },
});
```

### Log Payment Failure

```typescript
// When payment fails
logFinancialOperation({
  category: AuditCategory.PAYMENT_FAILED,
  userId: user.id,
  action: 'Payment failed',
  amount: totalAmount,
  success: false,
  error: paymentResult.error,
  details: {
    earningIds: earnings.map(e => e.id),
    attemptCount: retryCount,
  },
});

// This automatically alerts admins if amount > 1000 USDT or if failed
```

### Log Balance Change

```typescript
import { logBalanceChange } from './utils/audit-logger.util';

// After any balance modification
logBalanceChange({
  userId: user.id,
  balanceBefore: oldBalance,
  balanceAfter: newBalance,
  reason: 'Deposit confirmed',
  transactionId: deposit.id,
  details: {
    depositLevel: deposit.level,
    txHash: deposit.tx_hash,
  },
});
```

---

## ⚡ Performance Monitoring

### Automatic Tracking (Decorator)

```typescript
import { trackPerformance, PerformanceCategory } from './utils/performance-monitor.util';

class DepositService {
  @trackPerformance('createPendingDeposit', PerformanceCategory.DATABASE_QUERY)
  async createPendingDeposit(data: any): Promise<any> {
    // Method automatically tracked
    // Logs warning if > 1000ms
    return await this.depositRepository.save(data);
  }
}
```

### Manual Tracking

```typescript
import { withPerformanceTracking, PerformanceCategory } from './utils/performance-monitor.util';

async function complexOperation() {
  return await withPerformanceTracking(
    'calculateReferralChain',
    PerformanceCategory.REFERRAL_CHAIN,
    async () => {
      // Complex operation here
      return await buildReferralChain(userId, depth);
    }
  );
}
```

### Database Query Tracking

```typescript
import { trackDatabaseQuery } from './utils/performance-monitor.util';

async function getPendingDeposits() {
  return await trackDatabaseQuery('getPendingDeposits', async () => {
    return await depositRepo.find({
      where: { status: 'pending' },
    });
  });
}
```

### Blockchain Call Tracking

```typescript
import { trackBlockchainCall } from './utils/performance-monitor.util';

async function getBlockNumber() {
  return await trackBlockchainCall('getBlockNumber', async () => {
    return await provider.getBlockNumber();
  });
}
```

### Performance Statistics

```typescript
import { performanceStats } from './utils/performance-monitor.util';

// Get stats for specific operation
const stats = performanceStats.getStats('createPendingDeposit');
console.log(stats);
// {
//   operation: 'createPendingDeposit',
//   count: 150,
//   avgDuration: 234,
//   minDuration: 120,
//   maxDuration: 890,
//   successRate: 98.7,
//   failures: 2
// }

// Get all stats
const allStats = performanceStats.getAllStats();

// Log summary
performanceStats.logSummary();
```

### Start Monitoring

```typescript
import {
  startPerformanceReporting,
  startMemoryMonitoring
} from './utils/performance-monitor.util';

// In index.ts or main app file
startPerformanceReporting(); // Reports every hour
startMemoryMonitoring(); // Logs memory every 5 minutes
```

---

## 🔧 Integration Examples

### Example 1: User Registration

```typescript
// registration.handler.ts
import { logAuditEvent, AuditCategory } from '../utils/audit-logger.util';
import { withPerformanceTracking } from '../utils/performance-monitor.util';

export const handleWalletInput = async (ctx: Context) => {
  const walletAddress = ctx.text?.trim();

  // Track performance
  const result = await withPerformanceTracking(
    'userRegistration',
    'user_registration',
    async () => {
      return await userService.createUser({
        telegramId: ctx.from!.id,
        username: ctx.from?.username,
        walletAddress,
      });
    }
  );

  if (result.user) {
    // Audit log successful registration
    logAuditEvent({
      category: AuditCategory.USER_REGISTERED,
      severity: 'audit',
      userId: result.user.id,
      action: 'User registered successfully',
      success: true,
      details: {
        telegramId: result.user.telegram_id,
        username: result.user.username,
        walletAddress: result.user.wallet_address,
      },
    });
  }
};
```

### Example 2: Deposit Confirmation

```typescript
// deposit.service.ts
import {
  logFinancialOperation,
  logBalanceChange,
  AuditCategory
} from '../utils/audit-logger.util';
import { trackDatabaseQuery } from '../utils/performance-monitor.util';

async function confirmDeposit(txHash: string, blockNumber: number) {
  // Track database query performance
  const deposit = await trackDatabaseQuery('findDepositByTxHash', async () => {
    return await this.depositRepository.findOne({
      where: { tx_hash: txHash },
      relations: ['user'],
    });
  });

  if (!deposit) return;

  const balanceBefore = await this.getUserBalance(deposit.user_id);

  // Update deposit status
  deposit.status = TransactionStatus.CONFIRMED;
  deposit.confirmed_at = new Date();
  await this.depositRepository.save(deposit);

  const balanceAfter = await this.getUserBalance(deposit.user_id);

  // LOG: Financial operation
  logFinancialOperation({
    category: AuditCategory.DEPOSIT_CONFIRMED,
    userId: deposit.user_id,
    action: 'Deposit confirmed',
    amount: parseFloat(deposit.amount),
    balanceBefore,
    balanceAfter,
    transactionId: deposit.id,
    txHash: deposit.tx_hash,
    success: true,
    details: {
      level: deposit.level,
      blockNumber,
    },
  });

  // LOG: Balance change
  logBalanceChange({
    userId: deposit.user_id,
    balanceBefore,
    balanceAfter,
    reason: 'Deposit confirmed',
    transactionId: deposit.id,
    details: {
      depositLevel: deposit.level,
      amount: deposit.amount,
    },
  });
}
```

### Example 3: Admin Action

```typescript
// admin.handler.ts
import { logAdminAudit } from '../utils/audit-logger.util';

export const handleBanUser = async (ctx: AdminContext) => {
  const targetUserId = parseInt(ctx.text!);

  await userService.banUser(targetUserId);

  // LOG: Admin action
  logAdminAudit({
    adminId: ctx.admin!.id,
    action: 'User banned',
    targetUserId,
    details: {
      adminUsername: ctx.admin!.username,
      reason: 'Manual ban via admin panel',
    },
  });

  await ctx.reply('✅ User banned');
};
```

### Example 4: Security Event

```typescript
// rate-limit.middleware.ts
import { logSecurityAudit, AuditCategory } from '../utils/audit-logger.util';

if (isRateLimited) {
  // LOG: Security event
  logSecurityAudit({
    category: AuditCategory.RATE_LIMIT_EXCEEDED,
    severity: 'security',
    userId: ctx.from?.id,
    action: 'Rate limit exceeded',
    success: false,
    ipAddress: getIpAddress(ctx),
    details: {
      requestCount: userRequests.length,
      timeWindow: WINDOW_MS,
      maxRequests: MAX_REQUESTS,
    },
  });

  await ctx.reply('⚠️ Too many requests. Please wait.');
  return;
}
```

---

## 📂 Log Files & Retention

### Audit Logs

```
logs/audit/
  ├── audit-2025-11-10.log      (90 days retention)
  ├── financial-2025-11-10.log  (365 days retention) ⭐
  ├── security-2025-11-10.log   (180 days retention)
  └── critical-2025-11-10.log   (365 days retention) ⭐
```

### Standard Logs

```
logs/
  ├── app-2025-11-10.log        (14 days retention)
  ├── error-2025-11-10.log      (30 days retention)
  ├── combined-2025-11-10.log   (14 days retention)
  ├── exceptions-2025-11-10.log (30 days retention)
  └── rejections-2025-11-10.log (30 days retention)
```

### Log Rotation

- **Max Size:** 50MB per file (audit), 20MB (standard)
- **Format:** JSON for easy parsing
- **Compression:** Automatic after rotation
- **Backup:** Should be sent to cloud storage

---

## 🚨 Alerting

### Automatic Alerts

Admins are automatically notified for:

1. **Critical Events** (severity: 'critical')
   - Database errors
   - Blockchain disconnections
   - System failures

2. **Failed Payments**
   - Any failed payment attempt

3. **Large Transactions**
   - Deposits/withdrawals > 1000 USDT

4. **Security Events**
   - Multiple login failures
   - Suspicious activity
   - Rate limit violations (high frequency)

### Alert Format

```
🔴 **ALERT: payment_failed**

**Action:** Payment processing failed
**Severity:** critical
**Time:** 2025-11-10T15:30:45.123Z
**User ID:** 12345
**Amount:** 150.50 USDT
**Status:** ❌ FAILED
**Error:** Insufficient gas
**Request ID:** req_abc123-def456

**Details:**
```json
{
  "earningIds": [789, 790],
  "attemptCount": 3,
  "gasPrice": "5 gwei"
}
```
```

### Manual Alerts

```typescript
import { logAuditEvent, AuditCategory } from './utils/audit-logger.util';

// This will alert admins automatically
logAuditEvent({
  category: AuditCategory.SUSPICIOUS_ACTIVITY,
  severity: 'critical', // ← Triggers alert
  userId: suspiciousUser.id,
  action: 'Multiple failed withdrawal attempts',
  success: false,
  details: {
    attempts: 10,
    timespan: '5 minutes',
  },
});
```

---

## ✅ Best Practices

1. **Always log financial operations**
   ```typescript
   // ✅ Good
   logFinancialOperation({...});

   // ❌ Bad - no audit trail
   await depositRepo.save(deposit);
   ```

2. **Include all relevant context**
   ```typescript
   // ✅ Good
   logAuditEvent({
     category: AuditCategory.USER_BANNED,
     userId: user.id,
     details: {
       reason: 'Fraud detected',
       reportedBy: adminId,
       evidence: evidenceUrls,
     },
   });

   // ❌ Bad - not enough context
   logAuditEvent({
     category: AuditCategory.USER_BANNED,
     userId: user.id,
   });
   ```

3. **Track performance of critical paths**
   ```typescript
   // ✅ Good - tracked
   await withPerformanceTracking('processPayments', 'payment_processing', async () => {
     await processAllPayments();
   });

   // ❌ Bad - no performance insight
   await processAllPayments();
   ```

4. **Use request IDs for debugging**
   ```typescript
   // ✅ Good - can trace entire request
   const requestId = getRequestId();
   logger.error('Payment failed', { requestId, userId, amount });

   // ❌ Bad - hard to correlate logs
   logger.error('Payment failed', { userId, amount });
   ```

5. **Log both success and failure**
   ```typescript
   // ✅ Good
   logAuditEvent({
     action: 'Withdrawal request',
     success: false,
     error: 'Insufficient balance',
   });

   // ❌ Bad - only logs success
   if (success) {
     logAuditEvent({...});
   }
   ```

---

## 📊 Monitoring Dashboard

### View Audit Logs

```bash
# View all audit logs for today
tail -f logs/audit/audit-$(date +%Y-%m-%d).log | jq

# View financial operations
tail -f logs/audit/financial-$(date +%Y-%m-%d).log | jq

# View critical events
tail -f logs/audit/critical-$(date +%Y-%m-%d).log | jq

# Filter by user
cat logs/audit/audit-*.log | jq 'select(.userId == 12345)'

# Filter by request ID
cat logs/audit/audit-*.log | jq 'select(.requestId == "req_abc123")'

# Find failed payments
cat logs/audit/financial-*.log | jq 'select(.category == "payment_failed")'
```

### Performance Reports

```bash
# View slow operations
cat logs/app-*.log | jq 'select(.isSlow == true)'

# View database query times
cat logs/app-*.log | jq 'select(.category == "database_query")'
```

---

## 🔍 Debugging with Request IDs

When user reports an issue:

1. Get their Telegram ID
2. Find their recent requests:
   ```bash
   cat logs/audit/audit-$(date +%Y-%m-%d).log | jq 'select(.userId == 12345)'
   ```
3. Get request ID from audit log
4. Trace entire request:
   ```bash
   cat logs/**/*.log | jq 'select(.requestId == "req_abc123")'
   ```
5. See all operations in that request chain

---

## 📚 Additional Resources

- Main logger: `src/utils/logger.util.ts`
- Audit logger: `src/utils/audit-logger.util.ts`
- Performance monitor: `src/utils/performance-monitor.util.ts`
- Request ID middleware: `src/bot/middlewares/request-id.middleware.ts`

---

**Last Updated:** 2025-11-10
**Version:** 1.0.0
