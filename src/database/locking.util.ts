/**
 * Pessimistic Locking Utility
 *
 * Provides utilities for database-level pessimistic locking to prevent race conditions
 * in critical operations like deposits, withdrawals, and balance updates.
 *
 * Features:
 * - SELECT FOR UPDATE helpers with timeout protection
 * - Lock contention monitoring and alerting
 * - Automatic deadlock detection
 * - Lock acquisition tracking
 * - Multiple lock modes (UPDATE, SHARE, NO KEY UPDATE, KEY SHARE)
 *
 * Usage:
 * ```typescript
 * await withPessimisticLock(manager, User, userId, async (user) => {
 *   user.balance += 100;
 *   return await manager.save(user);
 * });
 * ```
 */

import { EntityManager, EntityTarget, FindOptionsWhere, ObjectLiteral } from 'typeorm';
import { createLogger } from '../utils/logger.util';
import { getRequestId, logAuditEvent } from '../utils/audit-logger.util';

const logger = createLogger('PessimisticLocking');

/**
 * Lock modes supported by PostgreSQL
 */
export enum LockMode {
  /** FOR UPDATE - Exclusive lock, blocks all other locks */
  FOR_UPDATE = 'pessimistic_write',

  /** FOR SHARE - Shared lock, blocks FOR UPDATE but allows other FOR SHARE */
  FOR_SHARE = 'pessimistic_read',

  /** FOR NO KEY UPDATE - Like FOR UPDATE but allows concurrent FOR KEY SHARE */
  FOR_NO_KEY_UPDATE = 'pessimistic_partial_write',

  /** FOR KEY SHARE - Like FOR SHARE but allows concurrent FOR NO KEY UPDATE */
  FOR_KEY_SHARE = 'pessimistic_write_or_fail',
}

/**
 * Lock options
 */
export interface LockOptions {
  /** Lock mode (default: FOR_UPDATE) */
  mode?: LockMode;

  /** Lock timeout in milliseconds (default: 5000) */
  timeout?: number;

  /** Skip locked rows instead of waiting (SKIP LOCKED) */
  skipLocked?: boolean;

  /** Fail immediately if lock cannot be acquired (NOWAIT) */
  nowait?: boolean;

  /** Enable detailed logging for debugging */
  enableDebugLogging?: boolean;

  /** Custom error message prefix */
  errorMessagePrefix?: string;
}

/**
 * Lock acquisition result
 */
export interface LockResult<T> {
  /** Whether lock was acquired */
  acquired: boolean;

  /** Locked entity (undefined if lock was not acquired) */
  entity?: T;

  /** Time taken to acquire lock in milliseconds */
  lockDuration?: number;

  /** Whether lock was skipped (when skipLocked is true) */
  skipped?: boolean;
}

/**
 * Lock statistics for monitoring
 */
class LockStats {
  private static stats = {
    totalAttempts: 0,
    successful: 0,
    failed: 0,
    timeouts: 0,
    skipped: 0,
    totalWaitTime: 0,
    maxWaitTime: 0,
    contentionEvents: 0,
  };

  static recordAttempt(
    success: boolean,
    waitTime: number,
    skipped: boolean = false,
    timeout: boolean = false
  ): void {
    this.stats.totalAttempts++;
    this.stats.totalWaitTime += waitTime;

    if (waitTime > this.stats.maxWaitTime) {
      this.stats.maxWaitTime = waitTime;
    }

    if (skipped) {
      this.stats.skipped++;
    } else if (timeout) {
      this.stats.timeouts++;
      this.stats.failed++;
    } else if (success) {
      this.stats.successful++;
    } else {
      this.stats.failed++;
    }

    // Log contention if wait time is significant
    if (waitTime > 1000) {
      this.stats.contentionEvents++;
      logger.warn('Lock contention detected', {
        waitTime,
        totalContention: this.stats.contentionEvents,
      });
    }
  }

