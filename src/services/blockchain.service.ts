/**
 * Blockchain Service
 * Handles BSC blockchain interactions via QuickNode
 * - USDT BEP-20 contract integration
 * - Transaction monitoring (deposits)
 * - Event processing (Transfer events)
 * - WebSocket connection for real-time updates
 */

import { ethers } from 'ethers';
import { config } from '../config';
import { logger } from '../utils/logger.util';
import { AppDataSource } from '../database/data-source';
import { Transaction } from '../database/entities/Transaction.entity';
import { Deposit } from '../database/entities/Deposit.entity';
import { User } from '../database/entities/User.entity';
import { TransactionStatus, TransactionType } from '../utils/constants';
import type { DepositService } from './deposit.service';
import { notificationService } from './notification.service';

// USDT BEP-20 ABI (ERC20 standard)
const USDT_ABI = [
  'function decimals() view returns (uint8)',
  'function balanceOf(address account) view returns (uint256)',
  'function transfer(address to, uint256 amount) returns (bool)',
  'event Transfer(address indexed from, address indexed to, uint256 value)',
];

export class BlockchainService {
  private static instance: BlockchainService;

  private httpProvider!: ethers.JsonRpcProvider;
  private wsProvider?: ethers.WebSocketProvider;
  private usdtContract!: ethers.Contract;
  private usdtContractWs?: ethers.Contract;
  private payoutWallet?: ethers.Wallet;

  // Cached USDT decimals (always 18, but cached to avoid repeated RPC calls)
  private usdtDecimals?: number;

  private isMonitoring = false;
  private reconnectAttempts = 0;
  private readonly MAX_RECONNECT_ATTEMPTS = 10;
  private readonly RECONNECT_DELAY_MS = 5000;
  private readonly DEPOSIT_TIMEOUT_MS = 24 * 60 * 60 * 1000; // 24 hours
  private readonly WS_HEALTH_CHECK_INTERVAL_MS = 30000; // 30 seconds
  private readonly HISTORICAL_BLOCKS_LOOKBACK = 2000; // ~100 minutes on BSC (3s per block)

  // Health check interval
  private wsHealthCheckInterval?: NodeJS.Timeout;
  private cleanupInterval?: NodeJS.Timeout;
  private lastWsActivity = Date.now();
  private readonly CLEANUP_INTERVAL_MS = 60 * 60 * 1000; // 1 hour

  // Lazy-loaded to avoid circular dependency
  private depositService?: DepositService;

  private constructor() {
    this.initializeProviders();
  }

  /**
   * Get deposit service instance (lazy-loaded)
   */
  private async getDepositService(): Promise<DepositService> {
    if (!this.depositService) {
      const { default: depositService } = await import('./deposit.service');
      this.depositService = depositService;
    }
    return this.depositService;
  }

  /**
   * Get singleton instance
   */
  public static getInstance(): BlockchainService {
    if (!BlockchainService.instance) {
      BlockchainService.instance = new BlockchainService();
    }
    return BlockchainService.instance;
  }

  /**
   * Initialize HTTP and WebSocket providers
   */
  private initializeProviders(): void {
    try {
      // HTTP Provider (for queries and transactions)
      this.httpProvider = new ethers.JsonRpcProvider(
        config.blockchain.quicknodeHttpsUrl,
        {
          chainId: config.blockchain.chainId,
          name: config.blockchain.network,
        }
      );

      // USDT Contract (read-only via HTTP)
      this.usdtContract = new ethers.Contract(
        config.blockchain.usdtContractAddress,
        USDT_ABI,
        this.httpProvider
      );

      // Payout wallet (for sending referral rewards)
      if (config.blockchain.payoutWalletPrivateKey) {
        this.payoutWallet = new ethers.Wallet(
          config.blockchain.payoutWalletPrivateKey,
          this.httpProvider
        );
        logger.info(`✅ Payout wallet initialized: ${this.payoutWallet.address}`);
      } else {
        logger.warn('⚠️ Payout wallet private key not configured - payments disabled');
      }

      logger.info('✅ Blockchain HTTP provider initialized');
    } catch (error) {
      logger.error('❌ Failed to initialize blockchain providers:', error);
      throw error;
    }
  }

  /**
   * Get cached USDT decimals (fetches once on first call)
   */
  private async getUsdtDecimals(): Promise<number> {
    if (this.usdtDecimals === undefined) {
      this.usdtDecimals = await this.usdtContract.decimals();
      logger.info(`✅ USDT decimals cached: ${this.usdtDecimals}`);
    }
    return this.usdtDecimals;
  }

