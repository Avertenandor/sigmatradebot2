import crypto from 'crypto';
import { getEnvConfig } from '../config/env.validator';
import { logger } from './logger.util';

/**
 * PII Encryption Utility
 *
 * Шифрует персональные данные (PII - Personally Identifiable Information)
 * используя AES-256-GCM для защиты чувствительной информации в базе данных
 *
 * Защищаемые данные:
 * - Номера телефонов
 * - Email адреса
 * - Любые другие персональные данные
 */

const ALGORITHM = 'aes-256-gcm';
const IV_LENGTH = 16; // 128 bits
const AUTH_TAG_LENGTH = 16; // 128 bits
const KEY_LENGTH = 32; // 256 bits

/**
 * Получить ключ шифрования из переменных окружения
 */
function getEncryptionKey(): Buffer {
  const config = getEnvConfig();

  if (!config.ENCRYPTION_KEY) {
    logger.warn(
      'ENCRYPTION_KEY не установлен - PII данные будут храниться в открытом виде! ' +
        'Установите ENCRYPTION_KEY для production.'
    );
    // Возвращаем временный ключ для development (НЕ используйте в production!)
    return Buffer.alloc(KEY_LENGTH, 0);
  }

  try {
    // Преобразуем hex строку в Buffer
    const key = Buffer.from(config.ENCRYPTION_KEY, 'hex');

    if (key.length !== KEY_LENGTH) {
      throw new Error(
        `ENCRYPTION_KEY должен быть ${KEY_LENGTH * 2} hex символов (${KEY_LENGTH} байт). ` +
          `Получено: ${key.length} байт. Сгенерируйте: openssl rand -hex 32`
      );
    }

    return key;
  } catch (error) {
    logger.error('Ошибка при получении ENCRYPTION_KEY:', error);
    throw new Error('Invalid ENCRYPTION_KEY format');
  }
}

/**
 * Зашифровать строку
 *
 * @param plaintext - Открытый текст для шифрования
 * @returns Зашифрованная строка в формате: iv:authTag:ciphertext (все в hex)
 */
export function encrypt(plaintext: string): string {
  if (!plaintext) {
    return '';
  }

  try {
    const key = getEncryptionKey();

    // Генерируем случайный IV (Initialization Vector)
    const iv = crypto.randomBytes(IV_LENGTH);

    // Создаём cipher
    const cipher = crypto.createCipheriv(ALGORITHM, key, iv);

    // Шифруем данные
    let ciphertext = cipher.update(plaintext, 'utf8', 'hex');
    ciphertext += cipher.final('hex');

    // Получаем authentication tag
    const authTag = cipher.getAuthTag();

    // Возвращаем в формате: iv:authTag:ciphertext
    return `${iv.toString('hex')}:${authTag.toString('hex')}:${ciphertext}`;
  } catch (error) {
    logger.error('Ошибка при шифровании данных:', error);
    throw new Error('Encryption failed');
  }
}

/**
 * Расшифровать строку
 *
 * @param encryptedData - Зашифрованная строка в формате: iv:authTag:ciphertext
 * @returns Расшифрованный текст
 */
export function decrypt(encryptedData: string): string {
  if (!encryptedData) {
    return '';
  }

  try {
    const key = getEncryptionKey();

    // Парсим зашифрованные данные
    const parts = encryptedData.split(':');
    if (parts.length !== 3) {
      throw new Error('Invalid encrypted data format');
    }

    const iv = Buffer.from(parts[0], 'hex');
    const authTag = Buffer.from(parts[1], 'hex');
    const ciphertext = parts[2];

    // Создаём decipher
    const decipher = crypto.createDecipheriv(ALGORITHM, key, iv);
    decipher.setAuthTag(authTag);

    // Расшифровываем данные
    let plaintext = decipher.update(ciphertext, 'hex', 'utf8');
    plaintext += decipher.final('utf8');

    return plaintext;
  } catch (error) {
    logger.error('Ошибка при расшифровке данных:', error);
    throw new Error('Decryption failed - data may be corrupted or key is wrong');
  }
}

/**
 * Проверить, зашифрованы ли данные
 *
 * @param data - Данные для проверки
 * @returns true если данные в зашифрованном формате
 */
