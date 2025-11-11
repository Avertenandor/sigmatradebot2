/**
 * Date and Time Utilities
 * Helper functions for date/time formatting and calculations
 */

/**
 * Format timestamp to readable date string (Russian locale)
 */
export const formatDate = (date: Date | number | string, includeTime: boolean = false): string => {
  const d = new Date(date);

  if (isNaN(d.getTime())) {
    return 'Неверная дата';
  }

  const day = d.getDate().toString().padStart(2, '0');
  const month = (d.getMonth() + 1).toString().padStart(2, '0');
  const year = d.getFullYear();

  if (!includeTime) {
    return `${day}.${month}.${year}`;
  }

  const hours = d.getHours().toString().padStart(2, '0');
  const minutes = d.getMinutes().toString().padStart(2, '0');

  return `${day}.${month}.${year} ${hours}:${minutes}`;
};

/**
 * Format timestamp to relative time string (Russian)
 */
export const formatRelativeTime = (date: Date | number | string): string => {
  const d = new Date(date);
  const now = new Date();

  if (isNaN(d.getTime())) {
    return 'Неверная дата';
  }

  const diffMs = now.getTime() - d.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);
  const diffWeeks = Math.floor(diffDays / 7);
  const diffMonths = Math.floor(diffDays / 30);
  const diffYears = Math.floor(diffDays / 365);

  if (diffSeconds < 10) {
    return 'только что';
  }

  if (diffSeconds < 60) {
    return `${diffSeconds} ${pluralize(diffSeconds, 'секунду', 'секунды', 'секунд')} назад`;
  }

  if (diffMinutes < 60) {
    return `${diffMinutes} ${pluralize(diffMinutes, 'минуту', 'минуты', 'минут')} назад`;
  }

  if (diffHours < 24) {
    return `${diffHours} ${pluralize(diffHours, 'час', 'часа', 'часов')} назад`;
  }

  if (diffDays < 7) {
    return `${diffDays} ${pluralize(diffDays, 'день', 'дня', 'дней')} назад`;
  }

  if (diffWeeks < 4) {
    return `${diffWeeks} ${pluralize(diffWeeks, 'неделю', 'недели', 'недель')} назад`;
  }

  if (diffMonths < 12) {
    return `${diffMonths} ${pluralize(diffMonths, 'месяц', 'месяца', 'месяцев')} назад`;
  }

  return `${diffYears} ${pluralize(diffYears, 'год', 'года', 'лет')} назад`;
};

/**
 * Pluralize Russian words based on number
 */
export const pluralize = (count: number, one: string, few: string, many: string): string => {
  const n = Math.abs(count) % 100;
  const n1 = n % 10;

  if (n > 10 && n < 20) {
    return many;
  }

  if (n1 > 1 && n1 < 5) {
    return few;
  }

  if (n1 === 1) {
    return one;
  }

  return many;
};

/**
 * Calculate time until date (future)
 */
export const formatTimeUntil = (date: Date | number | string): string => {
  const d = new Date(date);
  const now = new Date();

  if (isNaN(d.getTime())) {
    return 'Неверная дата';
  }

  const diffMs = d.getTime() - now.getTime();

  if (diffMs <= 0) {
    return 'истек';
  }

  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffDays > 0) {
    return `через ${diffDays} ${pluralize(diffDays, 'день', 'дня', 'дней')}`;
  }

  if (diffHours > 0) {
    return `через ${diffHours} ${pluralize(diffHours, 'час', 'часа', 'часов')}`;
  }

  if (diffMinutes > 0) {
    return `через ${diffMinutes} ${pluralize(diffMinutes, 'минуту', 'минуты', 'минут')}`;
  }

  return `через ${diffSeconds} ${pluralize(diffSeconds, 'секунду', 'секунды', 'секунд')}`;
};

/**
 * Format duration in milliseconds to readable string
 */
export const formatDuration = (durationMs: number): string => {
  if (durationMs < 0) {
    return '0 секунд';
  }

  const seconds = Math.floor(durationMs / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) {
    const remainingHours = hours % 24;
    return `${days} ${pluralize(days, 'день', 'дня', 'дней')}${
      remainingHours > 0 ? ` ${remainingHours} ${pluralize(remainingHours, 'час', 'часа', 'часов')}` : ''
    }`;
  }

  if (hours > 0) {
    const remainingMinutes = minutes % 60;
    return `${hours} ${pluralize(hours, 'час', 'часа', 'часов')}${
      remainingMinutes > 0 ? ` ${remainingMinutes} ${pluralize(remainingMinutes, 'минута', 'минуты', 'минут')}` : ''
    }`;
  }

  if (minutes > 0) {
    const remainingSeconds = seconds % 60;
    return `${minutes} ${pluralize(minutes, 'минута', 'минуты', 'минут')}${
      remainingSeconds > 0 ? ` ${remainingSeconds} ${pluralize(remainingSeconds, 'секунда', 'секунды', 'секунд')}` : ''
    }`;
  }

  if (seconds > 0) {
    return `${seconds} ${pluralize(seconds, 'секунда', 'секунды', 'секунд')}`;
  }

  return `${durationMs} мс`;
};

