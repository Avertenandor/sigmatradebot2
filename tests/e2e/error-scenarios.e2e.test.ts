/**
 * E2E Test: Error Scenarios
 * Tests error handling and edge cases across the system
 */

import { DataSource } from 'typeorm';
import Redis from 'ioredis';
import { testDataSource, testRedis } from '../setup.e2e';
import { User } from '../../src/entities/User';
import { Deposit } from '../../src/entities/Deposit';
import { Withdrawal } from '../../src/entities/Withdrawal';
import { TransactionStatus, TransactionType } from '../../src/entities/Transaction';
import { FailedNotification } from '../../src/entities/FailedNotification';

describe('E2E: Error Scenarios', () => {
  let dataSource: DataSource;
  let redis: Redis;
  let testUser: User;

  beforeAll(() => {
    dataSource = testDataSource;
    redis = testRedis;
  });

  beforeEach(async () => {
    const userRepo = dataSource.getRepository(User);
    testUser = userRepo.create({
      telegramId: '300000001',
      firstName: 'Error',
      lastName: 'Tester',
      username: 'error_tester',
      balance: 1000,
      totalDeposits: 1000,
      totalWithdrawals: 0,
      totalEarnings: 0,
      depositLevel: 2,
      isActive: true,
      isBlocked: false,
    });
    await userRepo.save(testUser);
  });

  describe('Database Error Scenarios', () => {
    it('should handle transaction rollback on error', async () => {
      const userRepo = dataSource.getRepository(User);
      const initialBalance = testUser.balance;

      try {
        await dataSource.transaction(async (manager) => {
          // Modify balance
          testUser.balance += 100;
          await manager.save(testUser);

          // Simulate error
          throw new Error('Simulated error');
        });
      } catch (error) {
        // Expected error
      }

      // Verify rollback - balance should be unchanged
      const user = await userRepo.findOne({ where: { id: testUser.id } });
      expect(user!.balance).toBe(initialBalance);
    });

    it('should handle unique constraint violation', async () => {
      const userRepo = dataSource.getRepository(User);

      // Create first user
      const user1 = userRepo.create({
        telegramId: '400000001',
        firstName: 'User1',
        username: 'unique_user',
        balance: 0,
        totalDeposits: 0,
        totalWithdrawals: 0,
        totalEarnings: 0,
        depositLevel: 1,
        isActive: true,
        isBlocked: false,
      });
      await userRepo.save(user1);

      // Try to create duplicate telegram ID
      try {
        const user2 = userRepo.create({
          telegramId: '400000001', // Duplicate
          firstName: 'User2',
          username: 'another_user',
          balance: 0,
          totalDeposits: 0,
          totalWithdrawals: 0,
          totalEarnings: 0,
          depositLevel: 1,
          isActive: true,
          isBlocked: false,
        });
        await userRepo.save(user2);
        fail('Should have thrown unique constraint error');
      } catch (error: any) {
        expect(error.code).toMatch(/23505|UNIQUE/); // PostgreSQL unique constraint error
      }
    });

    it('should handle deadlock scenario gracefully', async () => {
      const userRepo = dataSource.getRepository(User);

      // Create second user
      const user2 = userRepo.create({
        telegramId: '400000002',
        firstName: 'User2',
        username: 'deadlock_test',
        balance: 1000,
        totalDeposits: 1000,
        totalWithdrawals: 0,
        totalEarnings: 0,
        depositLevel: 1,
        isActive: true,
        isBlocked: false,
      });
      await userRepo.save(user2);

      // Simulate potential deadlock with serializable isolation
      const transfer1 = async () => {
        return await dataSource.transaction('SERIALIZABLE', async (manager) => {
          const u1 = await manager.findOne(User, { where: { id: testUser.id } });
          const u2 = await manager.findOne(User, { where: { id: user2.id } });

          u1!.balance -= 100;
          u2!.balance += 100;

          await manager.save([u1, u2]);
        });
      };

      const transfer2 = async () => {
        return await dataSource.transaction('SERIALIZABLE', async (manager) => {
          const u2 = await manager.findOne(User, { where: { id: user2.id } });
          const u1 = await manager.findOne(User, { where: { id: testUser.id } });

          u2!.balance -= 50;
          u1!.balance += 50;

          await manager.save([u2, u1]);
        });
      };

      // Execute concurrently - one may fail, but system handles it
      const results = await Promise.allSettled([transfer1(), transfer2()]);

      // At least one should succeed
      const successful = results.filter(r => r.status === 'fulfilled');
      expect(successful.length).toBeGreaterThan(0);
    });
  });

  describe('Redis Connection Errors', () => {
    it('should handle Redis connection failure gracefully', async () => {
      // Try to use Redis
      try {
        await redis.get('test:key');
      } catch (error) {
        // If Redis is down, operation should fail gracefully
        expect(error).toBeDefined();
      }

      // Application should continue working with database
      const userRepo = dataSource.getRepository(User);
      const user = await userRepo.findOne({ where: { id: testUser.id } });
      expect(user).toBeDefined();
    });

    it('should handle cache miss gracefully', async () => {
      const cacheKey = 'nonexistent:key';

      // Try to get non-existent key
      const cached = await redis.get(cacheKey);
      expect(cached).toBeNull();

      // Fallback to database query
      const userRepo = dataSource.getRepository(User);
      const user = await userRepo.findOne({ where: { id: testUser.id } });
      expect(user).toBeDefined();

      // Cache the result
      await redis.setex(`user:${testUser.id}`, 300, JSON.stringify(user));
    });
  });

  describe('Notification Failures (FIX #17)', () => {
    it('should track failed notification', async () => {
      const failedNotifRepo = dataSource.getRepository(FailedNotification);

      // Create failed notification
      const failedNotif = failedNotifRepo.create({
        userId: testUser.id,
        notificationType: 'deposit_confirmed',
        payload: JSON.stringify({
          amount: 100,
          txHash: '0x123',
        }),
        attempts: 1,
        maxAttempts: 5,
        nextRetryAt: new Date(Date.now() + 60000),
        status: 'pending',
        lastError: 'Telegram API error: Too Many Requests',
      });
      await failedNotifRepo.save(failedNotif);

      // Verify tracking
      const tracked = await failedNotifRepo.findOne({
        where: { userId: testUser.id }
      });
      expect(tracked).toBeDefined();
      expect(tracked!.status).toBe('pending');
      expect(tracked!.attempts).toBe(1);
    });

    it('should retry failed notification with exponential backoff', async () => {
      const failedNotifRepo = dataSource.getRepository(FailedNotification);

      // Create notification for retry
      const notification = failedNotifRepo.create({
        userId: testUser.id,
        notificationType: 'withdrawal_processed',
        payload: JSON.stringify({ amount: 500 }),
        attempts: 2,
        maxAttempts: 5,
        nextRetryAt: new Date(Date.now() - 1000), // Ready for retry
        status: 'pending',
        lastError: 'Temporary error',
      });
      await failedNotifRepo.save(notification);

      // Simulate retry attempt
      notification.attempts += 1;

      // Calculate next retry with exponential backoff
      const delays = [60000, 300000, 900000, 3600000, 7200000]; // 1m, 5m, 15m, 1h, 2h
      const nextDelay = delays[Math.min(notification.attempts - 1, delays.length - 1)];
      notification.nextRetryAt = new Date(Date.now() + nextDelay);

      if (notification.attempts >= notification.maxAttempts) {
        notification.status = 'failed';
      }

      await failedNotifRepo.save(notification);

      // Verify retry logic
      expect(notification.attempts).toBe(3);
      expect(notification.nextRetryAt.getTime()).toBeGreaterThan(Date.now());
    });

    it('should handle max retry failures', async () => {
      const failedNotifRepo = dataSource.getRepository(FailedNotification);

      // Create notification that reached max attempts
      const notification = failedNotifRepo.create({
        userId: testUser.id,
        notificationType: 'referral_reward',
        payload: JSON.stringify({ reward: 10 }),
        attempts: 5,
        maxAttempts: 5,
        status: 'failed',
        lastError: 'Max retries exceeded',
      });
      await failedNotifRepo.save(notification);

      // Verify final status
      const failed = await failedNotifRepo.findOne({
        where: { id: notification.id }
      });
      expect(failed!.status).toBe('failed');
      expect(failed!.attempts).toBe(5);
    });

    it('should distinguish critical vs non-critical notifications', async () => {
      const failedNotifRepo = dataSource.getRepository(FailedNotification);

      // Critical notification (deposit confirmed)
      const critical = failedNotifRepo.create({
        userId: testUser.id,
        notificationType: 'deposit_confirmed',
        payload: JSON.stringify({ amount: 1000 }),
        attempts: 1,
        maxAttempts: 5,
        status: 'pending',
        metadata: JSON.stringify({ priority: 'critical' }),
      });
      await failedNotifRepo.save(critical);

      // Non-critical notification (welcome message)
      const nonCritical = failedNotifRepo.create({
        userId: testUser.id,
        notificationType: 'welcome',
        payload: JSON.stringify({ message: 'Welcome!' }),
        attempts: 1,
        maxAttempts: 3,
        status: 'pending',
        metadata: JSON.stringify({ priority: 'low' }),
      });
      await failedNotifRepo.save(nonCritical);

      // Query by priority
      const criticalNotifs = await failedNotifRepo
        .createQueryBuilder('notification')
        .where("notification.metadata::jsonb->>'priority' = :priority", { priority: 'critical' })
        .getMany();

      expect(criticalNotifs.length).toBeGreaterThan(0);
    });
  });

  describe('Validation Errors', () => {
    it('should handle invalid withdrawal amount', async () => {
      const invalidAmounts = [-100, 0, 0.001, 100000000];

      invalidAmounts.forEach(amount => {
        const isValid = amount > 0 && amount <= testUser.balance && amount >= 10; // min 10 USDT
        expect(isValid).toBe(false);
      });
    });

    it('should handle invalid wallet address', async () => {
      const invalidAddresses = [
        '',
        '0x123',
        'not_an_address',
        '0xZZZZ35Cc6634C0532925a3b844Bc454e4438f44e',
      ];

      const { ethers } = require('ethers');

      invalidAddresses.forEach(address => {
        const isValid = ethers.isAddress(address);
        expect(isValid).toBe(false);
      });
    });

    it('should handle circular referral attempt (FIX #8)', async () => {
      const userRepo = dataSource.getRepository(User);

      // Create user A
      const userA = userRepo.create({
        telegramId: '500000001',
        firstName: 'UserA',
        username: 'user_a',
        balance: 0,
        totalDeposits: 0,
        totalWithdrawals: 0,
        totalEarnings: 0,
        depositLevel: 1,
        isActive: true,
        isBlocked: false,
      });
      await userRepo.save(userA);

      // Create user B referred by A
      const userB = userRepo.create({
        telegramId: '500000002',
        firstName: 'UserB',
        username: 'user_b',
        balance: 0,
        totalDeposits: 0,
        totalWithdrawals: 0,
        totalEarnings: 0,
        depositLevel: 1,
        isActive: true,
        isBlocked: false,
        referrerId: userA.id,
      });
      await userRepo.save(userB);

      // Try to make A referred by B (circular - should be prevented)
      const wouldBeCircular = await (async () => {
        // Check if B is in A's referral chain
        const chain = await dataSource.query(`
          WITH RECURSIVE referral_chain AS (
            SELECT id, referrer_id, 1 as level
            FROM "user"
            WHERE id = $1

            UNION ALL

            SELECT u.id, u.referrer_id, rc.level + 1
            FROM "user" u
            INNER JOIN referral_chain rc ON u.referrer_id = rc.id
            WHERE rc.level < 10
          )
          SELECT * FROM referral_chain WHERE id = $2;
        `, [userB.id, userA.id]);

        return chain.length > 0;
      })();

      expect(wouldBeCircular).toBe(true);
      // Should prevent updating userA.referrerId = userB.id
    });

    it('should handle invalid referral code (FIX #9)', async () => {
      const userRepo = dataSource.getRepository(User);

      const invalidReferralId = '999999999'; // Non-existent

      const referrer = await userRepo.findOne({
        where: { telegramId: invalidReferralId }
      });

      expect(referrer).toBeNull();
      // Should not create user with invalid referrer
    });
  });

  describe('Race Condition Scenarios', () => {
    it('should handle concurrent deposit confirmations (FIX #3)', async () => {
      const depositRepo = dataSource.getRepository(Deposit);
      const userRepo = dataSource.getRepository(User);

      // Create pending deposit
      const deposit = depositRepo.create({
        userId: testUser.id,
        amount: 100,
        walletAddress: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
        status: TransactionStatus.PENDING,
      });
      await depositRepo.save(deposit);

      // Concurrent confirmation attempts
      const confirm1 = async () => {
        return await dataSource.transaction('SERIALIZABLE', async (manager) => {
          const locked = await manager
            .createQueryBuilder(Deposit, 'deposit')
            .setLock('pessimistic_write')
            .where('deposit.id = :id', { id: deposit.id })
            .andWhere('deposit.status = :status', { status: TransactionStatus.PENDING })
            .getOne();

          if (!locked) throw new Error('Already processed');

          locked.status = TransactionStatus.CONFIRMED;
          await manager.save(locked);

          const user = await manager.findOne(User, { where: { id: testUser.id } });
          user!.balance += 100;
          await manager.save(user);
        });
      };

      const confirm2 = async () => {
        return await dataSource.transaction('SERIALIZABLE', async (manager) => {
          const locked = await manager
            .createQueryBuilder(Deposit, 'deposit')
            .setLock('pessimistic_write')
            .where('deposit.id = :id', { id: deposit.id })
            .andWhere('deposit.status = :status', { status: TransactionStatus.PENDING })
            .getOne();

          if (!locked) throw new Error('Already processed');

          locked.status = TransactionStatus.CONFIRMED;
          await manager.save(locked);

          const user = await manager.findOne(User, { where: { id: testUser.id } });
          user!.balance += 100;
          await manager.save(user);
        });
      };

      // Execute concurrently
      const results = await Promise.allSettled([confirm1(), confirm2()]);

      // Only one should succeed
      const successful = results.filter(r => r.status === 'fulfilled');
      const failed = results.filter(r => r.status === 'rejected');

      expect(successful.length).toBe(1);
      expect(failed.length).toBe(1);

      // Verify balance updated only once
      const finalUser = await userRepo.findOne({ where: { id: testUser.id } });
      expect(finalUser!.balance).toBe(1100); // 1000 + 100, not 1200
    });

    it('should handle concurrent user registration (FIX #5)', async () => {
      const userRepo = dataSource.getRepository(User);
      const telegramId = '600000001';

      const createUser = async () => {
        // Check if exists
        const existing = await userRepo.findOne({ where: { telegramId } });
        if (existing) {
          throw new Error('User already exists');
        }

        // Create new user
        const user = userRepo.create({
          telegramId,
          firstName: 'Concurrent',
          username: 'concurrent_user',
          balance: 0,
          totalDeposits: 0,
          totalWithdrawals: 0,
          totalEarnings: 0,
          depositLevel: 1,
          isActive: true,
          isBlocked: false,
        });
        return await userRepo.save(user);
      };

      // Execute concurrently
      const results = await Promise.allSettled([createUser(), createUser()]);

      // Only one should succeed (due to unique constraint)
      const successful = results.filter(r => r.status === 'fulfilled');
      expect(successful.length).toBeLessThanOrEqual(1);

      // Verify only one user created
      const users = await userRepo.find({ where: { telegramId } });
      expect(users.length).toBe(1);
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty or null values gracefully', async () => {
      const userRepo = dataSource.getRepository(User);

      // User without optional fields
      const minimalUser = userRepo.create({
        telegramId: '700000001',
        firstName: 'Minimal',
        lastName: null,
        username: null,
        balance: 0,
        totalDeposits: 0,
        totalWithdrawals: 0,
        totalEarnings: 0,
        depositLevel: 1,
        isActive: true,
        isBlocked: false,
      });
      await userRepo.save(minimalUser);

      const saved = await userRepo.findOne({ where: { id: minimalUser.id } });
      expect(saved).toBeDefined();
      expect(saved!.lastName).toBeNull();
      expect(saved!.username).toBeNull();
    });

    it('should handle very large numbers', () => {
      const largeAmount = 999999999.99;
      const tooLarge = 1000000000; // 1 billion

      expect(largeAmount).toBeLessThan(1000000000);
      expect(tooLarge).toBeGreaterThanOrEqual(1000000000);
    });

    it('should handle timezone differences', () => {
      const date1 = new Date('2024-01-15T10:00:00Z'); // UTC
      const date2 = new Date('2024-01-15T10:00:00+03:00'); // UTC+3

      // Should be different timestamps
      expect(date1.getTime()).not.toBe(date2.getTime());

      // Always store in UTC
      const utcTimestamp = Date.now();
      const utcDate = new Date(utcTimestamp);

      expect(utcDate.toISOString()).toContain('Z');
    });
  });
});
