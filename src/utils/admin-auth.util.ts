/**
 * Admin Authentication Utilities
 * Handles master key generation, hashing, and session management
 */

import crypto from 'crypto';
import bcrypt from 'bcrypt';

/**
 * Generate a secure random master key
 * Format: XXXX-XXXX-XXXX-XXXX (16 characters, easy to read)
 */
export function generateMasterKey(): string {
  const characters = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // Removed confusing chars (0,O,I,1)
  const segments = 4;
  const segmentLength = 4;

  const parts: string[] = [];

  for (let i = 0; i < segments; i++) {
    let segment = '';
    for (let j = 0; j < segmentLength; j++) {
      const randomIndex = crypto.randomInt(0, characters.length);
      segment += characters[randomIndex];
    }
    parts.push(segment);
  }

  return parts.join('-');
}

/**
 * Hash master key for secure storage
 */
export async function hashMasterKey(masterKey: string): Promise<string> {
  const saltRounds = 12;
  return await bcrypt.hash(masterKey, saltRounds);
}

/**
 * Verify master key against hashed value
 */
export async function verifyMasterKey(
  masterKey: string,
  hashedMasterKey: string
): Promise<boolean> {
  return await bcrypt.compare(masterKey, hashedMasterKey);
}

/**
 * Generate a secure session token
 */
export function generateSessionToken(): string {
  return crypto.randomBytes(32).toString('hex');
}

/**
 * Calculate session expiration time (1 hour from now)
 */
export function getSessionExpiration(): Date {
  return new Date(Date.now() + 60 * 60 * 1000); // 1 hour
}

/**
 * Format master key for display (with partial masking)
 * Example: ABCD-****-****-WXYZ
 */
export function maskMasterKey(masterKey: string): string {
  const parts = masterKey.split('-');
  if (parts.length !== 4) return '****-****-****-****';

  return `${parts[0]}-****-****-${parts[3]}`;
}

/**
 * Validate master key format
 */
export function isValidMasterKeyFormat(masterKey: string): boolean {
  // Format: XXXX-XXXX-XXXX-XXXX
  const regex = /^[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}$/;
  return regex.test(masterKey);
}
