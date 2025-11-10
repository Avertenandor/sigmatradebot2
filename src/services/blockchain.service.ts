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

  private isMonitoring = false;
  private reconnectAttempts = 0;
  private readonly MAX_RECONNECT_ATTEMPTS = 10;
  private readonly RECONNECT_DELAY_MS = 5000;

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
          await this.handleTransferEvent(from, to, value, event);
        } catch (error) {
          logger.error('❌ Error handling Transfer event:', error);
        }
      });

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
      const decimals = await this.usdtContract.decimals();
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

      // Find matching pending deposit
      const depositRepo = AppDataSource.getRepository(Deposit);
      const pendingDeposit = await depositRepo.findOne({
        where: {
          user_id: user.id,
          status: TransactionStatus.PENDING,
        },
        order: { created_at: 'DESC' },
      });

      if (!pendingDeposit) {
        logger.warn(
          `⚠️ No pending deposit found for user ${user.telegram_id}`
        );
        return;
      }

      // Verify amount matches expected deposit level
      const expectedAmount = parseFloat(pendingDeposit.amount);
      const tolerance = 0.01; // 1% tolerance for gas variations

      if (Math.abs(amount - expectedAmount) / expectedAmount > tolerance) {
        logger.warn(
          `⚠️ Amount mismatch: expected ${expectedAmount} USDT, got ${amount} USDT`
        );
        // Still create transaction but mark as failed
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

      // Update deposit with transaction hash (will be confirmed after N blocks)
      pendingDeposit.tx_hash = txHash;
      pendingDeposit.block_number = blockNumber;
      await depositRepo.save(pendingDeposit);

      // Create transaction record
      await transactionRepo.save({
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

      // Get all pending deposits with transaction hashes
      const pendingDeposits = await depositRepo.find({
        where: { status: TransactionStatus.PENDING },
        relations: ['user'],
      });

      if (pendingDeposits.length === 0) {
        return;
      }

      logger.info(`🔍 Checking ${pendingDeposits.length} pending deposits...`);

      // Get current block number
      const currentBlock = await this.httpProvider.getBlockNumber();

      for (const deposit of pendingDeposits) {
        try {
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

      // Get USDT decimals
      const decimals = await this.usdtContract.decimals();
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
      const decimals = await this.usdtContract.decimals();
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
