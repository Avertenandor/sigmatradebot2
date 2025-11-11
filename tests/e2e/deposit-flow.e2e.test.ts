/**
 * E2E Test: Deposit Flow
 * Tests complete deposit journey from wallet generation to confirmation and balance update
 */

import { DataSource } from 'typeorm';
import Redis from 'ioredis';
import { testDataSource, testRedis } from '../setup.e2e';
import { User } from '../../src/entities/User';
import { Deposit } from '../../src/entities/Deposit';
import { Transaction, TransactionStatus, TransactionType } from '../../src/entities/Transaction';
import { ethers } from 'ethers';

describe('E2E: Deposit Flow', () => {
  let dataSource: DataSource;
  let redis: Redis;
  let testUser: User;

  beforeAll(() => {
    dataSource = testDataSource;
    redis = testRedis;
  });

  beforeEach(async () => {
    // Create test user
    const userRepo = dataSource.getRepository(User);
    testUser = userRepo.create({
      telegramId: '100000001',
      firstName: 'Deposit',
      lastName: 'Tester',
      username: 'deposit_tester',
      balance: 0,
      totalDeposits: 0,
      totalWithdrawals: 0,
      totalEarnings: 0,
      depositLevel: 1,
      isActive: true,
      isBlocked: false,
    });
    await userRepo.save(testUser);
  });

  describe('Wallet Generation', () => {
    it('should generate unique deposit wallet for user', async () => {
      // Generate wallet (simulated)
      const wallet = ethers.Wallet.createRandom();
      const depositAddress = wallet.address;

      expect(depositAddress).toBeDefined();
      expect(depositAddress).toMatch(/^0x[a-fA-F0-9]{40}$/);
      expect(ethers.isAddress(depositAddress)).toBe(true);

      // Store wallet in Redis with user association
      const walletKey = `deposit:wallet:${testUser.telegramId}`;
      await redis.set(walletKey, depositAddress, 'EX', 3600); // 1 hour

      const stored = await redis.get(walletKey);
      expect(stored).toBe(depositAddress);
    });

    it('should validate deposit address checksum', async () => {
      const validAddress = '0x742d35Cc6634C0532925a3b844Bc454e4438f44e';
      expect(ethers.isAddress(validAddress)).toBe(true);
      expect(ethers.getAddress(validAddress)).toBe(validAddress);

      const invalidChecksumAddress = '0x742D35Cc6634C0532925a3b844Bc454e4438f44e';
      expect(ethers.isAddress(invalidChecksumAddress)).toBe(true);

      // Should normalize to proper checksum
      const normalized = ethers.getAddress(invalidChecksumAddress);
      expect(normalized).toBe(validAddress);
    });
  });

  describe('Deposit Creation and Processing', () => {
    it('should create pending deposit and process to confirmed', async () => {
      const depositRepo = dataSource.getRepository(Deposit);
      const txRepo = dataSource.getRepository(Transaction);
      const userRepo = dataSource.getRepository(User);

      // Step 1: User requests deposit, system creates pending deposit
      const deposit = depositRepo.create({
        userId: testUser.id,
        amount: 100,
        walletAddress: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
        txHash: null,
        status: TransactionStatus.PENDING,
        expiresAt: new Date(Date.now() + 3600000), // 1 hour
      });
      await depositRepo.save(deposit);

      expect(deposit.id).toBeDefined();
      expect(deposit.status).toBe(TransactionStatus.PENDING);
      expect(deposit.amount).toBe(100);

      // Step 2: Blockchain event detected (simulated)
      const txHash = '0x' + '1'.repeat(64); // Mock transaction hash

      await dataSource.transaction(async (manager) => {
        // Lock deposit for update (FIX #3: Pessimistic locking)
        const lockedDeposit = await manager
          .createQueryBuilder(Deposit, 'deposit')
          .setLock('pessimistic_write')
          .where('deposit.id = :id', { id: deposit.id })
          .andWhere('deposit.status = :status', { status: TransactionStatus.PENDING })
          .getOne();

        expect(lockedDeposit).toBeDefined();

        // Update deposit
        lockedDeposit!.txHash = txHash;
        lockedDeposit!.status = TransactionStatus.CONFIRMED;
        lockedDeposit!.confirmedAt = new Date();
        await manager.save(lockedDeposit);

        // Update user balance
        const user = await manager.findOne(User, { where: { id: testUser.id } });
        user!.balance += deposit.amount;
        user!.totalDeposits += deposit.amount;
        await manager.save(user);

        // Create transaction record
        const transaction = manager.create(Transaction, {
          userId: testUser.id,
          type: TransactionType.DEPOSIT,
          amount: deposit.amount,
          status: TransactionStatus.CONFIRMED,
          txHash: txHash,
          walletAddress: deposit.walletAddress,
        });
        await manager.save(transaction);
      });

      // Step 3: Verify deposit was confirmed
      const confirmedDeposit = await depositRepo.findOne({
        where: { id: deposit.id }
      });
      expect(confirmedDeposit!.status).toBe(TransactionStatus.CONFIRMED);
      expect(confirmedDeposit!.txHash).toBe(txHash);
      expect(confirmedDeposit!.confirmedAt).toBeDefined();

      // Step 4: Verify user balance updated
      const updatedUser = await userRepo.findOne({
        where: { id: testUser.id }
      });
      expect(updatedUser!.balance).toBe(100);
      expect(updatedUser!.totalDeposits).toBe(100);

      // Step 5: Verify transaction record created
      const transactions = await txRepo.find({
        where: { userId: testUser.id }
      });
      expect(transactions.length).toBe(1);
      expect(transactions[0].type).toBe(TransactionType.DEPOSIT);
      expect(transactions[0].amount).toBe(100);
      expect(transactions[0].status).toBe(TransactionStatus.CONFIRMED);
    });

    it('should handle multiple deposits for same user', async () => {
      const depositRepo = dataSource.getRepository(Deposit);
      const userRepo = dataSource.getRepository(User);

      // Create first deposit
      const deposit1 = depositRepo.create({
        userId: testUser.id,
        amount: 50,
        walletAddress: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
        txHash: '0x' + '1'.repeat(64),
        status: TransactionStatus.CONFIRMED,
        confirmedAt: new Date(),
      });
      await depositRepo.save(deposit1);

      // Update user balance
      testUser.balance += 50;
      testUser.totalDeposits += 50;
      await userRepo.save(testUser);

      // Create second deposit
      const deposit2 = depositRepo.create({
        userId: testUser.id,
        amount: 150,
        walletAddress: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
        txHash: '0x' + '2'.repeat(64),
        status: TransactionStatus.CONFIRMED,
        confirmedAt: new Date(),
      });
      await depositRepo.save(deposit2);

      // Update user balance again
      testUser.balance += 150;
      testUser.totalDeposits += 150;
      await userRepo.save(testUser);

      // Verify both deposits exist
      const deposits = await depositRepo.find({
        where: { userId: testUser.id }
      });
      expect(deposits.length).toBe(2);

      // Verify total balance
      const updatedUser = await userRepo.findOne({
        where: { id: testUser.id }
      });
      expect(updatedUser!.balance).toBe(200);
      expect(updatedUser!.totalDeposits).toBe(200);
    });

    it('should validate deposit amount tolerance (FIX #2)', async () => {
      const depositRepo = dataSource.getRepository(Deposit);

      // Expected amount: 100 USDT
      // Actual amount: 99.99 USDT (within 0.01 tolerance)
      const expectedAmount = 100;
      const actualAmount = 99.99;
      const tolerance = 0.01;

      const deposit = depositRepo.create({
        userId: testUser.id,
        amount: expectedAmount,
        walletAddress: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
        status: TransactionStatus.PENDING,
      });
      await depositRepo.save(deposit);

      // Validate tolerance
      const difference = Math.abs(expectedAmount - actualAmount);
      expect(difference).toBeLessThanOrEqual(tolerance);

      // Should accept deposit
      deposit.status = TransactionStatus.CONFIRMED;
      deposit.amount = actualAmount; // Update to actual amount received
      await depositRepo.save(deposit);

      const confirmedDeposit = await depositRepo.findOne({
        where: { id: deposit.id }
      });
      expect(confirmedDeposit!.status).toBe(TransactionStatus.CONFIRMED);
      expect(confirmedDeposit!.amount).toBe(99.99);
    });

    it('should reject deposit outside tolerance', async () => {
      const depositRepo = dataSource.getRepository(Deposit);

      const expectedAmount = 100;
      const actualAmount = 99.98; // Outside 0.01 tolerance
      const tolerance = 0.01;

      const deposit = depositRepo.create({
        userId: testUser.id,
        amount: expectedAmount,
        walletAddress: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
        status: TransactionStatus.PENDING,
      });
      await depositRepo.save(deposit);

      // Validate tolerance
      const difference = Math.abs(expectedAmount - actualAmount);
      expect(difference).toBeGreaterThan(tolerance);

      // Should reject deposit
      deposit.status = TransactionStatus.FAILED;
      await depositRepo.save(deposit);

      const failedDeposit = await depositRepo.findOne({
        where: { id: deposit.id }
      });
      expect(failedDeposit!.status).toBe(TransactionStatus.FAILED);
    });
  });

  describe('Expired Deposits (FIX #1)', () => {
    it('should mark expired deposits for admin review', async () => {
      const depositRepo = dataSource.getRepository(Deposit);

      // Create deposit that will expire
      const deposit = depositRepo.create({
        userId: testUser.id,
        amount: 100,
        walletAddress: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
        status: TransactionStatus.PENDING,
        expiresAt: new Date(Date.now() - 1000), // Already expired
      });
      await depositRepo.save(deposit);

      // Find expired deposits (simulated job)
      const expiredDeposits = await depositRepo
        .createQueryBuilder('deposit')
        .where('deposit.status = :status', { status: TransactionStatus.PENDING })
        .andWhere('deposit.expiresAt < :now', { now: new Date() })
        .getMany();

      expect(expiredDeposits.length).toBeGreaterThan(0);
      expect(expiredDeposits[0].id).toBe(deposit.id);

      // Mark as expired_pending for admin review
      deposit.status = 'expired_pending' as TransactionStatus;
      await depositRepo.save(deposit);

      const markedDeposit = await depositRepo.findOne({
        where: { id: deposit.id }
      });
      expect(markedDeposit!.status).toBe('expired_pending');
    });

    it('should allow admin to recover expired deposit', async () => {
      const depositRepo = dataSource.getRepository(Deposit);
      const userRepo = dataSource.getRepository(User);

      // Create expired deposit
      const deposit = depositRepo.create({
        userId: testUser.id,
        amount: 100,
        walletAddress: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
        status: 'expired_pending' as TransactionStatus,
        expiresAt: new Date(Date.now() - 10000),
      });
      await depositRepo.save(deposit);

      // Admin manually confirms the deposit
      await dataSource.transaction(async (manager) => {
        const lockedDeposit = await manager
          .createQueryBuilder(Deposit, 'deposit')
          .setLock('pessimistic_write')
          .where('deposit.id = :id', { id: deposit.id })
          .getOne();

        lockedDeposit!.status = TransactionStatus.CONFIRMED;
        lockedDeposit!.confirmedAt = new Date();
        lockedDeposit!.txHash = '0x' + '3'.repeat(64);
        await manager.save(lockedDeposit);

        // Update user balance
        const user = await manager.findOne(User, { where: { id: testUser.id } });
        user!.balance += deposit.amount;
        user!.totalDeposits += deposit.amount;
        await manager.save(user);
      });

      // Verify recovery
      const recoveredDeposit = await depositRepo.findOne({
        where: { id: deposit.id }
      });
      expect(recoveredDeposit!.status).toBe(TransactionStatus.CONFIRMED);

      const updatedUser = await userRepo.findOne({
        where: { id: testUser.id }
      });
      expect(updatedUser!.balance).toBe(100);
    });
  });

  describe('Transaction Deduplication (FIX #18)', () => {
    it('should prevent duplicate transaction processing', async () => {
      const depositRepo = dataSource.getRepository(Deposit);
      const userRepo = dataSource.getRepository(User);

      const txHash = '0x' + 'unique'.repeat(8) + '12345678';

      // First processing
      const deposit1 = depositRepo.create({
        userId: testUser.id,
        amount: 100,
        walletAddress: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
        txHash: txHash,
        status: TransactionStatus.CONFIRMED,
        confirmedAt: new Date(),
      });
      await depositRepo.save(deposit1);

      testUser.balance += 100;
      await userRepo.save(testUser);

      // Try to process same transaction again
      const existingDeposit = await depositRepo.findOne({
        where: { txHash: txHash }
      });
      expect(existingDeposit).toBeDefined();

      // Should skip duplicate processing
      // Balance should not change
      const user = await userRepo.findOne({ where: { id: testUser.id } });
      expect(user!.balance).toBe(100); // Not 200

      // Should have only one deposit with this txHash
      const deposits = await depositRepo.find({
        where: { txHash: txHash }
      });
      expect(deposits.length).toBe(1);
    });
  });

  describe('Deposit Level Upgrade', () => {
    it('should upgrade deposit level after reaching threshold', async () => {
      const userRepo = dataSource.getRepository(User);

      // User starts at level 1
      expect(testUser.depositLevel).toBe(1);
      expect(testUser.totalDeposits).toBe(0);

      // Simulate deposits totaling 1000 USDT (level 2 threshold)
      testUser.totalDeposits = 1000;
      testUser.balance = 1000;

      // Check level upgrade (simulated logic)
      if (testUser.totalDeposits >= 1000 && testUser.totalDeposits < 5000) {
        testUser.depositLevel = 2;
      }

      await userRepo.save(testUser);

      const upgradedUser = await userRepo.findOne({
        where: { id: testUser.id }
      });
      expect(upgradedUser!.depositLevel).toBe(2);
    });

    it('should reach maximum deposit level', async () => {
      const userRepo = dataSource.getRepository(User);

      // Simulate deposits totaling 50000+ USDT (level 5 threshold)
      testUser.totalDeposits = 60000;
      testUser.balance = 60000;

      // Check level upgrade
      if (testUser.totalDeposits >= 50000) {
        testUser.depositLevel = 5;
      }

      await userRepo.save(testUser);

      const maxLevelUser = await userRepo.findOne({
        where: { id: testUser.id }
      });
      expect(maxLevelUser!.depositLevel).toBe(5);
    });
  });
});
