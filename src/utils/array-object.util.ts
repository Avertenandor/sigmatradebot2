/**
 * Array and Object Utilities
 * Helper functions for working with arrays and objects
 */

/**
 * Group array items by key
 */
export const groupBy = <T>(
  array: T[],
  keyGetter: (item: T) => string | number
): Record<string | number, T[]> => {
  return array.reduce((result, item) => {
    const key = keyGetter(item);
    if (!result[key]) {
      result[key] = [];
    }
    result[key].push(item);
    return result;
  }, {} as Record<string | number, T[]>);
};

/**
 * Remove duplicate items from array
 */
export const unique = <T>(array: T[]): T[] => {
  return Array.from(new Set(array));
};

/**
 * Remove duplicate objects by key
 */
export const uniqueBy = <T>(
  array: T[],
  keyGetter: (item: T) => string | number
): T[] => {
  const seen = new Set<string | number>();
  return array.filter(item => {
    const key = keyGetter(item);
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
};

/**
 * Chunk array into smaller arrays
 */
export const chunk = <T>(array: T[], size: number): T[][] => {
  const chunks: T[][] = [];
  for (let i = 0; i < array.length; i += size) {
    chunks.push(array.slice(i, i + size));
  }
  return chunks;
};

/**
 * Shuffle array randomly
 */
export const shuffle = <T>(array: T[]): T[] => {
  const shuffled = [...array];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
};

/**
 * Get random item from array
 */
export const randomItem = <T>(array: T[]): T | undefined => {
  if (array.length === 0) return undefined;
  return array[Math.floor(Math.random() * array.length)];
};

/**
 * Get random items from array (without duplicates)
 */
export const randomItems = <T>(array: T[], count: number): T[] => {
  const shuffled = shuffle(array);
  return shuffled.slice(0, Math.min(count, array.length));
};

/**
 * Sort array by multiple keys
 */
export const sortBy = <T>(
  array: T[],
  ...keyGetters: ((item: T) => any)[]
): T[] => {
  return [...array].sort((a, b) => {
    for (const keyGetter of keyGetters) {
      const aValue = keyGetter(a);
      const bValue = keyGetter(b);

      if (aValue < bValue) return -1;
      if (aValue > bValue) return 1;
    }
    return 0;
  });
};

/**
 * Check if arrays are equal
 */
export const arraysEqual = <T>(arr1: T[], arr2: T[]): boolean => {
  if (arr1.length !== arr2.length) return false;

  return arr1.every((value, index) => value === arr2[index]);
};

/**
 * Find differences between two arrays
 */
export const arrayDiff = <T>(arr1: T[], arr2: T[]): {
  added: T[];
  removed: T[];
} => {
  const set1 = new Set(arr1);
  const set2 = new Set(arr2);

  const added = arr2.filter(item => !set1.has(item));
  const removed = arr1.filter(item => !set2.has(item));

  return { added, removed };
};

/**
 * Get intersection of two arrays
 */
export const intersection = <T>(arr1: T[], arr2: T[]): T[] => {
  const set2 = new Set(arr2);
  return arr1.filter(item => set2.has(item));
};

/**
 * Get union of two arrays (without duplicates)
 */
export const union = <T>(arr1: T[], arr2: T[]): T[] => {
  return unique([...arr1, ...arr2]);
};

/**
 * Deep clone object
 */
export const deepClone = <T>(obj: T): T => {
  return JSON.parse(JSON.stringify(obj));
};

/**
 * Pick specific keys from object
 */
export const pick = <T extends object, K extends keyof T>(
  obj: T,
  keys: K[]
): Pick<T, K> => {
  const result = {} as Pick<T, K>;

  keys.forEach(key => {
    if (key in obj) {
      result[key] = obj[key];
    }
  });

  return result;
};

/**
 * Omit specific keys from object
 */
export const omit = <T extends object, K extends keyof T>(
  obj: T,
  keys: K[]
): Omit<T, K> => {
  const result = { ...obj };

  keys.forEach(key => {
    delete result[key];
  });

  return result;
};

/**
 * Check if object is empty
 */
export const isEmpty = (obj: any): boolean => {
  if (obj === null || obj === undefined) return true;
  if (typeof obj === 'string' || Array.isArray(obj)) return obj.length === 0;
  if (typeof obj === 'object') return Object.keys(obj).length === 0;
  return false;
};

/**
 * Deep merge objects
 */
export const deepMerge = <T extends object>(target: T, ...sources: Partial<T>[]): T => {
  if (!sources.length) return target;

  const source = sources.shift();

  if (source === undefined) return target;

  if (isObject(target) && isObject(source)) {
    Object.keys(source).forEach(key => {
      const sourceValue = source[key as keyof typeof source];
      const targetValue = target[key as keyof T];

      if (isObject(sourceValue)) {
        if (!targetValue) {
          Object.assign(target, { [key]: {} });
        }
        deepMerge(targetValue as any, sourceValue as any);
      } else {
        Object.assign(target, { [key]: sourceValue });
      }
    });
  }

  return deepMerge(target, ...sources);
};

/**
 * Check if value is object
 */
const isObject = (item: any): boolean => {
  return item !== null && typeof item === 'object' && !Array.isArray(item);
};

/**
 * Flatten nested object
 */
export const flattenObject = (
  obj: Record<string, any>,
  prefix: string = ''
): Record<string, any> => {
  return Object.keys(obj).reduce((acc, key) => {
    const prefixedKey = prefix ? `${prefix}.${key}` : key;

    if (typeof obj[key] === 'object' && obj[key] !== null && !Array.isArray(obj[key])) {
      Object.assign(acc, flattenObject(obj[key], prefixedKey));
    } else {
      acc[prefixedKey] = obj[key];
    }

    return acc;
  }, {} as Record<string, any>);
};

/**
 * Get value from nested object by path
 */
export const getNestedValue = (
  obj: any,
  path: string,
  defaultValue?: any
): any => {
  const keys = path.split('.');
  let current = obj;

  for (const key of keys) {
    if (current === null || current === undefined || !(key in current)) {
      return defaultValue;
    }
    current = current[key];
  }

  return current;
};

/**
 * Set value in nested object by path
 */
export const setNestedValue = (
  obj: any,
  path: string,
  value: any
): void => {
  const keys = path.split('.');
  const lastKey = keys.pop();

  if (!lastKey) return;

  let current = obj;

  for (const key of keys) {
    if (!(key in current) || typeof current[key] !== 'object') {
      current[key] = {};
    }
    current = current[key];
  }

  current[lastKey] = value;
};

/**
 * Compare two objects for equality
 */
export const objectsEqual = (obj1: any, obj2: any): boolean => {
  return JSON.stringify(obj1) === JSON.stringify(obj2);
};

/**
 * Filter object by predicate
 */
export const filterObject = <T extends object>(
  obj: T,
  predicate: (key: keyof T, value: T[keyof T]) => boolean
): Partial<T> => {
  return Object.keys(obj).reduce((result, key) => {
    const typedKey = key as keyof T;
    if (predicate(typedKey, obj[typedKey])) {
      result[typedKey] = obj[typedKey];
    }
    return result;
  }, {} as Partial<T>);
};

/**
 * Map object values
 */
export const mapObject = <T extends object, R>(
  obj: T,
  mapper: (key: keyof T, value: T[keyof T]) => R
): Record<keyof T, R> => {
  return Object.keys(obj).reduce((result, key) => {
    const typedKey = key as keyof T;
    result[typedKey] = mapper(typedKey, obj[typedKey]);
    return result;
  }, {} as Record<keyof T, R>);
};

/**
 * Compact array (remove falsy values)
 */
export const compact = <T>(array: (T | null | undefined | false | '' | 0)[]): T[] => {
  return array.filter(Boolean) as T[];
};

/**
 * Debounce function
 */
export const debounce = <T extends (...args: any[]) => any>(
  func: T,
  wait: number
): ((...args: Parameters<T>) => void) => {
  let timeout: NodeJS.Timeout | null = null;

  return function(...args: Parameters<T>) {
    if (timeout) {
      clearTimeout(timeout);
    }

    timeout = setTimeout(() => {
      func(...args);
    }, wait);
  };
};

/**
 * Throttle function
 */
export const throttle = <T extends (...args: any[]) => any>(
  func: T,
  limit: number
): ((...args: Parameters<T>) => void) => {
  let inThrottle: boolean = false;

  return function(...args: Parameters<T>) {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => {
        inThrottle = false;
      }, limit);
    }
  };
};

export default {
  groupBy,
  unique,
  uniqueBy,
  chunk,
  shuffle,
  randomItem,
  randomItems,
  sortBy,
  arraysEqual,
  arrayDiff,
  intersection,
  union,
  deepClone,
  pick,
  omit,
  isEmpty,
  deepMerge,
  flattenObject,
  getNestedValue,
  setNestedValue,
  objectsEqual,
  filterObject,
  mapObject,
  compact,
  debounce,
  throttle,
};