  /**
   * Initialize WebSocket provider for real-time monitoring
   */
  private async initializeWebSocket(): Promise<void> {
    try {
      if (this.wsProvider) {
        await this.wsProvider.destroy();
      }

      this.wsProvider = new ethers.WebSocketProvider(
        config.blockchain.quicknodeWssUrl,
        {
          chainId: config.blockchain.chainId,
          name: config.blockchain.network,
        }
      );

      // USDT Contract (with WebSocket provider for events)
      this.usdtContractWs = new ethers.Contract(
        config.blockchain.usdtContractAddress,
        USDT_ABI,
        this.wsProvider
      );

      // WebSocket error handling
      this.wsProvider.websocket.on('error', (error) => {
        logger.error('❌ WebSocket error:', error);
        this.handleWebSocketDisconnect();
      });

      this.wsProvider.websocket.on('close', () => {
        logger.warn('⚠️ WebSocket connection closed');
        this.handleWebSocketDisconnect();
      });

      logger.info('✅ Blockchain WebSocket provider initialized');
    } catch (error) {
      logger.error('❌ Failed to initialize WebSocket provider:', error);
      throw error;
    }
  }

  /**
   * Handle WebSocket disconnect and reconnect
   */
  private async handleWebSocketDisconnect(): Promise<void> {
    if (!this.isMonitoring) {
      return; // Don't reconnect if monitoring is stopped
    }

    this.reconnectAttempts++;

    if (this.reconnectAttempts > this.MAX_RECONNECT_ATTEMPTS) {
      logger.error('❌ Max reconnect attempts reached. Stopping monitoring.');
      this.stopMonitoring();
      return;
    }

    logger.info(
      `🔄 Reconnecting WebSocket (attempt ${this.reconnectAttempts}/${this.MAX_RECONNECT_ATTEMPTS})...`
    );

    setTimeout(async () => {
      try {
        await this.initializeWebSocket();
        await this.startMonitoring();
        this.reconnectAttempts = 0; // Reset on successful reconnect
      } catch (error) {
        logger.error('❌ Failed to reconnect WebSocket:', error);
        this.handleWebSocketDisconnect();
      }
    }, this.RECONNECT_DELAY_MS);
  }

  /**
   * Fetch and process historical Transfer events since last processed block
   * Called once on startup to catch any deposits made while bot was offline
   */
  private async fetchHistoricalEvents(): Promise<void> {
    try {
      const transactionRepo = AppDataSource.getRepository(Transaction);

      // Get last processed block number from database
      const lastTransaction = await transactionRepo.findOne({
        where: { type: TransactionType.DEPOSIT },
        order: { block_number: 'DESC' },
        select: ['block_number'],
      });

      const currentBlock = await this.httpProvider.getBlockNumber();

      // Start from last processed block, or lookback N blocks if first run
      const fromBlock = lastTransaction?.block_number
        ? Number(lastTransaction.block_number) + 1
        : currentBlock - this.HISTORICAL_BLOCKS_LOOKBACK;

      const toBlock = currentBlock;

      if (fromBlock >= toBlock) {
        logger.info('✅ No historical blocks to process (already up to date)');
        return;
      }

      logger.info(
        `🔍 Fetching historical Transfer events from block ${fromBlock} to ${toBlock} (${toBlock - fromBlock} blocks)...`
      );

      // Query historical Transfer events to system wallet
      const filter = this.usdtContract.filters.Transfer(
        null,
        config.blockchain.systemWalletAddress
      );

      const events = await this.usdtContract.queryFilter(filter, fromBlock, toBlock);

      if (events.length === 0) {
        logger.info('✅ No historical deposits found');
        return;
      }

      logger.info(`📥 Found ${events.length} historical Transfer events, processing...`);

      // Process events sequentially to maintain order
      let processed = 0;
      let skipped = 0;

      for (const event of events) {
        try {
          if (!event.args) continue;

          const [from, to, value] = event.args;

          // Check if already processed
          const existing = await transactionRepo.findOne({
            where: { tx_hash: event.transactionHash },
          });

          if (existing) {
            skipped++;
            continue;
          }

          await this.handleTransferEvent(from, to, value, event);
          processed++;
        } catch (error) {
          logger.error(`❌ Error processing historical event ${event.transactionHash}:`, error);
        }
      }

      logger.info(
        `✅ Historical events processed: ${processed} new, ${skipped} already processed, ${events.length} total`
      );
    } catch (error) {
      logger.error('❌ Error fetching historical events:', error);
      // Don't throw - allow monitoring to continue even if historical fetch fails
    }
  }

