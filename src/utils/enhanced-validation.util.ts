/**
 * Enhanced Input Validation Utilities
 * Additional validation helpers for improved security and UX
 */

import { logger } from './logger.util';

/**
 * Sanitize text input to prevent XSS and injection attacks
 */
export const sanitizeTextInput = (input: string, maxLength: number = 1000): string => {
  if (!input || typeof input !== 'string') {
    return '';
  }

  let sanitized = input
    .trim()
    // Remove HTML tags
    .replace(/<[^>]*>/g, '')
    // Remove script tags even if malformed
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
    // Remove javascript: protocol
    .replace(/javascript:/gi, '')
    // Remove event handlers
    .replace(/on\w+\s*=\s*["'][^"']*["']/gi, '')
    // Remove null bytes
    .replace(/\0/g, '')
    // Normalize whitespace
    .replace(/\s+/g, ' ')
    .trim();

  // Truncate if too long
  if (sanitized.length > maxLength) {
    sanitized = sanitized.substring(0, maxLength);
  }

  return sanitized;
};

/**
 * Validate numeric input with constraints
 */
export interface NumericValidationOptions {
  min?: number;
  max?: number;
  allowNegative?: boolean;
  allowFloat?: boolean;
  allowZero?: boolean;
}

export const validateNumericInput = (
  input: string | number,
  options: NumericValidationOptions = {}
): { valid: boolean; value: number | null; error?: string } => {
  const {
    min,
    max,
    allowNegative = false,
    allowFloat = true,
    allowZero = true,
  } = options;

  // Parse input
  const parsed = typeof input === 'string' ? parseFloat(input) : input;

  // Check if valid number
  if (isNaN(parsed) || !isFinite(parsed)) {
    return { valid: false, value: null, error: 'Некорректное числовое значение' };
  }

  // Check if integer required
  if (!allowFloat && !Number.isInteger(parsed)) {
    return { valid: false, value: null, error: 'Требуется целое число' };
  }

  // Check negative
  if (!allowNegative && parsed < 0) {
    return { valid: false, value: null, error: 'Отрицательные значения не допускаются' };
  }

  // Check zero
  if (!allowZero && parsed === 0) {
    return { valid: false, value: null, error: 'Значение не может быть нулевым' };
  }

  // Check min
  if (min !== undefined && parsed < min) {
    return {
      valid: false,
      value: null,
      error: `Минимальное значение: ${min}`,
    };
  }

  // Check max
  if (max !== undefined && parsed > max) {
    return {
      valid: false,
      value: null,
      error: `Максимальное значение: ${max}`,
    };
  }

  return { valid: true, value: parsed };
};

/**
 * Validate telegram username
 */
export const validateTelegramUsername = (username: string): {
  valid: boolean;
  normalized?: string;
  error?: string;
} => {
  if (!username || typeof username !== 'string') {
    return { valid: false, error: 'Имя пользователя не указано' };
  }

  // Remove @ if present
  let normalized = username.replace(/^@/, '').trim();

  // Check length (5-32 characters)
  if (normalized.length < 5) {
    return { valid: false, error: 'Имя пользователя слишком короткое (минимум 5 символов)' };
  }

  if (normalized.length > 32) {
    return { valid: false, error: 'Имя пользователя слишком длинное (максимум 32 символа)' };
  }

  // Check format: alphanumeric + underscores, must not start/end with underscore
  const validFormat = /^[a-zA-Z0-9][a-zA-Z0-9_]{3,30}[a-zA-Z0-9]$/;
  if (!validFormat.test(normalized)) {
    return {
      valid: false,
      error: 'Неверный формат. Используйте только буквы, цифры и подчеркивания',
    };
  }

  return { valid: true, normalized };
};

/**
 * Validate email address
 */
export const validateEmail = (email: string): {
  valid: boolean;
  normalized?: string;
  error?: string;
} => {
  if (!email || typeof email !== 'string') {
    return { valid: false, error: 'Email не указан' };
  }

  const normalized = email.toLowerCase().trim();

  // Basic email regex (RFC 5322 compliant would be too complex)
  const emailRegex = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/;

  if (!emailRegex.test(normalized)) {
    return { valid: false, error: 'Неверный формат email адреса' };
  }

  // Check length
  if (normalized.length > 254) {
    return { valid: false, error: 'Email адрес слишком длинный' };
  }

  // Check for disposable email domains (basic check)
  const disposableDomains = [
    'tempmail.com',
    'throwaway.email',
    '10minutemail.com',
    'guerrillamail.com',
  ];

  const domain = normalized.split('@')[1];
  if (disposableDomains.includes(domain)) {
    return {
      valid: false,
      error: 'Временные email адреса не допускаются',
    };
  }

  return { valid: true, normalized };
};

