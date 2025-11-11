# 🔧 MASTER REFACTORING PLAN - SigmaTrade Bot
**Created:** 2025-11-10
**Status:** In Progress
**Priority:** Quality over Speed
**Approach:** Methodical, Test-Driven, Risk-Aware

---

## 📋 EXECUTIVE SUMMARY

**Total Issues Found:** 30+
**Critical (Money Loss):** 4
**High (User Deadlocks):** 4
**Medium (Data Inconsistency):** 3
**Low (Performance):** 5
**Architectural:** 14

**Estimated Timeline:** 4-6 weeks for full implementation
**Risk Level:** HIGH (production system with real money)

---

## 🎯 GUIDING PRINCIPLES

1. **NO BREAKING CHANGES** - Existing users must not be affected
2. **BACKWARD COMPATIBILITY** - All changes must work with existing data
3. **TEST EVERYTHING** - No code without tests
4. **INCREMENTAL ROLLOUT** - Deploy in small, reversible batches
5. **MONITORING FIRST** - Add observability before changes
6. **DATA INTEGRITY** - No user funds lost during migration
7. **ROLLBACK READY** - Every change must have rollback plan

---

## 📊 DEPENDENCY GRAPH

```
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: Foundation (Testing + Monitoring)                  │
│ ├── Setup test infrastructure                               │
│ ├── Add comprehensive logging                               │
│ └── Create database backup system                           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: Database Layer (Transactions + Locks)              │
│ ├── Add transaction wrapper utilities                       │
│ ├── Add pessimistic locking helpers                         │
│ └── Create migration framework                              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 3: CRITICAL FIXES (Money Loss Prevention)             │
│ ├── FIX #2: Reduce tolerance to 0.01 USDT                   │
│ ├── FIX #3: Add pessimistic locks for deposits              │
│ ├── FIX #18: Add transaction deduplication                  │
│ ├── FIX #1: Expired deposit recovery mechanism              │
│ └── FIX #4: Payment retry with exponential backoff          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 4: HIGH PRIORITY (User Experience)                    │
│ ├── FIX #7: Session state initialization                    │
│ ├── FIX #8: Global error handler state reset                │
│ ├── FIX #5: Safe referral ID storage                        │
│ └── FIX #6: Password recovery mechanism                     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 5: MEDIUM PRIORITY (Data Consistency)                 │
│ ├── FIX #9: Wrap registration in transaction                │
│ ├── FIX #10: Wrap referral creation in transaction          │
│ ├── FIX #11: Add null checks for referrers                  │
│ └── Add data validation layers                              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 6: LOW PRIORITY (Performance)                         │
│ ├── FIX #12: Optimize getReferralChain with CTE             │
│ ├── FIX #13: Increase pending deposit batch size            │
│ ├── FIX #14: Move admin sessions to Redis                   │
│ └── FIX #15: Add EIP-55 checksum validation                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 7: ARCHITECTURAL (Reliability)                        │
│ ├── FIX #16: Smart historical event fetching                │
│ ├── FIX #17: Notification failure alerting                  │
│ ├── Add health check endpoints                              │
│ ├── Add metrics collection                                  │
│ └── Add admin alert system                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔍 PHASE 1: FOUNDATION & INFRASTRUCTURE

### **Objective:** Build safety net before making changes

### **Tasks:**

#### 1.1 Testing Infrastructure
- [ ] Install testing framework (Jest + ts-jest)
- [ ] Setup test database (separate from production)
- [ ] Create test data fixtures
- [ ] Add integration test helpers
- [ ] Create mock Telegram bot for testing

**Files to Create:**
- `tests/setup.ts`
- `tests/fixtures/users.ts`
- `tests/fixtures/deposits.ts`
- `tests/helpers/database.ts`
- `tests/helpers/telegram-mock.ts`
- `jest.config.js`

**Risk:** LOW
**Time Estimate:** 2-3 days

#### 1.2 Enhanced Logging & Monitoring
- [ ] Add request ID tracking
- [ ] Add structured logging for money operations
- [ ] Create audit log for all balance changes
- [ ] Add performance metrics
- [ ] Create alert thresholds

**Files to Modify:**
- `src/utils/logger.util.ts`
- `src/services/payment.service.ts`
- `src/services/deposit.service.ts`

**Files to Create:**
- `src/utils/audit-logger.util.ts`
- `src/utils/performance-metrics.ts`

**Risk:** LOW
**Time Estimate:** 2 days

#### 1.3 Database Backup System
- [ ] Create automated backup job (before any changes)
- [ ] Test restore procedure
- [ ] Document rollback process

**Files to Create:**
- `scripts/backup-production.sh`
- `scripts/restore-from-backup.sh`
- `ROLLBACK_PROCEDURES.md`

**Risk:** LOW
**Time Estimate:** 1 day

**PHASE 1 TOTAL:** 5-6 days

---

## 🔧 PHASE 2: DATABASE LAYER IMPROVEMENTS

### **Objective:** Create utilities for safe database operations

### **Tasks:**

#### 2.1 Transaction Wrapper Utility
- [ ] Create transaction wrapper with retry logic
- [ ] Add deadlock detection and retry
- [ ] Add transaction timeout configuration
- [ ] Add rollback on error

**File to Create:**
- `src/database/transaction.util.ts`

**Code:**
```typescript
/**
 * Transaction wrapper with automatic retry on deadlock
 */
export async function withTransaction<T>(
  operation: (manager: EntityManager) => Promise<T>,
  options?: {
    maxRetries?: number;
    timeout?: number;
    isolationLevel?: IsolationLevel;
  }
): Promise<T> {
  const maxRetries = options?.maxRetries || 3;
  let attempt = 0;

  while (attempt < maxRetries) {
    try {
      return await AppDataSource.transaction(
        options?.isolationLevel || 'READ COMMITTED',
        async (manager) => {
          return await operation(manager);
        }
      );
    } catch (error) {
      if (isDeadlockError(error) && attempt < maxRetries - 1) {
        attempt++;
        await delay(Math.pow(2, attempt) * 100); // Exponential backoff
        continue;
      }
      throw error;
    }
  }

  throw new Error('Transaction failed after max retries');
}
```

**Risk:** LOW
**Time Estimate:** 1 day

#### 2.2 Pessimistic Locking Helpers
- [ ] Create helper for SELECT FOR UPDATE
- [ ] Add lock timeout configuration
- [ ] Add lock contention logging

**File to Create:**
- `src/database/locking.util.ts`

**Risk:** MEDIUM (can cause performance issues if used incorrectly)
**Time Estimate:** 1 day

#### 2.3 Migration Framework
- [ ] Create migration template
- [ ] Add migration versioning
- [ ] Create migration runner
- [ ] Test migrations on copy of production data

**Files to Create:**
- `src/database/migrations/001-add-deposit-constraints.ts`
- `scripts/run-migrations.ts`

**Risk:** MEDIUM
**Time Estimate:** 2 days

**PHASE 2 TOTAL:** 4 days

---

## 🚨 PHASE 3: CRITICAL FIXES (MONEY LOSS PREVENTION)

### **Objective:** Prevent all scenarios where user funds can be lost

### **Priority:** MAXIMUM - Deploy ASAP after testing

---

### **FIX #2: Reduce Deposit Tolerance**

**Bug:** Tolerance of 0.5 USDT allows users to send less than required
**Impact:** Platform loses 0.4 USDT per deposit (potential 400 USDT loss per 1000 deposits)
**Risk Level:** 🚨 CRITICAL

**Solution:**
1. Reduce tolerance from 0.5 to 0.01 USDT (1 cent)
2. Add exact amount validation
3. Log all deposits that fall within tolerance range
4. Add admin alert for tolerance-matched deposits

**Files to Modify:**
- `src/services/blockchain/deposit-processor.ts` (line 101)

**Code Change:**
```typescript
// BEFORE:
const tolerance = 0.5; // Too large!

// AFTER:
const DEPOSIT_AMOUNT_TOLERANCE = 0.01; // 1 cent tolerance for gas fees
const tolerance = DEPOSIT_AMOUNT_TOLERANCE;