  static getStats() {
    const { totalAttempts, successful, failed, timeouts, skipped, totalWaitTime, maxWaitTime, contentionEvents } =
      this.stats;

    return {
      totalAttempts,
      successful,
      failed,
      timeouts,
      skipped,
      successRate: totalAttempts > 0 ? (successful / totalAttempts) * 100 : 0,
      avgWaitTime: successful > 0 ? totalWaitTime / successful : 0,
      maxWaitTime,
      contentionEvents,
      contentionRate: totalAttempts > 0 ? (contentionEvents / totalAttempts) * 100 : 0,
    };
  }

  static reset(): void {
    this.stats = {
      totalAttempts: 0,
      successful: 0,
      failed: 0,
      timeouts: 0,
      skipped: 0,
      totalWaitTime: 0,
      maxWaitTime: 0,
      contentionEvents: 0,
    };
  }
}

/**
 * Acquire pessimistic lock on entity and execute operation
 *
 * This is the main function for pessimistic locking. It:
 * 1. Finds entity with SELECT FOR UPDATE (or other lock mode)
 * 2. Waits for lock acquisition (with timeout)
 * 3. Executes operation with locked entity
 * 4. Tracks lock statistics
 *
 * @param manager - TypeORM EntityManager (must be within a transaction)
 * @param entityClass - Entity class to lock
 * @param where - Find conditions
 * @param operation - Operation to perform with locked entity
 * @param options - Lock options
 * @returns Operation result
 *
 * @example
 * ```typescript
 * await withTransaction(async (manager) => {
 *   const result = await withPessimisticLock(
 *     manager,
 *     User,
 *     { id: userId },
 *     async (user) => {
 *       if (!user) throw new Error('User not found');
 *       user.balance += amount;
 *       return await manager.save(user);
 *     },
 *     { timeout: 5000 }
 *   );
 * });
 * ```
 */
export async function withPessimisticLock<Entity extends ObjectLiteral, Result>(
  manager: EntityManager,
  entityClass: EntityTarget<Entity>,
  where: FindOptionsWhere<Entity>,
  operation: (entity: Entity | null) => Promise<Result>,
  options: LockOptions = {}
): Promise<Result> {
  const {
    mode = LockMode.FOR_UPDATE,
    timeout = 5000,
    skipLocked = false,
    nowait = false,
    enableDebugLogging = false,
    errorMessagePrefix = 'Lock acquisition failed',
  } = options;

  const requestId = getRequestId();
  const startTime = Date.now();

  if (enableDebugLogging) {
    logger.debug('Attempting to acquire pessimistic lock', {
      requestId,
      entityClass: (entityClass as any).name,
      where,
      mode,
      timeout,
      skipLocked,
      nowait,
    });
  }

  try {
    // Set lock timeout for this transaction
    if (!nowait && !skipLocked) {
      await manager.query(`SET LOCAL lock_timeout = '${timeout}ms'`);
    }

    // Find entity with pessimistic lock
    const lockResult = await acquireLock(manager, entityClass, where, {
      mode,
      skipLocked,
      nowait,
    });

    const lockDuration = Date.now() - startTime;

    if (lockResult.skipped) {
      LockStats.recordAttempt(false, lockDuration, true, false);

      logger.warn('Lock skipped (row is locked by another transaction)', {
        requestId,
        entityClass: (entityClass as any).name,
        where,
        lockDuration,
      });

      // Execute operation with null entity
      return await operation(null);
    }

    if (!lockResult.acquired) {
      LockStats.recordAttempt(false, lockDuration, false, false);

      throw new Error(`${errorMessagePrefix}: Lock could not be acquired`);
    }

    LockStats.recordAttempt(true, lockDuration, false, false);

    if (enableDebugLogging || lockDuration > 1000) {
      logger.info('Pessimistic lock acquired', {
        requestId,
        entityClass: (entityClass as any).name,
        lockDuration,
      });
    }

    // Log to audit trail for critical operations
    if (lockDuration > 2000) {
      logAuditEvent({
        category: 'performance',
        severity: 'audit',
        action: 'lock_contention',
        requestId,
        details: {
          entityClass: (entityClass as any).name,
          lockDuration,
          mode,
        },
      });
    }

    // Execute operation with locked entity
    const result = await operation(lockResult.entity ?? null);

    return result;
  } catch (error: any) {
    const lockDuration = Date.now() - startTime;

    // Check if error is due to lock timeout
    const isTimeout =
      error.message?.includes('timeout') ||
      error.message?.includes('lock_timeout') ||
      error.code === '55P03';

    LockStats.recordAttempt(false, lockDuration, false, isTimeout);

    logger.error('Pessimistic lock failed', {
      requestId,
      entityClass: (entityClass as any).name,
      where,
      error: error.message,
      errorCode: error.code,
      lockDuration,
      isTimeout,
    });

    throw error;
  } finally {
    // Reset lock timeout to default
    if (!nowait && !skipLocked) {
      await manager.query(`SET LOCAL lock_timeout = DEFAULT`).catch(() => {
        // Ignore errors on cleanup
      });
    }
  }
}

