/**
 * Unit Tests: Date and Time Utilities
 * Tests for date/time formatting and manipulation
 */

import {
  formatDate,
  formatRelativeTime,
  formatTimeUntil,
  formatDuration,
  formatDateRange,
  addDays,
  addHours,
  addMinutes,
  isToday,
  isYesterday,
  isPast,
  isFuture,
  getDaysDifference,
  getStartOfDay,
  getEndOfDay,
  parseDate,
  pluralize,
} from '../../src/utils/date-time.util';

describe('Date and Time Utilities', () => {
  describe('formatDate', () => {
    it('should format date correctly', () => {
      const date = new Date('2024-03-15T10:30:00');
      const formatted = formatDate(date);
      expect(formatted).toMatch(/15\.03\.2024/);
    });

    it('should handle string input', () => {
      const formatted = formatDate('2024-03-15');
      expect(formatted).toMatch(/15\.03\.2024/);
    });

    it('should handle timestamp input', () => {
      const timestamp = new Date('2024-03-15').getTime();
      const formatted = formatDate(timestamp);
      expect(formatted).toMatch(/15\.03\.2024/);
    });
  });

  describe('formatDate with time', () => {
    it('should format date and time together', () => {
      const date = new Date('2024-03-15T14:30:00');
      const formatted = formatDate(date, true);
      expect(formatted).toContain('15.03.2024');
      expect(formatted).toContain('14:30');
    });

    it('should format date only when includeTime is false', () => {
      const date = new Date('2024-03-15T14:30:00');
      const formatted = formatDate(date, false);
      expect(formatted).toBe('15.03.2024');
      expect(formatted).not.toContain('14:30');
    });

    it('should handle invalid date', () => {
      const formatted = formatDate('invalid');
      expect(formatted).toBe('Неверная дата');
    });
  });

  describe('formatRelativeTime', () => {
    it('should show "только что" for very recent times', () => {
      const now = new Date();
      const formatted = formatRelativeTime(now);
      expect(formatted).toBe('только что');
    });

    it('should format seconds ago', () => {
      const date = new Date(Date.now() - 30000); // 30 seconds ago
      const formatted = formatRelativeTime(date);
      expect(formatted).toContain('секунд');
      expect(formatted).toContain('назад');
    });

    it('should format minutes ago', () => {
      const date = new Date(Date.now() - 5 * 60000); // 5 minutes ago
      const formatted = formatRelativeTime(date);
      expect(formatted).toContain('минут');
      expect(formatted).toContain('назад');
    });

    it('should format hours ago', () => {
      const date = new Date(Date.now() - 3 * 3600000); // 3 hours ago
      const formatted = formatRelativeTime(date);
      expect(formatted).toContain('час');
      expect(formatted).toContain('назад');
    });

    it('should format days ago', () => {
      const date = new Date(Date.now() - 2 * 86400000); // 2 days ago
      const formatted = formatRelativeTime(date);
      expect(formatted).toContain('дня');
      expect(formatted).toContain('назад');
    });

    it('should format weeks ago', () => {
      const date = new Date(Date.now() - 14 * 86400000); // 2 weeks ago
      const formatted = formatRelativeTime(date);
      expect(formatted).toContain('недел');
      expect(formatted).toContain('назад');
    });

    it('should format months ago', () => {
      const date = new Date(Date.now() - 60 * 86400000); // ~2 months ago
      const formatted = formatRelativeTime(date);
      expect(formatted).toContain('месяц');
      expect(formatted).toContain('назад');
    });
  });

  describe('formatTimeUntil', () => {
    it('should format future time', () => {
      const future = new Date(Date.now() + 5 * 60000); // 5 minutes from now
      const formatted = formatTimeUntil(future);
      expect(formatted).toContain('через');
      expect(formatted).toContain('минут');
    });

    it('should show "истек" for past times', () => {
      const past = new Date(Date.now() - 1000);
      const formatted = formatTimeUntil(past);
      expect(formatted).toBe('истек');
    });

    it('should handle invalid date', () => {
      const formatted = formatTimeUntil('invalid');
      expect(formatted).toBe('Неверная дата');
    });
  });

  describe('formatDuration', () => {
    it('should format seconds', () => {
      expect(formatDuration(30000)).toContain('секунд');
    });

    it('should format minutes', () => {
      expect(formatDuration(120000)).toContain('минут');
    });

    it('should format hours', () => {
      expect(formatDuration(3600000)).toContain('час');
    });

    it('should format days', () => {
      expect(formatDuration(86400000)).toContain('день');
    });

    it('should format combined duration', () => {
      const duration = 3665000; // 1 hour, 1 minute, 5 seconds
      const formatted = formatDuration(duration);
      expect(formatted).toContain('час');
      expect(formatted).toContain('минут');
    });

    it('should handle milliseconds only', () => {
      expect(formatDuration(500)).toBe('500 мс');
    });

    it('should handle negative duration', () => {
      expect(formatDuration(-1000)).toBe('0 секунд');
    });
  });

  describe('addDays', () => {
    it('should add days correctly', () => {
      const date = new Date('2024-03-15');
      const result = addDays(date, 5);
      expect(result.getDate()).toBe(20);
    });

    it('should handle negative days', () => {
      const date = new Date('2024-03-15');
      const result = addDays(date, -5);
      expect(result.getDate()).toBe(10);
    });

    it('should not modify original date', () => {
      const date = new Date('2024-03-15');
      const originalTime = date.getTime();
      addDays(date, 5);
      expect(date.getTime()).toBe(originalTime);
    });
  });

  describe('addHours', () => {
    it('should add hours correctly', () => {
      const date = new Date('2024-03-15T10:00:00');
      const result = addHours(date, 5);
      expect(result.getHours()).toBe(15);
    });

    it('should not modify original date', () => {
      const date = new Date('2024-03-15T10:00:00');
      const originalTime = date.getTime();
      addHours(date, 5);
      expect(date.getTime()).toBe(originalTime);
    });
  });

  describe('addMinutes', () => {
    it('should add minutes correctly', () => {
      const date = new Date('2024-03-15T10:30:00');
      const result = addMinutes(date, 45);
      expect(result.getMinutes()).toBe(15);
      expect(result.getHours()).toBe(11);
    });

    it('should not modify original date', () => {
      const date = new Date('2024-03-15T10:30:00');
      const originalTime = date.getTime();
      addMinutes(date, 45);
      expect(date.getTime()).toBe(originalTime);
    });
  });

  describe('getStartOfDay', () => {
    it('should return start of day', () => {
      const date = new Date('2024-03-15T14:30:45');
      const result = getStartOfDay(date);
      expect(result.getHours()).toBe(0);
      expect(result.getMinutes()).toBe(0);
      expect(result.getSeconds()).toBe(0);
      expect(result.getMilliseconds()).toBe(0);
    });
  });

  describe('getEndOfDay', () => {
    it('should return end of day', () => {
      const date = new Date('2024-03-15T14:30:45');
      const result = getEndOfDay(date);
      expect(result.getHours()).toBe(23);
      expect(result.getMinutes()).toBe(59);
      expect(result.getSeconds()).toBe(59);
    });
  });

  describe('isToday', () => {
    it('should return true for today', () => {
      const now = new Date();
      expect(isToday(now)).toBe(true);
    });

    it('should return false for yesterday', () => {
      const yesterday = new Date(Date.now() - 86400000);
      expect(isToday(yesterday)).toBe(false);
    });
  });

  describe('isYesterday', () => {
    it('should return true for yesterday', () => {
      const yesterday = new Date(Date.now() - 86400000);
      expect(isYesterday(yesterday)).toBe(true);
    });

    it('should return false for today', () => {
      const today = new Date();
      expect(isYesterday(today)).toBe(false);
    });
  });

  describe('parseDate', () => {
    it('should parse ISO format', () => {
      const result = parseDate('2024-03-15T10:00:00');
      expect(result).toBeInstanceOf(Date);
      expect(result?.getDate()).toBe(15);
    });

    it('should parse DD.MM.YYYY format', () => {
      const result = parseDate('15.03.2024');
      expect(result).toBeInstanceOf(Date);
      expect(result?.getDate()).toBe(15);
    });

    it('should parse DD.MM.YYYY HH:MM format', () => {
      const result = parseDate('15.03.2024 14:30');
      expect(result).toBeInstanceOf(Date);
      expect(result?.getHours()).toBe(14);
      expect(result?.getMinutes()).toBe(30);
    });

    it('should return null for invalid input', () => {
      expect(parseDate('invalid')).toBeNull();
      expect(parseDate('')).toBeNull();
    });
  });

  describe('isPast', () => {
    it('should return true for past date', () => {
      const past = new Date(Date.now() - 1000);
      expect(isPast(past)).toBe(true);
    });

    it('should return false for future date', () => {
      const future = new Date(Date.now() + 1000);
      expect(isPast(future)).toBe(false);
    });
  });

  describe('isFuture', () => {
    it('should return true for future date', () => {
      const future = new Date(Date.now() + 1000);
      expect(isFuture(future)).toBe(true);
    });

    it('should return false for past date', () => {
      const past = new Date(Date.now() - 1000);
      expect(isFuture(past)).toBe(false);
    });
  });

  describe('getDaysDifference', () => {
    it('should calculate days difference', () => {
      const date1 = new Date('2024-03-15');
      const date2 = new Date('2024-03-20');
      expect(getDaysDifference(date1, date2)).toBe(5);
    });

    it('should return positive value regardless of order', () => {
      const date1 = new Date('2024-03-20');
      const date2 = new Date('2024-03-15');
      expect(getDaysDifference(date1, date2)).toBe(5);
    });
  });

  describe('formatDateRange', () => {
    it('should format date range', () => {
      const start = new Date('2024-03-15');
      const end = new Date('2024-03-20');
      const formatted = formatDateRange(start, end);
      expect(formatted).toContain('15.03.2024');
      expect(formatted).toContain('20.03.2024');
    });

    it('should format same day range', () => {
      const date = new Date('2024-03-15T10:00:00');
      const formatted = formatDateRange(date, date);
      expect(formatted).toContain('15.03.2024');
    });

    it('should handle invalid dates', () => {
      const formatted = formatDateRange('invalid', 'invalid');
      expect(formatted).toBe('Неверный диапазон дат');
    });
  });

  describe('pluralize', () => {
    it('should use form "one" for 1', () => {
      expect(pluralize(1, 'день', 'дня', 'дней')).toBe('день');
    });

    it('should use form "few" for 2-4', () => {
      expect(pluralize(2, 'день', 'дня', 'дней')).toBe('дня');
      expect(pluralize(3, 'день', 'дня', 'дней')).toBe('дня');
      expect(pluralize(4, 'день', 'дня', 'дней')).toBe('дня');
    });

    it('should use form "many" for 5-20', () => {
      expect(pluralize(5, 'день', 'дня', 'дней')).toBe('дней');
      expect(pluralize(10, 'день', 'дня', 'дней')).toBe('дней');
      expect(pluralize(20, 'день', 'дня', 'дней')).toBe('дней');
    });

    it('should use form "one" for 21, 31, etc', () => {
      expect(pluralize(21, 'день', 'дня', 'дней')).toBe('день');
      expect(pluralize(31, 'день', 'дня', 'дней')).toBe('день');
    });

    it('should use form "few" for 22-24, 32-34, etc', () => {
      expect(pluralize(22, 'день', 'дня', 'дней')).toBe('дня');
      expect(pluralize(33, 'день', 'дня', 'дней')).toBe('дня');
    });

    it('should use form "many" for 0, 11-19, 25-30, etc', () => {
      expect(pluralize(0, 'день', 'дня', 'дней')).toBe('дней');
      expect(pluralize(11, 'день', 'дня', 'дней')).toBe('дней');
      expect(pluralize(25, 'день', 'дня', 'дней')).toBe('дней');
    });

    it('should handle negative numbers', () => {
      expect(pluralize(-1, 'день', 'дня', 'дней')).toBe('день');
      expect(pluralize(-2, 'день', 'дня', 'дней')).toBe('дня');
      expect(pluralize(-5, 'день', 'дня', 'дней')).toBe('дней');
    });
  });
});