// Add logging
if (Math.abs(amount - levelAmount) > 0 && Math.abs(amount - levelAmount) <= tolerance) {
  logger.warn('Deposit matched with tolerance', {
    expected: levelAmount,
    actual: amount,
    difference: amount - levelAmount,
    userId: user.id,
    txHash,
  });

  // Alert admin if significant deviation
  if (Math.abs(amount - levelAmount) > 0.005) {
    await notificationService.alertAdminDepositTolerance(
      user.telegram_id,
      levelAmount,
      amount,
      txHash
    );
  }
}
```

**Tests to Add:**
```typescript
describe('Deposit Amount Validation', () => {
  it('should reject deposit with 0.5 USDT less than required', async () => {
    // Send 9.5 USDT instead of 10 USDT
    // Should be rejected
  });

  it('should accept deposit with 0.005 USDT less (gas fees)', async () => {
    // Send 9.995 USDT instead of 10 USDT
    // Should be accepted with warning
  });

  it('should log and alert admin for deposits within tolerance', async () => {
    // Send 9.99 USDT
    // Check logs and admin alerts
  });
});
```

**Rollback Plan:**
- Change tolerance back to 0.5
- Deploy previous version
- No data migration needed

**Risk:** LOW (only makes validation stricter)
**Time Estimate:** 0.5 days

---

### **FIX #3: Race Condition in Pending Deposit Creation**

**Bug:** Multiple clicks create duplicate pending deposits
**Impact:** User confusion, stuck deposits
**Risk Level:** 🚨 CRITICAL

**Solution:**
1. Wrap deposit creation in database transaction
2. Add pessimistic lock on user's pending deposits
3. Add UNIQUE constraint on (user_id, level, status='pending')
4. Add idempotency key for deposit creation

**Files to Modify:**
- `src/services/deposit.service.ts` (line 233-311)
- `src/database/entities/Deposit.entity.ts`

**Code Change:**
```typescript
// deposit.service.ts
async createPendingDeposit(data: {
  userId: number;
  level: number;
  amount: number;
  txHash?: string;
}): Promise<{ deposit?: Deposit; error?: string }> {
  return await withTransaction(async (manager) => {
    const depositRepo = manager.getRepository(Deposit);

    // Use pessimistic lock to prevent race condition
    const existingPending = await depositRepo
      .createQueryBuilder('deposit')
      .where('deposit.user_id = :userId', { userId: data.userId })
      .andWhere('deposit.level = :level', { level: data.level })
      .andWhere('deposit.status = :status', { status: TransactionStatus.PENDING })
      .setLock('pessimistic_write') // SELECT FOR UPDATE
      .getOne();

    if (existingPending) {
      return { error: 'У вас уже есть ожидающий подтверждения депозит этого уровня' };
    }

    // Check if tx hash already used (if provided)
    if (data.txHash) {
      const existingByHash = await depositRepo.findOne({
        where: { tx_hash: data.txHash },
      });

      if (existingByHash) {
        return { error: 'Депозит с этим хешом транзакции уже существует' };
      }
    }

    // Validate can activate
    const { canActivate, reason } = await this.canActivateLevel(
      data.userId,
      data.level
    );

    if (!canActivate) {
      return { error: reason };
    }

    // Create deposit
    const deposit = depositRepo.create({
      user_id: data.userId,
      level: data.level,
      amount: data.amount.toString(),
      tx_hash: data.txHash || null,
      status: TransactionStatus.PENDING,
    });

    await depositRepo.save(deposit);

    logger.info('Pending deposit created with lock', {
      depositId: deposit.id,
      userId: data.userId,
      level: data.level,
      amount: data.amount,
    });

    return { deposit };
  }, {
    isolationLevel: 'REPEATABLE READ',
    maxRetries: 3,
  });
}
```

**Database Migration:**
```sql
-- Add partial unique index for pending deposits
CREATE UNIQUE INDEX idx_deposit_user_level_pending
ON deposits (user_id, level)
WHERE status = 'pending';
```

**Tests to Add:**
```typescript
describe('Deposit Race Condition Prevention', () => {
  it('should prevent duplicate pending deposits from concurrent requests', async () => {
    const userId = 1;
    const level = 1;

    // Simulate 10 concurrent clicks
    const promises = Array(10).fill(null).map(() =>
      depositService.createPendingDeposit({ userId, level, amount: 10 })
    );

    const results = await Promise.allSettled(promises);

    // Only one should succeed
    const successful = results.filter(r => r.status === 'fulfilled' && r.value.deposit);
    expect(successful).toHaveLength(1);
  });
});
```

**Rollback Plan:**
- Drop unique index
- Revert to old code
- Delete duplicate pending deposits manually if any

**Risk:** MEDIUM (database lock can affect performance)
**Time Estimate:** 1 day

---

### **FIX #18: Transaction Deduplication**

**Bug:** Race condition in handleTransferEvent can create duplicate transactions
**Impact:** Incorrect balance calculations, duplicate earnings
**Risk Level:** 🚨 CRITICAL

**Solution:**
1. Use database transaction with pessimistic lock
2. Add UNIQUE constraint on tx_hash
3. Use INSERT ON CONFLICT DO NOTHING pattern

**Files to Modify:**
- `src/services/blockchain/deposit-processor.ts` (line 68-76)
- `src/database/entities/Transaction.entity.ts`

**Code Change:**
```typescript
public async handleTransferEvent(
  from: string,
  to: string,
  value: bigint,
  event: any
): Promise<void> {
  const txHash = event.log.transactionHash;
  const blockNumber = event.log.blockNumber;

  try {
    // Use transaction to prevent race conditions
    await AppDataSource.transaction(async (manager) => {
      const transactionRepo = manager.getRepository(Transaction);

      // Check for existing transaction with lock
      const existingTx = await transactionRepo
        .createQueryBuilder('tx')
        .where('tx.tx_hash = :txHash', { txHash })
        .setLock('pessimistic_write')
        .getOne();

      if (existingTx) {
        logger.debug(`Transaction ${txHash} already processed, skipping`);
        return;
      }

      // Process transfer...
      // (rest of the logic)
    });
  } catch (error) {
    logger.error('Error processing Transfer event:', error);
  }
}
```

**Database Migration:**
```sql
-- tx_hash should already be unique, but verify
ALTER TABLE transactions
ADD CONSTRAINT uq_transactions_tx_hash
UNIQUE (tx_hash);
```

**Risk:** LOW
**Time Estimate:** 0.5 days

---

### **FIX #1: Expired Deposit Recovery Mechanism**

**Bug:** Deposits that timeout are marked as failed even if funds were sent
**Impact:** USER LOSES MONEY
**Risk Level:** 🚨 CRITICAL

**Solution:**
1. Don't automatically mark expired deposits as FAILED
2. Create "expired_pending" status
3. Add manual review queue for admins
4. Add blockchain scanner to match expired deposits with on-chain transactions
5. Add user notification with instructions to contact support

**Files to Modify:**
- `src/services/blockchain/deposit-processor.ts` (line 232-258)
- `src/database/entities/Deposit.entity.ts`

**New Status:**
```typescript
export enum DepositStatus {
  PENDING = 'pending',
  CONFIRMED = 'confirmed',
  FAILED = 'failed',
  EXPIRED_PENDING = 'expired_pending', // NEW: Needs manual review
  EXPIRED_CONFIRMED = 'expired_confirmed', // NEW: Manually confirmed
}
```

**Code Change:**
```typescript
// deposit-processor.ts
for (const deposit of pendingDeposits) {
  try {
    const depositAge = Date.now() - deposit.created_at.getTime();

    if (depositAge > this.DEPOSIT_TIMEOUT_MS) {
      // Don't mark as FAILED immediately!
      // Change to EXPIRED_PENDING for manual review
      deposit.status = DepositStatus.EXPIRED_PENDING;
      await depositRepo.save(deposit);

      logger.warn('Deposit expired - moved to manual review queue', {
        depositId: deposit.id,
        userId: deposit.user?.telegram_id,
        level: deposit.level,
        amount: deposit.amount,
        ageHours: Math.round(depositAge / 1000 / 60 / 60),
      });

      // Alert admin
      await notificationService.alertAdminExpiredDeposit(
        deposit.id,
        deposit.user?.telegram_id,
        parseFloat(deposit.amount),
        deposit.level
      );

      // Notify user with instructions
      if (deposit.user) {
        await notificationService.sendNotification(
          deposit.user.telegram_id,
          `⚠️ **Депозит требует проверки**\n\n` +
          `Ваш запрос на депозит уровня ${deposit.level} (${deposit.amount} USDT) создан более 24 часов назад.\n\n` +
          `Если вы уже отправили средства, наши администраторы проверят транзакцию вручную.\n\n` +
          `Если средства НЕ были отправлены, вы можете создать новый запрос.\n\n` +
          `Для помощи свяжитесь с поддержкой: @support`
        );
      }

      continue;
    }

    // ... rest of confirmation logic
  } catch (error) {
    logger.error(`Error checking deposit ${deposit.id}:`, error);
  }
}
```

**Admin Panel Addition:**
- Add "Expired Deposits" view
- Show user wallet, amount, creation time
- Allow admin to:
  - Search blockchain for matching transaction
  - Manually confirm if found
  - Mark as actually failed if not found

**Files to Create:**
- `src/bot/handlers/admin/expired-deposits.handler.ts`

**Tests:**
```typescript
describe('Expired Deposit Handling', () => {
  it('should move deposits to expired_pending after 24 hours', async () => {
    // Create deposit 25 hours ago
    // Run checkPendingDeposits
    // Verify status is expired_pending, not failed
  });

  it('should alert admin and user when deposit expires', async () => {
    // Verify notifications sent
  });

  it('should allow admin to manually confirm expired deposit', async () => {
    // Simulate admin confirmation
    // Verify deposit marked as expired_confirmed
    // Verify earnings created
  });
});
```

**Risk:** LOW (protects user funds)
**Time Estimate:** 2 days

---

### **FIX #4: Payment Retry with Exponential Backoff**

**Bug:** Failed payments stay unpaid forever
**Impact:** Users don't receive earnings
**Risk Level:** 🚨 CRITICAL

**Solution:**
1. Add retry queue with exponential backoff
2. Add max retry limit (e.g., 5 attempts)
3. Add Dead Letter Queue (DLQ) for permanent failures
4. Alert admin after max retries exceeded
5. Add manual retry interface for admins

**Files to Create:**
- `src/services/payment-retry.service.ts`
- `src/database/entities/PaymentRetry.entity.ts`

**New Entity:**
```typescript
@Entity('payment_retries')
export class PaymentRetry {
  @PrimaryGeneratedColumn()
  id: number;

