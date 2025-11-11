/**
 * Formatting Utilities
 * Format numbers, currency, and other data for display
 */

import { pluralize } from './date-time.util';

/**
 * Format number with thousands separators
 */
export const formatNumber = (
  num: number | string,
  decimals: number = 0
): string => {
  const n = typeof num === 'string' ? parseFloat(num) : num;

  if (isNaN(n) || !isFinite(n)) {
    return '0';
  }

  return n.toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
};

/**
 * Format currency amount (USDT)
 */
export const formatCurrency = (
  amount: number | string,
  currency: string = 'USDT',
  decimals: number = 2
): string => {
  const formatted = formatNumber(amount, decimals);
  return `${formatted} ${currency}`;
};

/**
 * Format percentage
 */
export const formatPercentage = (
  value: number | string,
  decimals: number = 1
): string => {
  const n = typeof value === 'string' ? parseFloat(value) : value;

  if (isNaN(n) || !isFinite(n)) {
    return '0%';
  }

  return `${n.toFixed(decimals)}%`;
};

/**
 * Format large numbers with K, M, B suffixes
 */
export const formatCompactNumber = (num: number | string): string => {
  const n = typeof num === 'string' ? parseFloat(num) : num;

  if (isNaN(n) || !isFinite(n)) {
    return '0';
  }

  if (n < 1000) {
    return n.toFixed(0);
  }

  if (n < 1000000) {
    return `${(n / 1000).toFixed(1)}K`;
  }

  if (n < 1000000000) {
    return `${(n / 1000000).toFixed(1)}M`;
  }

  return `${(n / 1000000000).toFixed(1)}B`;
};

/**
 * Format wallet address (show first 6 and last 4 characters)
 */
export const formatWalletAddress = (address: string, showFull: boolean = false): string => {
  if (!address || typeof address !== 'string') {
    return '';
  }

  if (showFull || address.length <= 12) {
    return address;
  }

  return `${address.substring(0, 6)}...${address.substring(address.length - 4)}`;
};

/**
 * Format transaction hash
 */
export const formatTxHash = (txHash: string, showFull: boolean = false): string => {
  if (!txHash || typeof txHash !== 'string') {
    return 'Ожидает подтверждения';
  }

  if (showFull || txHash.length <= 16) {
    return txHash;
  }

  return `${txHash.substring(0, 10)}...${txHash.substring(txHash.length - 6)}`;
};

/**
 * Format file size
 */
export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
};

/**
 * Format phone number for display
 */
export const formatPhoneDisplay = (phone: string): string => {
  if (!phone) return '';

  // Remove all non-digit characters except +
  const cleaned = phone.replace(/[^\d+]/g, '');

  // Format as +X (XXX) XXX-XX-XX
  if (cleaned.startsWith('+') && cleaned.length > 10) {
    const countryCode = cleaned.substring(1, cleaned.length - 10);
    const areaCode = cleaned.substring(cleaned.length - 10, cleaned.length - 7);
    const firstPart = cleaned.substring(cleaned.length - 7, cleaned.length - 4);
    const secondPart = cleaned.substring(cleaned.length - 4, cleaned.length - 2);
    const thirdPart = cleaned.substring(cleaned.length - 2);

    return `+${countryCode} (${areaCode}) ${firstPart}-${secondPart}-${thirdPart}`;
  }

  return phone;
};

/**
 * Truncate text with ellipsis
 */
export const truncate = (
  text: string,
  maxLength: number,
  suffix: string = '...'
): string => {
  if (!text || text.length <= maxLength) {
    return text;
  }

  return text.substring(0, maxLength - suffix.length) + suffix;
};

/**
 * Capitalize first letter of each word
 */
export const capitalizeWords = (text: string): string => {
  if (!text) return '';

  return text
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
};

/**
 * Capitalize first letter
 */
export const capitalize = (text: string): string => {
  if (!text) return '';
  return text.charAt(0).toUpperCase() + text.slice(1);
};

