# TypeScript Services Architecture - Complete Analysis

## Summary Statistics
- **Total Service Files**: 29 files
- **Service Categories**: 8 main categories
- **Critical Business Logic**: 6 core services
- **Infrastructure/Support Services**: 8 services

## Complete Services Map

### 1. USER MANAGEMENT (1 service)
#### UserService (`user.service.ts`)
**Methods:**
- `findByTelegramId(telegramId: number)` - Get user by Telegram ID with referrer relation
- `findByWalletAddress(walletAddress: string)` - Find user by wallet (normalized)
- `findById(userId: number)` - Get user with referrer
- `findByUsername(username: string)` - Case-insensitive username search
- `getAllUserTelegramIds()` - Get all user Telegram IDs (for admin broadcast)
- `createUser(data)` - Create new user with financial password, referrer validation
- `verifyUser(userId, contactInfo)` - Mark as verified, store phone/email
- `banUser(userId)` / `unbanUser(userId)` - Ban/unban user
- `getUserBalance(userId)` - Calculate available balance, earned, paid, pending
- `getUserStats(userId)` - Total deposits, earned, referral count, activated levels
- `generateReferralLink(userId, botUsername)` - Create referral link
- `parseReferralCode(startPayload)` - Extract referrer user ID from start command
- `getTotalUsers()` / `getVerifiedUsers()` - Count users
- `verifyFinancialPassword(userId, password)` - Verify password, UNBLOCK earnings
- `getPlainPassword(userId)` - Retrieve from Redis (1 hour TTL)

**Dependencies:**
- TypeORM (AppDataSource, EntityManager)
- Utilities: crypto, validation, money, logger
- Redis client for password storage
- Related entities: User, Deposit, Referral, ReferralEarning, Transaction