  @Column()
  earning_id: number;

  @Column()
  user_id: number;

  @Column('decimal', { precision: 18, scale: 8 })
  amount: string;

  @Column()
  attempt_count: number;

  @Column({ type: 'timestamp', nullable: true })
  last_attempt_at: Date;

  @Column({ type: 'text', nullable: true })
  last_error: string;

  @Column({ default: false })
  in_dlq: boolean; // Dead Letter Queue

  @CreateDateColumn()
  created_at: Date;
}
```

**Service Implementation:**
```typescript
export class PaymentRetryService {
  private readonly MAX_RETRIES = 5;
  private readonly INITIAL_DELAY_MS = 5000; // 5 seconds

  async scheduleRetry(
    earningId: number,
    userId: number,
    amount: number,
    error: string
  ): Promise<void> {
    const retryRepo = AppDataSource.getRepository(PaymentRetry);

    // Find or create retry record
    let retry = await retryRepo.findOne({
      where: { earning_id: earningId },
    });

    if (!retry) {
      retry = retryRepo.create({
        earning_id: earningId,
        user_id: userId,
        amount: amount.toString(),
        attempt_count: 0,
      });
    }

    retry.attempt_count += 1;
    retry.last_attempt_at = new Date();
    retry.last_error = error;

    // Check if exceeded max retries
    if (retry.attempt_count >= this.MAX_RETRIES) {
      retry.in_dlq = true;
      await retryRepo.save(retry);

      logger.error('Payment retry exceeded max attempts - moved to DLQ', {
        earningId,
        userId,
        amount,
        attempts: retry.attempt_count,
      });

      // Alert admin
      await notificationService.alertAdminPaymentDLQ(
        userId,
        amount,
        retry.attempt_count,
        error
      );

      return;
    }

    await retryRepo.save(retry);

    // Calculate exponential backoff
    const delayMs = this.INITIAL_DELAY_MS * Math.pow(2, retry.attempt_count - 1);

    logger.info('Payment retry scheduled', {
      earningId,
      userId,
      amount,
      attempt: retry.attempt_count,
      delayMs,
    });

    // Schedule retry (using setTimeout or job queue)
    setTimeout(async () => {
      await this.retryPayment(earningId);
    }, delayMs);
  }

  async retryPayment(earningId: number): Promise<void> {
    // Retry payment logic
    // Call paymentService.processUserPayments
    // If fails, call scheduleRetry again
  }

