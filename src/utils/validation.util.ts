/**
 * Validation Utility
 * Joi-based validation schemas for all user inputs
 */

import Joi from 'joi';
import { REGEX_PATTERNS, DEPOSIT_LEVELS } from './constants';
import { getAddress, isAddress } from 'ethers';
import { createLogger } from './logger.util';

const logger = createLogger('ValidationUtil');

/**
 * Validate BSC wallet address
 */
export const walletAddressSchema = Joi.string()
  .pattern(REGEX_PATTERNS.BSC_ADDRESS)
  .required()
  .messages({
    'string.pattern.base': 'Адрес кошелька должен начинаться с 0x и содержать 42 символа',
    'any.required': 'Адрес кошелька обязателен',
  });

/**
 * Validate transaction hash
 */
export const transactionHashSchema = Joi.string()
  .pattern(REGEX_PATTERNS.TRANSACTION_HASH)
  .required()
  .messages({
    'string.pattern.base': 'Неверный формат хеша транзакции',
    'any.required': 'Хеш транзакции обязателен',
  });

/**
 * Validate email
 */
export const emailSchema = Joi.string()
  .pattern(REGEX_PATTERNS.EMAIL)
  .optional()
  .allow('')
  .messages({
    'string.pattern.base': 'Неверный формат email адреса',
  });

/**
 * Validate phone number (international format)
 */
export const phoneSchema = Joi.string()
  .pattern(REGEX_PATTERNS.PHONE)
  .optional()
  .allow('')
  .messages({
    'string.pattern.base': 'Неверный формат номера телефона. Используйте международный формат',
  });

/**
 * Validate Telegram username
 */
export const telegramUsernameSchema = Joi.string()
  .pattern(REGEX_PATTERNS.TELEGRAM_USERNAME)
  .required()
  .messages({
    'string.pattern.base': 'Неверный формат Telegram username',
    'any.required': 'Telegram username обязателен',
  });

/**
 * Validate Telegram ID
 */
export const telegramIdSchema = Joi.number()
  .integer()
  .positive()
  .required()
  .messages({
    'number.base': 'Telegram ID должен быть числом',
    'number.positive': 'Telegram ID должен быть положительным',
    'any.required': 'Telegram ID обязателен',
  });

/**
 * Validate deposit level
 */
export const depositLevelSchema = Joi.number()
  .integer()
  .min(1)
  .max(5)
  .required()
  .messages({
    'number.base': 'Уровень депозита должен быть числом',
    'number.min': 'Уровень депозита должен быть от 1 до 5',
    'number.max': 'Уровень депозита должен быть от 1 до 5',
    'any.required': 'Уровень депозита обязателен',
  });

/**
 * Validate deposit amount
 */
export const depositAmountSchema = Joi.number()
  .valid(...Object.values(DEPOSIT_LEVELS))
  .required()
  .messages({
    'any.only': `Сумма депозита должна быть одной из: ${Object.values(DEPOSIT_LEVELS).join(', ')} USDT`,
    'any.required': 'Сумма депозита обязательна',
  });

/**
 * Validate financial password
 */
export const financialPasswordSchema = Joi.string()
  .min(8)
  .max(32)
  .pattern(/^[a-zA-Z0-9!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]*$/)
  .required()
  .messages({
    'string.min': 'Пароль должен содержать минимум 8 символов',
    'string.max': 'Пароль должен содержать максимум 32 символа',
    'string.pattern.base': 'Пароль содержит недопустимые символы',
    'any.required': 'Пароль обязателен',
  });

/**
 * User registration schema
 */
export const userRegistrationSchema = Joi.object({
  telegramId: telegramIdSchema,
  username: Joi.string().optional().allow(null, ''),
  walletAddress: walletAddressSchema,
  referrerId: Joi.number().integer().positive().optional().allow(null),
});

/**
 * User verification schema
 */
export const userVerificationSchema = Joi.object({
  userId: Joi.number().integer().positive().required(),
  phone: phoneSchema,
  email: emailSchema,
});