/**
 * Internal function to acquire lock on entity
 */
async function acquireLock<Entity extends ObjectLiteral>(
  manager: EntityManager,
  entityClass: EntityTarget<Entity>,
  where: FindOptionsWhere<Entity>,
  options: { mode: LockMode; skipLocked: boolean; nowait: boolean }
): Promise<LockResult<Entity>> {
  const { mode, skipLocked, nowait } = options;

  try {
    const entity = await manager.findOne(entityClass, {
      where,
      lock: {
        mode,
      },
    });

    return {
      acquired: true,
      entity: entity ?? undefined,
    };
  } catch (error: any) {
    // Handle SKIP LOCKED - row is locked, skip it
    if (skipLocked && error.message?.includes('could not obtain lock')) {
      return {
        acquired: false,
        skipped: true,
      };
    }

    // Handle NOWAIT - lock not available
    if (nowait && (error.code === '55P03' || error.message?.includes('could not obtain lock'))) {
      return {
        acquired: false,
      };
    }

    throw error;
  }
}

/**
 * Lock multiple entities in a specific order to prevent deadlocks
 *
 * Always lock entities in the same order (by ID) to prevent circular dependencies
 * that lead to deadlocks.
 *
 * @param manager - EntityManager
 * @param entityClass - Entity class
 * @param ids - Array of entity IDs to lock (will be sorted)
 * @param operation - Operation to perform with locked entities
 * @param options - Lock options
 * @returns Operation result
 *
 * @example
 * ```typescript
 * // Lock user 1 and user 2 in deterministic order
 * await withMultipleLocks(
 *   manager,
 *   User,
 *   [userId1, userId2],
 *   async (users) => {
 *     users[0].balance -= 100;
 *     users[1].balance += 100;
 *     await manager.save(users);
 *   }
 * );
 * ```
 */
export async function withMultipleLocks<Entity extends ObjectLiteral, Result>(
  manager: EntityManager,
  entityClass: EntityTarget<Entity>,
  ids: (number | string)[],
  operation: (entities: Entity[]) => Promise<Result>,
  options: LockOptions = {}
): Promise<Result> {
  // Sort IDs to ensure consistent lock order (prevents deadlocks)
  const sortedIds = [...ids].sort((a, b) => {
    if (typeof a === 'number' && typeof b === 'number') {
      return a - b;
    }
    return String(a).localeCompare(String(b));
  });

  const requestId = getRequestId();

  logger.debug('Acquiring multiple locks', {
    requestId,
    entityClass: (entityClass as any).name,
    count: sortedIds.length,
    ids: sortedIds,
  });

  const entities: Entity[] = [];

  // Lock entities one by one in sorted order
  for (const id of sortedIds) {
    await withPessimisticLock(
      manager,
      entityClass,
      { id } as any,
      async (entity) => {
        if (entity) {
          entities.push(entity);
        }
      },
      options
    );
  }

  // Execute operation with all locked entities
  return await operation(entities);
}

/**
 * Try to acquire lock without waiting
 * Returns null if lock cannot be acquired immediately
 *
 * @param manager - EntityManager
 * @param entityClass - Entity class
 * @param where - Find conditions
 * @param options - Lock options
 * @returns Locked entity or null
 *
 * @example
 * ```typescript
 * const user = await tryLockNowait(manager, User, { id: userId });
 * if (!user) {
 *   throw new Error('User is locked by another transaction');
 * }
 * ```
 */