  /**
   * Start monitoring blockchain for deposits
   */
  public async startMonitoring(): Promise<void> {
    if (this.isMonitoring) {
      logger.warn('⚠️ Blockchain monitoring is already running');
      return;
    }

    try {
      await this.initializeWebSocket();

      if (!this.usdtContractWs) {
        throw new Error('WebSocket USDT contract not initialized');
      }

      // Listen for Transfer events to system wallet
      const filter = this.usdtContractWs.filters.Transfer(
        null,
        config.blockchain.systemWalletAddress
      );

      this.usdtContractWs.on(filter, async (from, to, value, event) => {
        try {
          this.lastWsActivity = Date.now(); // Update activity timestamp
          await this.handleTransferEvent(from, to, value, event);
        } catch (error) {
          logger.error('❌ Error handling Transfer event:', error);
        }
      });

      // Start WebSocket health check
      this.startWsHealthCheck();

      // Start orphaned deposit cleanup job
      this.startCleanupJob();

      // Fetch historical events to catch deposits made while bot was offline
      await this.fetchHistoricalEvents();

      this.isMonitoring = true;
      logger.info('✅ Blockchain monitoring started');
      logger.info(`📡 Listening for deposits to: ${config.blockchain.systemWalletAddress}`);
    } catch (error) {
      logger.error('❌ Failed to start blockchain monitoring:', error);
      throw error;
    }
  }

  /**
   * Stop monitoring blockchain
   */
  public async stopMonitoring(): Promise<void> {
    try {
      this.isMonitoring = false;

      // Clear WebSocket health check interval
      if (this.wsHealthCheckInterval) {
        clearInterval(this.wsHealthCheckInterval);
        this.wsHealthCheckInterval = undefined;
      }

      // Clear cleanup interval
      if (this.cleanupInterval) {
        clearInterval(this.cleanupInterval);
        this.cleanupInterval = undefined;
      }

      if (this.usdtContractWs) {
        this.usdtContractWs.removeAllListeners();
      }

      if (this.wsProvider) {
        await this.wsProvider.destroy();
        this.wsProvider = undefined;
      }

      logger.info('✅ Blockchain monitoring stopped');
    } catch (error) {
      logger.error('❌ Error stopping blockchain monitoring:', error);
    }
  }

  /**
   * Start WebSocket health check
   */
  private startWsHealthCheck(): void {
    this.wsHealthCheckInterval = setInterval(async () => {
      try {
        const timeSinceActivity = Date.now() - this.lastWsActivity;

        if (timeSinceActivity > this.WS_HEALTH_CHECK_INTERVAL_MS * 2) {
          logger.warn(
            `⚠️ WebSocket appears inactive (${Math.round(timeSinceActivity / 1000)}s since last activity), reconnecting...`
          );
          await this.handleWebSocketDisconnect();
        }
      } catch (error) {
        logger.error('❌ Error in WebSocket health check:', error);
      }
    }, this.WS_HEALTH_CHECK_INTERVAL_MS);

    logger.info(
      `🏥 WebSocket health check started (interval: ${this.WS_HEALTH_CHECK_INTERVAL_MS / 1000}s)`
    );
  }

  /**
   * Start orphaned deposit cleanup job
   */
  private startCleanupJob(): void {
    // Run cleanup immediately
    this.runCleanup().catch((error) => {
      logger.error('❌ Error in initial cleanup run:', error);
    });

    // Then run periodically
    this.cleanupInterval = setInterval(async () => {
      try {
        await this.runCleanup();
      } catch (error) {
        logger.error('❌ Error in scheduled cleanup:', error);
      }
    }, this.CLEANUP_INTERVAL_MS);

    logger.info(
      `🧹 Orphaned deposit cleanup job started (interval: ${this.CLEANUP_INTERVAL_MS / 1000 / 60} minutes)`
    );
  }

