/**
 * Event Monitor
 * Monitors blockchain events in real-time and processes historical events
 */

import { config } from '../../config';
import { logger } from '../../utils/logger.util';
import { AppDataSource } from '../../database/data-source';
import { Transaction } from '../../database/entities/Transaction.entity';
import { TransactionType } from '../../utils/constants';
import { notificationService } from '../notification.service';
import { ProviderManager } from './provider.manager';
import { DepositProcessor } from './deposit-processor';
import Redis from 'ioredis';

// FIX #16: Redis client for tracking historical fetch state
const redis = new Redis({
  host: config.redis.host,
  port: config.redis.port,
  password: config.redis.password,
  db: config.redis.db,
});

export class EventMonitor {
  private isMonitoring = false;
  private reconnectAttempts = 0;
  private readonly MAX_RECONNECT_ATTEMPTS = 10;
  private readonly INITIAL_RECONNECT_DELAY_MS = 1000; // 1 second initial delay
  private readonly MAX_RECONNECT_DELAY_MS = 30000; // 30 seconds max delay
  private readonly HISTORICAL_BLOCKS_LOOKBACK = 2000; // ~100 minutes on BSC (3s per block)

  // FIX #16: Track if historical events were already fetched in this session
  private hasEverFetched = false;

  // FIX #16: Cooldown to prevent spam fetching on rapid reconnects
  private readonly FETCH_COOLDOWN_MS = 5 * 60 * 1000; // 5 minutes
  private readonly LAST_FETCH_KEY = 'blockchain:last_historical_fetch';

  constructor(
    private providerManager: ProviderManager,
    private depositProcessor: DepositProcessor
  ) {}

