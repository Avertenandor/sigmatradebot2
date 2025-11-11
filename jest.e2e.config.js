/**
 * Jest Configuration - End-to-End Tests
 * Full user journey tests with real bot interactions
 */

const baseConfig = require('./jest.config');

module.exports = {
  ...baseConfig,

  // Test match patterns (e2e tests only)
  testMatch: [
    '<rootDir>/tests/e2e/**/*.test.ts',
    '<rootDir>/tests/e2e/**/*.spec.ts',
  ],

  // Setup files - use e2e-specific setup
  setupFilesAfterEnv: [
    '<rootDir>/tests/setup.ts',
    '<rootDir>/tests/setup.e2e.ts',
  ],

  // Very long timeout for e2e tests
  testTimeout: 60000, // 60 seconds

  // Run tests serially
  maxWorkers: 1,

  // Don't collect coverage for e2e (too slow)
  collectCoverage: false,
};
