/**
 * Deposit Processor
 * Handles deposit confirmation and processing
 */

import { ethers } from 'ethers';
import { config } from '../../config';
import { logger } from '../../utils/logger.util';
import { AppDataSource } from '../../database/data-source';
import { Transaction } from '../../database/entities/Transaction.entity';
import { Deposit } from '../../database/entities/Deposit.entity';
import { User } from '../../database/entities/User.entity';
import { TransactionStatus, TransactionType, DEPOSIT_LEVELS } from '../../utils/constants';
import { notificationService } from '../notification.service';
import { ProviderManager } from './provider.manager';
import { getUsdtDecimals } from './utils';
import type { DepositService } from '../deposit.service';
import { logFinancialOperation } from '../../utils/audit-logger.util';
import { withTransaction, TRANSACTION_PRESETS } from '../../database/transaction.util';
import { lockForDepositProcessing } from '../../database/locking.util';

export class DepositProcessor {
  private readonly DEPOSIT_TIMEOUT_MS = 24 * 60 * 60 * 1000; // 24 hours
  private readonly CLEANUP_INTERVAL_MS = 60 * 60 * 1000; // 1 hour

  /**
   * Deposit amount tolerance in USDT
   *
   * CRITICAL: This tolerance accounts for blockchain gas fees and minor variations.
   * Reduced from 0.5 USDT to 0.01 USDT (1 cent) to prevent abuse.
   *
   * Previous value (0.5) allowed users to underpay by up to 0.49 USDT per deposit,
   * resulting in significant financial losses for the platform.
   *
   * Current value (0.01) provides minimal tolerance for legitimate gas fee variations
   * while preventing abuse.
   */
  private readonly DEPOSIT_AMOUNT_TOLERANCE = 0.01; // 1 cent tolerance

  /**
   * Threshold for admin alerts (in USDT)
   * Deposits within tolerance but above this threshold trigger admin notification
   */
  private readonly TOLERANCE_ALERT_THRESHOLD = 0.005; // 0.5 cent

  private cleanupInterval?: NodeJS.Timeout;

  // Lazy-loaded to avoid circular dependency
  private depositService?: DepositService;

  constructor(private providerManager: ProviderManager) {}

  /**
   * Get deposit service instance (lazy-loaded)
   */
  private async getDepositService(): Promise<DepositService> {
    if (!this.depositService) {
      const { default: depositService } = await import('../deposit.service');
      this.depositService = depositService;
    }
    return this.depositService;
  }

