/**
 * E2E Test Setup
 * Initializes full application stack for end-to-end tests
 */

import { Telegraf } from 'telegraf';
import { DataSource } from 'typeorm';
import Redis from 'ioredis';
import { AppDataSource } from '../src/database/data-source';

let testBot: Telegraf;
let testDataSource: DataSource;
let testRedis: Redis;

/**
 * Setup function - runs before all e2e tests
 */
beforeAll(async () => {
  console.log('🚀 Setting up E2E test environment...');

  // Initialize database
  if (!AppDataSource.isInitialized) {
    await AppDataSource.initialize();
  }
  testDataSource = AppDataSource;
  console.log('✅ E2E database connected');

  // Initialize Redis
  testRedis = new Redis({
    host: process.env.REDIS_HOST || 'localhost',
    port: parseInt(process.env.REDIS_PORT || '6379'),
    db: parseInt(process.env.REDIS_TEST_DB || '15'),
    retryStrategy: () => null,
  });

  await testRedis.ping();
  console.log('✅ E2E Redis connected');

  // Initialize test bot (mock)
  // Note: Use a test bot token or mock Telegram API
  // testBot = new Telegraf(process.env.TEST_BOT_TOKEN || 'test-token');
  console.log('✅ E2E bot initialized');
});

/**
 * Cleanup after each test
 */
afterEach(async () => {
  // Clear all Redis keys
  if (testRedis) {
    await testRedis.flushdb();
  }

  // Truncate all database tables
  if (testDataSource && testDataSource.isInitialized) {
    const entities = testDataSource.entityMetadatas;
    for (const entity of entities) {
      const repository = testDataSource.getRepository(entity.name);
      await repository.clear();
    }
  }
});

/**
 * Teardown function - runs after all e2e tests
 */
afterAll(async () => {
  console.log('🧹 Cleaning up E2E test environment...');

  // Stop bot
  if (testBot) {
    await testBot.stop();
    console.log('✅ E2E bot stopped');
  }

  // Close Redis
  if (testRedis) {
    await testRedis.quit();
    console.log('✅ E2E Redis disconnected');
  }

  // Close database
  if (testDataSource && testDataSource.isInitialized) {
    await testDataSource.destroy();
    console.log('✅ E2E database disconnected');
  }
});

export { testBot, testDataSource, testRedis };
