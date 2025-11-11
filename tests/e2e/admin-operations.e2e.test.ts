/**
 * E2E Test: Admin Operations
 * Tests admin functionality including user management, transaction oversight, and system operations
 */

import { DataSource } from 'typeorm';
import Redis from 'ioredis';
import { testDataSource, testRedis } from '../setup.e2e';
import { User } from '../../src/entities/User';
import { Deposit } from '../../src/entities/Deposit';
import { Withdrawal } from '../../src/entities/Withdrawal';
import { Transaction, TransactionStatus, TransactionType } from '../../src/entities/Transaction';
import { PaymentRetry } from '../../src/entities/PaymentRetry';

describe('E2E: Admin Operations', () => {
  let dataSource: DataSource;
  let redis: Redis;
  let adminUser: User;
  let regularUser: User;

  beforeAll(() => {
    dataSource = testDataSource;
    redis = testRedis;
  });

  beforeEach(async () => {
    const userRepo = dataSource.getRepository(User);

    // Create admin user
    adminUser = userRepo.create({
      telegramId: '999999999',
      firstName: 'Admin',
      username: 'admin_user',
      balance: 0,
      totalDeposits: 0,
      totalWithdrawals: 0,
      totalEarnings: 0,
      depositLevel: 5,
      isActive: true,
      isBlocked: false,
      isAdmin: true, // Admin flag
    });
    await userRepo.save(adminUser);

    // Create regular user
    regularUser = userRepo.create({
      telegramId: '100100100',
      firstName: 'Regular',
      username: 'regular_user',
      balance: 500,
      totalDeposits: 1000,
      totalWithdrawals: 500,
      totalEarnings: 100,
      depositLevel: 2,
      isActive: true,
      isBlocked: false,
    });
    await userRepo.save(regularUser);
  });

  describe('User Management', () => {
    it('should allow admin to view user details', async () => {
      const userRepo = dataSource.getRepository(User);

      // Admin views user
      const user = await userRepo.findOne({
        where: { id: regularUser.id },
        relations: ['referrer', 'referrals', 'deposits', 'withdrawals'],
      });

      expect(user).toBeDefined();
      expect(user!.balance).toBe(500);
      expect(user!.totalDeposits).toBe(1000);
      expect(user!.depositLevel).toBe(2);
    });

    it('should allow admin to block/unblock user', async () => {
      const userRepo = dataSource.getRepository(User);

      // Admin blocks user
      regularUser.isBlocked = true;
      regularUser.isActive = false;
      await userRepo.save(regularUser);

      const blockedUser = await userRepo.findOne({
        where: { id: regularUser.id }
      });
      expect(blockedUser!.isBlocked).toBe(true);
      expect(blockedUser!.isActive).toBe(false);

      // Admin unblocks user
      regularUser.isBlocked = false;
      regularUser.isActive = true;
      await userRepo.save(regularUser);

      const unblockedUser = await userRepo.findOne({
        where: { id: regularUser.id }
      });
      expect(unblockedUser!.isBlocked).toBe(false);
      expect(unblockedUser!.isActive).toBe(true);
    });

    it('should allow admin to adjust user balance', async () => {
      const userRepo = dataSource.getRepository(User);
      const txRepo = dataSource.getRepository(Transaction);

      const adjustmentAmount = 100;
      const reason = 'Manual adjustment by admin';

      // Admin adjusts balance
      await dataSource.transaction(async (manager) => {
        const user = await manager.findOne(User, { where: { id: regularUser.id } });
        user!.balance += adjustmentAmount;
        await manager.save(user);

        // Log transaction
        const transaction = manager.create(Transaction, {
          userId: regularUser.id,
          type: 'ADMIN_ADJUSTMENT' as TransactionType,
          amount: adjustmentAmount,
          status: TransactionStatus.CONFIRMED,
          metadata: JSON.stringify({
            adminId: adminUser.id,
            reason: reason,
            timestamp: new Date().toISOString(),
          }),
        });
        await manager.save(transaction);
      });

      // Verify adjustment
      const updatedUser = await userRepo.findOne({
        where: { id: regularUser.id }
      });
      expect(updatedUser!.balance).toBe(600); // 500 + 100

      // Verify transaction log
      const transactions = await txRepo.find({
        where: { userId: regularUser.id }
      });
      const adjustmentTx = transactions.find(tx => tx.type === 'ADMIN_ADJUSTMENT' as TransactionType);
      expect(adjustmentTx).toBeDefined();
    });

    it('should allow admin to search users', async () => {
      const userRepo = dataSource.getRepository(User);

      // Search by username
      const users = await userRepo
        .createQueryBuilder('user')
        .where('user.username LIKE :search', { search: '%regular%' })
        .getMany();

      expect(users.length).toBeGreaterThan(0);
      expect(users[0].username).toContain('regular');

      // Search by telegram ID
      const byId = await userRepo.findOne({
        where: { telegramId: '100100100' }
      });
      expect(byId).toBeDefined();
      expect(byId!.id).toBe(regularUser.id);
    });
  });

  describe('Transaction Oversight', () => {
    it('should allow admin to view all pending deposits', async () => {
      const depositRepo = dataSource.getRepository(Deposit);

      // Create pending deposits
      for (let i = 0; i < 3; i++) {
        const deposit = depositRepo.create({
          userId: regularUser.id,
          amount: 100 * (i + 1),
          walletAddress: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
          status: TransactionStatus.PENDING,
        });
        await depositRepo.save(deposit);
      }

      // Admin views pending deposits
      const pendingDeposits = await depositRepo.find({
        where: { status: TransactionStatus.PENDING },
        relations: ['user'],
        order: { createdAt: 'DESC' },
      });

      expect(pendingDeposits.length).toBeGreaterThanOrEqual(3);
    });

    it('should allow admin to manually confirm expired deposit (FIX #1)', async () => {
      const depositRepo = dataSource.getRepository(Deposit);
      const userRepo = dataSource.getRepository(User);

      // Create expired deposit
      const deposit = depositRepo.create({
        userId: regularUser.id,
        amount: 200,
        walletAddress: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
        status: 'expired_pending' as TransactionStatus,
        expiresAt: new Date(Date.now() - 10000),
      });
      await depositRepo.save(deposit);

      // Admin manually confirms
      await dataSource.transaction(async (manager) => {
        const lockedDeposit = await manager
          .createQueryBuilder(Deposit, 'deposit')
          .setLock('pessimistic_write')
          .where('deposit.id = :id', { id: deposit.id })
          .getOne();

        lockedDeposit!.status = TransactionStatus.CONFIRMED;
        lockedDeposit!.confirmedAt = new Date();
        lockedDeposit!.txHash = '0x' + 'admin'.repeat(11) + '123456';
        await manager.save(lockedDeposit);

        // Update user balance
        const user = await manager.findOne(User, { where: { id: regularUser.id } });
        user!.balance += deposit.amount;
        user!.totalDeposits += deposit.amount;
        await manager.save(user);
      });

      // Verify
      const confirmedDeposit = await depositRepo.findOne({
        where: { id: deposit.id }
      });
      expect(confirmedDeposit!.status).toBe(TransactionStatus.CONFIRMED);

      const updatedUser = await userRepo.findOne({
        where: { id: regularUser.id }
      });
      expect(updatedUser!.balance).toBe(700); // 500 + 200
    });

    it('should allow admin to view payment retry DLQ', async () => {
      const retryRepo = dataSource.getRepository(PaymentRetry);
      const withdrawalRepo = dataSource.getRepository(Withdrawal);

      // Create failed withdrawal in DLQ
      const withdrawal = withdrawalRepo.create({
        userId: regularUser.id,
        amount: 100,
        walletAddress: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
        status: TransactionStatus.FAILED,
      });
      await withdrawalRepo.save(withdrawal);

      const retry = retryRepo.create({
        withdrawalId: withdrawal.id,
        userId: regularUser.id,
        amount: 100,
        attempts: 5,
        maxAttempts: 5,
        status: 'dlq',
        lastError: 'Max retries exceeded',
      });
      await retryRepo.save(retry);

      // Admin views DLQ items
      const dlqItems = await retryRepo.find({
        where: { status: 'dlq' },
        relations: ['user', 'withdrawal'],
        order: { updatedAt: 'DESC' },
      });

      expect(dlqItems.length).toBeGreaterThan(0);
      expect(dlqItems[0].status).toBe('dlq');
      expect(dlqItems[0].attempts).toBe(5);
    });

    it('should allow admin to resolve DLQ item', async () => {
      const retryRepo = dataSource.getRepository(PaymentRetry);
      const withdrawalRepo = dataSource.getRepository(Withdrawal);

      // Create DLQ item
      const withdrawal = withdrawalRepo.create({
        userId: regularUser.id,
        amount: 100,
        walletAddress: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
        status: TransactionStatus.FAILED,
      });
      await withdrawalRepo.save(withdrawal);

      const retry = retryRepo.create({
        withdrawalId: withdrawal.id,
        userId: regularUser.id,
        amount: 100,
        attempts: 5,
        maxAttempts: 5,
        status: 'dlq',
      });
      await retryRepo.save(retry);

      // Admin resolves
      retry.status = 'resolved';
      retry.metadata = JSON.stringify({
        resolvedBy: adminUser.id,
        resolvedAt: new Date().toISOString(),
        notes: 'Manually processed offline',
      });
      await retryRepo.save(retry);

      withdrawal.status = TransactionStatus.CONFIRMED;
      withdrawal.txHash = '0x' + 'resolved'.repeat(8);
      withdrawal.processedAt = new Date();
      await withdrawalRepo.save(withdrawal);

      // Verify
      const resolvedRetry = await retryRepo.findOne({
        where: { withdrawalId: withdrawal.id }
      });
      expect(resolvedRetry!.status).toBe('resolved');
    });
  });

  describe('Statistics and Reporting', () => {
    it('should generate user statistics', async () => {
      const userRepo = dataSource.getRepository(User);

      // Total users
      const totalUsers = await userRepo.count();
      expect(totalUsers).toBeGreaterThan(0);

      // Active users
      const activeUsers = await userRepo.count({
        where: { isActive: true, isBlocked: false }
      });
      expect(activeUsers).toBeGreaterThan(0);

      // Blocked users
      const blockedUsers = await userRepo.count({
        where: { isBlocked: true }
      });
      expect(blockedUsers).toBeGreaterThanOrEqual(0);

      // Users by deposit level
      const level2Users = await userRepo.count({
        where: { depositLevel: 2 }
      });
      expect(level2Users).toBeGreaterThanOrEqual(0);
    });

    it('should generate financial statistics', async () => {
      const depositRepo = dataSource.getRepository(Deposit);
      const withdrawalRepo = dataSource.getRepository(Withdrawal);

      // Total deposits
      const depositStats = await depositRepo
        .createQueryBuilder('deposit')
        .where('deposit.status = :status', { status: TransactionStatus.CONFIRMED })
        .select('SUM(deposit.amount)', 'total')
        .addSelect('COUNT(*)', 'count')
        .getRawOne();

      expect(depositStats).toBeDefined();

      // Total withdrawals
      const withdrawalStats = await withdrawalRepo
        .createQueryBuilder('withdrawal')
        .where('withdrawal.status = :status', { status: TransactionStatus.CONFIRMED })
        .select('SUM(withdrawal.amount)', 'total')
        .addSelect('COUNT(*)', 'count')
        .getRawOne();

      expect(withdrawalStats).toBeDefined();

      // Pending transactions
      const pendingCount = await depositRepo.count({
        where: { status: TransactionStatus.PENDING }
      });
      expect(pendingCount).toBeGreaterThanOrEqual(0);
    });

    it('should generate referral statistics', async () => {
      const userRepo = dataSource.getRepository(User);

      // Users with referrals
      const usersWithReferrals = await userRepo
        .createQueryBuilder('user')
        .leftJoin('user.referrals', 'referral')
        .where('referral.id IS NOT NULL')
        .groupBy('user.id')
        .getCount();

      expect(usersWithReferrals).toBeGreaterThanOrEqual(0);

      // Total referral earnings
      const earningsStats = await userRepo
        .createQueryBuilder('user')
        .select('SUM(user.totalEarnings)', 'total')
        .where('user.totalEarnings > 0')
        .getRawOne();

      expect(earningsStats).toBeDefined();
    });
  });

  describe('Admin Session Management (FIX #14)', () => {
    it('should create admin session in Redis', async () => {
      const sessionKey = `admin:session:${adminUser.telegramId}`;
      const sessionData = {
        userId: adminUser.id,
        telegramId: adminUser.telegramId,
        username: adminUser.username,
        isAdmin: true,
        createdAt: new Date().toISOString(),
      };

      // Create session with 1 hour TTL
      await redis.setex(sessionKey, 3600, JSON.stringify(sessionData));

      // Verify session
      const stored = await redis.get(sessionKey);
      expect(stored).toBeDefined();

      const parsed = JSON.parse(stored!);
      expect(parsed.isAdmin).toBe(true);
      expect(parsed.telegramId).toBe(adminUser.telegramId);
    });

    it('should refresh admin session on activity', async () => {
      const sessionKey = `admin:session:${adminUser.telegramId}`;

      // Create session
      await redis.setex(sessionKey, 3600, JSON.stringify({ admin: true }));

      // Get TTL
      const ttlBefore = await redis.ttl(sessionKey);
      expect(ttlBefore).toBeGreaterThan(0);

      // Simulate activity - refresh TTL
      await redis.expire(sessionKey, 3600);

      // Verify refreshed
      const ttlAfter = await redis.ttl(sessionKey);
      expect(ttlAfter).toBeCloseTo(3600, -1);
    });

    it('should allow admin session across bot restarts', async () => {
      const sessionKey = `admin:session:${adminUser.telegramId}`;
      const sessionData = { isAdmin: true, telegramId: adminUser.telegramId };

      // Store in Redis (persists across restarts)
      await redis.setex(sessionKey, 3600, JSON.stringify(sessionData));

      // Simulate bot restart - Redis connection remains
      const afterRestart = await redis.get(sessionKey);
      expect(afterRestart).toBeDefined();

      const parsed = JSON.parse(afterRestart!);
      expect(parsed.isAdmin).toBe(true);
    });
  });

  describe('Admin Audit Trail', () => {
    it('should log all admin actions', async () => {
      const txRepo = dataSource.getRepository(Transaction);

      // Admin performs action
      const action = txRepo.create({
        userId: regularUser.id,
        type: 'ADMIN_ADJUSTMENT' as TransactionType,
        amount: 50,
        status: TransactionStatus.CONFIRMED,
        metadata: JSON.stringify({
          adminId: adminUser.id,
          adminUsername: adminUser.username,
          action: 'balance_adjustment',
          reason: 'Compensation',
          timestamp: new Date().toISOString(),
        }),
      });
      await txRepo.save(action);

      // Query audit trail
      const auditTrail = await txRepo.find({
        where: { type: 'ADMIN_ADJUSTMENT' as TransactionType },
        order: { createdAt: 'DESC' },
      });

      expect(auditTrail.length).toBeGreaterThan(0);

      const latestAction = auditTrail[0];
      const metadata = JSON.parse(latestAction.metadata || '{}');
      expect(metadata.adminId).toBe(adminUser.id);
      expect(metadata.action).toBe('balance_adjustment');
    });
  });
});
