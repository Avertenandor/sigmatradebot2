/**
 * User Test Fixtures
 * Predefined test data for users
 */

import { User } from '../../src/database/entities/User.entity';

export const mockUsers = {
  /**
   * Regular user without referrer
   */
  user1: {
    telegram_id: 123456789,
    username: 'testuser1',
    wallet_address: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
    financial_password: '$2b$12$abcdefghijklmnopqrstuvwxyz1234567', // bcrypt hash
    is_verified: false,
    is_banned: false,
    referrer_id: null,
  } as Partial<User>,

  /**
   * Verified user
   */
  user2: {
    telegram_id: 987654321,
    username: 'testuser2',
    wallet_address: '0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed',
    financial_password: '$2b$12$zyxwvutsrqponmlkjihgfedcba9876543',
    phone: '+1234567890',
    email: 'test@example.com',
    is_verified: true,
    is_banned: false,
    referrer_id: null,
  } as Partial<User>,

  /**
   * User with referrer
   */
  user3: {
    telegram_id: 555555555,
    username: 'testuser3',
    wallet_address: '0xfB6916095ca1df60bB79Ce92cE3Ea74c37c5d359',
    financial_password: '$2b$12$password_hash_here',
    is_verified: false,
    is_banned: false,
    referrer_id: 1, // Refers to user1's ID in database
  } as Partial<User>,

  /**
   * Banned user
   */
  bannedUser: {
    telegram_id: 999999999,
    username: 'banneduser',
    wallet_address: '0x4bbeEB066eD09B7AEd07bF39EEe0460DFa261520',
    financial_password: '$2b$12$banned_user_password_hash',
    is_verified: true,
    is_banned: true,
    referrer_id: null,
  } as Partial<User>,

  /**
   * Admin user
   */
  adminUser: {
    telegram_id: 111111111,
    username: 'adminuser',
    wallet_address: '0x78731D3Ca6b7E34aC0F824c42a7cC18A495cabaB',
    financial_password: '$2b$12$admin_password_hash',
    is_verified: true,
    is_banned: false,
    referrer_id: null,
  } as Partial<User>,
};

/**
 * Create a custom user fixture
 */
export function createUserFixture(overrides: Partial<User> = {}): Partial<User> {
  return {
    telegram_id: Math.floor(Math.random() * 1000000000),
    username: `testuser_${Date.now()}`,
    wallet_address: generateRandomWalletAddress(),
    financial_password: '$2b$12$default_test_password_hash',
    is_verified: false,
    is_banned: false,
    referrer_id: null,
    ...overrides,
  };
}

/**
 * Generate random wallet address (not real, for testing only)
 */
function generateRandomWalletAddress(): string {
  const chars = '0123456789abcdef';
  let address = '0x';
  for (let i = 0; i < 40; i++) {
    address += chars[Math.floor(Math.random() * chars.length)];
  }
  return address;
}