  async getFailedPayments(): Promise<PaymentRetry[]> {
    const retryRepo = AppDataSource.getRepository(PaymentRetry);
    return await retryRepo.find({
      where: { in_dlq: true },
      order: { created_at: 'DESC' },
    });
  }
}
```

**Files to Modify:**
- `src/services/payment.service.ts` (line 87-96)

**Code Change:**
```typescript
for (const [referrerId, earnings] of earningsByUser) {
  try {
    const result = await this.processUserPayments(referrerId, earnings);
    processed += result.processed;
    successful += result.successful;
    failed += result.failed;
  } catch (error) {
    logger.error(`Error processing payments for user ${referrerId}:`, error);

    // NEW: Schedule retry instead of just logging
    const totalAmount = earnings.reduce((sum, e) => sum + parseFloat(e.amount), 0);

    await paymentRetryService.scheduleRetry(
      earnings[0].id, // Use first earning as reference
      referrerId,
      totalAmount,
      error instanceof Error ? error.message : String(error)
    );

    failed += earnings.length;
  }
}
```

**Admin Interface:**
```typescript
// Add to admin panel
bot.action('admin_payment_dlq', async (ctx) => {
  const failedPayments = await paymentRetryService.getFailedPayments();

  // Show list with manual retry buttons
  // Allow admin to mark as resolved
  // Allow admin to manually process payment
});
```

**Risk:** LOW (only improves reliability)
**Time Estimate:** 2 days

---

**PHASE 3 TOTAL:** 6-7 days

---

## 🔴 PHASE 4: HIGH PRIORITY FIXES (USER DEADLOCKS)

### **Objective:** Eliminate all scenarios where users get stuck

---

### **FIX #7: Session State Initialization**

**Bug:** updateSessionState doesn't create session if it doesn't exist
**Impact:** User state not saved, bot doesn't respond correctly
**Risk Level:** 🔴 HIGH

**Solution:**
1. Create session if it doesn't exist
2. Add safety checks in all state operations
3. Add session recovery mechanism

**Files to Modify:**
- `src/bot/middlewares/session.middleware.ts` (line 118-136)

**Code Change:**
```typescript
export const updateSessionState = async (
  userId: number,
  state: BotState,
  data?: Record<string, any>
): Promise<void> => {
  let session = await getSession(userId);

  // CREATE SESSION IF NOT EXISTS
  if (!session) {
    logger.info('Creating new session for state update', { userId, state });
    session = {
      state: BotState.IDLE,
      data: {},
      lastActivity: Date.now(),
    };
  }

  session.state = state;
  if (data) {
    session.data = { ...session.data, ...data };
  }
  session.lastActivity = Date.now();

  const sessionKey = getSessionKey(userId);
  await redis.setex(sessionKey, 86400, JSON.stringify(session));

  logger.debug('Session state updated', { userId, state, hasData: !!data });
};
```

**Tests:**
```typescript
describe('Session State Management', () => {
  it('should create session if not exists', async () => {
    const userId = 999;

    // Verify no session exists
    let session = await getSession(userId);
    expect(session).toBeNull();

    // Update state
    await updateSessionState(userId, BotState.AWAITING_WALLET_ADDRESS);

    // Verify session created
    session = await getSession(userId);
    expect(session).not.toBeNull();
    expect(session.state).toBe(BotState.AWAITING_WALLET_ADDRESS);
  });
});
```

**Risk:** LOW
**Time Estimate:** 0.5 days

---

### **FIX #8: Global Error Handler State Reset**

**Bug:** Errors don't reset session state, user stuck in wrong state
**Impact:** User can't interact with bot
**Risk Level:** 🔴 HIGH

**Solution:**
1. Reset state to IDLE on error
2. Add error recovery instructions
3. Add /reset command for users

**Files to Modify:**
- `src/bot/index.ts` (line 299-311)

**Code Change:**
```typescript
bot.catch(async (err, ctx) => {
  const userId = ctx.from?.id;

  logger.error('Bot error', {
    error: err instanceof Error ? err.message : String(err),
    stack: err instanceof Error ? err.stack : undefined,
    updateType: ctx.updateType,
    userId,
  });

  // RESET SESSION STATE TO PREVENT STUCK USERS
  if (userId) {
    try {
      await updateSessionState(userId, BotState.IDLE);
      logger.info('Session state reset to IDLE after error', { userId });
    } catch (stateError) {
      logger.error('Failed to reset session state', {
        userId,
        error: stateError,
      });
    }
  }

  // Send user-friendly error message with recovery instructions
  try {
    await ctx.reply(
      '❌ Произошла ошибка при обработке вашего запроса.\n\n' +
      '🔄 Состояние сброшено. Вы можете продолжить работу.\n\n' +
      'Используйте /start для возврата в главное меню или /help для помощи.\n\n' +
      'Если проблема повторяется, свяжитесь с поддержкой.'
    );
  } catch (replyError) {
    logger.error('Failed to send error message to user', {
      userId,
      error: replyError,
    });
  }
});
```

**Add Reset Command:**
```typescript
// Add new command
bot.command('reset', async (ctx) => {
  const userId = ctx.from.id;

  await clearSession(userId);

  await ctx.reply(
    '🔄 **Сессия сброшена**\n\n' +
    'Все временные данные очищены.\n' +
    'Вы можете начать заново.\n\n' +
    'Используйте /start для входа.',
    { parse_mode: 'Markdown' }
  );
});
```

**Risk:** LOW
**Time Estimate:** 0.5 days

---

### **FIX #5: Safe Referral ID Storage**

**Bug:** ctx.session may be undefined, referral ID lost
**Impact:** User registered without referrer, loses benefits
**Risk Level:** 🔴 HIGH

**Solution:**
1. Use session middleware properly
2. Add safety check for session existence
3. Store referral ID in Redis separately as backup
4. Add recovery mechanism if session missing

**Files to Modify:**
- `src/bot/handlers/start.handler.ts` (line 52-55)

**Code Change:**
```typescript
export const handleStart = async (ctx: Context) => {
  const authCtx = ctx as AuthContext & AdminContext & SessionContext;
  const startPayload = ctx.text?.split(' ')[1];

  // ... existing code ...

  let referrerId: number | undefined;

  if (startPayload) {
    referrerId = userService.parseReferralCode(startPayload);

    if (referrerId) {
      logger.info('New user from referral', {
        referrerId,
        newUserTelegramId: ctx.from?.id,
      });

      // SAFE STORAGE: Multiple fallbacks

      // 1. Try to store in session (primary method)
      if (authCtx.session) {
        authCtx.session.data = {
          ...authCtx.session.data,
          referrerId,
        };
      } else {
        logger.warn('Session not available, using fallback storage', {
          userId: ctx.from?.id,
          referrerId,
        });
      }

      // 2. Store in Redis as backup (separate key)
      const referralKey = `referral:pending:${ctx.from!.id}`;
      await redis.setex(referralKey, 3600, String(referrerId)); // 1 hour TTL

      // 3. Update session state explicitly
      await updateSessionState(ctx.from!.id, BotState.IDLE, { referrerId });
    }
  }

  // ... rest of handler ...
};
```

**Recovery in Registration:**
```typescript
// registration.handler.ts
export const handleWalletInput = async (ctx: Context) => {
  const authCtx = ctx as AuthContext & SessionContext;

  // ... validation ...

  // Get referrer ID with fallback mechanism
  let referrerId = authCtx.session.data?.referrerId;

  // If not in session, check Redis backup
  if (!referrerId) {
    const referralKey = `referral:pending:${ctx.from!.id}`;
    const storedReferrerId = await redis.get(referralKey);

    if (storedReferrerId) {
      referrerId = parseInt(storedReferrerId, 10);
      logger.info('Recovered referral ID from backup storage', {
        userId: ctx.from!.id,
        referrerId,
      });
    }
  }

  // Create user with referrer
  const result = await userService.createUser({
    telegramId: ctx.from!.id,
    username: ctx.from?.username,
    walletAddress,
    referrerId,
  });

  // ... rest of handler ...

  // Clean up backup storage
  if (referrerId) {
    const referralKey = `referral:pending:${ctx.from!.id}`;
    await redis.del(referralKey);
  }
};
```

**Tests:**
```typescript
describe('Referral ID Storage', () => {
  it('should store referral ID even if session undefined', async () => {
    // Simulate session being undefined
    // Verify referral ID stored in Redis backup
    // Verify recovered during registration
  });

  it('should recover referral ID from backup if session cleared', async () => {
    // Store referral ID
    // Clear session
    // Start registration
    // Verify referral ID recovered
  });
});
```

**Risk:** LOW
**Time Estimate:** 1 day

---

### **FIX #6: Password Recovery Mechanism**

**Bug:** Financial password lost after user object reloaded from DB
**Impact:** User can't withdraw funds
**Risk Level:** 🔴 HIGH

**Solution:**
1. Store plainPassword in Redis temporarily (1 hour)
2. Add password recovery mechanism with admin approval
3. Add "Show password again" button (limited time)
4. Add password reset with verification

**Files to Modify:**
- `src/services/user.service.ts` (line 176-186)
- `src/bot/handlers/registration.handler.ts` (line 141-156)

**Code Change:**
```typescript
// user.service.ts - Store password temporarily
async createUser(data: {...}): Promise<{ user?: User; error?: string }> {
  // ... existing code ...

  await this.userRepository.save(user);

  logger.info('User created', {...});

  // Attach plain password for immediate return
  (user as any).plainPassword = plainPassword;

  // ALSO STORE IN REDIS for 1 hour (recovery window)
  const passwordKey = `password:plain:${user.id}`;
  await redis.setex(passwordKey, 3600, plainPassword); // 1 hour TTL

  logger.info('Plain password stored in Redis for recovery', {
    userId: user.id,
    ttl: 3600,
  });

  return { user };
}
```

**Add Password Retrieval:**
```typescript
// user.service.ts
async getPlainPassword(userId: number): Promise<string | null> {
  const passwordKey = `password:plain:${userId}`;
  const password = await redis.get(passwordKey);

  if (password) {
    logger.info('Plain password retrieved from Redis', { userId });
  }

  return password;
}
```

**Update Verification Handler:**
```typescript
// registration.handler.ts
export const handleStartVerification = async (ctx: Context) => {
  const authCtx = ctx as AuthContext & SessionContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.answerCbQuery(ERROR_MESSAGES.USER_NOT_REGISTERED);
    return;
  }

  if (authCtx.user.is_verified) {
    await ctx.answerCbQuery('Вы уже верифицированы');
    return;
  }

  // Verify user
  const result = await userService.verifyUser(authCtx.user.id);

  if (!result.success) {
    await ctx.answerCbQuery(`Ошибка: ${result.error}`);
    return;
  }

  // Try to get plain password (with fallbacks)
  let plainPassword = (authCtx.user as any).plainPassword;

  if (!plainPassword) {
    // Fallback 1: Try Redis
    plainPassword = await userService.getPlainPassword(authCtx.user.id);
  }

  if (!plainPassword) {
    // Fallback 2: Password no longer available
    plainPassword = 'Пароль был показан при регистрации. ' +
      'Если вы потеряли пароль, используйте команду /reset_password';
  }

  const verificationMessage = BOT_MESSAGES.VERIFICATION_START.replace(
    '{password}',
    `\`${plainPassword}\``
  );

  await ctx.editMessageText(verificationMessage, {
    parse_mode: 'Markdown',
    ...Markup.inlineKeyboard([
      [Markup.button.callback('📧 Указать контакты', 'add_contact_info')],
      [Markup.button.callback('⏭️ Пропустить', 'skip_contact_info')],
      [Markup.button.callback('🔑 Показать пароль еще раз', 'show_password_again')],
    ]),
  });

  await ctx.answerCbQuery(SUCCESS_MESSAGES.VERIFICATION_COMPLETE);
};
```

**Add Show Password Handler:**
```typescript
bot.action('show_password_again', async (ctx) => {
  const authCtx = ctx as AuthContext;

  if (!authCtx.user) {
    await ctx.answerCbQuery('Ошибка: пользователь не найден');
    return;
  }

  const plainPassword = await userService.getPlainPassword(authCtx.user.id);

  if (!plainPassword) {
    await ctx.answerCbQuery(
      '⚠️ Пароль больше недоступен (прошло более 1 часа с момента регистрации).\n\n' +
      'Используйте /reset_password для сброса пароля.',
      { show_alert: true }
    );
    return;
  }

  await ctx.answerCbQuery(
    `🔑 Ваш финансовый пароль:\n\n${plainPassword}\n\n` +
    '⚠️ Сохраните его сейчас! Он больше не будет показан.',
    { show_alert: true }
  );
});
```

**Add Password Reset Command:**
```typescript
bot.command('reset_password', async (ctx) => {
  const authCtx = ctx as AuthContext;

  if (!authCtx.isRegistered || !authCtx.user) {
    await ctx.reply('Вы не зарегистрированы.');
    return;
  }

  await ctx.reply(
    '🔐 **Сброс финансового пароля**\n\n' +
    'Для безопасности сброс пароля требует подтверждения администратором.\n\n' +
    'Ваш запрос отправлен. Администратор свяжется с вами в течение 24 часов.\n\n' +
    '**Для подтверждения личности подготовьте:**\n' +
    '- Telegram ID\n' +
    '- Адрес кошелька\n' +
    '- Дату регистрации',
    { parse_mode: 'Markdown' }
  );

  // Alert admin
  await notificationService.alertAdminPasswordReset(
    authCtx.user.telegram_id,
    authCtx.user.username,
    authCtx.user.wallet_address
  );

  logger.info('Password reset requested', {
    userId: authCtx.user.id,
    telegramId: authCtx.user.telegram_id,
  });
});
```

**Risk:** MEDIUM (involves password handling)
**Time Estimate:** 1.5 days

---

**PHASE 4 TOTAL:** 3.5-4 days

---

## ⚠️ PHASE 5: MEDIUM PRIORITY (DATA CONSISTENCY)

### **Objective:** Ensure atomic operations and prevent data corruption

---

### **FIX #9: Wrap Registration in Database Transaction**

**Bug:** User created but referral relationships fail → inconsistent state
**Impact:** Referrer doesn't receive commissions, stats incorrect
**Risk Level:** ⚠️ MEDIUM

**Solution:**
1. Wrap entire registration in single database transaction
2. Rollback if any step fails
3. Add validation before commit

**Files to Modify:**
- `src/bot/handlers/registration.handler.ts` (line 79-134)

**Code Change:**
```typescript
export const handleWalletInput = async (ctx: Context) => {
  const authCtx = ctx as AuthContext & SessionContext;

  // ... validation ...

  const walletAddress = ctx.text?.trim();
  const referrerId = authCtx.session.data?.referrerId;

  // WRAP IN TRANSACTION
  const result = await withTransaction(async (manager) => {
    const userRepo = manager.getRepository(User);

    // Create user
    const { user, error } = await userService.createUser({
      telegramId: ctx.from!.id,
      username: ctx.from?.username,
      walletAddress,
      referrerId,
    });

    if (error || !user) {
      throw new Error(error || 'Failed to create user');
    }

    // Create referral relationships (inside same transaction)
    if (referrerId) {
      const referralResult = await referralService.createReferralRelationships(
        user.id,
        referrerId,
        manager // Pass transaction manager
      );

      if (!referralResult.success) {
        // Now we FAIL the registration if referrals can't be created
        throw new Error(referralResult.error || 'Failed to create referral relationships');
      }

      logger.info('Referral relationships created', {
        userId: user.id,
        referrerId,
      });
    }

    return { user };
  }, {
    isolationLevel: 'REPEATABLE READ',
  });

  if (!result.user) {
    await ctx.reply('❌ Ошибка регистрации. Пожалуйста, попробуйте позже.');
    await updateSessionState(ctx.from!.id, BotState.IDLE);
    return;
  }

  // ... success message ...
};
```

**Update ReferralService to accept transaction manager:**
```typescript
// referral/core.service.ts
async createReferralRelationships(
  newUserId: number,
  directReferrerId: number,
  transactionManager?: EntityManager // NEW: Optional transaction manager
): Promise<{ success: boolean; error?: string }> {
  const referralRepo = transactionManager
    ? transactionManager.getRepository(Referral)
    : this.referralRepository;

  const userRepo = transactionManager
    ? transactionManager.getRepository(User)
    : this.userRepository;

  try {
    // ... existing logic using referralRepo and userRepo ...
  } catch (error) {
    // ...
  }
}
```

**Risk:** LOW (improves consistency)
**Time Estimate:** 1 day

---

### **FIX #10: Wrap Referral Chain Creation in Transaction**

**Bug:** Partial referral chains created if one level fails
**Impact:** Incomplete referral structure
**Risk Level:** ⚠️ MEDIUM

**Solution:**
1. Already using transaction manager from Fix #9
2. Ensure all referral levels created atomically
3. Add validation for complete chain

**Files to Modify:**
- `src/services/referral/core.service.ts` (line 103-157)

**Code Change:**
```typescript
async createReferralRelationships(
  newUserId: number,
  directReferrerId: number,
  transactionManager?: EntityManager
): Promise<{ success: boolean; error?: string }> {
  const execute = async (manager: EntityManager) => {
    const referralRepo = manager.getRepository(Referral);
    const userRepo = manager.getRepository(User);

    // ... validation logic ...

    // Collect all referrals to create
    const referralsToCreate: Partial<Referral>[] = [];

    for (let i = 0; i < referrers.length && i < REFERRAL_DEPTH; i++) {
      const referrer = referrers[i];
      const level = i + 1;

      // Check if exists
      const existing = await referralRepo.findOne({
        where: {
          referrer_id: referrer.id,
          referral_id: newUserId,
        },
      });

      if (!existing) {
        referralsToCreate.push({
          referrer_id: referrer.id,
          referral_id: newUserId,
          level,
          total_earned: '0',
        });
      }
    }

    // Create all at once (atomic)
    if (referralsToCreate.length > 0) {
      await referralRepo.save(referralsToCreate);

      logger.info('Referral chain created atomically', {
        newUserId,
        directReferrerId,
        levelsCreated: referralsToCreate.length,
      });
    }

    return { success: true };
  };

  // If transaction manager provided, use it; otherwise create new transaction
  if (transactionManager) {
    return await execute(transactionManager);
  } else {
    return await withTransaction(execute);
  }
}
```

**Risk:** LOW
**Time Estimate:** 0.5 days

---

### **FIX #11: Add Null Checks for Referrers**

**Bug:** Assuming referrer exists with ! operator, can be null
**Impact:** Crash when referrer deleted
**Risk Level:** ⚠️ MEDIUM

**Solution:**
1. Add explicit null checks
2. Handle deleted referrers gracefully
3. Add referrer existence validation

**Files to Modify:**
- `src/services/referral/core.service.ts` (line 68-71)

**Code Change:**
```typescript
async createReferralRelationships(
  newUserId: number,
  directReferrerId: number,
  transactionManager?: EntityManager
): Promise<{ success: boolean; error?: string }> {
  const execute = async (manager: EntityManager) => {
    const userRepo = manager.getRepository(User);

    // Validate direct referrer exists
    const directReferrer = await userRepo.findOne({
      where: { id: directReferrerId },
    });

    if (!directReferrer) {
      logger.error('Direct referrer not found', {
        directReferrerId,
        newUserId,
      });
      return {
        success: false,
        error: 'Реферер не найден. Возможно, аккаунт был удален.',
      };
    }

    // Get referral chain
    const referrers = await this.getReferralChain(directReferrerId, REFERRAL_DEPTH);

    // Add direct referrer as level 1 (already validated)
    referrers.unshift(directReferrer); // No ! operator needed

    // Filter out any null values (defensive)
    const validReferrers = referrers.filter((r): r is User => r !== null && r !== undefined);

    if (validReferrers.length === 0) {
      return {
        success: false,
        error: 'Не удалось построить реферальную цепочку',
      };
    }

    // ... rest of logic with validReferrers ...
  };

  // ...
}
```

**Also update getReferralChain:**
```typescript
async getReferralChain(
  userId: number,
  depth: number = REFERRAL_DEPTH
): Promise<User[]> {
  const chain: User[] = [];

  try {
    let currentUser = await this.userRepository.findOne({
      where: { id: userId },
      relations: ['referrer'],
    });

    for (let level = 0; level < depth; level++) {
      // Explicit null check
      if (!currentUser || !currentUser.referrer) {
        break;
      }

      chain.push(currentUser.referrer);

      // Load next level
      currentUser = await this.userRepository.findOne({
        where: { id: currentUser.referrer.id },
        relations: ['referrer'],
      });
    }

    return chain;
  } catch (error) {
    logger.error('Error getting referral chain', {
      userId,
      depth,
      error: error instanceof Error ? error.message : String(error),
    });
    return [];
  }
}
```

**Risk:** LOW
**Time Estimate:** 0.5 days

---

**PHASE 5 TOTAL:** 2 days

---

## 🟡 PHASE 6: LOW PRIORITY (PERFORMANCE OPTIMIZATION)

### **Objective:** Improve performance and scalability

---

### **FIX #12: Optimize getReferralChain with Recursive CTE**

**Bug:** N+1 queries for referral chain
**Impact:** Slow response time, database load
**Risk Level:** 🟡 LOW

**Solution:**
1. Use PostgreSQL recursive CTE (Common Table Expression)
2. Single query instead of N queries
3. Add query caching

**Files to Modify:**
- `src/services/referral/core.service.ts` (line 22-51)

**Code Change:**
```typescript
async getReferralChain(
  userId: number,
  depth: number = REFERRAL_DEPTH
): Promise<User[]> {
  try {
    // Use recursive CTE for efficient chain retrieval
    const result = await AppDataSource.query(
      `
      WITH RECURSIVE referral_chain AS (
        -- Base case: start with the user
        SELECT
          u.id,
          u.telegram_id,
          u.username,
          u.wallet_address,
          u.referrer_id,
          u.created_at,
          0 AS level
        FROM users u
        WHERE u.id = $1

        UNION ALL

        -- Recursive case: get referrer of previous level
        SELECT
          u.id,
          u.telegram_id,
          u.username,
          u.wallet_address,
          u.referrer_id,
          u.created_at,
          rc.level + 1 AS level
        FROM users u
        INNER JOIN referral_chain rc ON u.id = rc.referrer_id
        WHERE rc.level < $2
      )
      SELECT *
      FROM referral_chain
      WHERE level > 0
      ORDER BY level ASC;
      `,
      [userId, depth]
    );

    // Map raw results to User entities
    return result.map((row: any) => {
      const user = new User();
      user.id = row.id;
      user.telegram_id = row.telegram_id;
      user.username = row.username;
      user.wallet_address = row.wallet_address;
      user.referrer_id = row.referrer_id;
      user.created_at = row.created_at;
      return user;
    });
  } catch (error) {
    logger.error('Error getting referral chain with CTE', {
      userId,
      depth,
      error: error instanceof Error ? error.message : String(error),
    });
    return [];
  }
}
```

**Add Caching:**
```typescript
async getReferralChain(
  userId: number,
  depth: number = REFERRAL_DEPTH
): Promise<User[]> {
  // Check cache first
  const cacheKey = `referral:chain:${userId}:${depth}`;
  const cached = await redis.get(cacheKey);

  if (cached) {
    return JSON.parse(cached);
  }

  // Execute query
  const chain = await this.getReferralChainFromDB(userId, depth);

  // Cache for 5 minutes
  await redis.setex(cacheKey, 300, JSON.stringify(chain));

  return chain;
}
```

**Performance Improvement:**
- Before: 3 sequential queries for depth=3
- After: 1 single query
- **~60% faster**

**Risk:** LOW
**Time Estimate:** 1 day

---

### **FIX #13: Increase Pending Deposit Batch Size**

**Bug:** Only 100 pending deposits processed per cycle
**Impact:** Backlog growth under high load
**Risk Level:** 🟡 LOW

**Solution:**
1. Make batch size configurable
2. Increase default to 500
3. Add monitoring for backlog size
4. Add parallel processing

**Files to Modify:**
- `src/services/blockchain/deposit-processor.ts` (line 212)
- `src/config/index.ts`

**Code Change:**
```typescript
// config/index.ts
export const config = {
  // ... existing config ...
  blockchain: {
    // ... existing ...
    depositBatchSize: parseInt(process.env.DEPOSIT_BATCH_SIZE || '500', 10),
    depositConcurrency: parseInt(process.env.DEPOSIT_CONCURRENCY || '5', 10),
  },
};