export async function tryLockNowait<Entity extends ObjectLiteral>(
  manager: EntityManager,
  entityClass: EntityTarget<Entity>,
  where: FindOptionsWhere<Entity>,
  options: Omit<LockOptions, 'nowait'> = {}
): Promise<Entity | null> {
  let result: Entity | null = null;

  await withPessimisticLock(
    manager,
    entityClass,
    where,
    async (entity) => {
      result = entity;
    },
    { ...options, nowait: true }
  );

  return result;
}

/**
 * Try to acquire lock, skip if locked
 * Returns null if entity is locked by another transaction
 *
 * @param manager - EntityManager
 * @param entityClass - Entity class
 * @param where - Find conditions
 * @param options - Lock options
 * @returns Locked entity or null
 *
 * @example
 * ```typescript
 * const user = await tryLockSkipLocked(manager, User, { id: userId });
 * if (!user) {
 *   // User is being processed by another transaction, skip
 *   return;
 * }
 * ```
 */
export async function tryLockSkipLocked<Entity extends ObjectLiteral>(
  manager: EntityManager,
  entityClass: EntityTarget<Entity>,
  where: FindOptionsWhere<Entity>,
  options: Omit<LockOptions, 'skipLocked'> = {}
): Promise<Entity | null> {
  let result: Entity | null = null;

  await withPessimisticLock(
    manager,
    entityClass,
    where,
    async (entity) => {
      result = entity;
    },
    { ...options, skipLocked: true }
  );

  return result;
}

/**
 * Lock for balance update
 * Specialized helper for locking user entities during balance changes
 *
 * @param manager - EntityManager
 * @param userId - User ID
 * @param operation - Operation to perform with locked user
 * @returns Operation result
 *
 * @example
 * ```typescript
 * await lockForBalanceUpdate(manager, userId, async (user) => {
 *   if (user.balance < amount) {
 *     throw new Error('Insufficient balance');
 *   }
 *   user.balance -= amount;
 *   return await manager.save(user);
 * });
 * ```
 */
export async function lockForBalanceUpdate<Result>(
  manager: EntityManager,
  userId: number,
  operation: (user: any) => Promise<Result>
): Promise<Result> {
  // Import User entity dynamically to avoid circular dependencies
  const { User } = await import('../database/entities/user.entity');

  return await withPessimisticLock(
    manager,
    User,
    { id: userId } as any,
    async (user) => {
      if (!user) {
        throw new Error(`User not found: ${userId}`);
      }
      return await operation(user);
    },
    {
      mode: LockMode.FOR_UPDATE,
      timeout: 10000, // 10 seconds for balance operations
      errorMessagePrefix: 'Failed to lock user for balance update',
    }
  );
}

/**
 * Lock for deposit processing
 * Specialized helper for locking deposits during blockchain confirmation
 *
 * @param manager - EntityManager
 * @param depositId - Deposit ID
 * @param operation - Operation to perform with locked deposit
 * @returns Operation result
 */
export async function lockForDepositProcessing<Result>(
  manager: EntityManager,
  depositId: number,
  operation: (deposit: any) => Promise<Result>
): Promise<Result> {
  const { Deposit } = await import('../database/entities/deposit.entity');

  return await withPessimisticLock(
    manager,
    Deposit,
    { id: depositId } as any,
    async (deposit) => {
      if (!deposit) {
        throw new Error(`Deposit not found: ${depositId}`);
      }
      return await operation(deposit);
    },
    {
      mode: LockMode.FOR_UPDATE,
      timeout: 15000, // 15 seconds for deposit processing
      errorMessagePrefix: 'Failed to lock deposit for processing',
    }
  );
}

/**
 * Get lock statistics
 */
export function getLockStats() {
  return LockStats.getStats();
}

/**
 * Reset lock statistics
 */
export function resetLockStats() {
  LockStats.reset();
}

/**
 * Export lock stats class for testing
 */
export { LockStats };
