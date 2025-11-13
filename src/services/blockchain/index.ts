/**
 * Blockchain Service
 * Main orchestrator for blockchain operations
 * Handles BSC blockchain interactions via QuickNode
 */

import { ProviderManager } from './provider.manager';
import { EventMonitor } from './event-monitor';
import { DepositProcessor } from './deposit-processor';
import { PaymentSender } from './payment-sender';
import { getBalance, verifyTransaction } from './utils';

export class BlockchainService {
  private static instance: BlockchainService;

  private providerManager: ProviderManager;
  private eventMonitor: EventMonitor;
  private depositProcessor: DepositProcessor;
  private paymentSender: PaymentSender;

  private constructor() {
    // Initialize all modules
    this.providerManager = new ProviderManager();
    this.depositProcessor = new DepositProcessor(this.providerManager);
    this.eventMonitor = new EventMonitor(this.providerManager, this.depositProcessor);
    this.paymentSender = new PaymentSender(this.providerManager);
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
   * Start monitoring blockchain for deposits
   */
  public async startMonitoring(): Promise<void> {
    await this.eventMonitor.startMonitoring();
  }

  /**
   * Stop monitoring blockchain
   */
  public async stopMonitoring(): Promise<void> {
    await this.eventMonitor.stopMonitoring();
  }

  /**
   * Check and confirm pending deposits (called by background job)
   */
  public async checkPendingDeposits(): Promise<void> {
    await this.depositProcessor.checkPendingDeposits();
  }

  /**
   * Send USDT payment (for referral rewards and withdrawals)
   */
  public async sendPayment(
    toAddress: string,
    amount: number
  ): Promise<{ success: boolean; txHash?: string; error?: string }> {
    return this.paymentSender.sendPayment(toAddress, amount);
  }

  /**
   * Get USDT balance of an address
   */
  public async getBalance(address: string): Promise<number> {
    return getBalance(address, this.providerManager.getUsdtContract());
  }

  /**
   * Get current block number
   */
  public async getCurrentBlock(): Promise<number> {
    try {
      return await this.providerManager.getHttpProvider().getBlockNumber();
    } catch (error) {
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
    return verifyTransaction(txHash, this.providerManager.getHttpProvider());
  }

  /**
   * Get system wallet balance
   */
  public async getSystemWalletBalance(): Promise<number> {
    return this.paymentSender.getSystemWalletBalance();
  }

  /**
   * Get payout wallet balance
   */
  public async getPayoutWalletBalance(): Promise<number> {
    return this.paymentSender.getPayoutWalletBalance();
  }

  /**
   * Reload payout wallet with new private key from Secret Manager
   * Called when admin applies wallet change request
   * @param secretRef - Reference to secret in Secret Manager
   */
  public async reloadPayoutWallet(secretRef: string): Promise<void> {
    return this.providerManager.reloadPayoutWallet(secretRef);
  }

  /**
   * Reload system wallet address for deposit monitoring
   * Called when admin applies system wallet change request
   * @param newAddress - New system wallet address (checksummed)
   */
  public async reloadSystemWalletAddress(newAddress: string): Promise<void> {
    return this.providerManager.reloadSystemWalletAddress(newAddress);
  }
}

// Export singleton instance
export const blockchainService = BlockchainService.getInstance();