  /**
   * Start monitoring blockchain for deposits
   */
  public async startMonitoring(): Promise<void> {
    if (this.isMonitoring) {
      logger.warn('⚠️ Blockchain monitoring is already running');
      return;
    }

    try {
      await this.providerManager.initializeWebSocket();

      const usdtContractWs = this.providerManager.getUsdtContractWs();

      if (!usdtContractWs) {
        throw new Error('WebSocket USDT contract not initialized');
      }

      // Set WebSocket error handlers
      this.providerManager.setWebSocketErrorHandlers(
        () => this.handleWebSocketDisconnect(),
        () => this.handleWebSocketDisconnect()
      );

      // Listen for Transfer events to system wallet
      const filter = usdtContractWs.filters.Transfer(
        null,
        config.blockchain.systemWalletAddress
      );

      usdtContractWs.on(filter, async (from, to, value, event) => {
        try {
          this.providerManager.updateWsActivity(); // Update activity timestamp
          await this.depositProcessor.handleTransferEvent(from, to, value, event);
        } catch (error) {
          logger.error('❌ Error handling Transfer event:', error);
        }
      });

      // Start WebSocket health check
      this.providerManager.startWsHealthCheck(() => this.handleWebSocketDisconnect());

      // Start orphaned deposit cleanup job
      this.depositProcessor.startCleanupJob();

      // FIX #16: Only fetch historical on FIRST start (not reconnects)
      if (!this.hasEverFetched) {
        await this.fetchHistoricalEvents();
        this.hasEverFetched = true;
      } else {
        logger.info('⏭️ Skipping historical fetch (reconnect detected)');
      }

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

      // Stop WebSocket health check
      this.providerManager.stopWsHealthCheck();

      // Stop cleanup job
      this.depositProcessor.stopCleanupJob();

      // Destroy WebSocket provider
      await this.providerManager.destroyWebSocket();

      logger.info('✅ Blockchain monitoring stopped');
    } catch (error) {
      logger.error('❌ Error stopping blockchain monitoring:', error);
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

    // Alert admins on critical reconnection issues
    await notificationService.alertWebSocketDisconnect(
      this.reconnectAttempts,
      this.MAX_RECONNECT_ATTEMPTS
    ).catch((err) => {
      logger.error('Failed to send WebSocket alert', { error: err });
    });

    if (this.reconnectAttempts > this.MAX_RECONNECT_ATTEMPTS) {
      logger.error('❌ Max reconnect attempts reached. Stopping monitoring.');
      this.stopMonitoring();
      return;
    }

    // Calculate exponential backoff delay: min(initialDelay * 2^attempts, maxDelay)
    const exponentialDelay = Math.min(
      this.INITIAL_RECONNECT_DELAY_MS * Math.pow(2, this.reconnectAttempts - 1),
      this.MAX_RECONNECT_DELAY_MS
    );

    logger.info(
      `🔄 Reconnecting WebSocket (attempt ${this.reconnectAttempts}/${this.MAX_RECONNECT_ATTEMPTS}) in ${exponentialDelay}ms...`
    );

    setTimeout(async () => {
      try {
        await this.providerManager.initializeWebSocket();
        await this.startMonitoring();
        this.reconnectAttempts = 0; // Reset on successful reconnect
        logger.info('✅ WebSocket reconnected successfully');
      } catch (error) {
        logger.error('❌ Failed to reconnect WebSocket:', error);
        this.handleWebSocketDisconnect();
      }
    }, exponentialDelay);
  }

  /**
   * Fetch and process historical Transfer events since last processed block
   * Called once on startup to catch any deposits made while bot was offline
   * FIX #16: Enhanced with Redis tracking and cooldown to prevent spam
   */
  private async fetchHistoricalEvents(): Promise<void> {
    try {
      // FIX #16: Check cooldown - prevent spam fetching on rapid reconnects
      const lastFetchTime = await redis.get(`${this.LAST_FETCH_KEY}:time`);
      if (lastFetchTime) {
        const timeSinceLastFetch = Date.now() - parseInt(lastFetchTime);
        if (timeSinceLastFetch < this.FETCH_COOLDOWN_MS) {
          const remainingMs = this.FETCH_COOLDOWN_MS - timeSinceLastFetch;
          logger.info('⏸️ Historical fetch on cooldown', {
            remainingSeconds: Math.round(remainingMs / 1000),
          });
          return;
        }
      }

      const transactionRepo = AppDataSource.getRepository(Transaction);
      const httpProvider = this.providerManager.getHttpProvider();
      const usdtContract = this.providerManager.getUsdtContract();
      const currentBlock = await httpProvider.getBlockNumber();

      // FIX #16: Get last fetched block from Redis (persists across restarts)
      // Fallback to database if Redis doesn't have it
      const lastFetchedBlockRedis = await redis.get(`${this.LAST_FETCH_KEY}:block`);
      let fromBlock: number;

      if (lastFetchedBlockRedis) {
        // Use Redis tracked block (most reliable)
        fromBlock = parseInt(lastFetchedBlockRedis) + 1;
        logger.debug('Using last fetched block from Redis', { fromBlock: fromBlock - 1 });
      } else {
        // Fallback to database
        const lastTransaction = await transactionRepo.findOne({
          where: { type: TransactionType.DEPOSIT },
          order: { block_number: 'DESC' },
          select: ['block_number'],
        });

        fromBlock = lastTransaction?.block_number
          ? Number(lastTransaction.block_number) + 1
          : currentBlock - this.HISTORICAL_BLOCKS_LOOKBACK;

        logger.debug('Using last block from database fallback', {
          fromBlock,
          hasTransaction: !!lastTransaction,
        });
      }

      const toBlock = currentBlock;

      if (fromBlock >= toBlock) {
        logger.info('✅ No historical blocks to process (already up to date)', {
          currentBlock,
          lastFetched: fromBlock - 1,
        });
        return;
      }

      logger.info(
        `🔍 Fetching historical Transfer events from block ${fromBlock} to ${toBlock} (${toBlock - fromBlock} blocks)...`
      );

      // Query historical Transfer events to system wallet
      const filter = usdtContract.filters.Transfer(
        null,
        config.blockchain.systemWalletAddress
      );

      const events = await usdtContract.queryFilter(filter, fromBlock, toBlock);

      if (events.length === 0) {
        logger.info('✅ No historical deposits found');

        // FIX #16: Still update tracking even if no events
        await redis.set(`${this.LAST_FETCH_KEY}:block`, String(toBlock));
        await redis.set(`${this.LAST_FETCH_KEY}:time`, String(Date.now()));

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

          await this.depositProcessor.handleTransferEvent(from, to, value, event);
          processed++;
        } catch (error) {
          logger.error(`❌ Error processing historical event ${event.transactionHash}:`, error);
        }
      }

      // FIX #16: Update last fetched block and time in Redis
      await redis.set(`${this.LAST_FETCH_KEY}:block`, String(toBlock));
      await redis.set(`${this.LAST_FETCH_KEY}:time`, String(Date.now()));

      logger.info(
        `✅ Historical events processed: ${processed} new, ${skipped} already processed, ${events.length} total`,
        {
          fromBlock,
          toBlock,
          blocksFetched: toBlock - fromBlock,
        }
      );
    } catch (error) {
      logger.error('❌ Error fetching historical events:', error);
      // Don't throw - allow monitoring to continue even if historical fetch fails
    }
  }

  /**
   * Get monitoring status
   */
  public isActive(): boolean {
    return this.isMonitoring;
  }
}