  /**
   * Run cleanup of orphaned deposits
   */
  private async runCleanup(): Promise<void> {
    if (!this.depositService) {
      const { default: depositService } = await import('./deposit.service');
      this.depositService = depositService;
    }

    logger.info('🧹 Running orphaned deposit cleanup...');
    const { cleaned, errors } = await this.depositService.cleanupOrphanedDeposits();

    if (cleaned > 0 || errors > 0) {
      logger.info(`🧹 Cleanup complete: ${cleaned} cleaned, ${errors} errors`);
    } else {
      logger.debug('🧹 Cleanup complete: No orphaned deposits found');
    }
  }

  /**
   * Handle Transfer event from blockchain
   */
  private async handleTransferEvent(
    from: string,
    to: string,
    value: bigint,
    event: any
  ): Promise<void> {
    const txHash = event.log.transactionHash;
    const blockNumber = event.log.blockNumber;

    logger.info(
      `📥 New Transfer event detected: ${txHash} (block ${blockNumber})`
    );

    try {
      // Convert USDT amount (6 decimals for USDT on BSC)
      const decimals = await this.getUsdtDecimals();
      const amount = parseFloat(ethers.formatUnits(value, decimals));

      logger.info(
        `💰 Transfer: ${amount} USDT from ${from} to ${to}`
      );

      // Check if transaction already exists
      const transactionRepo = AppDataSource.getRepository(Transaction);
      const existingTx = await transactionRepo.findOne({
        where: { tx_hash: txHash },
      });

      if (existingTx) {
        logger.info(`ℹ️ Transaction ${txHash} already processed`);
        return;
      }

      // Find user by wallet address
      const userRepo = AppDataSource.getRepository(User);
      const user = await userRepo.findOne({
        where: { wallet_address: from.toLowerCase() },
      });

      if (!user) {
        logger.warn(`⚠️ No user found with wallet address: ${from}`);
        // Still create transaction record for audit purposes
        await transactionRepo.save({
          tx_hash: txHash,
          type: TransactionType.DEPOSIT,
          amount: amount.toString(),
          from_address: from.toLowerCase(),
          to_address: to.toLowerCase(),
          block_number: blockNumber,
          status: TransactionStatus.PENDING,
        });
        return;
      }

      // Determine deposit level from amount
      const { DEPOSIT_LEVELS } = await import('../utils/constants');
      let matchedLevel: number | null = null;
      const tolerance = 0.5; // 0.5 USDT tolerance

      for (const [level, levelAmount] of Object.entries(DEPOSIT_LEVELS)) {
        if (Math.abs(amount - levelAmount) <= tolerance) {
          matchedLevel = parseInt(level);
          break;
        }
      }

      if (!matchedLevel) {
        logger.warn(
          `⚠️ Amount ${amount} USDT doesn't match any deposit level for user ${user.telegram_id}`
        );
        // Create transaction record for audit
        await transactionRepo.save({
          user_id: user.id,
          tx_hash: txHash,
          type: TransactionType.DEPOSIT,
          amount: amount.toString(),
          from_address: from.toLowerCase(),
          to_address: to.toLowerCase(),
          block_number: blockNumber,
          status: TransactionStatus.FAILED,
        });
        return;
      }

      // Use database transaction with pessimistic lock to prevent race conditions
      // This ensures only one concurrent transaction can claim a pending deposit
      const depositRepo = AppDataSource.getRepository(Deposit);

      await AppDataSource.transaction(async (transactionalEntityManager) => {
        // Find and lock matching pending deposit (SELECT FOR UPDATE)
        // This prevents race conditions when multiple transactions arrive simultaneously
        const pendingDeposit = await transactionalEntityManager
          .createQueryBuilder(Deposit, 'deposit')
          .where('deposit.user_id = :userId', { userId: user.id })
          .andWhere('deposit.level = :level', { level: matchedLevel })
          .andWhere('deposit.status = :status', { status: TransactionStatus.PENDING })
          .andWhere('(deposit.tx_hash IS NULL OR deposit.tx_hash = \'\')')
          .orderBy('deposit.created_at', 'DESC')
          .setLock('pessimistic_write') // Row-level lock (SELECT FOR UPDATE)
          .getOne();

        if (!pendingDeposit) {
          logger.warn(
            `⚠️ No pending deposit found for user ${user.telegram_id} level ${matchedLevel}`
          );
          // Create transaction record for manual review
          await transactionalEntityManager.save(Transaction, {
            user_id: user.id,
            tx_hash: txHash,
            type: TransactionType.DEPOSIT,
            amount: amount.toString(),
            from_address: from.toLowerCase(),
            to_address: to.toLowerCase(),
            block_number: blockNumber,
            status: TransactionStatus.PENDING,
          });
          logger.info(
            `ℹ️ Transaction recorded for manual review: ${txHash}`
          );
          return;
        }

        // Update deposit with transaction hash (will be confirmed after N blocks)
        pendingDeposit.tx_hash = txHash;
        pendingDeposit.block_number = blockNumber;
        await transactionalEntityManager.save(Deposit, pendingDeposit);

        // Create transaction record
        await transactionalEntityManager.save(Transaction, {
          user_id: user.id,
          tx_hash: txHash,
          type: TransactionType.DEPOSIT,
          amount: amount.toString(),
          from_address: from.toLowerCase(),
          to_address: to.toLowerCase(),
          block_number: blockNumber,
          status: TransactionStatus.PENDING,
        });

        logger.info(
          `✅ Deposit tracked: ${amount} USDT for user ${user.telegram_id} (tx: ${txHash})`
        );
      });

      // Notify user about detected deposit (pending confirmation)
      await notificationService.notifyDepositPending(
        user.telegram_id,
        amount,
        matchedLevel!,
        txHash
      ).catch((err) => {
        logger.error('Failed to send deposit pending notification', { error: err });
      });
    } catch (error) {
      logger.error('❌ Error processing Transfer event:', error);
    }
  }