// deposit-processor.ts
public async checkPendingDeposits(): Promise<void> {
  try {
    const depositRepo = AppDataSource.getRepository(Deposit);

    const BATCH_SIZE = config.blockchain.depositBatchSize; // Now 500

    const pendingDeposits = await depositRepo.find({
      where: { status: TransactionStatus.PENDING },
      relations: ['user'],
      order: { created_at: 'ASC' },
      take: BATCH_SIZE,
    });

    if (pendingDeposits.length === 0) {
      return;
    }

    logger.info(`Checking ${pendingDeposits.length} pending deposits...`);

    // Process in parallel batches for speed
    const CONCURRENCY = config.blockchain.depositConcurrency; // 5 concurrent
    for (let i = 0; i < pendingDeposits.length; i += CONCURRENCY) {
      const batch = pendingDeposits.slice(i, i + CONCURRENCY);

      await Promise.all(
        batch.map(deposit => this.processSingleDeposit(deposit))
      );
    }
  } catch (error) {
    logger.error('Error checking pending deposits:', error);
  }
}

private async processSingleDeposit(deposit: Deposit): Promise<void> {
  // Move existing deposit processing logic here
  // ... (current logic from lines 229-316)
}
```

**Add Backlog Monitoring:**
```typescript
async getDepositBacklogSize(): Promise<number> {
  const depositRepo = AppDataSource.getRepository(Deposit);
  return await depositRepo.count({
    where: { status: TransactionStatus.PENDING },
  });
}

