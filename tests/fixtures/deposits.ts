/**
 * Deposit Test Fixtures
 * Predefined test data for deposits
 */

import { Deposit } from '../../src/database/entities/Deposit.entity';
import { TransactionStatus } from '../../src/utils/constants';

export const mockDeposits = {
  /**
   * Pending deposit without transaction hash
   */
  pendingDeposit: {
    user_id: 1,
    level: 1,
    amount: '10',
    tx_hash: null,
    status: TransactionStatus.PENDING,
    block_number: null,
    confirmed_at: null,
  } as Partial<Deposit>,

  /**
   * Pending deposit with transaction hash
   */
  pendingWithTxHash: {
    user_id: 1,
    level: 1,
    amount: '10',
    tx_hash: '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
    status: TransactionStatus.PENDING,
    block_number: 12345678,
    confirmed_at: null,
  } as Partial<Deposit>,

  /**
   * Confirmed deposit
   */
  confirmedDeposit: {
    user_id: 1,
    level: 1,
    amount: '10',
    tx_hash: '0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
    status: TransactionStatus.CONFIRMED,
    block_number: 12345678,
    confirmed_at: new Date(),
  } as Partial<Deposit>,

  /**
   * Failed deposit
   */
  failedDeposit: {
    user_id: 1,
    level: 1,
    amount: '10',
    tx_hash: '0x9999999999999999999999999999999999999999999999999999999999999999',
    status: TransactionStatus.FAILED,
    block_number: 12345678,
    confirmed_at: null,
  } as Partial<Deposit>,

  /**
   * Level 2 deposit (50 USDT)
   */
  level2Deposit: {
    user_id: 1,
    level: 2,
    amount: '50',
    tx_hash: null,
    status: TransactionStatus.PENDING,
    block_number: null,
    confirmed_at: null,
  } as Partial<Deposit>,

  /**
   * Level 5 deposit (300 USDT)
   */
  level5Deposit: {
    user_id: 1,
    level: 5,
    amount: '300',
    tx_hash: null,
    status: TransactionStatus.PENDING,
    block_number: null,
    confirmed_at: null,
  } as Partial<Deposit>,
};

/**
 * Create a custom deposit fixture
 */
export function createDepositFixture(overrides: Partial<Deposit> = {}): Partial<Deposit> {
  return {
    user_id: 1,
    level: 1,
    amount: '10',
    tx_hash: null,
    status: TransactionStatus.PENDING,
    block_number: null,
    confirmed_at: null,
    ...overrides,
  };
}

/**
 * Generate random transaction hash (for testing)
 */
export function generateTxHash(): string {
  const chars = '0123456789abcdef';
  let hash = '0x';
  for (let i = 0; i < 64; i++) {
    hash += chars[Math.floor(Math.random() * chars.length)];
  }
  return hash;
}