/**
 * Check if date is today
 */
export const isToday = (date: Date | number | string): boolean => {
  const d = new Date(date);
  const today = new Date();

  return (
    d.getDate() === today.getDate() &&
    d.getMonth() === today.getMonth() &&
    d.getFullYear() === today.getFullYear()
  );
};

/**
 * Check if date is yesterday
 */
export const isYesterday = (date: Date | number | string): boolean => {
  const d = new Date(date);
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);

  return (
    d.getDate() === yesterday.getDate() &&
    d.getMonth() === yesterday.getMonth() &&
    d.getFullYear() === yesterday.getFullYear()
  );
};

/**
 * Get start of day (00:00:00)
 */
export const getStartOfDay = (date: Date | number | string = new Date()): Date => {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
};

/**
 * Get end of day (23:59:59)
 */
export const getEndOfDay = (date: Date | number | string = new Date()): Date => {
  const d = new Date(date);
  d.setHours(23, 59, 59, 999);
  return d;
};

/**
 * Add days to date
 */
export const addDays = (date: Date | number | string, days: number): Date => {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
};

/**
 * Add hours to date
 */
export const addHours = (date: Date | number | string, hours: number): Date => {
  const d = new Date(date);
  d.setHours(d.getHours() + hours);
  return d;
};

/**
 * Add minutes to date
 */
export const addMinutes = (date: Date | number | string, minutes: number): Date => {
  const d = new Date(date);
  d.setMinutes(d.getMinutes() + minutes);
  return d;
};

/**
 * Check if date is in the past
 */
export const isPast = (date: Date | number | string): boolean => {
  const d = new Date(date);
  return d.getTime() < Date.now();
};

/**
 * Check if date is in the future
 */
export const isFuture = (date: Date | number | string): boolean => {
  const d = new Date(date);
  return d.getTime() > Date.now();
};

/**
 * Get difference between two dates in days
 */
export const getDaysDifference = (date1: Date | number | string, date2: Date | number | string): number => {
  const d1 = new Date(date1);
  const d2 = new Date(date2);

  const diffMs = Math.abs(d2.getTime() - d1.getTime());
  return Math.floor(diffMs / (1000 * 60 * 60 * 24));
};

/**
 * Parse date string in various formats
 */
export const parseDate = (dateString: string): Date | null => {
  if (!dateString) {
    return null;
  }

  // Try ISO format
  let date = new Date(dateString);
  if (!isNaN(date.getTime())) {
    return date;
  }

  // Try DD.MM.YYYY format
  const ddmmyyyy = dateString.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
  if (ddmmyyyy) {
    const [, day, month, year] = ddmmyyyy;
    date = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
    if (!isNaN(date.getTime())) {
      return date;
    }
  }

  // Try DD.MM.YYYY HH:MM format
  const ddmmyyyyhhmm = dateString.match(/^(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})$/);
  if (ddmmyyyyhhmm) {
    const [, day, month, year, hours, minutes] = ddmmyyyyhhmm;
    date = new Date(
      parseInt(year),
      parseInt(month) - 1,
      parseInt(day),
      parseInt(hours),
      parseInt(minutes)
    );
    if (!isNaN(date.getTime())) {
      return date;
    }
  }

  return null;
};

/**
 * Format date range
 */
export const formatDateRange = (startDate: Date | number | string, endDate: Date | number | string): string => {
  const start = new Date(startDate);
  const end = new Date(endDate);

  if (isNaN(start.getTime()) || isNaN(end.getTime())) {
    return 'Неверный диапазон дат';
  }

  const sameDay = start.toDateString() === end.toDateString();

  if (sameDay) {
    return formatDate(start, true);
  }

  return `${formatDate(start)} - ${formatDate(end)}`;
};

export default {
  formatDate,
  formatRelativeTime,
  formatTimeUntil,
  formatDuration,
  pluralize,
  isToday,
  isYesterday,
  getStartOfDay,
  getEndOfDay,
  addDays,
  addHours,
  addMinutes,
  isPast,
  isFuture,
  getDaysDifference,
  parseDate,
  formatDateRange,
};
