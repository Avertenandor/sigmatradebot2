# Testing Guide

## Overview

This project uses **Jest** for testing with three test types:
- **Unit Tests**: Fast, isolated tests for individual functions
- **Integration Tests**: Tests involving database, Redis, and multiple components
- **E2E Tests**: Full user journey tests with real bot interactions

## Setup

### Prerequisites

1. **PostgreSQL** for test database:
```bash
# Create test database
createdb sigmatrade_test
```

2. **Redis** for test cache (uses separate DB 15):
```bash
# Redis should be running on localhost:6379
redis-cli ping  # Should return PONG
```

3. **Environment variables**:
```bash
# Copy test environment file
cp .env.test .env.test.local  # Optional: for local overrides
```

## Running Tests

### All Tests
```bash
npm test
```

### Unit Tests Only
```bash
npm test -- tests/unit
```

### Integration Tests Only
```bash
npm run test:integration
```

### E2E Tests Only
```bash
npm run test:e2e
```

### Watch Mode
```bash
npm run test:watch
```

### Coverage Report
```bash
npm run test:cov
# Opens coverage report in browser
open coverage/index.html
```

## Writing Tests

### Unit Test Example

```typescript
// tests/unit/my-service.test.ts
import { myFunction } from '../../src/services/my-service';

describe('MyService', () => {
  describe('myFunction', () => {
    it('should return expected result', () => {
      const result = myFunction('input');
      expect(result).toBe('expected');
    });

    it('should handle edge case', () => {
      expect(() => myFunction(null)).toThrow();
    });
  });
});
```

### Integration Test Example

```typescript
// tests/integration/user-flow.test.ts
import { createTestUser, clearDatabase } from '../helpers/database';
import { mockUsers } from '../fixtures/users';

describe('User Flow Integration', () => {
  beforeEach(async () => {
    await clearDatabase();
  });

  it('should create user and deposit', async () => {
    const user = await createTestUser(mockUsers.user1);
    // ... test database operations
  });
});
```

### E2E Test Example

```typescript
// tests/e2e/registration-flow.test.ts
import { createMockContext } from '../helpers/telegram-mock';
import { handleStart } from '../../src/bot/handlers/start.handler';

describe('Registration Flow E2E', () => {
  it('should complete full registration', async () => {
    const ctx = createMockContext();
    await handleStart(ctx);
    // ... test full user journey
  });
});
```

## Test Fixtures

Pre-defined test data available in `/tests/fixtures/`:

```typescript
import { mockUsers } from '../fixtures/users';
import { mockDeposits } from '../fixtures/deposits';

// Use in tests
const user = mockUsers.user1;
const deposit = mockDeposits.pendingDeposit;
```

## Test Helpers

Utility functions in `/tests/helpers/`:

```typescript
import { createTestUser, clearDatabase } from '../helpers/database';
import { createMockContext } from '../helpers/telegram-mock';

// Database helpers
const user = await createTestUser({...});
await clearDatabase();

// Telegram mocks
const ctx = createMockContext({ text: '/start' });
```

## Best Practices

### 1. Isolation
- Each test should be independent
- Use `beforeEach` to reset state
- Don't rely on test execution order

### 2. Clarity
- Test one thing per test
- Use descriptive test names
- Follow AAA pattern: Arrange, Act, Assert

### 3. Coverage
- Aim for 80%+ coverage
- Test happy path and edge cases
- Test error handling

### 4. Performance
- Keep unit tests fast (<100ms)
- Use mocks for external dependencies
- Run integration tests in CI only if slow

### 5. Data Management
- Use fixtures for consistent test data
- Clear database after each test
- Don't use production data

## Debugging Tests

### Run Single Test File
```bash
npm test -- tests/unit/my-test.test.ts
```

### Run Single Test Suite
```bash
npm test -- -t "MyService"
```

### Run With Debugging
```bash
node --inspect-brk node_modules/.bin/jest --runInBand
```

### View Test Output
```bash
npm test -- --verbose
```

## CI/CD Integration

Tests run automatically on:
- Pull requests
- Pushes to main branch
- Before deployment

## Troubleshooting

### Database Connection Issues
```bash
# Check PostgreSQL is running
pg_isready

# Check test database exists
psql -l | grep sigmatrade_test

# Reset test database
npm run schema:drop -- --config .env.test
npm run schema:sync -- --config .env.test
```

### Redis Connection Issues
```bash
# Check Redis is running
redis-cli ping

# Clear test Redis DB
redis-cli -n 15 FLUSHDB
```

### Jest Configuration Issues
```bash
# Clear Jest cache
npx jest --clearCache

# Run tests with no cache
npm test -- --no-cache
```

## Coverage Goals

| Type | Target |
|------|--------|
| **Statements** | 80% |
| **Branches** | 70% |
| **Functions** | 70% |
| **Lines** | 80% |

## Resources

- [Jest Documentation](https://jestjs.io/docs/getting-started)
- [ts-jest Documentation](https://kulshekhar.github.io/ts-jest/)
- [Testing Best Practices](https://github.com/goldbergyoni/javascript-testing-best-practices)
