/**
 * Integration Test Setup
 * Initializes database and Redis for integration tests
 */

import { DataSource } from 'typeorm';
import Redis from 'ioredis';
import { AppDataSource } from '../src/database/data-source';

let testDataSource: DataSource;
let testRedis: Redis;

/**
 * Setup function - runs before all integration tests
 */
beforeAll(async () => {
  console.log('🔧 Setting up integration test environment...');

  // Initialize test database
  try {
    if (!AppDataSource.isInitialized) {
      await AppDataSource.initialize();
    }
    testDataSource = AppDataSource;
    console.log('✅ Test database connected');
  } catch (error) {
    console.error('❌ Failed to connect to test database:', error);
    throw error;
  }

  // Initialize test Redis
  try {
    testRedis = new Redis({
      host: process.env.REDIS_HOST || 'localhost',
      port: parseInt(process.env.REDIS_PORT || '6379'),
      db: parseInt(process.env.REDIS_TEST_DB || '15'), // Use separate DB for tests
      retryStrategy: () => null, // Don't retry in tests
    });

    await testRedis.ping();
    console.log('✅ Test Redis connected');
  } catch (error) {
    console.error('❌ Failed to connect to test Redis:', error);
    throw error;
  }
});

/**
 * Cleanup after each test
 */
afterEach(async () => {
  // Clear all Redis keys in test DB
  if (testRedis) {
    await testRedis.flushdb();
  }

  // Truncate all tables (preserve schema)
  if (testDataSource && testDataSource.isInitialized) {
    const entities = testDataSource.entityMetadatas;

    for (const entity of entities) {
      const repository = testDataSource.getRepository(entity.name);
      await repository.clear();
    }
  }
});

/**
 * Teardown function - runs after all integration tests
 */
afterAll(async () => {
  console.log('🧹 Cleaning up integration test environment...');

  // Close Redis connection
  if (testRedis) {
    await testRedis.quit();
    console.log('✅ Test Redis disconnected');
  }

  // Close database connection
  if (testDataSource && testDataSource.isInitialized) {
    await testDataSource.destroy();
    console.log('✅ Test database disconnected');
  }
});

export { testDataSource, testRedis };
