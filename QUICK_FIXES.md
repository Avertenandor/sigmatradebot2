# Quick Fixes for Critical Issues

**Generated:** 2025-11-12
**Status:** 2 P0 Critical issues require immediate attention

---

## P0 CRITICAL #1: Add Trust Proxy Configuration

### Problem
Without trust proxy, client IP detection fails behind GCP Load Balancer.

### Quick Fix

#### Option A: If using Telegraf with built-in webhook
```typescript
// src/bot/index.ts or wherever bot is initialized

import express from 'express';
import { Telegraf } from 'telegraf';

const app = express();

// ✅ ADD THIS LINE
app.set('trust proxy', true);

// Or be more specific (trust only first proxy = GCP LB)
app.set('trust proxy', 1);

// Then attach Telegraf webhook
bot.telegram.setWebhook(webhookUrl, {
  secret_token: secretToken,
});

// If using express webhook callback
app.use(bot.webhookCallback('/telegram/webhook'));

app.listen(port);
```

#### Option B: If webhook server already exists
Find where Express app is created and add `trust proxy` immediately after creation:
```typescript
const app = express();
app.set('trust proxy', true);  // ← ADD THIS
```

### Verification
```bash
# After deploying, check logs show real client IP, not internal LB IP
# Internal IP: 10.x.x.x or 172.x.x.x
# Should see: External IPs like 91.108.x.x (Telegram servers)
```

---

## P0 CRITICAL #2: Replace parseFloat in Financial Services

### Problem
`parseFloat()` causes precision loss in money calculations:
- `0.1 + 0.2 !== 0.3` in JavaScript
- Sum/comparison errors in deposits/payments/rewards

### Files to Fix (15+ occurrences)

#### 1. src/services/payment-retry.service.ts

**Line 210:**
```typescript
// BEFORE ❌
const amount = parseFloat(retry.amount);

// AFTER ✅
import { fromDbString, toUsdtString } from '../utils/money.util';
const amountMoney = fromDbString(retry.amount);
```

**Line 312, 326, 346:**
```typescript
// BEFORE ❌
amount: parseFloat(retry.amount),

// AFTER ✅
amount: parseFloat(toUsdtString(amountMoney)),  // For logging/notifications only
```

**Line 467, 472:**
```typescript
// BEFORE ❌
(sum, r) => sum + parseFloat(r.amount),

// AFTER ✅
import { sum as sumMoney, fromDbString } from '../utils/money.util';
const totalMoney = sumMoney(retries.map(r => fromDbString(r.amount)));
const total = parseFloat(toUsdtString(totalMoney));  // For display only
```

#### 2. src/services/deposit.service.ts

**Line 355, 380:**
```typescript
// BEFORE ❌
parseFloat(deposit.amount),

// AFTER ✅
const amountMoney = fromDbString(deposit.amount);
parseFloat(toUsdtString(amountMoney)),  // Only for notification display
```

**Line 424, 449:**
```typescript
// BEFORE ❌
return deposits.reduce((sum, d) => sum + parseFloat(d.amount), 0);

// AFTER ✅
import { sum as sumMoney, fromDbString, toUsdtString } from '../utils/money.util';
const totalMoney = sumMoney(deposits.map(d => fromDbString(d.amount)));
return parseFloat(toUsdtString(totalMoney));  // Convert to number for return type
// OR better: change return type to string and return toUsdtString(totalMoney)
```

#### 3. src/services/reward.service.ts

**Line 254:**
```typescript
// BEFORE ❌
const depositAmount = parseFloat(deposit.amount);

// AFTER ✅
const depositAmountMoney = fromDbString(deposit.amount);
```

**Line 338, 340, 342:**
```typescript
// BEFORE ❌
totalAmount: parseFloat(totalAmountResult?.total || '0'),
paidAmount: parseFloat(paidAmountResult?.total || '0'),
pendingAmount: parseFloat(pendingAmountResult?.total || '0'),

// AFTER ✅
const totalMoney = fromDbString(totalAmountResult?.total || '0');
const paidMoney = fromDbString(paidAmountResult?.total || '0');
const pendingMoney = fromDbString(pendingAmountResult?.total || '0');

// If return type requires number, convert at the end
totalAmount: parseFloat(toUsdtString(totalMoney)),
paidAmount: parseFloat(toUsdtString(paidMoney)),
pendingAmount: parseFloat(toUsdtString(pendingMoney)),
```

#### 4. src/services/user.service.ts

**Line 483:**
```typescript
// BEFORE ❌
(sum, earning) => sum + parseFloat(earning.amount),

// AFTER ✅
import { sum as sumMoney, fromDbString, toUsdtString } from '../utils/money.util';
const totalMoney = sumMoney(earnings.map(e => fromDbString(e.amount)));
const total = parseFloat(toUsdtString(totalMoney));
```

### Universal Pattern

```typescript
// 1. Import money utilities
import {
  fromDbString,
  toUsdtString,
  sum as sumMoney,
  add,
  subtract,
  compare,
  type MoneyAmount
} from '../utils/money.util';

// 2. Read from DB → MoneyAmount
const amountMoney: MoneyAmount = fromDbString(dbRecord.amount);

// 3. Do calculations with bigint
const totalMoney = sumMoney([amount1, amount2, amount3]);
const diffMoney = subtract(amount1, amount2);

// 4. Compare precisely
if (compare(actualMoney, expectedMoney) >= 0) {
  // actualMoney >= expectedMoney (no float errors!)
}

// 5. Only convert to number/float for:
//    - Display in UI/notifications
//    - Logging (but log string is better)
const displayAmount = parseFloat(toUsdtString(amountMoney));  // OK for display
const logAmount = toUsdtString(amountMoney);  // Better: keep as string "100.50"
```