/**
 * Format list with commas and "and"
 */
export const formatList = (items: string[], conjunction: string = 'и'): string => {
  if (!items || items.length === 0) {
    return '';
  }

  if (items.length === 1) {
    return items[0];
  }

  if (items.length === 2) {
    return `${items[0]} ${conjunction} ${items[1]}`;
  }

  const lastItem = items[items.length - 1];
  const otherItems = items.slice(0, -1);

  return `${otherItems.join(', ')} ${conjunction} ${lastItem}`;
};

/**
 * Format status badge text
 */
export const formatStatus = (status: string): string => {
  const statusMap: Record<string, string> = {
    pending: '⏳ Ожидает',
    confirmed: '✅ Подтвержден',
    failed: '❌ Ошибка',
    cancelled: '🚫 Отменен',
    processing: '⚙️ Обработка',
    completed: '✅ Завершен',
    expired: '⏰ Истек',
    active: '🟢 Активен',
    inactive: '⚪ Неактивен',
    banned: '🚫 Заблокирован',
  };

  return statusMap[status.toLowerCase()] || capitalize(status);
};

/**
 * Format user display name
 */
export const formatUserName = (
  firstName?: string,
  lastName?: string,
  username?: string
): string => {
  const parts: string[] = [];

  if (firstName) parts.push(firstName);
  if (lastName) parts.push(lastName);

  if (parts.length > 0) {
    return parts.join(' ');
  }

  if (username) {
    return `@${username}`;
  }

  return 'Пользователь';
};

/**
 * Format deposit level with emoji
 */
export const formatDepositLevel = (level: number): string => {
  const emojis = ['', '🥉', '🥈', '🥇', '💎', '👑'];
  const emoji = emojis[level] || '⭐';
  return `${emoji} Уровень ${level}`;
};

/**
 * Format referral count text
 */
export const formatReferralCount = (count: number): string => {
  if (count === 0) {
    return 'Нет рефералов';
  }

  return `${count} ${pluralize(count, 'реферал', 'реферала', 'рефералов')}`;
};

/**
 * Format earning text
 */
export const formatEarning = (amount: number, source: string = 'реферал'): string => {
  return `+${formatCurrency(amount)} от ${pluralize(1, source, source + 'ов', source + 'ов')}`;
};

/**
 * Mask sensitive data (keep first and last N characters)
 */
export const maskSensitiveData = (
  data: string,
  visibleChars: number = 2,
  maskChar: string = '*'
): string => {
  if (!data || data.length <= visibleChars * 2) {
    return data;
  }

  const start = data.substring(0, visibleChars);
  const end = data.substring(data.length - visibleChars);
  const middle = maskChar.repeat(data.length - visibleChars * 2);

  return `${start}${middle}${end}`;
};

/**
 * Format boolean as Yes/No in Russian
 */
export const formatBoolean = (value: boolean): string => {
  return value ? 'Да' : 'Нет';
};

/**
 * Format array as numbered list
 */
export const formatNumberedList = (items: string[]): string => {
  return items.map((item, index) => `${index + 1}. ${item}`).join('\n');
};

/**
 * Format array as bulleted list
 */
export const formatBulletedList = (items: string[], bullet: string = '•'): string => {
  return items.map(item => `${bullet} ${item}`).join('\n');
};

/**
 * Escape markdown special characters
 */
export const escapeMarkdown = (text: string): string => {
  if (!text) return '';

  return text
    .replace(/[_*[\]()~`>#+=|{}.!-]/g, '\\$&')
    .replace(/\n/g, '\\n');
};

/**
 * Format error message for user display
 */
export const formatErrorMessage = (error: unknown): string => {
  if (error instanceof Error) {
    return error.message;
  }

  if (typeof error === 'string') {
    return error;
  }

  return 'Произошла неизвестная ошибка';
};

export default {
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
};