/**
 * Deposit creation schema
 */
export const depositCreationSchema = Joi.object({
  userId: Joi.number().integer().positive().required(),
  level: depositLevelSchema,
  amount: depositAmountSchema,
  txHash: transactionHashSchema,
});

/**
 * Transaction schema
 */
export const transactionSchema = Joi.object({
  userId: Joi.number().integer().positive().optional().allow(null),
  txHash: transactionHashSchema,
  type: Joi.string().valid('deposit', 'referral_reward', 'system_payout').required(),
  amount: Joi.number().positive().required(),
  fromAddress: walletAddressSchema,
  toAddress: walletAddressSchema,
  blockNumber: Joi.number().integer().positive().optional(),
});

/**
 * Admin action schema
 */
export const adminActionSchema = Joi.object({
  adminId: telegramIdSchema,
  action: Joi.string().required(),
  targetUserId: Joi.number().integer().positive().optional(),
  details: Joi.object().optional(),
});

/**
 * Broadcast message schema
 */
export const broadcastMessageSchema = Joi.object({
  message: Joi.string().min(1).max(4096).required().messages({
    'string.min': 'Сообщение не может быть пустым',
    'string.max': 'Сообщение слишком длинное (максимум 4096 символов)',
  }),
});

/**
 * Pagination schema
 */
export const paginationSchema = Joi.object({
  page: Joi.number().integer().min(1).default(1),
  limit: Joi.number().integer().min(1).max(100).default(10),
});

/**
 * Date range schema
 */
export const dateRangeSchema = Joi.object({
  startDate: Joi.date().optional(),
  endDate: Joi.date().optional().min(Joi.ref('startDate')).messages({
    'date.min': 'Дата окончания должна быть после даты начала',
  }),
});

/**
 * Referral link schema
 */
export const referralLinkSchema = Joi.object({
  referrerId: Joi.number().integer().positive().required(),
});

/**
 * Helper function to validate data against schema
 */
export const validate = <T>(
  schema: Joi.Schema,
  data: unknown
): { value: T; error: string | null } => {
  const { value, error } = schema.validate(data, {
    abortEarly: false,
    stripUnknown: true,
  });

  if (error) {
    const errorMessage = error.details.map((detail) => detail.message).join('; ');
    return { value: value as T, error: errorMessage };
  }

  return { value: value as T, error: null };
};

/**
 * Async validation helper
 */
export const validateAsync = async <T>(
  schema: Joi.Schema,
  data: unknown
): Promise<{ value: T; error: string | null }> => {
  try {
    const value = await schema.validateAsync(data, {
      abortEarly: false,
      stripUnknown: true,
    });
    return { value: value as T, error: null };
  } catch (error) {
    if (error instanceof Joi.ValidationError) {
      const errorMessage = error.details.map((detail) => detail.message).join('; ');
      return { value: null as T, error: errorMessage };
    }
    throw error;
  }
};

/**
 * Validate BSC address format with EIP-55 checksum
 * FIX #15: Strict checksum validation to prevent typos
 */
export const isValidBSCAddress = (address: string): boolean => {
  if (!address || typeof address !== 'string') {
    return false;
  }

  // Basic format check (must start with 0x and have 40 hex chars)
  if (!/^0x[a-fA-F0-9]{40}$/.test(address)) {
    return false;
  }

  // FIX #15: EIP-55 checksum validation using ethers
  // This catches typos and invalid addresses
  try {
    getAddress(address); // Throws if invalid checksum
    return true;
  } catch (error) {
    logger.warn('Invalid address checksum', { address });
    return false;
  }
};

/**
 * Validate transaction hash format
 */
export const isValidTransactionHash = (hash: string): boolean => {
  return REGEX_PATTERNS.TRANSACTION_HASH.test(hash);
};

/**
 * Validate email format
 */
export const isValidEmail = (email: string): boolean => {
  return REGEX_PATTERNS.EMAIL.test(email);
};

