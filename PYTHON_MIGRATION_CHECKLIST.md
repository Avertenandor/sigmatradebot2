# Python Migration Checklist - TypeScript Services

## Complete Services Inventory for Python Migration

### TIER 1: Core Business Logic Services (CRITICAL)
These services handle financial operations and are the heart of the platform.

1. **UserService** (user.service.ts) - 15 public methods
   - User CRUD, verification, banning
   - Financial password management
   - Balance and statistics calculations
   - Referral link generation
   - Key: earnings_blocked flag handling

2. **DepositService** (deposit.service.ts) - 17 public methods
   - Level management (1-5 sequential activation)
   - Pending/confirmed deposit tracking
   - ROI cap management (Level 1: 500%)
   - Race condition prevention (SELECT FOR UPDATE)
   - Key: Level 1 ROI mechanics

3. **PaymentService** (payment.service.ts) - 9 public methods
   - Process pending payments with batching
   - Create referral earnings (3%/2%/5%)
   - ROI tracking and completion detection
   - Handle blocked earnings
   - Key: Batching optimization, ROI cap enforcement

4. **WithdrawalService** (withdrawal.service.ts) - 8 public methods
   - Withdrawal request lifecycle
   - Admin approval/rejection flow
   - Balance verification with lock
   - Key: Pessimistic locking on withdrawal

### TIER 2: Payment Processing & Retry Services
Handle payment failures and retries automatically.

5. **PaymentRetryService** (payment-retry.service.ts) - 6 public methods
   - Exponential backoff retry logic
   - Dead Letter Queue (DLQ) management
   - Manual admin retries
   - Key: 5 retries max (1-16 min), then DLQ

6. **NotificationRetryService** (notification-retry.service.ts) - 3 public methods
   - Notification failure tracking
   - Retry with exponential backoff
   - Admin alerts on failure
   - Key: 5 retries max (1min-2hrs)

### TIER 3: Referral & Rewards System
Multi-level referral commission management.

7. **ReferralService** (referral.service.ts) - Facade pattern
   - Composed of 3 submodules:
     - **ReferralCoreService**: Create/get referral relationships
     - **ReferralRewardsService**: Calculate commissions
     - **ReferralStatsService**: Per-level statistics

8. **RewardService** (reward.service.ts) - 9 public methods
   - Session management (create/update/delete)
   - Per-level reward rate configuration
   - Bulk reward calculation
   - ROI cap enforcement for Level 1
   - Key: Dynamic reward rates per session

### TIER 4: Blockchain Integration (CRITICAL - External)
Direct blockchain interaction for deposits and payments.

9. **BlockchainService** (blockchain/index.ts) - Orchestrator - 10 public methods
   - Coordinate all blockchain operations
   - Singleton pattern
   - Manages 4 submodules

10. **ProviderManager** (blockchain/provider.manager.ts)
    - HTTP & WebSocket provider management
    - USDT contract instance
    - Payout wallet signer
    - System wallet address tracking
    - Key: Provider failover and hot-reload

11. **EventMonitor** (blockchain/event-monitor.ts)
    - Listen for USDT Transfer events to system wallet
    - 12-block confirmation threshold
    - WebSocket auto-reconnect with exponential backoff
    - Rescan recent blocks on wallet change
    - Key: Real-time event listening

12. **DepositProcessor** (blockchain/deposit-processor.ts)
    - Confirm pending deposits
    - Check tx status on blockchain
    - Tolerance mode (accept ±2% amount)
    - Trigger referral earnings creation
    - Key: Transaction verification

13. **PaymentSender** (blockchain/payment-sender.ts)
    - Send USDT from payout wallet
    - Gas fee management
    - Balance warnings
    - Retry with exponential backoff
    - Key: Transaction submission & monitoring

### TIER 5: User & Account Management
User-facing features and account controls.

14. **TransactionService** (transaction.service.ts) - 3 public methods
    - Unified transaction view (deposits + withdrawals + earnings)
    - Transaction statistics
    - Composite ID format for unified display

15. **FinpassRecoveryService** (finpass-recovery.service.ts) - 7 public methods
    - Financial password reset requests
    - Admin review & approval workflow
    - Earnings blocking during recovery
    - Earnings unblock on password use
    - Key: earnings_blocked flag lifecycle

16. **SupportService** (support.service.ts) - 10 public methods
    - Support ticket CRUD
    - Message threading (user/admin/system)
    - Ticket assignment to admins
    - On-duty admin detection
    - Key: One active ticket per user constraint

### TIER 6: Admin & Security Services
Administrative tools and security management.

17. **AdminService** (admin.service.ts) - 10 public methods
    - Admin authentication with master key
    - Session management
    - Session cleanup (expired sessions)
    - Key: Master key (not password) authentication

18. **WalletAdminService** (wallet-admin.service.ts) - 6 public methods
    - Wallet change request workflow
    - Support 2 wallet types (system_deposit, payout_withdrawal)
    - Private key validation against address
    - Approve/apply workflow
    - Key: Multi-signature approval flow

19. **SecretStoreService** (secret-store.service.ts) - 3 public methods
    - GCP Secret Manager integration (production)
    - Local file storage (development)
    - Never log secrets
    - Version management
    - Key: External secret storage (never in database)

