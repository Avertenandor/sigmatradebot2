/**
 * Money Utilities
 *
 * Utilities for precise financial calculations using bigint arithmetic.
 * NEVER use parseFloat or Number() for money - use these functions instead.
 *
 * Critical: Floating point arithmetic is imprecise and can lead to
 * financial losses in production (e.g., 0.1 + 0.2 !== 0.3)
 *
 * @see https://docs.ethers.org/v6/api/utils/#about-units
 */

import { ethers } from 'ethers';
import { logger } from './logger.util';

/**
 * USDT decimals on BSC (same as most stablecoins)
 */
export const USDT_DECIMALS = 6;

/**
 * Internal representation uses 18 decimals for maximum precision
 */
export const INTERNAL_DECIMALS = 18;

/**
 * Money amount represented as bigint with internal precision
 * This ensures all calculations are exact (no floating point errors)
 */
export type MoneyAmount = {
  /** The amount in smallest units (wei-like) */
  value: bigint;
  /** Number of decimal places */
  decimals: number;
};

/**
 * Create MoneyAmount from USDT wei value (from blockchain)
 */
export function fromUsdtWei(value: bigint): MoneyAmount {
  // Convert from 6 decimals (USDT) to 18 decimals (internal)
  const scaleFactor = BigInt(10) ** BigInt(INTERNAL_DECIMALS - USDT_DECIMALS);
  return {
    value: value * scaleFactor,
    decimals: INTERNAL_DECIMALS,
  };
}

/**
 * Create MoneyAmount from human-readable USDT string
 * Example: "100.50" -> MoneyAmount
 */
export function fromUsdtString(amount: string): MoneyAmount {
  try {
    const parsed = ethers.parseUnits(amount, INTERNAL_DECIMALS);
    return {
      value: parsed,
      decimals: INTERNAL_DECIMALS,
    };
  } catch (error) {
    logger.error('Failed to parse USDT amount', { amount, error });
    throw new Error(`Invalid USDT amount: ${amount}`);
  }
}

/**
 * Convert MoneyAmount to human-readable USDT string
 * Example: MoneyAmount -> "100.50"
 */
export function toUsdtString(amount: MoneyAmount, maxDecimals = 8): string {
  const formatted = ethers.formatUnits(amount.value, amount.decimals);

  // Trim to max decimals to avoid ultra-long strings
  const parts = formatted.split('.');
  if (parts.length === 2 && parts[1].length > maxDecimals) {
    return `${parts[0]}.${parts[1].substring(0, maxDecimals)}`;
  }

  return formatted;
}

/**
 * Convert MoneyAmount to database string (decimal precision)
 * Uses 8 decimal places for storage (matches database schema)
 */
export function toDbString(amount: MoneyAmount): string {
  return toUsdtString(amount, 8);
}

/**
 * Convert database string back to MoneyAmount
 */
export function fromDbString(amount: string): MoneyAmount {
  return fromUsdtString(amount);
}

/**
 * Compare two money amounts
 * Returns: -1 if a < b, 0 if a === b, 1 if a > b
 */
export function compare(a: MoneyAmount, b: MoneyAmount): number {
  // Ensure same decimals for comparison
  const aNormalized = normalize(a, INTERNAL_DECIMALS);
  const bNormalized = normalize(b, INTERNAL_DECIMALS);

  if (aNormalized.value < bNormalized.value) return -1;
  if (aNormalized.value > bNormalized.value) return 1;
  return 0;
}

/**
 * Check if two amounts are equal
 */
export function equals(a: MoneyAmount, b: MoneyAmount): boolean {
  return compare(a, b) === 0;
}

/**
 * Check if a > b
 */
export function greaterThan(a: MoneyAmount, b: MoneyAmount): boolean {
  return compare(a, b) > 0;
}

/**
 * Check if a >= b
 */
export function greaterThanOrEqual(a: MoneyAmount, b: MoneyAmount): boolean {
  return compare(a, b) >= 0;
}

/**
 * Check if a < b
 */
export function lessThan(a: MoneyAmount, b: MoneyAmount): boolean {
  return compare(a, b) < 0;
}

/**
 * Check if a <= b
 */
export function lessThanOrEqual(a: MoneyAmount, b: MoneyAmount): boolean {
  return compare(a, b) <= 0;
}

/**
 * Add two money amounts
 */
export function add(a: MoneyAmount, b: MoneyAmount): MoneyAmount {
  const aNormalized = normalize(a, INTERNAL_DECIMALS);
  const bNormalized = normalize(b, INTERNAL_DECIMALS);

  return {
    value: aNormalized.value + bNormalized.value,
    decimals: INTERNAL_DECIMALS,
  };
}

/**
 * Subtract b from a
 */
export function subtract(a: MoneyAmount, b: MoneyAmount): MoneyAmount {
  const aNormalized = normalize(a, INTERNAL_DECIMALS);
  const bNormalized = normalize(b, INTERNAL_DECIMALS);

  return {
    value: aNormalized.value - bNormalized.value,
    decimals: INTERNAL_DECIMALS,
  };
}