export function isEncrypted(data: string): boolean {
  if (!data) {
    return false;
  }

  // Проверяем формат: iv:authTag:ciphertext
  const parts = data.split(':');
  if (parts.length !== 3) {
    return false;
  }

  // Проверяем что все части - валидный hex
  const hexRegex = /^[a-fA-F0-9]+$/;
  return parts.every((part) => hexRegex.test(part));
}

/**
 * Безопасно зашифровать email
 * Проверяет формат перед шифрованием
 */
export function encryptEmail(email: string): string {
  if (!email) {
    return '';
  }

  // Базовая валидация email
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) {
    throw new Error('Invalid email format');
  }

  return encrypt(email.toLowerCase().trim());
}

/**
 * Безопасно зашифровать телефон
 * Нормализует формат перед шифрованием
 */
export function encryptPhone(phone: string): string {
  if (!phone) {
    return '';
  }

  // Нормализуем телефон (удаляем все кроме цифр и +)
  const normalized = phone.replace(/[^\d+]/g, '');

  if (normalized.length < 10) {
    throw new Error('Invalid phone number');
  }

  return encrypt(normalized);
}

/**
 * Маскировать PII данные для логирования
 * Показывает только первые и последние символы
 */
export function maskPII(data: string, type: 'email' | 'phone' | 'generic' = 'generic'): string {
  if (!data || data.length < 4) {
    return '***';
  }

  if (type === 'email') {
    const [local, domain] = data.split('@');
    if (!domain) return '***@***';

    const maskedLocal =
      local.length > 2 ? local[0] + '*'.repeat(local.length - 2) + local[local.length - 1] : '***';

    const [domainName, tld] = domain.split('.');
    const maskedDomain = domainName.length > 2 ? domainName[0] + '***' : '***';

    return `${maskedLocal}@${maskedDomain}.${tld}`;
  }

  if (type === 'phone') {
    // Показываем только последние 4 цифры
    return '*'.repeat(data.length - 4) + data.slice(-4);
  }

  // Generic masking
  if (data.length <= 6) {
    return data[0] + '*'.repeat(data.length - 2) + data[data.length - 1];
  }

  return data.substring(0, 2) + '*'.repeat(data.length - 4) + data.substring(data.length - 2);
}

/**
 * TypeORM Transformer для автоматического шифрования/расшифровки полей
 *
 * Использование в Entity:
 * @Column({ type: 'text', transformer: encryptionTransformer })
 * phone?: string;
 */
export const encryptionTransformer = {
  to: (value: string | null): string | null => {
    if (!value) return null;

    // Если уже зашифровано - не шифруем повторно
    if (isEncrypted(value)) {
      return value;
    }

    return encrypt(value);
  },

  from: (value: string | null): string | null => {
    if (!value) return null;

    // Если не зашифровано - возвращаем как есть (для обратной совместимости)
    if (!isEncrypted(value)) {
      logger.warn('Found unencrypted PII data in database - consider migration');
      return value;
    }

    return decrypt(value);
  },
};

/**
 * Мигрировать существующие незашифрованные данные
 * Используется для массового шифрования при первом внедрении
 */
export async function migrateUnencryptedData<T>(
  repository: any,
  fields: string[]
): Promise<number> {
  let migratedCount = 0;

  const entities = await repository.find();

  for (const entity of entities) {
    let modified = false;

    for (const field of fields) {
      const value = entity[field];

      if (value && !isEncrypted(value)) {
        entity[field] = encrypt(value);
        modified = true;
      }
    }

    if (modified) {
      await repository.save(entity);
      migratedCount++;
    }
  }

  logger.info(`Migrated ${migratedCount} entities with unencrypted PII data`);
  return migratedCount;
}

/**
 * Сгенерировать новый encryption key
 * Для использования в development/setup
 */
export function generateEncryptionKey(): string {
  return crypto.randomBytes(KEY_LENGTH).toString('hex');
}

/**
 * Валидировать encryption key
 */
export function validateEncryptionKey(key: string): boolean {
  if (!key) return false;

  try {
    const buffer = Buffer.from(key, 'hex');
    return buffer.length === KEY_LENGTH;
  } catch {
    return false;
  }
}