### TIER 7: Configuration & Infrastructure
System settings and utility services.

20. **SettingsService** (settings.service.ts) - 8 public methods
    - Runtime configuration management
    - In-memory cache (60s TTL)
    - Wallet address management
    - Max open level control
    - Key: Cached settings, wallet version tracking

21. **NotificationService** (notification.service.ts) - 18+ public methods
    - Telegram message delivery
    - Photo/voice/audio messages
    - Specific notification types
    - Admin broadcast
    - System alerts (low balance, payment failed, etc)
    - Key: Failure tracking and retry hooks

22. **BlacklistService** (blacklist.service.ts) - 5 public methods
    - Pre-registration ban list
    - Admin audit logging
    - Idempotent operations
    - Key: Prevents unwanted registrations

---

## Critical Business Rules for Python Implementation

### Deposit System
- **Levels 1-5** with sequential activation
- **Level 1 (10 USDT)**: 500% ROI cap (5x investment)
  - Only ONE active Level 1 at a time
  - Can create new L1 after previous completes ROI
- **Level 2+ (Higher amounts)**: Require previous level + referral count
- **ROI Calculation**: Track roi_paid_amount vs roi_cap_amount
- **ROI Completion**: Mark is_roi_completed when roi_paid >= roi_cap

### Referral System
- **3 Levels** of referral commission
  - Level 1: 3% (direct referrals)
  - Level 2: 2% (referrals' referrals)
  - Level 3: 5% (referrals' referrals' referrals)
- **Only verified referrals** count
- **Earnings can be blocked** during finpass recovery
- **Skip earnings** if referrer has earnings_blocked = true

### Payment Processing
- **Batch payments by user** (gas optimization)
- **Skip blocked earnings** during finpass recovery
- **Cap rewards to remaining ROI** for Level 1
- **Mark paid on blockchain confirmation**
- **Retry with exponential backoff** on failure (5 attempts, 1-16 min)
- **Move to DLQ** after max retries

### Financial Password Recovery
- **BLOCKS all earnings** when request created
- **Unblocks earnings** when user verifies new password
- **Video verification** outside of bot
- **Plain password stored in Redis** 1 hour TTL
- **SLA: 3-5 business days**

### Blockchain Operations
- **12-block confirmation** threshold
- **Tolerance mode**: Accept deposits within ±2% of expected amount
- **Payout wallet**: Requires BNB for gas
- **System wallet**: Receives deposits
- **WebSocket reconnection**: Auto-reconnect with exponential backoff

### Locking & Race Conditions
- **SELECT FOR UPDATE** in createPendingDeposit
- **Pessimistic lock** on user row in requestWithdrawal
- **Atomic transactions** for payment retries

---

## Database Transactions Required

| Operation | Lock Type | Service | Method |
|-----------|-----------|---------|--------|
| Create pending deposit | SELECT FOR UPDATE | DepositService | createPendingDeposit |
| Withdraw funds | Pessimistic Write | WithdrawalService | requestWithdrawal |
| Process payment retry | Full Transaction | PaymentRetryService | processRetry |
| Update ROI | Safe Read-Modify-Write | PaymentService | processUserRewardPayments |

---

## Background Jobs Required for Scheduling

1. **Every 5 minutes**: PaymentService.processPendingPayments()
2. **Every 1 minute**: PaymentRetryService.processPendingRetries()
3. **Every 5 minutes**: NotificationRetryService.processPendingRetries()
4. **Every 1 hour**: DepositService.cleanupOrphanedDeposits()
5. **Every 1 hour**: AdminService.cleanupExpiredSessions()
6. **On startup**: BlockchainService.startMonitoring() (EventMonitor WebSocket)

---

## Redis Usage
- **Plain passwords**: 1 hour TTL (user registration + finpass recovery)
- **Key format**: `password:plain:{userId}`
- **Purpose**: Recovery window for new passwords

---

## GCP Integration
- **Secret Manager**: Store payout wallet private keys
- **Service Account**: Required for authentication
- **Secret naming**: `sigmatradebot-wallet-{name}`
- **Fallback**: Local file storage in development

---

## Key External Dependencies
- **ethers.js**: Ethereum/BSC blockchain interaction
- **Telegraf**: Telegram bot API
- **TypeORM** (becomes SQLAlchemy in Python): ORM for database
- **Redis**: Cache and temporary storage
- **GCP Secret Manager**: Secure secret storage

---

## Summary for Python Migration

### Services to Create: 22 modules
- 16 main services
- 4 blockchain submodules
- 2 support services (notification, retry)

### Total Methods to Implement: ~120 public methods
### Total Business Logic Rules: 30+ critical rules
### Database Entities: 18 entities (already migrated)
### External Integrations: 5 (Telegram, Blockchain, Redis, GCP, Database)

### Risk Areas (Require Extra Testing)
1. **Deposit confirmation and ROI mechanics** (complex state)
2. **Payment retry with exponential backoff** (timing critical)
3. **Race conditions in concurrent operations** (SELECT FOR UPDATE)
4. **Blockchain event monitoring** (external dependency)
5. **Earnings blocking during finpass recovery** (flag coordination)