**Critical Business Logic:**
- Password stored in Redis for 1-hour recovery window
- Earnings unblock after successful password verification
- Referrer validation (skip if invalid, don't fail registration)
- Precise money calculations for referral earnings

---

### 2. DEPOSIT MANAGEMENT (1 service)
#### DepositService (`deposit.service.ts`)
**Methods:**
- `getActivatedLevels(userId)` - Get confirmed deposit levels
- `getActiveLevel1Cycle(userId)` - Get active Level 1 (not completed ROI)
- `canActivateLevel(userId, level)` - Check level eligibility
- `getAvailableLevels(userId)` - Get levels user can activate
- `getDepositInfo(level)` - Get amount and referral requirements
- `getDirectReferralCount(userId)` - Count verified referrals
- `getPendingDeposits(userId)` - Get pending (not confirmed) deposits
- `getDepositHistory(userId, options)` - Paginated deposit history
- `getDepositByTxHash(txHash)` - Find deposit by transaction hash
- `createPendingDeposit(data)` - Create pending deposit with SELECT FOR UPDATE lock
- `confirmDeposit(txHash, blockNumber)` - Mark as confirmed, initialize Level 1 ROI
- `getLevel1RoiProgress(userId)` - Get current ROI progress (%, remaining)
- `getTotalDeposited(userId)` - Sum confirmed deposits
- `getRoiStatistics()` - Admin stats: active/completed L1, totals, nearing completion
- `getPlatformStats()` - Total deposits, amount, users, by level
- `cleanupOrphanedDeposits()` - Mark 24+ hour pending deposits as failed
- `cancelPendingDeposit(userId, depositId)` - Cancel if no tx_hash

**Dependencies:**
- Deposit, User, Transaction entities
- PaymentService (create referral earnings)
- NotificationService (confirmations, level activation, ROI)
- SettingsService (max open level)
- Utilities: money (precise calculations), constants

**Critical Business Logic:**
- **Level 1 (10 USDT)**: 500% ROI cap (5x investment)
- Only ONE active Level 1 at a time
- Levels must be activated sequentially (1 → 2 → 3 → 4 → 5)
- Level 2+ require previous level + referral count
- ROI cap initialized on confirmation
- SELECT FOR UPDATE prevents race conditions

---

### 3. REFERRAL MANAGEMENT (3 services)
#### ReferralService (`referral.service.ts`)
- Re-exports from `./referral` subdirectory (facade pattern)

#### ReferralService Core (`referral/core.service.ts`)
**Methods:**
- `getReferrals(userId)` - Get all referrals at different levels
- `createReferral(userId, referrerId)` - Create referral relationship
- `getReferralStats(userId)` - Referral counts per level

**Dependencies:**
- Referral entity

#### ReferralRewardsService (`referral/rewards.service.ts`)
**Methods:**
- `calculateRewards(amount)` - Calculate 3% / 2% / 5% by level
- `createReferralEarnings(userId, amount)` - Create earning records

**Dependencies:**
- ReferralEarning entity

#### ReferralStatsService (`referral/stats.service.ts`)
**Methods:**
- `getUserReferralStats(userId)` - Referrals per level, earnings

**Critical Business Logic:**
- **Referral Rates**:
  - Level 1: 3% (direct referrals)
  - Level 2: 2% (referrals of referrals)
  - Level 3: 5% (referrals of level 2)
- Earnings blocked during finpass recovery
- Only verified referrals count

---

### 4. PAYMENT & WITHDRAWAL (3 services)

#### PaymentService (`payment.service.ts`)
**Methods:**
- `processPendingPayments()` - Process all pending referral earnings + deposit rewards
- `processUserPayments(referrerId, earnings)` - Process payments for one user
- `processUserRewardPayments(userId, rewards)` - Process deposit reward payments
- `createReferralEarnings(userId, amount, sourceTransactionId)` - Create earnings on deposit confirmation
- `calculateRewards(amount)` - Get reward amounts by level
- `getPaymentStats()` - Pending/paid earnings and amounts
- `getUserPendingEarnings(userId)` - Get unpaid earnings for user
- `getUserPaidEarnings(userId)` - Get paid earnings for user
- `retryFailedPayments(earningIds)` - Manual retry for failed payments

**Dependencies:**
- ReferralEarning, DepositReward, Transaction, User, Referral entities
- BlockchainService (send payment)
- NotificationService (payment alerts, ROI completion)
- PaymentRetryService (handle failures)
- Utilities: money (precise calculations)

**Critical Business Logic:**
- **Batching**: Group earnings by user (gas optimization)
- **ROI Tracking**: For Level 1, update roi_paid_amount, check if cap reached
- **ROI Completion**: Mark deposit as completed when roi_paid >= roi_cap
- **Blocked Earnings**: Skip if referrer has earnings_blocked flag
- **ROI Cap**: Don't pay past 500% for Level 1

#### WithdrawalService (`withdrawal.service.ts`)
**Methods:**
- `requestWithdrawal(data)` - Create withdrawal transaction (min 5 USDT)
- `getPendingWithdrawals()` - Get pending (admin review)
- `getUserWithdrawals(userId, options)` - Paginated withdrawal history
- `cancelWithdrawal(transactionId, userId)` - Cancel pending only
- `approveWithdrawal(transactionId, txHash)` - Mark confirmed
- `rejectWithdrawal(transactionId, reason)` - Reject pending
- `getWithdrawalById(transactionId)` - Get withdrawal details
- `getMinWithdrawalAmount()` - Return constant (5 USDT)

**Dependencies:**
- Transaction, User entities
- UserService (balance check)
- Uses pessimistic lock (SELECT FOR UPDATE)

**Critical Business Logic:**
- **Min Amount**: 5 USDT
- **Balance Check**: Available = total_earned - confirmed_withdrawals - pending_withdrawals
- **Race Condition Prevention**: Pessimistic lock on user row

---

### 5. TRANSACTION HISTORY (1 service)
#### TransactionService (`transaction.service.ts`)
**Methods:**
- `getAllTransactions(userId, options)` - Unified view: deposits + withdrawals + referral earnings
- `getTransactionStats(userId)` - Totals and counts by type
- `getRecentTransactions(userId, limit)` - Last N transactions

**Dependencies:**
- Deposit, Transaction, ReferralEarning entities

**Critical Business Logic:**
- **Unified Format**: Composite ID (e.g., "deposit:123", "withdrawal:456")
- **Status Mapping**: referral earnings: pending → PENDING, paid → CONFIRMED
- **Explorer Links**: BSCscan links for on-chain transactions

---

### 6. REWARD SESSIONS (1 service)
#### RewardService (`reward.service.ts`)
**Methods:**
- `createSession(data)` - Create reward session with per-level rates
- `updateSession(sessionId, data)` - Update rates, dates, active status
- `deleteSession(sessionId)` - Delete only if no rewards calculated
- `getAllSessions()` / `getActiveSessions()` - Get sessions
- `getSessionById(sessionId)` - Get session details
- `calculateRewardsForSession(sessionId)` - Bulk calculate rewards
- `getSessionStatistics(sessionId)` - Total/paid/pending rewards
- `getUserUnpaidRewards(userId)` - Get unpaid rewards
- `markRewardsAsPaid(rewardIds, txHash)` - Bulk mark as paid

**Dependencies:**
- RewardSession, DepositReward, Deposit, User entities
- Utilities: money (precise calculations)

**Critical Business Logic:**
- **ROI Cap**: Level 1 deposits can't earn past 500%
- **Earnings Blocked**: Skip rewards if user has earnings_blocked
- **Precise Math**: Use MoneyAmount for all calculations
- **Reward Capping**: Cap to remaining ROI space

---

### 7. BLOCKCHAIN OPERATIONS (5 services)

#### BlockchainService (Orchestrator) (`blockchain/index.ts`)
**Methods:**
- `startMonitoring()` / `stopMonitoring()` - Event monitor lifecycle
- `checkPendingDeposits()` - Confirm deposits via blockchain
- `sendPayment(toAddress, amount)` - Send USDT payment
- `getBalance(address)` - Get USDT balance
- `getCurrentBlock()` - Get current block number
- `verifyTransaction(txHash)` - Check if tx exists and confirmed
- `getSystemWalletBalance()` / `getPayoutWalletBalance()` / `getPayoutWalletBnbBalance()` - Check balances
- `reloadPayoutWallet(secretRef)` - Reload payout signer
- `reloadSystemWalletAddress(newAddress)` - Restart monitor with new address

**Architecture:**
- Singleton pattern
- Manages ProviderManager, EventMonitor, DepositProcessor, PaymentSender
- Exposes high-level API

#### ProviderManager (`blockchain/provider.manager.ts`)
**Responsibilities:**
- HTTP provider (block queries, reads)
- WebSocket provider (real-time events)
- USDT contract instance (ERC20 ABI)
- Payout wallet signer (sends transactions)
- System wallet address (receives deposits)

#### EventMonitor (`blockchain/event-monitor.ts`)
**Responsibilities:**
- Listen for USDT Transfer events to system wallet
- 12-block confirmation threshold
- WebSocket with auto-reconnect
- Rescan recent blocks after system wallet change

#### DepositProcessor (`blockchain/deposit-processor.ts`)
**Responsibilities:**
- Confirm pending deposits (check tx status)
- Update database on confirmation
- Create referral earnings

#### PaymentSender (`blockchain/payment-sender.ts`)
**Responsibilities:**
- Send USDT from payout wallet
- Gas fee management
- Retry logic (exponential backoff)
- Balance warnings

**Dependencies:**
- ethers.js library
- GCP Secret Manager (payout wallet key)
- SettingsService (wallet addresses)
- AppDataSource (database)

**Critical Business Logic:**
- **12-block confirmation**: Deposits need 12 blocks to be confirmed
- **Tolerance Mode**: Accept deposits within 2% of expected amount
- **Gas Management**: Ensure payout wallet has BNB for gas
- **WebSocket Reconnection**: Auto-reconnect with exponential backoff
- **Secret Storage**: Private keys never in code, only in Secret Manager

---

### 8. NOTIFICATION SYSTEM (2 services)

#### NotificationService (`notification.service.ts`)
**Methods:**
- `sendCustomMessage(telegramId, message, options)` - Send arbitrary message
- `sendPhotoMessage(telegramId, fileId, caption, options)` - Send photo
- `sendVoiceMessage(telegramId, fileId, caption, options)` - Send voice
- `sendAudioMessage(telegramId, fileId, caption, options)` - Send audio
- `notifyDepositConfirmed(telegramId, amount, level, txHash)` - Deposit confirmation
- `notifyReferralEarning(telegramId, amount, level, username)` - Earning notification
- `notifyPaymentSent(telegramId, amount, txHash)` - Payment sent
- `notifyDepositRewardPayment(telegramId, amount, txHash)` - Reward payment
- `notifyRoiCompleted(telegramId, level, capAmount)` - ROI 500% reached
- `notifyNewReferral(telegramId, username)` - New referral joined
- `notifyLevelActivated(telegramId, level)` - Level activated
- `notifyAdmin(adminTelegramId, title, message)` - Admin alert
- `notifyAllAdmins(title, message)` - Critical alert to all admins
- **Alerts:**
  - `alertLowPayoutBalance(balance, threshold)`
  - `alertPaymentFailed(userId, amount, error)`
  - `alertSignificantDepositDeviation(params)`
  - `alertPaymentMovedToDLQ(userId, amount, attempts, error)`
  - `alertWebSocketDisconnect(attempts, maxAttempts)`
  - `alertAdminNotificationFailure(userId, type, error)`
  - `alertNotificationGaveUp(userId, type, message, error)`
- `notifyDepositPending(telegramId, amount, level, txHash)`
- `notifyDepositTimeout(telegramId, amount, level)`
- `notifyWithdrawalReceived/Processed/Rejected(telegramId, amount, ...)`

**Dependencies:**
- Telegraf bot instance
- FailedNotification entity (track failures)
- Admin entity (broadcast to admins)

**Critical Business Logic:**
- **Failure Tracking**: Store failed notifications for retry
- **Critical Flag**: Alert admins immediately for critical failures
- **Markdown Format**: Support Markdown and HTML parse modes
- **No Logging Sensitive Data**: Never log payment amounts in production

#### NotificationRetryService (`notification-retry.service.ts`)
**Methods:**
- `processPendingRetries()` - Retry failed notifications
- `getStatistics()` - Failed notification stats
- `resolveNotification(notificationId)` - Manual resolution

**Dependencies:**
- FailedNotification entity
- Telegraf bot instance

**Critical Business Logic:**
- **Max Retries**: 5 attempts before giving up
- **Exponential Backoff**: 1min → 5min → 15min → 1hr → 2hrs
- **Admin Alert**: Alert admins when notification fails

---

### 9. PAYMENT RETRY SYSTEM (1 service)
#### PaymentRetryService (`payment-retry.service.ts`)
**Methods:**
- `createRetryRecord(params)` - Create retry on failed payment
- `processPendingRetries()` - Process scheduled retries
- `getDLQItems()` - Get Dead Letter Queue items
- `retryDLQItem(retryId)` - Manual retry by admin
- `getRetryStats()` - Pending/DLQ/resolved counts and amounts
- `getUserRetries(userId)` - Get user's pending retries

**Architecture:**
- Singleton pattern
- Exponential backoff: 1min, 2min, 4min, 8min, 16min
- Max 5 retries before DLQ

**Dependencies:**
- PaymentRetry, ReferralEarning, DepositReward, Transaction entities
- BlockchainService (send payment)
- NotificationService (failure alerts)
- Utilities: money (precise calculations), audit logger

**Critical Business Logic:**
- **Dead Letter Queue**: After 5 failed attempts, move to DLQ
- **Atomic Operations**: Use transaction for earnings → paid → transaction record
- **Admin Retry**: Reset attempt count to 0 when manually retried
- **Audit Logging**: All payment operations logged

---

### 10. ADMIN MANAGEMENT (1 service)
#### AdminService (`admin.service.ts`)
**Methods:**
- `createAdmin(data)` - Create admin with master key
- `login(data)` - Authenticate and create session
- `logout(sessionToken)` - Deactivate session
- `validateSession(sessionToken)` - Check and refresh session
- `cleanupExpiredSessions()` - Remove expired sessions
- `getActiveSessions(adminId)` - Get active sessions for admin
- `removeAdmin(adminId)` - Delete admin and deactivate sessions
- `getAllAdmins()` - List all admins
- `getByTelegramId(telegramId)` - Find admin by Telegram ID
- `regenerateMasterKey(adminId)` - Generate new key and deactivate sessions

**Dependencies:**
- Admin, AdminSession entities
- Utilities: admin auth (master key generation/hashing)

**Critical Business Logic:**
- **Master Key**: Unique authentication key per admin (not password)
- **Session Management**: One session per login (old sessions deactivated)
- **Session TTL**: Configurable expiration
- **Activity Tracking**: Update last_activity on validation

---

### 11. WALLET MANAGEMENT (1 service)
#### WalletAdminService (`wallet-admin.service.ts`)
**Methods:**
- `createRequest(type, newAddress, initiatorId, keyOrMnemonic, reason)` - Create change request
- `approveRequest(requestId, approverId, reason)` - Approve change
- `rejectRequest(requestId, rejectorId, reason)` - Reject change
- `applyRequest(requestId, applierId)` - Apply approved change
- `getRequests(filters)` - List requests
- `getRequest(requestId)` - Get single request

**Architecture:**
- Request workflow: pending → approved → applied
- Separate handling for system_deposit vs payout_withdrawal
- Partial unique index on pending requests

**Dependencies:**
- WalletChangeRequest, Admin entities
- SettingsService (update wallet addresses)
- SecretStoreService (store payout key)
- BlockchainService (reload monitors)
- ethers.js (validate key/mnemonic against address)

**Critical Business Logic:**
- **Two Wallet Types**:
  - **system_deposit**: Receives deposits (address only)
  - **payout_withdrawal**: Sends payments (requires private key/mnemonic)
- **Validation**: Key must match address before approval
- **Secret Storage**: Private keys stored in GCP Secret Manager
- **Blockchain Reload**: On apply, restart monitors with new addresses
- **Audit Trail**: All actions logged

---

### 12. SECRET STORAGE (1 service)
#### SecretStoreService (`secret-store.service.ts`)
**Methods:**
- `saveSecret(name, value)` - Store secret
- `accessSecret(secretRef)` - Retrieve secret by reference
- `deleteSecret(secretRef)` - Delete secret

**Architecture:**
- **Development**: Local file storage (.secrets/dev/)
- **Production**: GCP Secret Manager

**Dependencies:**
- GCP Secret Manager SDK
- File system (development only)

**Critical Business Logic:**
- **Never Log Secrets**: Only log names/lengths
- **Encryption**: GCP handles encryption at rest/transit
- **Access Auditing**: GCP logs all access
- **Version Management**: Multiple versions of same secret

---

### 13. SETTINGS MANAGEMENT (1 service)
#### SettingsService (`settings.service.ts`)
**Methods:**
- `get(key, fallback)` - Get setting with 60s cache
- `set(key, value)` - Set and invalidate cache
- `getMaxOpenLevel()` / `setMaxOpenLevel(level)` - Control available levels
- `getSystemWalletAddress()` / `setSystemWalletAddress(address)` - System wallet
- `getPayoutWalletAddress()` / `setPayoutWalletAddress(address)` - Payout wallet
- `getWalletsVersion()` / `incrementWalletsVersion()` - Version tracking
- `requiresSecondApprover()` / `setRequireSecondApprover(require)` - Policy
- `clearCache()` - For testing

**Dependencies:**
- SystemSetting entity
- In-memory cache (60s TTL)

**Critical Business Logic:**
- **Caching**: Reduces database hits, 60-second TTL
- **Version Tracking**: Detect wallet changes across nodes
- **Max Level Control**: Admin can restrict available levels

---

### 14. SUPPORT SYSTEM (1 service)
#### SupportService (`support.service.ts`)
**Methods:**
- `createTicket(data)` - Create support ticket
- `addUserMessage(data)` - User replies
- `addAdminMessage(data)` - Admin replies
- `addSystemMessage(ticketId, text)` - System notifications
- `assignToSelf(ticketId, adminId)` - Assign to admin
- `close(ticketId)` / `reopen(ticketId)` - Ticket lifecycle
- `listOpen()` - Get open/in_progress/answered tickets
- `get(ticketId)` - Get ticket with messages
- `getUserActiveTicket(userId)` - Get user's active ticket
- `findOnDutyAdmin()` - Find admin with active session

**Dependencies:**
- SupportTicket, SupportMessage, AdminSession entities

**Critical Business Logic:**
- **One Active Ticket**: User can only have one open ticket at a time
- **Status Flow**: open → in_progress → answered → closed
- **On-Duty Admin**: Admin must have active session to be on-duty
- **Partial Unique Index**: Enforces one active ticket per user

---

### 15. FINANCIAL PASSWORD RECOVERY (1 service)
#### FinpassRecoveryService (`finpass-recovery.service.ts`)
**Methods:**
- `createRequest(userId)` - User initiates recovery
- `listPending(limit)` - Get pending/in_review/approved requests (FIFO)
- `getRequest(requestId)` - Get request details
- `takeInReview(requestId, adminId)` - Admin takes request
- `reject(requestId, adminId, comment)` - Admin rejects
- `approveAndReset(requestId, adminId)` - Admin generates new password
- `getLastRequest(userId)` - Get most recent request (anti-abuse)

**Dependencies:**
- FinancialPasswordRecovery, User entities
- NotificationService (alerts)
- Redis (store plain password, 1-hour TTL)
- Utilities: crypto (generate/hash password)

**Critical Business Logic:**
- **Earnings Blocked**: Block all earnings from request creation
- **Unblock Trigger**: Use new password to unblock (proof of possession)
- **SLA**: 3-5 business days manual processing
- **Video Verification**: Conducted outside bot, tracked in flags
- **Plain Password TTL**: 1 hour for repeat view
- **One Open Request**: Unique constraint prevents abuse

---

### 16. BLACKLIST MANAGEMENT (1 service)
#### BlacklistService (`blacklist.service.ts`)
**Methods:**
- `isBlacklisted(telegramId)` - Check if blacklisted
- `add(telegramId, adminId, reason)` - Add to blacklist (idempotent)
- `remove(telegramId, adminId)` - Remove from blacklist
- `getEntry(telegramId)` - Get blacklist details
- `getCount()` - Total blacklisted users

**Dependencies:**
- Blacklist entity
- Admin audit logging

**Critical Business Logic:**
- **Pre-Registration Ban**: Prevents registration before user exists
- **Idempotent Add**: Return success if already exists
- **Admin Audit**: Log who added/removed entries

---

## Dependency Graph

```
User Registration Flow:
  BlacklistService.isBlacklisted()
    ↓
  UserService.createUser()
    ↓
  DepositService.createPendingDeposit()
    ↓
  [BlockchainService] monitors...
    ↓
  DepositService.confirmDeposit()
    ↓
  PaymentService.createReferralEarnings()
    ↓
  NotificationService.notifyReferralEarning()

Payment Processing:
  PaymentService.processPendingPayments()
    ↓
  BlockchainService.sendPayment()
    ↓
  SUCCESS: PaymentRetryService skipped
  FAILURE: PaymentRetryService.createRetryRecord()
    ↓
  [Background Job] PaymentRetryService.processPendingRetries()
    ↓
  After 5 attempts: Move to Dead Letter Queue (DLQ)
    ↓
  Admin: PaymentRetryService.retryDLQItem()

Wallet Change:
  WalletAdminService.createRequest()
    ↓
  SecretStoreService.saveSecret() [payout key]
    ↓
  WalletAdminService.approveRequest()
    ↓
  WalletAdminService.applyRequest()
    ↓
  SettingsService.set{System|Payout}WalletAddress()
    ↓
  BlockchainService.reload{Payout|System}Wallet()

Finpass Recovery:
  FinpassRecoveryService.createRequest()
    ↓
  UserService.earnings_blocked = true
    ↓
  [Admin verifies video]
    ↓
  FinpassRecoveryService.approveAndReset()
    ↓
  UserService.financial_password updated
    ↓
  Redis: store plain password (1 hour TTL)
    ↓
  UserService.verifyFinancialPassword()
    ↓
  earnings_blocked = false [UNBLOCKED]
```

## Service-to-Entity Mapping

| Service | Primary Entities | Relations |
|---------|------------------|-----------|
| UserService | User | Deposit, Referral, ReferralEarning, Transaction |
| DepositService | Deposit | User, Transaction |
| PaymentService | ReferralEarning, DepositReward | User, Referral, Deposit, Transaction |
| WithdrawalService | Transaction | User |
| TransactionService | Deposit, Transaction, ReferralEarning | User |
| RewardService | RewardSession, DepositReward | Deposit, User |
| AdminService | Admin, AdminSession | - |
| WalletAdminService | WalletChangeRequest | Admin |
| SupportService | SupportTicket, SupportMessage | User, Admin |
| FinpassRecoveryService | FinancialPasswordRecovery | User, Admin |
| BlacklistService | Blacklist | Admin (creator) |
| SettingsService | SystemSetting | - |
| NotificationService | FailedNotification | Admin (broadcast) |

## Database Transactions & Locks

| Service | Type | Method |
|---------|------|--------|
| DepositService | SELECT FOR UPDATE | createPendingDeposit |
| WithdrawalService | Pessimistic Write Lock | requestWithdrawal |
| PaymentRetryService | Transaction | processRetry |

## Background Jobs Required

1. **Payment Processor** → `paymentService.processPendingPayments()`
2. **Payment Retry** → `paymentRetryService.processPendingRetries()`
3. **Notification Retry** → `notificationRetryService.processPendingRetries()`
4. **Deposit Cleanup** → `depositService.cleanupOrphanedDeposits()`
5. **Admin Session Cleanup** → `adminService.cleanupExpiredSessions()`
6. **Blockchain Monitor** → `blockchainService.startMonitoring()`

## Critical Configurations

- **Deposit Levels**: 1-5 (configurable max open level)
- **Level 1 ROI Cap**: 500% (5x investment)
- **Referral Rates**: 3% / 2% / 5%
- **Min Withdrawal**: 5 USDT
- **Payment Retry**: 5 attempts, 1-16 min exponential backoff
- **Notification Retry**: 5 attempts, 1min-2hrs exponential backoff
- **Block Confirmation**: 12 blocks for deposits
- **Deposit Timeout**: 24 hours
- **Finpass Recovery SLA**: 3-5 business days
- **Settings Cache TTL**: 60 seconds

---

## Python Migration Requirements

### Must Create (1:1 Mapping)
1. UserService
2. DepositService
3. PaymentService
4. WithdrawalService
5. TransactionService
6. ReferralService (with Core, Rewards, Stats submodules)
7. RewardService
8. NotificationService
9. NotificationRetryService
10. PaymentRetryService
11. AdminService
12. WalletAdminService
13. SupportService
14. FinpassRecoveryService
15. BlacklistService
16. SettingsService
17. BlockchainService (with ProviderManager, EventMonitor, DepositProcessor, PaymentSender)
18. SecretStoreService

### Total Services: 18 core services + 4 blockchain submodules = 22 modules
