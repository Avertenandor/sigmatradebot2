/**
 * Unit Tests: Format Utilities
 * Tests for formatting numbers, currency, and other display data
 */

import {
  formatNumber,
  formatCurrency,
  formatPercentage,
  formatCompactNumber,
  formatWalletAddress,
  formatTxHash,
  formatFileSize,
  formatPhoneDisplay,
  truncate,
  capitalizeWords,
  capitalize,
  formatList,
  formatStatus,
  formatUserName,
  formatDepositLevel,
  formatReferralCount,
  formatEarning,
  maskSensitiveData,
  formatBoolean,
  formatNumberedList,
  formatBulletedList,
  escapeMarkdown,
  formatErrorMessage,
} from '../../src/utils/format.util';

describe('Format Utilities', () => {
  describe('formatNumber', () => {
    it('should format number with thousands separators', () => {
      expect(formatNumber(1000)).toBe('1 000');
      expect(formatNumber(1000000)).toBe('1 000 000');
    });

    it('should format number with decimals', () => {
      expect(formatNumber(1234.56, 2)).toBe('1 234.56');
      expect(formatNumber(999.999, 1)).toBe('1 000.0');
    });

    it('should handle string input', () => {
      expect(formatNumber('5000', 0)).toBe('5 000');
    });

    it('should handle invalid input', () => {
      expect(formatNumber('invalid')).toBe('0');
      expect(formatNumber(NaN)).toBe('0');
      expect(formatNumber(Infinity)).toBe('0');
    });
  });

  describe('formatCurrency', () => {
    it('should format currency with USDT default', () => {
      expect(formatCurrency(100)).toBe('100.00 USDT');
      expect(formatCurrency(1000.5)).toBe('1 000.50 USDT');
    });

    it('should format with custom currency', () => {
      expect(formatCurrency(100, 'BTC', 8)).toContain('BTC');
    });

    it('should handle string input', () => {
      expect(formatCurrency('500.25')).toBe('500.25 USDT');
    });
  });

  describe('formatPercentage', () => {
    it('should format percentage', () => {
      expect(formatPercentage(5)).toBe('5.0%');
      expect(formatPercentage(12.345, 2)).toBe('12.35%');
    });

    it('should handle string input', () => {
      expect(formatPercentage('8.5')).toBe('8.5%');
    });

    it('should handle invalid input', () => {
      expect(formatPercentage('invalid')).toBe('0%');
    });
  });

  describe('formatCompactNumber', () => {
    it('should format small numbers normally', () => {
      expect(formatCompactNumber(999)).toBe('999');
    });

    it('should format thousands with K', () => {
      expect(formatCompactNumber(1500)).toBe('1.5K');
      expect(formatCompactNumber(50000)).toBe('50.0K');
    });

    it('should format millions with M', () => {
      expect(formatCompactNumber(1500000)).toBe('1.5M');
      expect(formatCompactNumber(25000000)).toBe('25.0M');
    });

    it('should format billions with B', () => {
      expect(formatCompactNumber(1500000000)).toBe('1.5B');
    });

    it('should handle string input', () => {
      expect(formatCompactNumber('5000')).toBe('5.0K');
    });

    it('should handle invalid input', () => {
      expect(formatCompactNumber('invalid')).toBe('0');
    });
  });

  describe('formatWalletAddress', () => {
    it('should shorten long address', () => {
      const address = '0x742d35Cc6634C0532925a3b844Bc454e4438f44e';
      expect(formatWalletAddress(address)).toBe('0x742d...f44e');
    });

    it('should show full address when showFull is true', () => {
      const address = '0x742d35Cc6634C0532925a3b844Bc454e4438f44e';
      expect(formatWalletAddress(address, true)).toBe(address);
    });

    it('should handle short address', () => {
      const address = '0x123456';
      expect(formatWalletAddress(address)).toBe(address);
    });

    it('should handle empty input', () => {
      expect(formatWalletAddress('')).toBe('');
      expect(formatWalletAddress(null as any)).toBe('');
    });
  });

  describe('formatTxHash', () => {
    it('should shorten long transaction hash', () => {
      const hash = '0x1234567890abcdef1234567890abcdef1234567890abcdef';
      const formatted = formatTxHash(hash);
      expect(formatted).toContain('0x12345678');
      expect(formatted).toContain('...');
    });

    it('should show full hash when showFull is true', () => {
      const hash = '0x1234567890abcdef';
      expect(formatTxHash(hash, true)).toBe(hash);
    });

    it('should handle empty input', () => {
      expect(formatTxHash('')).toBe('Ожидает подтверждения');
      expect(formatTxHash(null as any)).toBe('Ожидает подтверждения');
    });
  });

  describe('formatFileSize', () => {
    it('should format bytes', () => {
      expect(formatFileSize(0)).toBe('0 Bytes');
      expect(formatFileSize(500)).toBe('500 Bytes');
    });

    it('should format KB', () => {
      expect(formatFileSize(1024)).toBe('1 KB');
      expect(formatFileSize(1536)).toBe('1.5 KB');
    });

    it('should format MB', () => {
      expect(formatFileSize(1048576)).toBe('1 MB');
      expect(formatFileSize(5242880)).toBe('5 MB');
    });

    it('should format GB', () => {
      expect(formatFileSize(1073741824)).toBe('1 GB');
    });
  });

  describe('formatPhoneDisplay', () => {
    it('should format phone number', () => {
      const formatted = formatPhoneDisplay('+12345678901');
      expect(formatted).toContain('+1');
      expect(formatted).toContain('(234)');
    });

    it('should handle empty input', () => {
      expect(formatPhoneDisplay('')).toBe('');
    });

    it('should remove non-digit characters', () => {
      const formatted = formatPhoneDisplay('+1 (234) 567-89-01');
      expect(formatted).toContain('+1');
    });
  });

  describe('truncate', () => {
    it('should truncate long text', () => {
      const text = 'This is a very long text';
      expect(truncate(text, 10)).toBe('This is...');
    });

    it('should not truncate short text', () => {
      const text = 'Short';
      expect(truncate(text, 10)).toBe('Short');
    });

    it('should use custom suffix', () => {
      expect(truncate('Long text', 5, '…')).toBe('Long…');
    });

    it('should handle empty input', () => {
      expect(truncate('', 10)).toBe('');
    });
  });

  describe('capitalizeWords', () => {
    it('should capitalize each word', () => {
      expect(capitalizeWords('hello world')).toBe('Hello World');
      expect(capitalizeWords('HELLO WORLD')).toBe('Hello World');
    });

    it('should handle empty input', () => {
      expect(capitalizeWords('')).toBe('');
    });
  });

  describe('capitalize', () => {
    it('should capitalize first letter only', () => {
      expect(capitalize('hello')).toBe('Hello');
      expect(capitalize('hello world')).toBe('Hello world');
    });

    it('should handle empty input', () => {
      expect(capitalize('')).toBe('');
    });
  });

  describe('formatList', () => {
    it('should format empty list', () => {
      expect(formatList([])).toBe('');
    });

    it('should format single item', () => {
      expect(formatList(['apple'])).toBe('apple');
    });

    it('should format two items', () => {
      expect(formatList(['apple', 'banana'])).toBe('apple и banana');
    });

    it('should format multiple items', () => {
      const result = formatList(['apple', 'banana', 'cherry']);
      expect(result).toContain('apple, banana');
      expect(result).toContain('и cherry');
    });

    it('should use custom conjunction', () => {
      expect(formatList(['a', 'b'], 'or')).toBe('a or b');
    });
  });

  describe('formatStatus', () => {
    it('should format known statuses', () => {
      expect(formatStatus('pending')).toContain('Ожидает');
      expect(formatStatus('confirmed')).toContain('Подтвержден');
      expect(formatStatus('failed')).toContain('Ошибка');
      expect(formatStatus('active')).toContain('Активен');
    });

    it('should capitalize unknown status', () => {
      expect(formatStatus('custom_status')).toBe('Custom_status');
    });

    it('should handle case insensitive', () => {
      expect(formatStatus('PENDING')).toContain('Ожидает');
    });
  });

  describe('formatUserName', () => {
    it('should format full name', () => {
      expect(formatUserName('John', 'Doe')).toBe('John Doe');
    });

    it('should format first name only', () => {
      expect(formatUserName('John')).toBe('John');
    });

    it('should format username with @', () => {
      expect(formatUserName(undefined, undefined, 'johndoe')).toBe('@johndoe');
    });

    it('should default to "Пользователь"', () => {
      expect(formatUserName()).toBe('Пользователь');
    });
  });

  describe('formatDepositLevel', () => {
    it('should format level with emoji', () => {
      expect(formatDepositLevel(1)).toContain('🥉');
      expect(formatDepositLevel(2)).toContain('🥈');
      expect(formatDepositLevel(3)).toContain('🥇');
      expect(formatDepositLevel(4)).toContain('💎');
      expect(formatDepositLevel(5)).toContain('👑');
    });

    it('should handle unknown level', () => {
      expect(formatDepositLevel(10)).toContain('⭐');
    });
  });

  describe('formatReferralCount', () => {
    it('should format zero referrals', () => {
      expect(formatReferralCount(0)).toBe('Нет рефералов');
    });

    it('should format with pluralization', () => {
      expect(formatReferralCount(1)).toContain('реферал');
      expect(formatReferralCount(2)).toContain('реферала');
      expect(formatReferralCount(5)).toContain('рефералов');
    });
  });

  describe('formatEarning', () => {
    it('should format earning', () => {
      const result = formatEarning(100, 'реферал');
      expect(result).toContain('+');
      expect(result).toContain('USDT');
    });
  });

  describe('maskSensitiveData', () => {
    it('should mask middle characters', () => {
      expect(maskSensitiveData('1234567890', 2)).toBe('12******90');
    });

    it('should use custom mask character', () => {
      expect(maskSensitiveData('1234567890', 2, 'X')).toBe('12XXXXXX90');
    });

    it('should handle short data', () => {
      expect(maskSensitiveData('123', 2)).toBe('123');
    });

    it('should handle empty input', () => {
      expect(maskSensitiveData('', 2)).toBe('');
    });
  });

  describe('formatBoolean', () => {
    it('should format true as Да', () => {
      expect(formatBoolean(true)).toBe('Да');
    });

    it('should format false as Нет', () => {
      expect(formatBoolean(false)).toBe('Нет');
    });
  });

  describe('formatNumberedList', () => {
    it('should format numbered list', () => {
      const result = formatNumberedList(['First', 'Second', 'Third']);
      expect(result).toContain('1. First');
      expect(result).toContain('2. Second');
      expect(result).toContain('3. Third');
    });

    it('should handle empty list', () => {
      expect(formatNumberedList([])).toBe('');
    });
  });

  describe('formatBulletedList', () => {
    it('should format bulleted list', () => {
      const result = formatBulletedList(['First', 'Second']);
      expect(result).toContain('• First');
      expect(result).toContain('• Second');
    });

    it('should use custom bullet', () => {
      const result = formatBulletedList(['First'], '-');
      expect(result).toBe('- First');
    });

    it('should handle empty list', () => {
      expect(formatBulletedList([])).toBe('');
    });
  });

  describe('escapeMarkdown', () => {
    it('should escape special characters', () => {
      const result = escapeMarkdown('*bold* _italic_ [link]');
      expect(result).toContain('\\*');
      expect(result).toContain('\\_');
      expect(result).toContain('\\[');
    });

    it('should escape newlines', () => {
      const result = escapeMarkdown('Line 1\nLine 2');
      expect(result).toContain('\\n');
    });

    it('should handle empty input', () => {
      expect(escapeMarkdown('')).toBe('');
    });
  });

  describe('formatErrorMessage', () => {
    it('should format Error object', () => {
      const error = new Error('Something went wrong');
      expect(formatErrorMessage(error)).toBe('Something went wrong');
    });

    it('should format string error', () => {
      expect(formatErrorMessage('Error message')).toBe('Error message');
    });

    it('should format unknown error', () => {
      expect(formatErrorMessage(null)).toBe('Произошла неизвестная ошибка');
      expect(formatErrorMessage({})).toBe('Произошла неизвестная ошибка');
    });
  });
});
