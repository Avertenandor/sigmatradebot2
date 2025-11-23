/**
 * Crypto Utility
 * Cryptographic functions for password hashing and generation
 */

import bcrypt from 'bcrypt';
import crypto from 'crypto';
import { FINANCIAL_PASSWORD_CONFIG } from './constants';

/**
 * Generate random financial password
 * @returns Generated password string
 */
export const generateFinancialPassword = (): string => {
  const { LENGTH, CHARSET } = FINANCIAL_PASSWORD_CONFIG;
  let password = '';

  const randomBytes = crypto.randomBytes(LENGTH);

  for (let i = 0; i < LENGTH; i++) {
    const randomIndex = randomBytes[i] % CHARSET.length;
    password += CHARSET[randomIndex];
  }

  return password;
};

/**
 * Hash password using bcrypt
 * @param password - Plain text password
 * @returns Hashed password
 */
export const hashPassword = async (password: string): Promise<string> => {
  const salt = await bcrypt.genSalt(FINANCIAL_PASSWORD_CONFIG.BCRYPT_ROUNDS);
  return bcrypt.hash(password, salt);
};

/**
 * Verify password against hash
 * @param password - Plain text password
 * @param hash - Hashed password to compare against
 * @returns True if password matches
 */
export const verifyPassword = async (
  password: string,
  hash: string
): Promise<boolean> => {
  return bcrypt.compare(password, hash);
};

/**
 * Generate secure random token
 * @param length - Token length in bytes (default: 32)
 * @returns Hex string token
 */
export const generateToken = (length: number = 32): string => {
  return crypto.randomBytes(length).toString('hex');
};

/**
 * Generate referral code for user
 * @param userId - User ID
 * @returns Short referral code
 */
export const generateReferralCode = (userId: number): string => {
  // Create a deterministic but obscured code from user ID
  const buffer = Buffer.from(userId.toString());
  const hash = crypto.createHash('sha256').update(buffer).digest('hex');
  // Take first 8 characters
  return hash.substring(0, 8).toUpperCase();
};

/**
 * Generate UUID v4
 * @returns UUID string
 */
export const generateUUID = (): string => {
  return crypto.randomUUID();
};

/**
 * Hash string using SHA256
 * @param input - String to hash
 * @returns Hex string hash
 */
export const sha256 = (input: string): string => {
  return crypto.createHash('sha256').update(input).digest('hex');
};

/**
 * Generate HMAC signature
 * @param data - Data to sign
 * @param secret - Secret key
 * @returns HMAC signature
 */
export const generateHMAC = (data: string, secret: string): string => {
  return crypto.createHmac('sha256', secret).update(data).digest('hex');
};

/**
 * Verify HMAC signature
 * @param data - Original data
 * @param signature - Signature to verify
 * @param secret - Secret key
 * @returns True if signature is valid
 */
export const verifyHMAC = (
  data: string,
  signature: string,
  secret: string
): boolean => {
  const expectedSignature = generateHMAC(data, secret);
  return crypto.timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expectedSignature)
  );
};

/**
 * Encrypt data using AES-256-GCM
 * @param plaintext - Data to encrypt
 * @param key - Encryption key (32 bytes)
 * @returns Encrypted data with IV and auth tag
 */
export const encrypt = (
  plaintext: string,
  key: string
): { encrypted: string; iv: string; authTag: string } => {
  const iv = crypto.randomBytes(16);
  const keyBuffer = Buffer.from(key.padEnd(32, '0').substring(0, 32));

  const cipher = crypto.createCipheriv('aes-256-gcm', keyBuffer, iv);

  let encrypted = cipher.update(plaintext, 'utf8', 'hex');
  encrypted += cipher.final('hex');

  const authTag = cipher.getAuthTag();

  return {
    encrypted,
    iv: iv.toString('hex'),
    authTag: authTag.toString('hex'),
  };
};

/**
 * Decrypt data using AES-256-GCM
 * @param encrypted - Encrypted data
 * @param key - Decryption key (32 bytes)
 * @param iv - Initialization vector
 * @param authTag - Authentication tag
 * @returns Decrypted plaintext
 */
export const decrypt = (
  encrypted: string,
  key: string,
  iv: string,
  authTag: string
): string => {
  const keyBuffer = Buffer.from(key.padEnd(32, '0').substring(0, 32));
  const ivBuffer = Buffer.from(iv, 'hex');
  const authTagBuffer = Buffer.from(authTag, 'hex');

  const decipher = crypto.createDecipheriv('aes-256-gcm', keyBuffer, ivBuffer);
  decipher.setAuthTag(authTagBuffer);

  let decrypted = decipher.update(encrypted, 'hex', 'utf8');
  decrypted += decipher.final('utf8');

  return decrypted;
};

/**
 * Generate cryptographically secure random number
 * @param min - Minimum value (inclusive)
 * @param max - Maximum value (inclusive)
 * @returns Random number
 */
export const randomInt = (min: number, max: number): number => {
  const range = max - min + 1;
  const bytesNeeded = Math.ceil(Math.log2(range) / 8);
  const maxValue = Math.pow(256, bytesNeeded);
  const randomBytes = crypto.randomBytes(bytesNeeded);
  let randomValue = randomBytes.reduce((acc, byte) => acc * 256 + byte, 0);

  // Reject values that would cause bias
  while (randomValue >= maxValue - (maxValue % range)) {
    const newBytes = crypto.randomBytes(bytesNeeded);
    randomValue = newBytes.reduce((acc, byte) => acc * 256 + byte, 0);
  }

  return min + (randomValue % range);
};

/**
 * Mask sensitive data for logging
 * @param data - Sensitive data to mask
 * @param visibleChars - Number of visible characters (default: 4)
 * @returns Masked string
 */
export const maskSensitiveData = (
  data: string,
  visibleChars: number = 4
): string => {
  if (!data || data.length <= visibleChars) {
    return '***';
  }

  const visible = data.substring(0, visibleChars);
  const masked = '*'.repeat(Math.min(data.length - visibleChars, 10));

  return `${visible}${masked}`;
};

/**
 * Mask wallet address for display
 * Shows first 6 and last 4 characters
 * @param address - Wallet address
 * @returns Masked address (e.g., 0x1234...abcd)
 */
export const maskWalletAddress = (address: string): string => {
  if (!address || address.length < 10) {
    return address;
  }

  const start = address.substring(0, 6);
  const end = address.substring(address.length - 4);

  return `${start}...${end}`;
};

/**
 * Generate deterministic ID from string
 * Useful for generating consistent IDs from user data
 * @param input - Input string
 * @returns Numeric ID
 */
export const generateDeterministicId = (input: string): number => {
  const hash = crypto.createHash('sha256').update(input).digest();
  // Take first 8 bytes and convert to number
  return hash.readUInt32BE(0);
};

/**
 * Constant-time string comparison
 * Prevents timing attacks
 * @param a - First string
 * @param b - Second string
 * @returns True if strings are equal
 */
export const constantTimeEqual = (a: string, b: string): boolean => {
  if (a.length !== b.length) {
    return false;
  }

  return crypto.timingSafeEqual(Buffer.from(a), Buffer.from(b));
};

export default {
  generateFinancialPassword,
  hashPassword,
  verifyPassword,
  generateToken,
  generateReferralCode,
  generateUUID,
  sha256,
  generateHMAC,
  verifyHMAC,
  encrypt,
  decrypt,
  randomInt,
  maskSensitiveData,
  maskWalletAddress,
  generateDeterministicId,
  constantTimeEqual,
};
