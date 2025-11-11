/**
 * Example Integration Test
 * Tests for user registration flow
 */

import { createTestUser, clearDatabase, findUserByTelegramId } from '../helpers/database';
import { mockUsers } from '../fixtures/users';

describe('User Registration Integration', () => {
  beforeEach(async () => {
    // Clear database before each test
    await clearDatabase();
  });

  it('should create a new user in database', async () => {
    const userData = mockUsers.user1;

    const user = await createTestUser(userData);

    expect(user.id).toBeDefined();
    expect(user.telegram_id).toBe(userData.telegram_id);
    expect(user.wallet_address).toBe(userData.wallet_address);
    expect(user.is_verified).toBe(false);
    expect(user.is_banned).toBe(false);
  });

  it('should find user by telegram ID', async () => {
    const userData = mockUsers.user1;
    await createTestUser(userData);

    const foundUser = await findUserByTelegramId(userData.telegram_id!);

    expect(foundUser).not.toBeNull();
    expect(foundUser?.telegram_id).toBe(userData.telegram_id);
  });

  it('should create user with referrer relationship', async () => {
    // Create referrer first
    const referrer = await createTestUser(mockUsers.user1);

    // Create user with referrer
    const userData = {
      ...mockUsers.user3,
      referrer_id: referrer.id,
    };

    const user = await createTestUser(userData);

    expect(user.referrer_id).toBe(referrer.id);
  });

  it('should not allow duplicate telegram IDs', async () => {
    const userData = mockUsers.user1;

    // Create first user
    await createTestUser(userData);

    // Try to create duplicate
    await expect(createTestUser(userData)).rejects.toThrow();
  });

  it('should not allow duplicate wallet addresses', async () => {
    const user1 = await createTestUser(mockUsers.user1);

    const user2Data = {
      ...mockUsers.user2,
      wallet_address: user1.wallet_address, // Same wallet
    };

    await expect(createTestUser(user2Data)).rejects.toThrow();
  });
});