/**
 * Multiply money amount by integer multiplier
 */
export function multiply(amount: MoneyAmount, multiplier: number | bigint): MoneyAmount {
  const mult = typeof multiplier === 'number' ? BigInt(Math.floor(multiplier)) : multiplier;

  return {
    value: amount.value * mult,
    decimals: amount.decimals,
  };
}

/**
 * Multiply by percentage (e.g., 5% = 0.05)
 * Uses basis points for precision (1% = 100 basis points)
 */
export function multiplyByPercentage(amount: MoneyAmount, percentage: number): MoneyAmount {
  // Convert percentage to basis points (avoid floating point)
  const basisPoints = BigInt(Math.floor(percentage * 10000)); // 5% = 500 basis points

  return {
    value: (amount.value * basisPoints) / BigInt(10000),
    decimals: amount.decimals,
  };
}

/**
 * Check if amount is within tolerance of target
 * Returns: { matches: boolean, difference: MoneyAmount }
 */
export function isWithinTolerance(
  actual: MoneyAmount,
  expected: MoneyAmount,
  tolerance: MoneyAmount
): { matches: boolean; difference: MoneyAmount; percentDiff: string } {
  const diff = subtract(actual, expected);
  const absDiff: MoneyAmount = {
    value: diff.value < 0n ? -diff.value : diff.value,
    decimals: diff.decimals,
  };

  const matches = lessThanOrEqual(absDiff, tolerance);

  // Calculate percentage difference for logging
  let percentDiff = '0';
  if (expected.value !== 0n) {
    // (actual - expected) / expected * 100
    const percentBigInt = (diff.value * BigInt(10000)) / expected.value;
    percentDiff = (Number(percentBigInt) / 100).toFixed(2);
  }

  return {
    matches,
    difference: diff,
    percentDiff,
  };
}

/**
 * Absolute value of money amount
 */
export function abs(amount: MoneyAmount): MoneyAmount {
  return {
    value: amount.value < 0n ? -amount.value : amount.value,
    decimals: amount.decimals,
  };
}

/**
 * Check if amount is zero
 */
export function isZero(amount: MoneyAmount): boolean {
  return amount.value === 0n;
}

/**
 * Check if amount is positive (> 0)
 */
export function isPositive(amount: MoneyAmount): boolean {
  return amount.value > 0n;
}

/**
 * Check if amount is negative (< 0)
 */
export function isNegative(amount: MoneyAmount): boolean {
  return amount.value < 0n;
}

/**
 * Get zero amount
 */
export function zero(): MoneyAmount {
  return {
    value: 0n,
    decimals: INTERNAL_DECIMALS,
  };
}

/**
 * Normalize money amount to specific decimal precision
 * Internal helper function
 */
function normalize(amount: MoneyAmount, targetDecimals: number): MoneyAmount {
  if (amount.decimals === targetDecimals) {
    return amount;
  }

  if (amount.decimals < targetDecimals) {
    // Scale up
    const scale = BigInt(10) ** BigInt(targetDecimals - amount.decimals);
    return {
      value: amount.value * scale,
      decimals: targetDecimals,
    };
  } else {
    // Scale down (may lose precision)
    const scale = BigInt(10) ** BigInt(amount.decimals - targetDecimals);
    return {
      value: amount.value / scale,
      decimals: targetDecimals,
    };
  }
}

/**
 * Format money for display in Telegram messages
 * Example: "100.50 USDT"
 */
export function formatForDisplay(amount: MoneyAmount, currency = 'USDT'): string {
  const formatted = toUsdtString(amount, 2); // 2 decimals for display
  return `${formatted} ${currency}`;
}

/**
 * Validate that string is a valid money amount
 */
export function isValidAmount(amount: string): boolean {
  try {
    const parsed = ethers.parseUnits(amount, USDT_DECIMALS);
    return parsed >= 0n;
  } catch {
    return false;
  }
}

/**
 * Sum array of money amounts
 */
export function sum(amounts: MoneyAmount[]): MoneyAmount {
  return amounts.reduce(
    (acc, amount) => add(acc, amount),
    zero()
  );
}

/**
 * Get minimum of two amounts
 */
export function min(a: MoneyAmount, b: MoneyAmount): MoneyAmount {
  return lessThan(a, b) ? a : b;
}

/**
 * Get maximum of two amounts
 */
export function max(a: MoneyAmount, b: MoneyAmount): MoneyAmount {
  return greaterThan(a, b) ? a : b;
}

/**
 * Format USDT amount for user-facing messages
 * Always uses 2 decimal places for consistency
 * Example: 100.5 -> "100.50", 10 -> "10.00"
 */
export function formatUSDT(amount: number): string {
  return amount.toFixed(2);
}

/**
 * Format USDT amount with currency suffix
 * Example: 100.5 -> "100.50 USDT"
 */
export function formatUSDTWithCurrency(amount: number): string {
  return `${formatUSDT(amount)} USDT`;
}