// Alert if backlog > threshold
if (backlogSize > 1000) {
  await notificationService.alertAdminDepositBacklog(backlogSize);
}
```

**Risk:** LOW
**Time Estimate:** 1 day

---

### **FIX #14: Move Admin Sessions to Redis**

**Bug:** Admin sessions stored in memory, lost on restart
**Impact:** All admins logged out on bot restart
**Risk Level:** 🟡 LOW

**Solution:**
1. Store admin sessions in Redis
2. Add session persistence
3. Add cross-instance session sharing (for scaling)

**Files to Modify:**
- `src/bot/middlewares/admin.middleware.ts`

**Current (in-memory):**
```typescript
const adminSessions = new Map<number, string>(); // Lost on restart!
```

**New (Redis-based):**
```typescript
// admin.middleware.ts
const ADMIN_SESSION_PREFIX = 'admin:session:';
const ADMIN_SESSION_TTL = 3600; // 1 hour

export const setAdminSession = async (
  telegramId: number,
  sessionToken: string
): Promise<void> => {
  const key = `${ADMIN_SESSION_PREFIX}${telegramId}`;
  await redis.setex(key, ADMIN_SESSION_TTL, sessionToken);

  logger.info('Admin session stored in Redis', {
    telegramId,
    ttl: ADMIN_SESSION_TTL,
  });
};

export const getAdminSession = async (
  telegramId: number
): Promise<string | null> => {
  const key = `${ADMIN_SESSION_PREFIX}${telegramId}`;
  return await redis.get(key);
};

export const clearAdminSession = async (
  telegramId: number
): Promise<void> => {
  const key = `${ADMIN_SESSION_PREFIX}${telegramId}`;
  await redis.del(key);
};