/**
 * Validate phone number (international format)
 */
export const validatePhoneNumber = (phone: string): {
  valid: boolean;
  normalized?: string;
  error?: string;
} => {
  if (!phone || typeof phone !== 'string') {
    return { valid: false, error: 'Номер телефона не указан' };
  }

  // Remove all non-digit characters except +
  let normalized = phone.replace(/[^\d+]/g, '');

  // Must start with +
  if (!normalized.startsWith('+')) {
    normalized = '+' + normalized;
  }

  // Check length (international format: +1234567890, typically 10-15 digits)
  const digitsOnly = normalized.replace(/\+/g, '');
  if (digitsOnly.length < 10) {
    return { valid: false, error: 'Номер телефона слишком короткий' };
  }

  if (digitsOnly.length > 15) {
    return { valid: false, error: 'Номер телефона слишком длинный' };
  }

  // Basic format validation
  const phoneRegex = /^\+\d{10,15}$/;
  if (!phoneRegex.test(normalized)) {
    return { valid: false, error: 'Неверный формат номера телефона. Используйте международный формат (+1234567890)' };
  }

  return { valid: true, normalized };
};

/**
 * Rate limiting check for sensitive operations
 */
const operationTimestamps = new Map<string, number[]>();

export const checkRateLimit = (
  key: string,
  maxAttempts: number,
  windowMs: number
): { allowed: boolean; remainingAttempts: number; retryAfterMs?: number } => {
  const now = Date.now();
  const timestamps = operationTimestamps.get(key) || [];

  // Remove old timestamps outside window
  const validTimestamps = timestamps.filter(ts => now - ts < windowMs);

  if (validTimestamps.length >= maxAttempts) {
    const oldestTimestamp = Math.min(...validTimestamps);
    const retryAfterMs = windowMs - (now - oldestTimestamp);

    return {
      allowed: false,
      remainingAttempts: 0,
      retryAfterMs,
    };
  }

  // Add current attempt
  validTimestamps.push(now);
  operationTimestamps.set(key, validTimestamps);

  return {
    allowed: true,
    remainingAttempts: maxAttempts - validTimestamps.length,
  };
};

/**
 * Clear rate limit for specific key
 */
export const clearRateLimit = (key: string): void => {
  operationTimestamps.delete(key);
};

/**
 * Validate password strength
 */
export const validatePasswordStrength = (password: string): {
  valid: boolean;
  strength: 'weak' | 'medium' | 'strong';
  suggestions: string[];
} => {
  const suggestions: string[] = [];
  let strength: 'weak' | 'medium' | 'strong' = 'weak';

  if (!password || password.length < 8) {
    suggestions.push('Минимальная длина пароля - 8 символов');
    return { valid: false, strength, suggestions };
  }

  if (password.length > 128) {
    suggestions.push('Максимальная длина пароля - 128 символов');
    return { valid: false, strength, suggestions };
  }

  const hasLowercase = /[a-z]/.test(password);
  const hasUppercase = /[A-Z]/.test(password);
  const hasDigit = /\d/.test(password);
  const hasSpecial = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password);

  let score = 0;
  if (hasLowercase) score++;
  if (hasUppercase) score++;
  if (hasDigit) score++;
  if (hasSpecial) score++;
  if (password.length >= 12) score++;

  if (!hasLowercase) suggestions.push('Добавьте строчные буквы');
  if (!hasUppercase) suggestions.push('Добавьте заглавные буквы');
  if (!hasDigit) suggestions.push('Добавьте цифры');
  if (!hasSpecial) suggestions.push('Добавьте специальные символы');

  if (score < 3) {
    strength = 'weak';
    return { valid: false, strength, suggestions };
  } else if (score === 3) {
    strength = 'medium';
  } else {
    strength = 'strong';
  }

  // Check for common passwords
  const commonPasswords = ['password', '12345678', 'qwerty', 'admin', 'letmein'];
  if (commonPasswords.some(common => password.toLowerCase().includes(common))) {
    suggestions.push('Пароль слишком простой, используйте более сложную комбинацию');
    return { valid: false, strength: 'weak', suggestions };
  }

  return { valid: true, strength, suggestions };
};

export default {
  sanitizeTextInput,
  validateNumericInput,
  validateTelegramUsername,
  validateEmail,
  validatePhoneNumber,
  checkRateLimit,
  clearRateLimit,
  validatePasswordStrength,
};
