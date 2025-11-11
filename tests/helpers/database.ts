/**
 * Database Test Helpers
 * Utilities for working with test database
 */

import { DataSource, Repository, EntityTarget } from 'typeorm';
import { AppDataSource } from '../../src/database/data-source';
import { User } from '../../src/database/entities/User.entity';
import { Deposit } from '../../src/database/entities/Deposit.entity';
import { Transaction } from '../../src/database/entities/Transaction.entity';

/**
 * Get repository for entity
 */
export function getRepository<T>(entity: EntityTarget<T>): Repository<T> {
  return AppDataSource.getRepository(entity);
}

/**
 * Clear all data from database (preserve schema)
 */
export async function clearDatabase(): Promise<void> {
  if (!AppDataSource.isInitialized) {
    throw new Error('Database not initialized');
  }

  const entities = AppDataSource.entityMetadatas;

  // Truncate in reverse order to handle foreign keys
  for (const entity of entities.reverse()) {
    const repository = AppDataSource.getRepository(entity.name);
    await repository.clear();
  }
}

/**
 * Create a user in test database
 */
export async function createTestUser(data: Partial<User>): Promise<User> {
  const userRepo = getRepository(User);
  const user = userRepo.create(data);
  return await userRepo.save(user);
}

/**
 * Create a deposit in test database
 */
export async function createTestDeposit(data: Partial<Deposit>): Promise<Deposit> {
  const depositRepo = getRepository(Deposit);
  const deposit = depositRepo.create(data);
  return await depositRepo.save(deposit);
}

/**
 * Create a transaction in test database
 */
export async function createTestTransaction(data: Partial<Transaction>): Promise<Transaction> {
  const txRepo = getRepository(Transaction);
  const transaction = txRepo.create(data);
  return await txRepo.save(transaction);
}

/**
 * Find user by telegram ID
 */
export async function findUserByTelegramId(telegramId: number): Promise<User | null> {
  const userRepo = getRepository(User);
  return await userRepo.findOne({ where: { telegram_id: telegramId } });
}

/**
 * Count entities
 */
export async function countEntities<T>(entity: EntityTarget<T>): Promise<number> {
  const repo = getRepository(entity);
  return await repo.count();
}

/**
 * Execute raw SQL query (for complex test scenarios)
 */
export async function executeQuery<T = any>(query: string, parameters?: any[]): Promise<T[]> {
  return await AppDataSource.query(query, parameters);
}

/**
 * Begin transaction (for testing transaction rollback)
 */
export async function withTransaction<T>(
  callback: (manager: DataSource) => Promise<T>
): Promise<T> {
  return await AppDataSource.transaction(async (transactionalEntityManager) => {
    // Cast to DataSource for type compatibility
    return await callback(transactionalEntityManager as any);
  });
}