### Test After Fix
```typescript
// Test file: tests/unit/money-precision.test.ts
import { fromUsdtString, add, toUsdtString } from '../utils/money.util';

describe('Money Precision', () => {
  it('should add 0.1 + 0.2 = 0.3 exactly', () => {
    const a = fromUsdtString('0.1');
    const b = fromUsdtString('0.2');
    const result = add(a, b);
    expect(toUsdtString(result)).toBe('0.3');  // ✅ PASS

    // Compare to parseFloat
    expect(0.1 + 0.2).not.toBe(0.3);  // ❌ Demonstrates float problem
  });

  it('should sum deposit amounts precisely', () => {
    const amounts = ['100.01', '200.02', '300.03'].map(fromUsdtString);
    const total = sumMoney(amounts);
    expect(toUsdtString(total)).toBe('600.06');  // ✅ Exact

    // Compare to parseFloat
    const floatSum = amounts.reduce((s, a) => s + parseFloat(toUsdtString(a)), 0);
    // floatSum might be 600.0599999999999 ❌
  });
});
```

---

## P1 IMPORTANT #3: Add ON CONFLICT Patterns

### Problem
Application doesn't handle duplicate key violations gracefully when UNIQUE constraints fail.

### Quick Fix Pattern

```typescript
// src/services/blockchain/deposit-processor.ts
// When inserting transaction records

// BEFORE ❌
await transactionRepo.save({
  tx_hash: txHash,
  user_id: userId,
  amount: amount,
  type: TransactionType.DEPOSIT,
  status: TransactionStatus.PENDING,
});

// AFTER ✅
const result = await AppDataSource.query(`
  INSERT INTO transactions (tx_hash, user_id, amount, type, status, block_number, from_address, to_address)
  VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
  ON CONFLICT (tx_hash) DO NOTHING
  RETURNING *
`, [txHash, userId, amount, type, status, blockNumber, fromAddress, toAddress]);

if (!result || result.length === 0) {
  logger.info('Transaction already exists (idempotent insert)', { txHash });
  // Fetch existing record if needed
  const existing = await transactionRepo.findOne({ where: { tx_hash: txHash } });
  return existing;
}

return result[0];
```

### Locations to Apply

1. **Transaction insertions** - `src/services/blockchain/deposit-processor.ts`
2. **Payment retry insertions** - `src/services/payment-retry.service.ts`
3. **Notification retry insertions** - `src/services/notification-retry.service.ts`

### Alternative: TypeORM with ON CONFLICT

```typescript
// Using TypeORM QueryBuilder
await dataSource
  .createQueryBuilder()
  .insert()
  .into(Transaction)
  .values({
    tx_hash: txHash,
    user_id: userId,
    amount: amount,
    type: TransactionType.DEPOSIT,
    status: TransactionStatus.PENDING,
  })
  .onConflict(`("tx_hash") DO NOTHING`)
  .returning('*')
  .execute();
```

---

## Verification Commands

### 1. Check Trust Proxy Works
```bash
# Deploy and check logs
gcloud logging read "resource.type=cloud_run_revision" \
  --filter='jsonPayload.ip' \
  --limit=10 \
  --format='value(jsonPayload.ip)'

# Should see Telegram IPs: 91.108.x.x, 149.154.x.x
# NOT internal: 10.x.x.x, 172.x.x.x
```

### 2. Test Money Precision
```bash
# Run unit tests
npm test -- money-precision

# Check specific service
npm test -- deposit.service

# Manual calculation check
node -e "
const { fromUsdtString, add, toUsdtString } = require('./dist/utils/money.util');
const a = fromUsdtString('0.1');
const b = fromUsdtString('0.2');
const result = add(a, b);
console.log('Result:', toUsdtString(result));  // Should print: 0.3
console.log('Float:', 0.1 + 0.2);  // Prints: 0.30000000000000004
"
```

### 3. Test ON CONFLICT
```bash
# Try inserting duplicate transaction
psql $DB_URL <<EOF
BEGIN;
INSERT INTO transactions (tx_hash, user_id, amount, type, status)
VALUES ('0xtest123', 1, '100.00', 'deposit', 'pending');

-- This should not error, just return 0 rows
INSERT INTO transactions (tx_hash, user_id, amount, type, status)
VALUES ('0xtest123', 1, '100.00', 'deposit', 'pending')
ON CONFLICT (tx_hash) DO NOTHING
RETURNING *;
ROLLBACK;
EOF
# Expected: No error, 0 rows returned on second insert
```

---

## Estimated Time

- **Trust Proxy:** 5 minutes
- **parseFloat fixes:** 30-45 minutes (4 files, 15+ occurrences)
- **ON CONFLICT patterns:** 15-20 minutes (3 locations)

**Total:** ~1 hour for all critical fixes

---

## Deployment Order

1. ✅ Add trust proxy (5 min)
2. ✅ Replace parseFloat in services (45 min)
3. ✅ Add ON CONFLICT patterns (20 min)
4. ✅ Run tests
5. ✅ Deploy to staging
6. ✅ Validate with checklist (POST_AUDIT_CHECKLIST.md)
7. ✅ Deploy to production

---

## Next Steps

After these fixes, run full verification:
```bash
# Run all checks from POST_AUDIT_CHECKLIST.md
./scripts/run-audit-checks.sh

# Expected: 11/11 PASS
```
