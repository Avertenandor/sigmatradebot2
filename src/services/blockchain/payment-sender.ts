/**
 * Payment Sender
 * Handles sending USDT payments (for withdrawals and referral rewards)
 */

import { ethers } from 'ethers';
import { config } from '../../config';
import { logger } from '../../utils/logger.util';
import { notificationService } from '../notification.service';
import { ProviderManager } from './provider.manager';
import { USDT_ABI, getUsdtDecimals, getBalance } from './utils';

export class PaymentSender {
  private readonly LOW_BALANCE_THRESHOLD = 100; // Alert when payout wallet below 100 USDT

  constructor(private providerManager: ProviderManager) {}

  /**
   * Send USDT payment (for referral rewards)
   */
  public async sendPayment(
    toAddress: string,
    amount: number
  ): Promise<{ success: boolean; txHash?: string; error?: string }> {
    try {
      const payoutWallet = this.providerManager.getPayoutWallet();

      if (!payoutWallet) {
        return {
          success: false,
          error: 'Payout wallet not configured',
        };
      }

      const usdtContract = this.providerManager.getUsdtContract();

      // Get USDT decimals (cached)
      const decimals = await getUsdtDecimals(usdtContract);
      const amountWei = ethers.parseUnits(amount.toString(), decimals);

      // Create contract instance with signer
      const usdtWithSigner = new ethers.Contract(
        config.blockchain.usdtContractAddress,
        USDT_ABI,
        payoutWallet
      );

      // Check balance
      const balance = await usdtContract.balanceOf(payoutWallet.address);
      const balanceUsdt = parseFloat(ethers.formatUnits(balance, decimals));

      // Alert admins if balance is low (even if this payment can still go through)
      if (balanceUsdt < this.LOW_BALANCE_THRESHOLD && balanceUsdt >= amount) {
        await notificationService.alertLowPayoutBalance(
          balanceUsdt,
          this.LOW_BALANCE_THRESHOLD
        ).catch((err) => {
          logger.error('Failed to send low balance alert', { error: err });
        });
      }

      if (balance < amountWei) {
        logger.error(
          `❌ Insufficient USDT balance: ${balanceUsdt} (need ${amount})`
        );

        // Alert admins about failed payment
        await notificationService.alertLowPayoutBalance(
          balanceUsdt,
          amount
        ).catch((err) => {
          logger.error('Failed to send insufficient balance alert', { error: err });
        });

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
   * Get system wallet balance
   */
  public async getSystemWalletBalance(): Promise<number> {
    return getBalance(
      config.blockchain.systemWalletAddress,
      this.providerManager.getUsdtContract()
    );
  }

  /**
   * Get payout wallet balance
   */
  public async getPayoutWalletBalance(): Promise<number> {
    const payoutWallet = this.providerManager.getPayoutWallet();
    if (!payoutWallet) {
      return 0;
    }
    return getBalance(payoutWallet.address, this.providerManager.getUsdtContract());
  }

  /**
   * Get payout wallet BNB (gas) balance
   */
  public async getPayoutWalletBnbBalance(): Promise<number> {
    const payoutWallet = this.providerManager.getPayoutWallet();
    if (!payoutWallet) {
      return 0;
    }
    const balance = await this.providerManager.getHttpProvider().getBalance(payoutWallet.address);
    // Convert from wei to BNB
    return parseFloat(ethers.formatEther(balance));
  }
}
