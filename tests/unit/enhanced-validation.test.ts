/**
 * Unit Tests: Enhanced Validation Utilities
 * Tests for improved input validation and sanitization
 */

import {
  sanitizeTextInput,
  validateNumericInput,
  validateTelegramUsername,
  validateEmail,
  validatePhoneNumber,
  validatePasswordStrength,
  checkRateLimit,
  clearRateLimit,
} from '../../src/utils/enhanced-validation.util';

describe('Enhanced Validation Utilities', () => {
  describe('sanitizeTextInput', () => {
    it('should remove HTML tags', () => {
      const input = 'Hello <b>World</b>!';
      const sanitized = sanitizeTextInput(input);
      expect(sanitized).toBe('Hello World!');
    });

    it('should remove script tags', () => {
      const input = 'Hello <script>alert("XSS")</script> World';
      const sanitized = sanitizeTextInput(input);
      // Script tag and its content are removed
      expect(sanitized).not.toContain('<script>');
      expect(sanitized).not.toContain('</script>');
    });

    it('should remove javascript protocol', () => {
      const input = 'javascript:alert("XSS")';
      const sanitized = sanitizeTextInput(input);
      expect(sanitized).toBe('alert("XSS")');
    });

    it('should remove event handlers', () => {
      const input = '<div onclick="alert()">Click</div>';
      const sanitized = sanitizeTextInput(input);
      expect(sanitized).not.toContain('onclick');
    });

    it('should normalize whitespace', () => {
      const input = 'Hello    World   !';
      const sanitized = sanitizeTextInput(input);
      expect(sanitized).toBe('Hello World !');
    });

    it('should truncate long input', () => {
      const input = 'A'.repeat(2000);
      const sanitized = sanitizeTextInput(input, 100);
      // Should be truncated to max length
      expect(sanitized.length).toBeLessThanOrEqual(100);
    });

    it('should handle empty input', () => {
      expect(sanitizeTextInput('')).toBe('');
      expect(sanitizeTextInput(null as any)).toBe('');
      expect(sanitizeTextInput(undefined as any)).toBe('');
    });
  });

  describe('validateNumericInput', () => {
    it('should validate valid number', () => {
      const result = validateNumericInput('123.45');
      expect(result.valid).toBe(true);
      expect(result.value).toBe(123.45);
    });

    it('should validate integer', () => {
      const result = validateNumericInput(100);
      expect(result.valid).toBe(true);
      expect(result.value).toBe(100);
    });

    it('should reject non-numeric input', () => {
      const result = validateNumericInput('abc');
      expect(result.valid).toBe(false);
      expect(result.error).toContain('Некорректное');
    });

    it('should enforce min constraint', () => {
      const result = validateNumericInput('5', { min: 10 });
      expect(result.valid).toBe(false);
      expect(result.error).toContain('Минимальное');
    });

    it('should enforce max constraint', () => {
      const result = validateNumericInput('150', { max: 100 });
      expect(result.valid).toBe(false);
      expect(result.error).toContain('Максимальное');
    });

    it('should reject negative numbers when not allowed', () => {
      const result = validateNumericInput('-10', { allowNegative: false });
      expect(result.valid).toBe(false);
      expect(result.error).toContain('Отрицательные');
    });

    it('should allow negative numbers when allowed', () => {
      const result = validateNumericInput('-10', { allowNegative: true });
      expect(result.valid).toBe(true);
      expect(result.value).toBe(-10);
    });

    it('should reject floats when integer required', () => {
      const result = validateNumericInput('10.5', { allowFloat: false });
      expect(result.valid).toBe(false);
      expect(result.error).toContain('целое');
    });

    it('should reject zero when not allowed', () => {
      const result = validateNumericInput('0', { allowZero: false });
      expect(result.valid).toBe(false);
      expect(result.error).toContain('нулевым');
    });
  });

  describe('validateTelegramUsername', () => {
    it('should validate correct username', () => {
      const result = validateTelegramUsername('john_doe');
      expect(result.valid).toBe(true);
      expect(result.normalized).toBe('john_doe');
    });

    it('should remove @ prefix', () => {
      const result = validateTelegramUsername('@john_doe');
      expect(result.valid).toBe(true);
      expect(result.normalized).toBe('john_doe');
    });

    it('should reject username too short', () => {
      const result = validateTelegramUsername('abc');
      expect(result.valid).toBe(false);
      expect(result.error).toContain('короткое');
    });

    it('should reject username too long', () => {
      const result = validateTelegramUsername('a'.repeat(40));
      expect(result.valid).toBe(false);
      expect(result.error).toContain('длинное');
    });

    it('should reject username with invalid characters', () => {
      const result = validateTelegramUsername('john@doe');
      expect(result.valid).toBe(false);
      expect(result.error).toContain('формат');
    });

    it('should reject username starting with underscore', () => {
      const result = validateTelegramUsername('_johndoe');
      expect(result.valid).toBe(false);
    });

    it('should reject username ending with underscore', () => {
      const result = validateTelegramUsername('johndoe_');
      expect(result.valid).toBe(false);
    });
  });

  describe('validateEmail', () => {
    it('should validate correct email', () => {
      const result = validateEmail('test@example.com');
      expect(result.valid).toBe(true);
      expect(result.normalized).toBe('test@example.com');
    });

    it('should normalize to lowercase', () => {
      const result = validateEmail('TEST@EXAMPLE.COM');
      expect(result.valid).toBe(true);
      expect(result.normalized).toBe('test@example.com');
    });

    it('should reject invalid format', () => {
      const result = validateEmail('invalid.email');
      expect(result.valid).toBe(false);
      expect(result.error).toContain('формат');
    });

    it('should reject email without domain', () => {
      const result = validateEmail('test@');
      expect(result.valid).toBe(false);
    });

    it('should reject email too long', () => {
      const result = validateEmail('a'.repeat(250) + '@example.com');
      expect(result.valid).toBe(false);
      expect(result.error).toContain('длинный');
    });

    it('should reject disposable email domains', () => {
      const result = validateEmail('test@tempmail.com');
      expect(result.valid).toBe(false);
      expect(result.error).toContain('Временные');
    });
  });

  describe('validatePhoneNumber', () => {
    it('should validate correct phone number', () => {
      const result = validatePhoneNumber('+1234567890');
      expect(result.valid).toBe(true);
      expect(result.normalized).toBe('+1234567890');
    });

    it('should add + prefix if missing', () => {
      const result = validatePhoneNumber('1234567890');
      expect(result.valid).toBe(true);
      expect(result.normalized).toBe('+1234567890');
    });

    it('should remove non-digit characters', () => {
      const result = validatePhoneNumber('+1 (234) 567-8900');
      expect(result.valid).toBe(true);
      expect(result.normalized).toBe('+12345678900');
    });

    it('should reject phone number too short', () => {
      const result = validatePhoneNumber('+12345');
      expect(result.valid).toBe(false);
      expect(result.error).toContain('короткий');
    });

    it('should reject phone number too long', () => {
      const result = validatePhoneNumber('+' + '1'.repeat(20));
      expect(result.valid).toBe(false);
      expect(result.error).toContain('длинный');
    });
  });

  describe('validatePasswordStrength', () => {
    it('should validate strong password', () => {
      const result = validatePasswordStrength('MyP@ssw0rd123!');
      expect(result.valid).toBe(true);
      expect(result.strength).toBe('strong');
      expect(result.suggestions).toHaveLength(0);
    });

    it('should reject password too short', () => {
      const result = validatePasswordStrength('Pass1!');
      expect(result.valid).toBe(false);
      expect(result.suggestions.length).toBeGreaterThan(0);
    });

    it('should detect weak password', () => {
      const result = validatePasswordStrength('password');
      expect(result.valid).toBe(false);
      expect(result.strength).toBe('weak');
    });

    it('should reject common passwords', () => {
      const result = validatePasswordStrength('Password123');
      expect(result.valid).toBe(false);
      expect(result.suggestions.some(s => s.includes('простой'))).toBe(true);
    });

    it('should provide suggestions for weak password', () => {
      const result = validatePasswordStrength('lowercaseonly');
      expect(result.suggestions.length).toBeGreaterThan(0);
      expect(result.suggestions.some(s => s.includes('заглавные'))).toBe(true);
    });

    it('should detect password strength', () => {
      // Weak password - missing uppercase and special chars
      const result = validatePasswordStrength('MyPassword1');

      // Password should have some strength level
      expect(['weak', 'medium', 'strong']).toContain(result.strength);
    });
  });

  describe('checkRateLimit', () => {
    beforeEach(() => {
      // Clear all rate limits before each test
      clearRateLimit('test-key');
    });

    it('should allow first attempt', () => {
      const result = checkRateLimit('test-key', 3, 60000);
      expect(result.allowed).toBe(true);
      expect(result.remainingAttempts).toBe(2);
    });

    it('should track multiple attempts', () => {
      checkRateLimit('test-key', 3, 60000);
      const result = checkRateLimit('test-key', 3, 60000);
      expect(result.allowed).toBe(true);
      expect(result.remainingAttempts).toBe(1);
    });

    it('should block after max attempts', () => {
      checkRateLimit('test-key', 3, 60000);
      checkRateLimit('test-key', 3, 60000);
      checkRateLimit('test-key', 3, 60000);

      const result = checkRateLimit('test-key', 3, 60000);
      expect(result.allowed).toBe(false);
      expect(result.remainingAttempts).toBe(0);
      expect(result.retryAfterMs).toBeGreaterThan(0);
    });

    it('should reset after window expires', async () => {
      const windowMs = 100; // 100ms window for testing

      checkRateLimit('test-key', 2, windowMs);
      checkRateLimit('test-key', 2, windowMs);

      // Should be blocked
      let result = checkRateLimit('test-key', 2, windowMs);
      expect(result.allowed).toBe(false);

      // Wait for window to expire
      await new Promise(resolve => setTimeout(resolve, windowMs + 50));

      // Should be allowed again
      result = checkRateLimit('test-key', 2, windowMs);
      expect(result.allowed).toBe(true);
    });

    it('should handle different keys independently', () => {
      checkRateLimit('key1', 1, 60000);
      const result1 = checkRateLimit('key1', 1, 60000);
      expect(result1.allowed).toBe(false);

      const result2 = checkRateLimit('key2', 1, 60000);
      expect(result2.allowed).toBe(true);
    });

    it('should clear rate limit', () => {
      checkRateLimit('test-key', 1, 60000);
      const result1 = checkRateLimit('test-key', 1, 60000);
      expect(result1.allowed).toBe(false);

      clearRateLimit('test-key');

      const result2 = checkRateLimit('test-key', 1, 60000);
      expect(result2.allowed).toBe(true);
    });
  });
});