/**
 * Validate phone format
 */
export const isValidPhone = (phone: string): boolean => {
  return REGEX_PATTERNS.PHONE.test(phone);
};

/**
 * Sanitize user input (basic XSS prevention)
 */
export const sanitizeInput = (input: string): string => {
  return input
    .replace(/[<>]/g, '') // Remove < and >
    .replace(/javascript:/gi, '') // Remove javascript: protocol
    .replace(/on\w+=/gi, '') // Remove event handlers
    .trim();
};

/**
 * Validate and sanitize message text
 */
export const validateMessageText = (text: string): { valid: boolean; message: string } => {
  if (!text || text.trim().length === 0) {
    return { valid: false, message: 'Сообщение не может быть пустым' };
  }

  if (text.length > 4096) {
    return { valid: false, message: 'Сообщение слишком длинное (максимум 4096 символов)' };
  }

  return { valid: true, message: '' };
};

/**
 * Normalize wallet address to EIP-55 checksummed format
 * FIX #15: Returns proper checksummed address
 */
export const normalizeWalletAddress = (address: string): string => {
  try {
    // getAddress returns the checksummed version
    return getAddress(address);
  } catch (error) {
    // If invalid, return lowercase for backward compatibility
    logger.warn('Failed to normalize address, returning lowercase', { address });
    return address.toLowerCase().trim();
  }
};

/**
 * Check if address has correct EIP-55 checksum
 * FIX #15: Validate that the case matches the checksum
 */
export const hasValidChecksum = (address: string): boolean => {
  try {
    const checksummed = getAddress(address);
    return checksummed === address; // Exact match (case-sensitive)
  } catch {
    return false;
  }
};

/**
 * Normalize telegram username
 */
export const normalizeTelegramUsername = (username: string): string => {
  return username.replace(/^@/, '').toLowerCase().trim();
};

/**
 * Safe parseFloat with validation
 * Returns null if value is NaN, Infinity, or invalid
 */
export const safeParseFloat = (value: string | number): number | null => {
  const parsed = typeof value === 'string' ? parseFloat(value) : value;

  // Check for invalid values
  if (isNaN(parsed) || !isFinite(parsed)) {
    return null;
  }

  return parsed;
};

/**
 * Validate financial amount
 * Returns validated and rounded amount or null if invalid
 */
export const validateFinancialAmount = (
  amount: string | number,
  options: {
    min?: number;
    max?: number;
    decimals?: number;
  } = {}
): { valid: boolean; value: number | null; error?: string } => {
  const { min = 0, max = 1000000, decimals = 2 } = options;

  const parsed = safeParseFloat(amount);

  if (parsed === null) {
    return { valid: false, value: null, error: 'Неверный формат числа' };
  }

  if (parsed <= min) {
    return { valid: false, value: null, error: `Сумма должна быть больше ${min}` };
  }

  if (parsed > max) {
    return { valid: false, value: null, error: `Сумма не может превышать ${max.toLocaleString()}` };
  }

  // Round to specified decimal places
  const rounded = Math.round(parsed * Math.pow(10, decimals)) / Math.pow(10, decimals);

  return { valid: true, value: rounded };
};

/**
 * Format transaction hash for display
 * Returns shortened hash or fallback text if invalid
 */
export const formatTxHash = (txHash: string | null | undefined, fallback: string = 'Ожидает подтверждения'): string => {
  if (!txHash || txHash.length < 16) {
    return fallback;
  }

  // Show first 10 and last 6 characters
  return `${txHash.substring(0, 10)}...${txHash.substring(txHash.length - 6)}`;
};

export default {
  validate,
  validateAsync,
  isValidBSCAddress,
  isValidTransactionHash,
  isValidEmail,
  isValidPhone,
  sanitizeInput,
  validateMessageText,
  normalizeWalletAddress,
  hasValidChecksum,
  normalizeTelegramUsername,
  safeParseFloat,
  validateFinancialAmount,
  formatTxHash,
};