  /**
   * Check and confirm pending deposits (called by background job)
   */
  public async checkPendingDeposits(): Promise<void> {
    try {
      const depositRepo = AppDataSource.getRepository(Deposit);
      const transactionRepo = AppDataSource.getRepository(Transaction);

      // Get pending deposits in batches (pagination to prevent memory issues)
      // Process oldest first to ensure timely confirmations
      const BATCH_SIZE = 100;
      const pendingDeposits = await depositRepo.find({
        where: { status: TransactionStatus.PENDING },
        relations: ['user'],
        order: { created_at: 'ASC' },
        take: BATCH_SIZE,
      });

      if (pendingDeposits.length === 0) {
        return;
      }

      logger.info(`🔍 Checking ${pendingDeposits.length} pending deposits (batch of ${BATCH_SIZE})...`);

      // Get current block number
      const currentBlock = await this.httpProvider.getBlockNumber();

      for (const deposit of pendingDeposits) {
        try {
          // Check for deposit timeout (24 hours without confirmation)
          const depositAge = Date.now() - deposit.created_at.getTime();
          if (depositAge > this.DEPOSIT_TIMEOUT_MS) {
            deposit.status = TransactionStatus.FAILED;
            await depositRepo.save(deposit);

            // Update transaction status if exists
            if (deposit.tx_hash) {
              await transactionRepo.update(
                { tx_hash: deposit.tx_hash },
                { status: TransactionStatus.FAILED }
              );
            }

            logger.warn(
              `⏱️ Deposit ${deposit.id} timed out after ${Math.round(depositAge / 1000 / 60 / 60)}h (user: ${deposit.user?.telegram_id})`
            );

            // Notify user about timeout
            if (deposit.user) {
              await notificationService.notifyDepositTimeout(
                deposit.user.telegram_id,
                parseFloat(deposit.amount),
                deposit.level
              );
            }

            continue;
          }

          if (!deposit.block_number) {
            continue; // Skip if no block number yet
          }

          const confirmations = currentBlock - deposit.block_number;

          // Check if enough confirmations
          if (confirmations >= config.blockchain.confirmationBlocks) {
            // Verify transaction still exists and is successful
            const receipt = await this.httpProvider.getTransactionReceipt(
              deposit.tx_hash
            );

            if (!receipt) {
              logger.warn(
                `⚠️ Transaction receipt not found: ${deposit.tx_hash}`
              );
              continue;
            }

            if (receipt.status !== 1) {
              // Transaction failed
              deposit.status = TransactionStatus.FAILED;
              await depositRepo.save(deposit);

              await transactionRepo.update(
                { tx_hash: deposit.tx_hash },
                { status: TransactionStatus.FAILED }
              );

              logger.warn(
                `❌ Deposit transaction failed: ${deposit.tx_hash}`
              );
              continue;
            }

            // Confirm deposit using DepositService (creates referral earnings)
            const depositService = await this.getDepositService();
            await depositService.confirmDeposit(deposit.tx_hash, deposit.block_number);

            // Update transaction status
            await transactionRepo.update(
              { tx_hash: deposit.tx_hash },
              { status: TransactionStatus.CONFIRMED }
            );

            logger.info(
              `✅ Deposit confirmed: ${deposit.amount} USDT for user ${deposit.user.telegram_id} (${confirmations} confirmations)`
            );
          }
        } catch (error) {
          logger.error(
            `❌ Error checking deposit ${deposit.id}:`,
            error
          );
        }
      }
    } catch (error) {
      logger.error('❌ Error checking pending deposits:', error);
    }
  }

