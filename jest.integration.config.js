/**
 * Jest Configuration - Integration Tests
 * Tests involving multiple components, database, Redis, etc.
 */

const baseConfig = require('./jest.config');

module.exports = {
  ...baseConfig,

  // Test match patterns (integration tests only)
  testMatch: [
    '<rootDir>/tests/integration/**/*.test.ts',
    '<rootDir>/tests/integration/**/*.spec.ts',
  ],

  // Setup files - use integration-specific setup
  setupFilesAfterEnv: [
    '<rootDir>/tests/setup.ts',
    '<rootDir>/tests/setup.integration.ts',
  ],

  // Longer timeout for integration tests
  testTimeout: 30000, // 30 seconds

  // Don't force exit (let connections close gracefully)
  forceExit: false,

  // Run tests serially (not in parallel) to avoid database conflicts
  maxWorkers: 1,
};