  /**
   * Handle Transfer event from blockchain
   */
  public async handleTransferEvent(
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
      const usdtContract = this.providerManager.getUsdtContract();

      // Convert USDT amount (6 decimals for USDT on BSC)
      const decimals = await getUsdtDecimals(usdtContract);
      const amount = parseFloat(ethers.formatUnits(value, decimals));

      logger.info(
        `💰 Transfer: ${amount} USDT from ${from} to ${to}`
      );

      // Check if transaction already exists (fast pre-check to avoid unnecessary processing)
      // Note: This is not a substitute for database-level UNIQUE constraint
      // The UNIQUE index on tx_hash provides final protection against duplicates
      const transactionRepo = AppDataSource.getRepository(Transaction);
      const existingTx = await transactionRepo.findOne({
        where: { tx_hash: txHash },
      });

      if (existingTx) {
        logger.info(`ℹ️ Transaction ${txHash} already processed`, {
          txHash,
          existingId: existingTx.id,
          status: existingTx.status,
        });

        // Log to audit trail for monitoring duplicate attempts
        logFinancialOperation({
          category: 'deposit',
          userId: existingTx.user_id,
          action: 'duplicate_transaction_attempt',
          amount,
          success: false,
          error: 'Transaction already processed',
          details: {
            txHash,
            existingTransactionId: existingTx.id,
            existingStatus: existingTx.status,
          },
        });

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
      let matchedLevel: number | null = null;
      let expectedAmount: number | null = null;
      let actualDifference = 0;

      for (const [level, levelAmount] of Object.entries(DEPOSIT_LEVELS)) {
        const difference = Math.abs(amount - levelAmount);

        if (difference <= this.DEPOSIT_AMOUNT_TOLERANCE) {
          matchedLevel = parseInt(level);
          expectedAmount = levelAmount;
          actualDifference = amount - levelAmount; // Can be negative if underpaid

          // Log if deposit is within tolerance but not exact
          if (difference > 0) {
            logger.warn('Deposit amount within tolerance but not exact', {
              txHash,
              userId: user.id,
              telegramId: user.telegram_id,
              expected: levelAmount,
              actual: amount,
              difference: actualDifference,
              tolerance: this.DEPOSIT_AMOUNT_TOLERANCE,
              level: matchedLevel,
            });

            // Log to audit trail for financial compliance
            logFinancialOperation({
              category: 'deposit',
              userId: user.id,
              action: 'deposit_tolerance_match',
              amount: amount,
              success: true,
              details: {
                txHash,
                expected: levelAmount,
                actual: amount,
                difference: actualDifference,
                tolerance: this.DEPOSIT_AMOUNT_TOLERANCE,
                level: matchedLevel,
              },
            });

            // Alert admin if difference is significant
            if (Math.abs(actualDifference) > this.TOLERANCE_ALERT_THRESHOLD) {
              logger.error('⚠️ ALERT: Significant deposit amount deviation', {
                txHash,
                userId: user.id,
                telegramId: user.telegram_id,
                expected: levelAmount,
                actual: amount,
                difference: actualDifference,
                toleranceUsed: this.DEPOSIT_AMOUNT_TOLERANCE,
                alertThreshold: this.TOLERANCE_ALERT_THRESHOLD,
              });

              // TODO: Send Telegram notification to super admin
              // This requires integration with notification service
              // For now, critical error log will be picked up by monitoring
            }
          }

          break;
        }
      }

      if (!matchedLevel) {
        logger.warn(
          `⚠️ Amount ${amount} USDT doesn't match any deposit level for user ${user.telegram_id}`,
          {
            txHash,
            amount,
            tolerance: this.DEPOSIT_AMOUNT_TOLERANCE,
            availableLevels: Object.values(DEPOSIT_LEVELS),
          }
        );

        // Log failed deposit attempt to audit trail
        logFinancialOperation({
          category: 'deposit',
          userId: user.id,
          action: 'deposit_amount_mismatch',
          amount: amount,
          success: false,
          error: 'Amount does not match any deposit level',
          details: {
            txHash,
            amount,
            tolerance: this.DEPOSIT_AMOUNT_TOLERANCE,
            availableLevels: Object.values(DEPOSIT_LEVELS),
          },
        });

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
      // Uses withTransaction for automatic retry on deadlock/serialization errors
      try {
        await withTransaction(async (manager) => {
        // Find and lock matching pending deposit (SELECT FOR UPDATE)
        // This prevents race conditions when multiple transactions arrive simultaneously
        const pendingDeposit = await manager
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
            `⚠️ No pending deposit found for user ${user.telegram_id} level ${matchedLevel}`,
            {
              userId: user.id,
              telegramId: user.telegram_id,
              level: matchedLevel,
              amount,
              txHash,
            }
          );

          // Log to audit trail
          logFinancialOperation({
            category: 'deposit',
            userId: user.id,
            action: 'no_pending_deposit_found',
            amount,
            success: false,
            details: {
              txHash,
              level: matchedLevel,
              expected: expectedAmount,
            },
          });

          // Create transaction record for manual review
          await manager.save(Transaction, {
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
        await manager.save(Deposit, pendingDeposit);

        // Create transaction record
        await manager.save(Transaction, {
          user_id: user.id,
          tx_hash: txHash,
          type: TransactionType.DEPOSIT,
          amount: amount.toString(),
          from_address: from.toLowerCase(),
          to_address: to.toLowerCase(),
          block_number: blockNumber,
          status: TransactionStatus.PENDING,
        });

        // Log successful deposit tracking to audit trail
        logFinancialOperation({
          category: 'deposit',
          userId: user.id,
          action: 'deposit_tracked',
          amount,
          success: true,
          details: {
            txHash,
            level: matchedLevel,
            depositId: pendingDeposit.id,
            blockNumber,
          },
        });

        logger.info(
          `✅ Deposit tracked: ${amount} USDT for user ${user.telegram_id} (tx: ${txHash})`
        );
      }, TRANSACTION_PRESETS.FINANCIAL); // Use FINANCIAL preset for higher retries and timeout

        // Notify user about detected deposit (pending confirmation)
        await notificationService.notifyDepositPending(
          user.telegram_id,
          amount,
          matchedLevel!,
          txHash
        ).catch((err) => {
          logger.error('Failed to send deposit pending notification', { error: err });
        });

      } catch (error: any) {
        // Handle duplicate transaction error (race condition case)
        if (error.code === '23505' || error.message?.includes('duplicate key')) {
          logger.warn('Transaction already processed (caught duplicate key violation)', {
            txHash,
            errorCode: error.code,
            errorDetail: error.detail,
          });

          // Log to audit trail for monitoring
          logFinancialOperation({
            category: 'deposit',
            userId: user?.id || 0,
            action: 'duplicate_transaction_caught',
            amount,
            success: false,
            error: 'Duplicate transaction prevented by database constraint',
            details: {
              txHash,
              errorCode: error.code,
            },
          });

          // This is expected behavior - not an error
          return;
        }

        // Other errors are unexpected - log and re-throw
        logger.error('❌ Error processing Transfer event:', {
          txHash,
          amount,
          from,
          to,
          error: error.message,
          stack: error.stack,
        });
        throw error;
      }
    } catch (error) {
      logger.error('❌ Unexpected error in handleTransferEvent:', error);
    }
  }

  /**
   * Search blockchain for transaction matching deposit
   * Used for expired deposit recovery
   *
   * @returns Found tx_hash or null
   */
  private async searchBlockchainForDeposit(
    deposit: Deposit
  ): Promise<{ found: boolean; txHash: string | null; blockNumber: number | null }> {
    if (!deposit.wallet_address || !deposit.user?.wallet_address) {
      return { found: false, txHash: null, blockNumber: null };
    }

    try {
      const usdtContract = this.providerManager.getUsdtContract();
      const decimals = await getUsdtDecimals(usdtContract);
      const expectedAmount = parseFloat(deposit.amount);

      // Search last 7 days of blockchain history
      const currentBlock = await this.providerManager.getHttpProvider().getBlockNumber();
      const blocksPerDay = 28800; // ~3s per block on BSC
      const searchDepthBlocks = blocksPerDay * 7;
      const fromBlock = Math.max(0, currentBlock - searchDepthBlocks);

      // Get Transfer events FROM user's wallet TO our wallet
      const filter = usdtContract.filters.Transfer(
        deposit.wallet_address.toLowerCase(),
        deposit.user.wallet_address.toLowerCase()
      );

      const events = await usdtContract.queryFilter(filter, fromBlock, currentBlock);

      // Check each event for matching amount
      for (const event of events) {
        const eventAmount = parseFloat(ethers.formatUnits(event.args.value, decimals));

        // Match with tolerance
        if (Math.abs(eventAmount - expectedAmount) <= this.DEPOSIT_AMOUNT_TOLERANCE) {
          // Get receipt to verify transaction succeeded
          const receipt = await this.providerManager
            .getHttpProvider()
            .getTransactionReceipt(event.transactionHash);

          if (receipt && receipt.status === 1) {
            logger.info('Found matching blockchain transaction for expired deposit', {
              depositId: deposit.id,
              txHash: event.transactionHash,
              blockNumber: receipt.blockNumber,
              amount: eventAmount,
              expected: expectedAmount,
            });

            return {
              found: true,
              txHash: event.transactionHash,
              blockNumber: receipt.blockNumber,
            };
          }
        }
      }

      return { found: false, txHash: null, blockNumber: null };
    } catch (error) {
      logger.error('Error searching blockchain for expired deposit', {
        depositId: deposit.id,
        error,
      });
      return { found: false, txHash: null, blockNumber: null };
    }
  }

  /**
   * Check and confirm pending deposits (called by background job)
   */
  public async checkPendingDeposits(): Promise<void> {
    try {
      const depositRepo = AppDataSource.getRepository(Deposit);
      const transactionRepo = AppDataSource.getRepository(Transaction);

      // FIX #13: Get pending deposits in configurable batches (default 500, was 100)
      // Process oldest first to ensure timely confirmations
      const BATCH_SIZE = config.blockchain.depositBatchSize;
      const CONCURRENCY = config.blockchain.depositConcurrency;

      const pendingDeposits = await depositRepo.find({
        where: { status: TransactionStatus.PENDING },
        relations: ['user'],
        order: { created_at: 'ASC' },
        take: BATCH_SIZE,
      });

      if (pendingDeposits.length === 0) {
        return;
      }

      logger.info(
        `🔍 Checking ${pendingDeposits.length} pending deposits (batch size: ${BATCH_SIZE}, concurrency: ${CONCURRENCY})...`
      );

      // Get current block number
      const currentBlock = await this.providerManager.getHttpProvider().getBlockNumber();

      // FIX #13: Process deposits in parallel batches for better performance
      // Split into concurrent batches to avoid overwhelming the blockchain provider
      let processedCount = 0;
      let errorCount = 0;

      for (let i = 0; i < pendingDeposits.length; i += CONCURRENCY) {
        const batch = pendingDeposits.slice(i, i + CONCURRENCY);

        // Process this batch in parallel
        const results = await Promise.allSettled(
          batch.map(async (deposit) => {
        try {
          // Check for deposit timeout (24 hours without confirmation)
          const depositAge = Date.now() - deposit.created_at.getTime();
          if (depositAge > this.DEPOSIT_TIMEOUT_MS) {
            // CRITICAL FIX #1: Search blockchain for transaction before marking as FAILED
            // User may have sent funds but we missed the blockchain event
            logger.info(`Deposit ${deposit.id} expired - searching blockchain for transaction...`);

            const searchResult = await this.searchBlockchainForDeposit(deposit);

            // Use pessimistic lock to prevent race conditions
            await withTransaction(async (manager) => {
              await lockForDepositProcessing(manager, deposit.id, async (lockedDeposit) => {
                // Double-check status after acquiring lock (another worker might have processed it)
                if (lockedDeposit.status !== TransactionStatus.PENDING) {
                  logger.info(
                    `Deposit ${deposit.id} already processed by another worker (status: ${lockedDeposit.status})`
                  );
                  return;
                }

                // If transaction found on blockchain - RECOVER IT!
                if (searchResult.found && searchResult.txHash && searchResult.blockNumber) {
                  logger.info(
                    `🔄 AUTO-RECOVERING expired deposit ${deposit.id} - transaction found on blockchain!`,
                    {
                      depositId: deposit.id,
                      txHash: searchResult.txHash,
                      blockNumber: searchResult.blockNumber,
                      ageHours: Math.round(depositAge / 1000 / 60 / 60),
                    }
                  );

                  // Update deposit with found transaction
                  lockedDeposit.tx_hash = searchResult.txHash;
                  lockedDeposit.block_number = searchResult.blockNumber;
                  await manager.save(Deposit, lockedDeposit);

                  // Create transaction record
                  await manager.save(Transaction, {
                    user_id: lockedDeposit.user_id,
                    tx_hash: searchResult.txHash,
                    type: TransactionType.DEPOSIT,
                    amount: lockedDeposit.amount,
                    from_address: deposit.wallet_address?.toLowerCase() || '',
                    to_address: deposit.user?.wallet_address?.toLowerCase() || '',
                    block_number: searchResult.blockNumber,
                    status: TransactionStatus.PENDING, // Will be confirmed in next iteration
                  });

                  // Log recovery to audit trail
                  logFinancialOperation({
                    category: 'deposit',
                    userId: lockedDeposit.user_id,
                    action: 'expired_deposit_recovered',
                    amount: parseFloat(lockedDeposit.amount),
                    success: true,
                    details: {
                      depositId: lockedDeposit.id,
                      txHash: searchResult.txHash,
                      blockNumber: searchResult.blockNumber,
                      ageHours: Math.round(depositAge / 1000 / 60 / 60),
                      autoRecovered: true,
                      searchedBlockchain: true,
                    },
                  });

                  logger.info(
                    `✅ Expired deposit ${deposit.id} auto-recovered - will be confirmed in next check cycle`
                  );

                  // Notify user about recovery
                  if (deposit.user) {
                    await notificationService.notifyDepositPending(
                      deposit.user.telegram_id,
                      parseFloat(lockedDeposit.amount),
                      lockedDeposit.level,
                      searchResult.txHash
                    ).catch(err => {
                      logger.error('Failed to send recovery notification', { error: err });
                    });
                  }

                  return; // Exit - don't mark as FAILED
                }

                // No transaction found - mark as FAILED
                lockedDeposit.status = TransactionStatus.FAILED;
                await manager.save(Deposit, lockedDeposit);

                // Update transaction status if exists
                if (lockedDeposit.tx_hash) {
                  await manager.update(Transaction,
                    { tx_hash: lockedDeposit.tx_hash },
                    { status: TransactionStatus.FAILED }
                  );
                }

                // Log to audit trail
                logFinancialOperation({
                  category: 'deposit',
                  userId: lockedDeposit.user_id,
                  action: 'deposit_timeout',
                  amount: parseFloat(lockedDeposit.amount),
                  success: false,
                  error: 'Deposit timed out after 24 hours - no blockchain transaction found',
                  details: {
                    depositId: lockedDeposit.id,
                    txHash: lockedDeposit.tx_hash,
                    ageHours: Math.round(depositAge / 1000 / 60 / 60),
                    blockchainSearched: true,
                    transactionFound: false,
                  },
                });

                logger.warn(
                  `⏱️ Deposit ${lockedDeposit.id} timed out after ${Math.round(depositAge / 1000 / 60 / 60)}h - no transaction found on blockchain (user: ${deposit.user?.telegram_id})`
                );
              });
            }, TRANSACTION_PRESETS.FINANCIAL);

            // Notify user about timeout (only if not recovered)
            if (deposit.user && !searchResult.found) {
              await notificationService.notifyDepositTimeout(
                deposit.user.telegram_id,
                parseFloat(deposit.amount),
                deposit.level
              ).catch(err => {
                logger.error('Failed to send timeout notification', { error: err });
              });
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
            const receipt = await this.providerManager.getHttpProvider().getTransactionReceipt(
              deposit.tx_hash
            );

            if (!receipt) {
              logger.warn(
                `⚠️ Transaction receipt not found: ${deposit.tx_hash}`
              );
              continue;
            }

            if (receipt.status !== 1) {
              // Transaction failed - use pessimistic lock to prevent race conditions
              await withTransaction(async (manager) => {
                await lockForDepositProcessing(manager, deposit.id, async (lockedDeposit) => {
                  // Double-check status after acquiring lock
                  if (lockedDeposit.status !== TransactionStatus.PENDING) {
                    logger.info(
                      `Deposit ${deposit.id} already processed (status: ${lockedDeposit.status})`
                    );
                    return;
                  }

                  lockedDeposit.status = TransactionStatus.FAILED;
                  await manager.save(Deposit, lockedDeposit);

                  await manager.update(Transaction,
                    { tx_hash: lockedDeposit.tx_hash },
                    { status: TransactionStatus.FAILED }
                  );

                  // Log to audit trail
                  logFinancialOperation({
                    category: 'deposit',
                    userId: lockedDeposit.user_id,
                    action: 'deposit_transaction_failed',
                    amount: parseFloat(lockedDeposit.amount),
                    success: false,
                    error: 'Blockchain transaction failed',
                    details: {
                      depositId: lockedDeposit.id,
                      txHash: lockedDeposit.tx_hash,
                      blockNumber: lockedDeposit.block_number,
                    },
                  });

                  logger.warn(
                    `❌ Deposit transaction failed: ${lockedDeposit.tx_hash}`
                  );
                });
              }, TRANSACTION_PRESETS.FINANCIAL);

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
          throw error; // Re-throw to be caught by Promise.allSettled
        }
          })
        );

        // FIX #13: Count successes and failures for this batch
        results.forEach((result, index) => {
          processedCount++;
          if (result.status === 'rejected') {
            errorCount++;
            logger.error(`Deposit processing failed in batch:`, {
              depositId: batch[index].id,
              error: result.reason,
            });
          }
        });

        logger.debug(`Batch processed: ${batch.length} deposits, ${errorCount} errors so far`);
      }

      // FIX #13: Log summary of parallel processing
      logger.info(
        `✅ Pending deposit check complete: ${processedCount} deposits processed, ${errorCount} errors, concurrency: ${CONCURRENCY}`
      );
    } catch (error) {
      logger.error('❌ Error checking pending deposits:', error);
    }
  }

  /**
   * Start orphaned deposit cleanup job
   */
  public startCleanupJob(): void {
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
   * Stop cleanup job
   */
  public stopCleanupJob(): void {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = undefined;
    }
  }

  /**
   * Run cleanup of orphaned deposits
   */
  private async runCleanup(): Promise<void> {
    const depositService = await this.getDepositService();

    logger.info('🧹 Running orphaned deposit cleanup...');
    const { cleaned, errors } = await depositService.cleanupOrphanedDeposits();

    if (cleaned > 0 || errors > 0) {
      logger.info(`🧹 Cleanup complete: ${cleaned} cleaned, ${errors} errors`);
    } else {
      logger.debug('🧹 Cleanup complete: No orphaned deposits found');
    }
  }
}