  /**
   * Send USDT payment (for referral rewards)
   */
  public async sendPayment(
    toAddress: string,
    amount: number
  ): Promise<{ success: boolean; txHash?: string; error?: string }> {
    try {
      if (!this.payoutWallet) {
        return {
          success: false,
          error: 'Payout wallet not configured',
        };
      }

      // Get USDT decimals (cached)
      const decimals = await this.getUsdtDecimals();
      const amountWei = ethers.parseUnits(amount.toString(), decimals);

      // Create contract instance with signer
      const usdtWithSigner = new ethers.Contract(
        config.blockchain.usdtContractAddress,
        USDT_ABI,
        this.payoutWallet
      );

      // Check balance
      const balance = await this.usdtContract.balanceOf(
        this.payoutWallet.address
      );

      if (balance < amountWei) {
        logger.error(
          `❌ Insufficient USDT balance: ${ethers.formatUnits(balance, decimals)} (need ${amount})`
        );
        return {
          success: false,
          error: 'Insufficient balance',
        };
      }

      // Estimate gas
      const gasLimit = await usdtWithSigner.transfer.estimateGas(
        toAddress,
        amountWei
      );

      // Send transaction
      const tx = await usdtWithSigner.transfer(toAddress, amountWei, {
        gasLimit: gasLimit * BigInt(120) / BigInt(100), // 20% buffer
      });

      logger.info(
        `📤 Payment sent: ${amount} USDT to ${toAddress} (tx: ${tx.hash})`
      );

      // Wait for confirmation
      const receipt = await tx.wait();

      if (receipt.status !== 1) {
        logger.error(`❌ Payment transaction failed: ${tx.hash}`);
        return {
          success: false,
          txHash: tx.hash,
          error: 'Transaction failed',
        };
      }

      logger.info(`✅ Payment confirmed: ${tx.hash}`);

      return {
        success: true,
        txHash: tx.hash,
      };
    } catch (error: any) {
      logger.error('❌ Error sending payment:', error);
      return {
        success: false,
        error: error.message || 'Unknown error',
      };
    }
  }

  /**
   * Get USDT balance of an address
   */
  public async getBalance(address: string): Promise<number> {
    try {
      const decimals = await this.getUsdtDecimals();
      const balance = await this.usdtContract.balanceOf(address);
      return parseFloat(ethers.formatUnits(balance, decimals));
    } catch (error) {
      logger.error(`❌ Error getting balance for ${address}:`, error);
      return 0;
    }
  }

  /**
   * Get current block number
   */
  public async getCurrentBlock(): Promise<number> {
    try {
      return await this.httpProvider.getBlockNumber();
    } catch (error) {
      logger.error('❌ Error getting current block:', error);
      return 0;
    }
  }

  /**
   * Verify transaction exists and is confirmed
   */
  public async verifyTransaction(txHash: string): Promise<{
    exists: boolean;
    confirmed: boolean;
    blockNumber?: number;
  }> {
    try {
      const receipt = await this.httpProvider.getTransactionReceipt(txHash);

      if (!receipt) {
        return { exists: false, confirmed: false };
      }

      const currentBlock = await this.httpProvider.getBlockNumber();
      const confirmations = currentBlock - receipt.blockNumber;

      return {
        exists: true,
        confirmed:
          receipt.status === 1 &&
          confirmations >= config.blockchain.confirmationBlocks,
        blockNumber: receipt.blockNumber,
      };
    } catch (error) {
      logger.error(`❌ Error verifying transaction ${txHash}:`, error);
      return { exists: false, confirmed: false };
    }
  }

  /**
   * Get system wallet balance
   */
  public async getSystemWalletBalance(): Promise<number> {
    return this.getBalance(config.blockchain.systemWalletAddress);
  }

  /**
   * Get payout wallet balance
   */
  public async getPayoutWalletBalance(): Promise<number> {
    if (!this.payoutWallet) {
      return 0;
    }
    return this.getBalance(this.payoutWallet.address);
  }
}

// Export singleton instance
export const blockchainService = BlockchainService.getInstance();