// Update middleware
export const adminMiddleware: MiddlewareFn<Context> = async (ctx, next) => {
  const adminCtx = ctx as AdminContext;

  if (!ctx.from) {
    return next();
  }

  // Check if user is admin
  const admin = await adminService.findByTelegramId(ctx.from.id);

  if (!admin) {
    adminCtx.isAdmin = false;
    adminCtx.isAuthenticated = false;
    return next();
  }

  adminCtx.isAdmin = true;
  adminCtx.admin = admin;

  // Check session from Redis (not memory)
  const sessionToken = await getAdminSession(ctx.from.id);

  if (!sessionToken) {
    adminCtx.isAuthenticated = false;
    return next();
  }

  // Validate session
  const session = await adminService.getSessionByToken(sessionToken);

  if (!session || !session.is_active || session.expires_at < new Date()) {
    // Session expired
    await clearAdminSession(ctx.from.id);
    adminCtx.isAuthenticated = false;
    return next();
  }

  // Update activity and extend TTL
  await adminService.updateSessionActivity(session.id);
  await setAdminSession(ctx.from.id, sessionToken); // Refresh Redis TTL

  adminCtx.isAuthenticated = true;
  adminCtx.adminSession = session;

  return next();
};
```

**Benefits:**
- Sessions survive bot restarts
- Cross-instance compatibility (for horizontal scaling)
- Automatic TTL management

**Risk:** LOW
**Time Estimate:** 1 day

---

### **FIX #15: Add EIP-55 Checksum Validation**

**Bug:** Wallet addresses validated only by regex, not checksum
**Impact:** User can enter typo in address, lose funds
**Risk Level:** 🟡 LOW

**Solution:**
1. Use ethers.getAddress() for validation
2. Normalize to checksum format
3. Show warning if case doesn't match checksum

**Files to Modify:**
- `src/utils/validation.util.ts`

**Code Change:**
```typescript
import { getAddress, isAddress } from 'ethers';

/**
 * Validate BSC address with EIP-55 checksum
 */
export function isValidBSCAddress(address: string): boolean {
  if (!address || typeof address !== 'string') {
    return false;
  }

  // Basic format check
  if (!/^0x[a-fA-F0-9]{40}$/.test(address)) {
    return false;
  }

  // EIP-55 checksum validation
  try {
    getAddress(address); // Throws if invalid checksum
    return true;
  } catch (error) {
    logger.warn('Invalid address checksum', { address });
    return false;
  }
}

/**
 * Normalize address to checksummed format
 */
export function normalizeWalletAddress(address: string): string {
  try {
    return getAddress(address); // Returns checksummed address
  } catch (error) {
    // If invalid, return lowercase (for backward compatibility)
    return address.toLowerCase();
  }
}

/**
 * Check if address has correct checksum
 */
export function hasValidChecksum(address: string): boolean {
  try {
    const checksummed = getAddress(address);
    return checksummed === address; // Exact match
  } catch {
    return false;
  }
}
```

**Update Registration Handler:**
```typescript
// registration.handler.ts
export const handleWalletInput = async (ctx: Context) => {
  const walletAddress = ctx.text?.trim();

  if (!walletAddress) {
    await ctx.reply(ERROR_MESSAGES.INVALID_INPUT);
    return;
  }

  // Validate with checksum
  if (!isValidBSCAddress(walletAddress)) {
    await ctx.reply(
      '❌ Неверный формат адреса кошелька.\n\n' +
      'Адрес должен:\n' +
      '• Начинаться с 0x\n' +
      '• Содержать 40 символов\n' +
      '• Иметь корректную контрольную сумму (EIP-55)\n\n' +
      'Пожалуйста, скопируйте адрес из вашего кошелька.'
    );
    return;
  }

  // Warn if checksum doesn't match
  if (!hasValidChecksum(walletAddress)) {
    await ctx.reply(
      '⚠️ **Предупреждение:** Регистр букв в адресе не соответствует контрольной сумме.\n\n' +
      'Это может указывать на опечатку. Проверьте адрес еще раз.\n\n' +
      'Правильный формат:\n' +
      `\`${normalizeWalletAddress(walletAddress)}\`\n\n` +
      'Продолжить с текущим адресом?',
      {
        parse_mode: 'Markdown',
        ...Markup.inlineKeyboard([
          [Markup.button.callback('✅ Да, продолжить', 'confirm_address')],
          [Markup.button.callback('❌ Ввести заново', 'start_registration')],
        ]),
      }
    );
    return;
  }

  // ... rest of registration logic ...
};
```

**Risk:** LOW (only adds validation)
**Time Estimate:** 0.5 days

---

**PHASE 6 TOTAL:** 4 days

---

## 🔵 PHASE 7: ARCHITECTURAL IMPROVEMENTS

### **Objective:** Increase reliability and observability

---

### **FIX #16: Smart Historical Event Fetching**

**Bug:** fetchHistoricalEvents called on every reconnect, overloads system
**Impact:** Wasted resources, slow reconnection
**Risk Level:** 🔵 ARCHITECTURAL

**Solution:**
1. Track last fetched block in Redis
2. Only fetch since last successful fetch
3. Add rate limiting for historical fetching

**Files to Modify:**
- `src/services/blockchain/event-monitor.ts` (line 158-238)

**Code Change:**
```typescript
private async fetchHistoricalEvents(): Promise<void> {
  const LAST_FETCH_KEY = 'blockchain:last_historical_fetch';
  const FETCH_COOLDOWN_MS = 5 * 60 * 1000; // 5 minutes cooldown

  try {
    // Check if recently fetched (prevent spam)
    const lastFetchTime = await redis.get(`${LAST_FETCH_KEY}:time`);
    if (lastFetchTime) {
      const timeSinceLastFetch = Date.now() - parseInt(lastFetchTime);
      if (timeSinceLastFetch < FETCH_COOLDOWN_MS) {
        logger.info('Historical fetch on cooldown', {
          remainingMs: FETCH_COOLDOWN_MS - timeSinceLastFetch,
        });
        return;
      }
    }

    const httpProvider = this.providerManager.getHttpProvider();
    const currentBlock = await httpProvider.getBlockNumber();

    // Get last fetched block from Redis (persists across restarts)
    const lastFetchedBlock = await redis.get(`${LAST_FETCH_KEY}:block`);
    const fromBlock = lastFetchedBlock
      ? parseInt(lastFetchedBlock) + 1
      : currentBlock - this.HISTORICAL_BLOCKS_LOOKBACK;

    const toBlock = currentBlock;

    if (fromBlock >= toBlock) {
      logger.info('Already up to date with blockchain');
      return;
    }

    logger.info('Fetching historical events', {
      fromBlock,
      toBlock,
      blocksToFetch: toBlock - fromBlock,
    });

    // ... existing fetch logic ...

    // Update last fetched block
    await redis.set(`${LAST_FETCH_KEY}:block`, String(toBlock));
    await redis.set(`${LAST_FETCH_KEY}:time`, String(Date.now()));

    logger.info('Historical fetch complete', {
      fromBlock,
      toBlock,
      processed,
    });
  } catch (error) {
    logger.error('Error fetching historical events:', error);
  }
}
```

**Update startMonitoring:**
```typescript
public async startMonitoring(): Promise<void> {
  if (this.isMonitoring) {
    logger.warn('Blockchain monitoring already running');
    return;
  }

  try {
    await this.providerManager.initializeWebSocket();
    // ... setup listeners ...

    // Only fetch historical on FIRST start (not reconnects)
    if (!this.hasEverFetched) {
      await this.fetchHistoricalEvents();
      this.hasEverFetched = true;
    } else {
      logger.info('Skipping historical fetch (reconnect)');
    }

    this.isMonitoring = true;
  } catch (error) {
    logger.error('Failed to start monitoring:', error);
    throw error;
  }
}
```

**Risk:** LOW
**Time Estimate:** 1 day

---

### **FIX #17: Notification Failure Alerting**

**Bug:** Notifications silently fail, users don't know about important events
**Impact:** User misses deposit confirmations, earnings, etc.
**Risk Level:** 🔵 ARCHITECTURAL

**Solution:**
1. Track notification failures
2. Retry notifications with exponential backoff
3. Alert admin if user unreachable
4. Store failed notifications for manual review

**Files to Create:**
- `src/database/entities/FailedNotification.entity.ts`
- `src/services/notification-retry.service.ts`

**New Entity:**
```typescript
@Entity('failed_notifications')
export class FailedNotification {
  @PrimaryGeneratedColumn()
  id: number;

