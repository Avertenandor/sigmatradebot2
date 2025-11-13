/**
 * Provider Manager
 * Manages HTTP and WebSocket providers for blockchain communication
 */

import { ethers } from 'ethers';
import { config } from '../../config';
import { logger } from '../../utils/logger.util';
import { USDT_ABI } from './utils';

export class ProviderManager {
  private httpProvider!: ethers.JsonRpcProvider;
  private wsProvider?: ethers.WebSocketProvider;
  private usdtContract!: ethers.Contract;
  private usdtContractWs?: ethers.Contract;
  private payoutWallet?: ethers.Wallet;

  private wsHealthCheckInterval?: NodeJS.Timeout;
  private lastWsActivity = Date.now();
  private readonly WS_HEALTH_CHECK_INTERVAL_MS = 30000; // 30 seconds

  constructor() {
    this.initializeHttpProvider();
  }

  /**
   * Initialize HTTP Provider
   */
  private initializeHttpProvider(): void {
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
  public async initializeWebSocket(): Promise<void> {
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

      logger.info('✅ Blockchain WebSocket provider initialized');
    } catch (error) {
      logger.error('❌ Failed to initialize WebSocket provider:', error);
      throw error;
    }
  }

  /**
   * Set WebSocket error handlers
   */
  public setWebSocketErrorHandlers(
    onError: (error: Error) => void,
    onClose: () => void
  ): void {
    if (!this.wsProvider) {
      throw new Error('WebSocket provider not initialized');
    }

    this.wsProvider.websocket.on('error', (error) => {
      logger.error('❌ WebSocket error:', error);
      onError(error);
    });

    this.wsProvider.websocket.on('close', () => {
      logger.warn('⚠️ WebSocket connection closed');
      onClose();
    });
  }

  /**
   * Start WebSocket health check
   */
  public startWsHealthCheck(onInactivity: () => void): void {
    this.wsHealthCheckInterval = setInterval(async () => {
      try {
        const timeSinceActivity = Date.now() - this.lastWsActivity;

        if (timeSinceActivity > this.WS_HEALTH_CHECK_INTERVAL_MS * 2) {
          logger.warn(
            `⚠️ WebSocket appears inactive (${Math.round(timeSinceActivity / 1000)}s since last activity), reconnecting...`
          );
          onInactivity();
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
   * Stop WebSocket health check
   */
  public stopWsHealthCheck(): void {
    if (this.wsHealthCheckInterval) {
      clearInterval(this.wsHealthCheckInterval);
      this.wsHealthCheckInterval = undefined;
    }
  }

  /**
   * Update WebSocket activity timestamp
   */
  public updateWsActivity(): void {
    this.lastWsActivity = Date.now();
  }

  /**
   * Destroy WebSocket provider
   */
  public async destroyWebSocket(): Promise<void> {
    if (this.usdtContractWs) {
      this.usdtContractWs.removeAllListeners();
      this.usdtContractWs = undefined;
    }

    if (this.wsProvider) {
      await this.wsProvider.destroy();
      this.wsProvider = undefined;
    }
  }

  /**
   * Get HTTP Provider
   */
  public getHttpProvider(): ethers.JsonRpcProvider {
    return this.httpProvider;
  }

  /**
   * Get WebSocket Provider
   */
  public getWsProvider(): ethers.WebSocketProvider | undefined {
    return this.wsProvider;
  }

  /**
   * Get USDT Contract (HTTP)
   */
  public getUsdtContract(): ethers.Contract {
    return this.usdtContract;
  }

  /**
   * Get USDT Contract (WebSocket)
   */
  public getUsdtContractWs(): ethers.Contract | undefined {
    return this.usdtContractWs;
  }

  /**
   * Get Payout Wallet
   */
  public getPayoutWallet(): ethers.Wallet | undefined {
    return this.payoutWallet;
  }

  /**
   * Reload payout wallet with new private key from Secret Manager
   * Called when admin applies wallet change request
   * @param secretRef - Reference to secret in Secret Manager
   */
  public async reloadPayoutWallet(secretRef: string): Promise<void> {
    try {
      logger.info('Reloading payout wallet from Secret Manager', { secretRef });

      // Import secret store service
      const { default: secretStoreService } = await import('../secret-store.service');

      // Access secret from Secret Manager
      const privateKey = await secretStoreService.accessSecret(secretRef);

      // Create new wallet with new private key
      const newWallet = new ethers.Wallet(privateKey, this.httpProvider);

      // Update payout wallet
      this.payoutWallet = newWallet;

      logger.info('✅ Payout wallet reloaded successfully', {
        address: newWallet.address,
        secretRef,
      });
    } catch (error) {
      logger.error('❌ Failed to reload payout wallet', { error, secretRef });
      throw new Error(`Failed to reload payout wallet: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Reload system wallet address for deposit monitoring
   * Called when admin applies system wallet change request
   * Note: This is a placeholder - actual implementation requires
   * restarting the event monitor with new address filter
   * @param newAddress - New system wallet address (checksummed)
   */
  public async reloadSystemWalletAddress(newAddress: string): Promise<void> {
    try {
      logger.info('System wallet address changed', { newAddress });

      // TODO: Implement event monitor restart with new address
      // This requires integration with EventMonitor service
      // For now, we just log the change - manual restart may be required

      logger.warn(
        '⚠️ System wallet address changed. Event monitor restart may be required.',
        { newAddress }
      );

      // Note: In production, this should:
      // 1. Stop current event monitor
      // 2. Update filter to listen for Transfer events to new address
      // 3. Restart event monitor
      // 4. Optionally: scan recent blocks for missed transactions
    } catch (error) {
      logger.error('❌ Failed to update system wallet address', { error, newAddress });
      throw new Error(`Failed to update system wallet address: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }
}
