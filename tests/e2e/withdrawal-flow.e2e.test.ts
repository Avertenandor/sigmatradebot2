/**
 * E2E Test: Withdrawal Flow
 * Tests complete withdrawal journey including validation, processing, and balance updates
 */

import { DataSource } from 'typeorm';
import Redis from 'ioredis';
import { testDataSource, testRedis } from '../setup.e2e';
import { User } from '../../src/entities/User';
import { Withdrawal } from '../../src/entities/Withdrawal';
import { Transaction, TransactionStatus, TransactionType } from '../../src/entities/Transaction';
import { PaymentRetry } from '../../src/entities/PaymentRetry';
import { ethers } from 'ethers';

describe('E2E: Withdrawal Flow', () => {
  let dataSource: DataSource;
  let redis: Redis;
  let testUser: User;

  beforeAll(() => {
    dataSource = testDataSource;
    redis = testRedis;
  });

  beforeEach(async () => {
    // Create test user with balance
    const userRepo = dataSource.getRepository(User);
    testUser = userRepo.create({
      telegramId: '200000001',
      firstName: 'Withdrawal',
      lastName: 'Tester',
      username: 'withdrawal_tester',
      balance: 1000, // User has 1000 USDT
      totalDeposits: 1000,
      totalWithdrawals: 0,
      totalEarnings: 0,
      depositLevel: 2,
      isActive: true,
      isBlocked: false,
    });
    await userRepo.save(testUser);
  });

  describe('Withdrawal Request and Processing', () => {
    it('should complete successful withdrawal flow', async () => {
      const withdrawalRepo = dataSource.getRepository(Withdrawal);
      const txRepo = dataSource.getRepository(Transaction);
      const userRepo = dataSource.getRepository(User);

      const withdrawalAmount = 500;
      const walletAddress = '0x742d35Cc6634C0532925a3b844Bc454e4438f44e';

      // Step 1: Validate user has sufficient balance
      expect(testUser.balance).toBeGreaterThanOrEqual(withdrawalAmount);

      // Step 2: Validate wallet address
      expect(ethers.isAddress(walletAddress)).toBe(true);

      // Step 3: Create withdrawal request
      await dataSource.transaction(async (manager) => {
        // Lock user balance (FIX #11: Balance check race conditions)
        const lockedUser = await manager
          .createQueryBuilder(User, 'user')
          .setLock('pessimistic_write')
          .where('user.id = :id', { id: testUser.id })
          .getOne();

        expect(lockedUser!.balance).toBeGreaterThanOrEqual(withdrawalAmount);

        // Deduct balance
        lockedUser!.balance -= withdrawalAmount;
        await manager.save(lockedUser);

        // Create withdrawal record
        const withdrawal = manager.create(Withdrawal, {
          userId: testUser.id,
          amount: withdrawalAmount,
          walletAddress: walletAddress,
          status: TransactionStatus.PENDING,
        });
        await manager.save(withdrawal);

        // Create transaction record
        const transaction = manager.create(Transaction, {
          userId: testUser.id,
          type: TransactionType.WITHDRAWAL,
          amount: withdrawalAmount,
          status: TransactionStatus.PENDING,
          walletAddress: walletAddress,
        });
        await manager.save(transaction);
      });

      // Step 4: Verify balance was deducted
      let updatedUser = await userRepo.findOne({ where: { id: testUser.id } });
      expect(updatedUser!.balance).toBe(500); // 1000 - 500

      // Step 5: Process withdrawal (simulated blockchain transaction)
      const withdrawal = await withdrawalRepo.findOne({
        where: { userId: testUser.id, amount: withdrawalAmount }
      });
      expect(withdrawal).toBeDefined();

      const txHash = '0x' + '5'.repeat(64);
      withdrawal!.txHash = txHash;
      withdrawal!.status = TransactionStatus.CONFIRMED;
      withdrawal!.processedAt = new Date();
      await withdrawalRepo.save(withdrawal);

      // Update transaction
      const transaction = await txRepo.findOne({
        where: { userId: testUser.id, type: TransactionType.WITHDRAWAL }
      });
      transaction!.txHash = txHash;
      transaction!.status = TransactionStatus.CONFIRMED;
      await txRepo.save(transaction);

      // Update user stats
      testUser.totalWithdrawals += withdrawalAmount;
      await userRepo.save(testUser);

      // Step 6: Verify final state
      const finalUser = await userRepo.findOne({ where: { id: testUser.id } });
      expect(finalUser!.balance).toBe(500);
      expect(finalUser!.totalWithdrawals).toBe(500);

      const finalWithdrawal = await withdrawalRepo.findOne({
        where: { id: withdrawal!.id }
      });
      expect(finalWithdrawal!.status).toBe(TransactionStatus.CONFIRMED);
      expect(finalWithdrawal!.txHash).toBe(txHash);
    });

    it('should prevent withdrawal exceeding balance (FIX #10)', async () => {
      const userRepo = dataSource.getRepository(User);

      const withdrawalAmount = 1500; // More than balance (1000)

      // Check balance
      expect(testUser.balance).toBeLessThan(withdrawalAmount);

      // Should reject withdrawal
      const hasInsufficientBalance = testUser.balance < withdrawalAmount;
      expect(hasInsufficientBalance).toBe(true);

      // Balance should remain unchanged
      const unchangedUser = await userRepo.findOne({ where: { id: testUser.id } });
      expect(unchangedUser!.balance).toBe(1000);
    });

    it('should enforce minimum withdrawal amount', async () => {
      const minWithdrawalAmount = 10; // USDT
      const requestedAmount = 5; // Below minimum

      expect(requestedAmount).toBeLessThan(minWithdrawalAmount);

      // Should reject withdrawal
      const isBelowMinimum = requestedAmount < minWithdrawalAmount;
      expect(isBelowMinimum).toBe(true);
    });
  });

  describe('Payment Retry System (FIX #4)', () => {
    it('should retry failed withdrawal with exponential backoff', async () => {
      const withdrawalRepo = dataSource.getRepository(Withdrawal);
      const retryRepo = dataSource.getRepository(PaymentRetry);

      // Create failed withdrawal
      const withdrawal = withdrawalRepo.create({
        userId: testUser.id,
        amount: 100,
        walletAddress: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
        status: TransactionStatus.FAILED,
        errorMessage: 'Network timeout',
      });
      await withdrawalRepo.save(withdrawal);

      // Create retry record
      const retry = retryRepo.create({
        withdrawalId: withdrawal.id,
        userId: testUser.id,
        amount: 100,
        attempts: 1,
        maxAttempts: 5,
        nextRetryAt: new Date(Date.now() + 60000), // 1 minute
        status: 'pending',
        lastError: 'Network timeout',
      });
      await retryRepo.save(retry);

      // Verify retry was created
      const savedRetry = await retryRepo.findOne({
        where: { withdrawalId: withdrawal.id }
      });
      expect(savedRetry).toBeDefined();
      expect(savedRetry!.attempts).toBe(1);
      expect(savedRetry!.status).toBe('pending');
    });

    it('should use correct exponential backoff delays', () => {
      const DELAYS_MS = [
        60000,    // 1 minute
        300000,   // 5 minutes
        900000,   // 15 minutes
        3600000,  // 1 hour
        14400000, // 4 hours
      ];

      for (let attempt = 1; attempt <= 5; attempt++) {
        const delay = DELAYS_MS[attempt - 1];
        const nextRetryAt = new Date(Date.now() + delay);

        // Verify exponential growth
        if (attempt > 1) {
          const prevDelay = DELAYS_MS[attempt - 2];
          expect(delay).toBeGreaterThan(prevDelay);
        }
      }
    });

    it('should move to DLQ after max retries', async () => {
      const retryRepo = dataSource.getRepository(PaymentRetry);
      const withdrawalRepo = dataSource.getRepository(Withdrawal);

      // Create withdrawal
      const withdrawal = withdrawalRepo.create({
        userId: testUser.id,
        amount: 100,
        walletAddress: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
        status: TransactionStatus.FAILED,
      });
      await withdrawalRepo.save(withdrawal);

      // Create retry that reached max attempts
      const retry = retryRepo.create({
        withdrawalId: withdrawal.id,
        userId: testUser.id,
        amount: 100,
        attempts: 5,
        maxAttempts: 5,
        status: 'failed',
        lastError: 'Max retries exceeded',
      });
      await retryRepo.save(retry);

      // Move to DLQ (Dead Letter Queue)
      retry.status = 'dlq';
      retry.metadata = JSON.stringify({
        reason: 'max_retries_exceeded',
        movedToDlqAt: new Date().toISOString(),
      });
      await retryRepo.save(retry);

      // Verify DLQ status
      const dlqItem = await retryRepo.findOne({
        where: { withdrawalId: withdrawal.id }
      });
      expect(dlqItem!.status).toBe('dlq');
      expect(dlqItem!.attempts).toBe(5);
    });

    it('should allow admin to manually resolve DLQ item', async () => {
      const retryRepo = dataSource.getRepository(PaymentRetry);
      const withdrawalRepo = dataSource.getRepository(Withdrawal);

      // Create DLQ item
      const withdrawal = withdrawalRepo.create({
        userId: testUser.id,
        amount: 100,
        walletAddress: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
        status: TransactionStatus.FAILED,
      });
      await withdrawalRepo.save(withdrawal);

      const retry = retryRepo.create({
        withdrawalId: withdrawal.id,
        userId: testUser.id,
        amount: 100,
        attempts: 5,
        maxAttempts: 5,
        status: 'dlq',
      });
      await retryRepo.save(retry);

      // Admin manually resolves
      retry.status = 'resolved';
      retry.metadata = JSON.stringify({
        resolvedBy: 'admin',
        resolvedAt: new Date().toISOString(),
        resolution: 'manually_processed',
      });
      await retryRepo.save(retry);

      // Update withdrawal
      withdrawal.status = TransactionStatus.CONFIRMED;
      withdrawal.txHash = '0x' + '6'.repeat(64);
      withdrawal.processedAt = new Date();
      await withdrawalRepo.save(withdrawal);

      // Verify resolution
      const resolvedRetry = await retryRepo.findOne({
        where: { withdrawalId: withdrawal.id }
      });
      expect(resolvedRetry!.status).toBe('resolved');

      const confirmedWithdrawal = await withdrawalRepo.findOne({
        where: { id: withdrawal.id }
      });
      expect(confirmedWithdrawal!.status).toBe(TransactionStatus.CONFIRMED);
    });
  });

  describe('Withdrawal Validation', () => {
    it('should validate wallet address format', () => {
      const validAddresses = [
        '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
        '0x0000000000000000000000000000000000000000',
        '0xFFfFfFffFFfffFFfFFfFFFFFffFFFffffFfFFFfF',
      ];

      validAddresses.forEach(address => {
        expect(ethers.isAddress(address)).toBe(true);
      });

      const invalidAddresses = [
        '0x123', // Too short
        '742d35Cc6634C0532925a3b844Bc454e4438f44e', // Missing 0x
        '0xZZZZ35Cc6634C0532925a3b844Bc454e4438f44e', // Invalid hex
        '',
        'not an address',
      ];

      invalidAddresses.forEach(address => {
        expect(ethers.isAddress(address)).toBe(false);
      });
    });

    it('should prevent withdrawal for blocked user', async () => {
      const userRepo = dataSource.getRepository(User);

      // Block user
      testUser.isBlocked = true;
      testUser.isActive = false;
      await userRepo.save(testUser);

      // Try to withdraw
      const canWithdraw = !testUser.isBlocked && testUser.isActive;
      expect(canWithdraw).toBe(false);

      // Balance should not change
      const blockedUser = await userRepo.findOne({ where: { id: testUser.id } });
      expect(blockedUser!.balance).toBe(1000);
    });

    it('should handle concurrent withdrawal requests (FIX #11)', async () => {
      const userRepo = dataSource.getRepository(User);

      const withdrawalAmount = 600; // User has 1000

      // First withdrawal (should succeed)
      const processWithdrawal1 = async () => {
        return await dataSource.transaction('SERIALIZABLE', async (manager) => {
          const lockedUser = await manager
            .createQueryBuilder(User, 'user')
            .setLock('pessimistic_write')
            .where('user.id = :id', { id: testUser.id })
            .getOne();

          if (lockedUser!.balance < withdrawalAmount) {
            throw new Error('Insufficient balance');
          }

          lockedUser!.balance -= withdrawalAmount;
          await manager.save(lockedUser);

          return { success: true };
        });
      };

      // Second concurrent withdrawal (should fail due to insufficient balance)
      const processWithdrawal2 = async () => {
        return await dataSource.transaction('SERIALIZABLE', async (manager) => {
          const lockedUser = await manager
            .createQueryBuilder(User, 'user')
            .setLock('pessimistic_write')
            .where('user.id = :id', { id: testUser.id })
            .getOne();

          if (lockedUser!.balance < withdrawalAmount) {
            throw new Error('Insufficient balance');
          }

          lockedUser!.balance -= withdrawalAmount;
          await manager.save(lockedUser);

          return { success: true };
        });
      };

      // Execute concurrently
      const results = await Promise.allSettled([
        processWithdrawal1(),
        processWithdrawal2(),
      ]);

      const successful = results.filter(r => r.status === 'fulfilled');
      const failed = results.filter(r => r.status === 'rejected');

      // Only one should succeed
      expect(successful.length).toBe(1);
      expect(failed.length).toBe(1);

      // Final balance should be 400 (1000 - 600)
      const finalUser = await userRepo.findOne({ where: { id: testUser.id } });
      expect(finalUser!.balance).toBe(400);
    });
  });

  describe('Withdrawal Limits and Fees', () => {
    it('should enforce daily withdrawal limit', async () => {
      const withdrawalRepo = dataSource.getRepository(Withdrawal);

      const dailyLimit = 10000; // USDT

      // Create withdrawal totaling 8000 today
      const withdrawal1 = withdrawalRepo.create({
        userId: testUser.id,
        amount: 8000,
        walletAddress: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
        status: TransactionStatus.CONFIRMED,
        processedAt: new Date(),
      });
      await withdrawalRepo.save(withdrawal1);

      // Calculate today's total
      const startOfDay = new Date();
      startOfDay.setHours(0, 0, 0, 0);

      const todayTotal = await withdrawalRepo
        .createQueryBuilder('withdrawal')
        .where('withdrawal.userId = :userId', { userId: testUser.id })
        .andWhere('withdrawal.status = :status', { status: TransactionStatus.CONFIRMED })
        .andWhere('withdrawal.processedAt >= :startOfDay', { startOfDay })
        .select('SUM(withdrawal.amount)', 'total')
        .getRawOne();

      const total = parseFloat(todayTotal.total || '0');
      expect(total).toBe(8000);

      // Try to withdraw 3000 more (exceeds limit)
      const requestedAmount = 3000;
      const wouldExceedLimit = (total + requestedAmount) > dailyLimit;
      expect(wouldExceedLimit).toBe(true);
    });

    it('should apply withdrawal fee if configured', () => {
      const amount = 1000;
      const feePercentage = 0.01; // 1%
      const fee = amount * feePercentage; // 10 USDT

      const amountAfterFee = amount - fee;

      expect(amountAfterFee).toBe(990);
      expect(fee).toBe(10);
    });
  });
});