  @Column()
  user_telegram_id: number;

  @Column()
  notification_type: string; // 'deposit_confirmed', 'earning', etc.

  @Column('text')
  message: string;

  @Column('jsonb', { nullable: true })
  metadata: any;

  @Column()
  attempt_count: number;

  @Column({ type: 'text', nullable: true })
  last_error: string;

  @Column({ default: false })
  resolved: boolean;

  @CreateDateColumn()
  created_at: Date;

  @Column({ type: 'timestamp', nullable: true })
  last_attempt_at: Date;
}
```

**Update Notification Service:**
```typescript
async sendNotification(
  telegramId: number,
  message: string,
  options?: {
    type?: string;
    metadata?: any;
    critical?: boolean;
  }
): Promise<{ success: boolean; error?: string }> {
  try {
    await this.bot.telegram.sendMessage(telegramId, message, {
      parse_mode: 'Markdown',
    });

    return { success: true };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);

    logger.error('Failed to send notification', {
      telegramId,
      type: options?.type,
      error: errorMessage,
    });

    // Store failed notification
    const failedRepo = AppDataSource.getRepository(FailedNotification);
    await failedRepo.save({
      user_telegram_id: telegramId,
      notification_type: options?.type || 'generic',
      message,
      metadata: options?.metadata,
      attempt_count: 1,
      last_error: errorMessage,
      last_attempt_at: new Date(),
    });

    // If critical, alert admin immediately
    if (options?.critical) {
      await this.alertAdminNotificationFailure(
        telegramId,
        options.type || 'generic',
        errorMessage
      );
    }

    return { success: false, error: errorMessage };
  }
}
```

**Add Retry Job:**
```typescript
// Run every 30 minutes
async retryFailedNotifications(): Promise<void> {
  const failedRepo = AppDataSource.getRepository(FailedNotification);

  const pending = await failedRepo.find({
    where: {
      resolved: false,
      attempt_count: LessThan(5), // Max 5 retries
    },
    order: { created_at: 'ASC' },
    take: 100,
  });

  for (const failed of pending) {
    try {
      await this.bot.telegram.sendMessage(
        failed.user_telegram_id,
        failed.message,
        { parse_mode: 'Markdown' }
      );

      // Success - mark as resolved
      failed.resolved = true;
      await failedRepo.save(failed);

      logger.info('Notification retry successful', {
        id: failed.id,
        telegramId: failed.user_telegram_id,
      });
    } catch (error) {
      // Failed again - increment counter
      failed.attempt_count += 1;
      failed.last_error = error instanceof Error ? error.message : String(error);
      failed.last_attempt_at = new Date();
      await failedRepo.save(failed);

      // If max retries reached, alert admin
      if (failed.attempt_count >= 5) {
        await this.alertAdminNotificationGaveUp(
          failed.user_telegram_id,
          failed.notification_type,
          failed.message
        );
      }
    }
  }
}
```

**Admin Interface:**
```typescript
// View failed notifications
bot.action('admin_failed_notifications', async (ctx) => {
  const failedRepo = AppDataSource.getRepository(FailedNotification);

  const failed = await failedRepo.find({
    where: { resolved: false },
    order: { created_at: 'DESC' },
    take: 10,
  });

  // Show list with manual retry/resolve buttons
});
```

**Risk:** LOW
**Time Estimate:** 2 days

---

### **Health Check Endpoints**

**Create REST endpoints for monitoring:**

**Files to Create:**
- `src/api/health.ts`

```typescript
import express from 'express';

const router = express.Router();

// Basic health check
router.get('/health', async (req, res) => {
  const checks = {
    database: await checkDatabase(),
    redis: await checkRedis(),
    blockchain: await checkBlockchain(),
    bot: await checkBot(),
  };

  const isHealthy = Object.values(checks).every(c => c.status === 'ok');

  res.status(isHealthy ? 200 : 503).json({
    status: isHealthy ? 'healthy' : 'unhealthy',
    timestamp: new Date().toISOString(),
    checks,
  });
});

// Detailed metrics
router.get('/metrics', async (req, res) => {
  const metrics = {
    users: {
      total: await userService.getTotalUsers(),
      verified: await userService.getVerifiedUsers(),
    },
    deposits: {
      pending: await depositService.getPendingCount(),
      confirmed: await depositService.getConfirmedCount(),
    },
    payments: {
      pending: await paymentService.getPendingCount(),
      failed: await paymentService.getFailedCount(),
    },
    blockchain: {
      currentBlock: await blockchainService.getCurrentBlock(),
      lastProcessedBlock: await blockchainService.getLastProcessedBlock(),
    },
  };

  res.json(metrics);
});

export default router;
```

**Risk:** LOW
**Time Estimate:** 1 day

---

**PHASE 7 TOTAL:** 4 days

---

## 📝 PHASE 8: MIGRATIONS & ROLLBACK PLANS

### **Objective:** Ensure safe deployment with rollback capability

**Tasks:**
1. Create database migration scripts
2. Document rollback procedures
3. Test migrations on production copy
4. Create deployment checklist

**Time Estimate:** 2-3 days

---

## ✅ PHASE 9: COMPREHENSIVE TESTING

### **Objective:** Prevent regressions and ensure quality

**Test Coverage:**
1. Unit tests for all services (80%+ coverage)
2. Integration tests for workflows
3. End-to-end tests for user journeys
4. Load testing for performance
5. Security testing for vulnerabilities

**Time Estimate:** 5-7 days

---

## 📚 PHASE 10: DOCUMENTATION & DEPLOYMENT

### **Objective:** Document changes and create deployment guide

**Deliverables:**
1. Update ARCHITECTURE.md
2. Create CHANGELOG.md
3. Write deployment guide
4. Document API changes
5. Create runbook for operations

**Time Estimate:** 2-3 days

---

## 📊 TOTAL TIMELINE SUMMARY

| Phase | Duration | Risk | Priority |
|-------|----------|------|----------|
| Phase 1: Foundation | 5-6 days | LOW | CRITICAL |
| Phase 2: Database Layer | 4 days | MEDIUM | CRITICAL |
| Phase 3: Critical Fixes | 6-7 days | HIGH | CRITICAL |
| Phase 4: User Deadlocks | 3.5-4 days | MEDIUM | HIGH |
| Phase 5: Data Consistency | 2 days | LOW | MEDIUM |
| Phase 6: Performance | 4 days | LOW | LOW |
| Phase 7: Architecture | 4 days | LOW | MEDIUM |
| Phase 8: Migrations | 2-3 days | HIGH | CRITICAL |
| Phase 9: Testing | 5-7 days | LOW | CRITICAL |
| Phase 10: Documentation | 2-3 days | LOW | MEDIUM |
| **TOTAL** | **38-47 days** | **~6-9 weeks** | - |

---

## 🚀 DEPLOYMENT STRATEGY

### **Incremental Rollout:**

1. **Week 1-2:** Foundation + Database Layer (Phases 1-2)
2. **Week 3-4:** Critical Fixes (Phase 3) → Deploy to production
3. **Week 5:** User Deadlocks + Data Consistency (Phases 4-5) → Deploy
4. **Week 6:** Performance + Architecture (Phases 6-7) → Deploy
5. **Week 7-8:** Testing + Documentation (Phases 9-10)
6. **Week 9:** Final deployment + monitoring

### **Success Metrics:**

- ✅ Zero money loss incidents
- ✅ <0.1% user deadlock rate
- ✅ 99.9% deposit confirmation rate
- ✅ <1% notification failure rate
- ✅ <500ms avg response time
- ✅ Zero data inconsistencies

---

## ✅ READY TO BEGIN IMPLEMENTATION

This master plan provides a comprehensive, methodical approach to fixing all identified issues while maintaining system stability and user trust.

**Next Steps:**
1. Review and approve plan
2. Setup development environment
3. Begin Phase 1: Foundation

Would you like me to proceed with implementation?
