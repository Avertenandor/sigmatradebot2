/**
 * Unit Tests: Array and Object Utilities
 * Tests for array/object manipulation functions
 */

import {
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
} from '../../src/utils/array-object.util';

describe('Array and Object Utilities', () => {
  describe('groupBy', () => {
    it('should group items by key', () => {
      const items = [
        { type: 'fruit', name: 'apple' },
        { type: 'fruit', name: 'banana' },
        { type: 'vegetable', name: 'carrot' },
      ];

      const grouped = groupBy(items, item => item.type);

      expect(grouped['fruit']).toHaveLength(2);
      expect(grouped['vegetable']).toHaveLength(1);
    });

    it('should handle empty array', () => {
      const result = groupBy([], item => item);
      expect(result).toEqual({});
    });
  });

  describe('unique', () => {
    it('should remove duplicates', () => {
      expect(unique([1, 2, 2, 3, 3, 3])).toEqual([1, 2, 3]);
      expect(unique(['a', 'b', 'a', 'c'])).toEqual(['a', 'b', 'c']);
    });

    it('should handle empty array', () => {
      expect(unique([])).toEqual([]);
    });
  });

  describe('uniqueBy', () => {
    it('should remove duplicates by key', () => {
      const items = [
        { id: 1, name: 'first' },
        { id: 2, name: 'second' },
        { id: 1, name: 'duplicate' },
      ];

      const result = uniqueBy(items, item => item.id);

      expect(result).toHaveLength(2);
      expect(result[0].name).toBe('first');
    });

    it('should handle empty array', () => {
      expect(uniqueBy([], item => item)).toEqual([]);
    });
  });

  describe('chunk', () => {
    it('should chunk array into smaller arrays', () => {
      const result = chunk([1, 2, 3, 4, 5], 2);

      expect(result).toHaveLength(3);
      expect(result[0]).toEqual([1, 2]);
      expect(result[1]).toEqual([3, 4]);
      expect(result[2]).toEqual([5]);
    });

    it('should handle empty array', () => {
      expect(chunk([], 2)).toEqual([]);
    });

    it('should handle chunk size larger than array', () => {
      expect(chunk([1, 2], 5)).toEqual([[1, 2]]);
    });
  });

  describe('shuffle', () => {
    it('should shuffle array', () => {
      const original = [1, 2, 3, 4, 5];
      const shuffled = shuffle(original);

      expect(shuffled).toHaveLength(original.length);
      expect(shuffled).toEqual(expect.arrayContaining(original));
    });

    it('should not modify original array', () => {
      const original = [1, 2, 3];
      const originalCopy = [...original];
      shuffle(original);

      expect(original).toEqual(originalCopy);
    });
  });

  describe('randomItem', () => {
    it('should return random item from array', () => {
      const items = [1, 2, 3, 4, 5];
      const result = randomItem(items);

      expect(items).toContain(result);
    });

    it('should return undefined for empty array', () => {
      expect(randomItem([])).toBeUndefined();
    });
  });

  describe('randomItems', () => {
    it('should return random items without duplicates', () => {
      const items = [1, 2, 3, 4, 5];
      const result = randomItems(items, 3);

      expect(result).toHaveLength(3);
      expect(unique(result)).toHaveLength(3);
      result.forEach(item => {
        expect(items).toContain(item);
      });
    });

    it('should handle count larger than array', () => {
      const items = [1, 2, 3];
      const result = randomItems(items, 10);

      expect(result).toHaveLength(3);
    });
  });

  describe('sortBy', () => {
    it('should sort by single key', () => {
      const items = [
        { age: 30, name: 'Alice' },
        { age: 20, name: 'Bob' },
        { age: 25, name: 'Charlie' },
      ];

      const result = sortBy(items, item => item.age);

      expect(result[0].age).toBe(20);
      expect(result[2].age).toBe(30);
    });

    it('should sort by multiple keys', () => {
      const items = [
        { age: 30, name: 'Alice' },
        { age: 20, name: 'Bob' },
        { age: 20, name: 'Alice' },
      ];

      const result = sortBy(items, item => item.age, item => item.name);

      expect(result[0]).toEqual({ age: 20, name: 'Alice' });
      expect(result[1]).toEqual({ age: 20, name: 'Bob' });
    });

    it('should not modify original array', () => {
      const original = [{ x: 3 }, { x: 1 }, { x: 2 }];
      const originalCopy = JSON.parse(JSON.stringify(original));
      sortBy(original, item => item.x);

      expect(original).toEqual(originalCopy);
    });
  });

  describe('arraysEqual', () => {
    it('should return true for equal arrays', () => {
      expect(arraysEqual([1, 2, 3], [1, 2, 3])).toBe(true);
    });

    it('should return false for different arrays', () => {
      expect(arraysEqual([1, 2, 3], [1, 2, 4])).toBe(false);
      expect(arraysEqual([1, 2], [1, 2, 3])).toBe(false);
    });
  });

  describe('arrayDiff', () => {
    it('should find added and removed items', () => {
      const result = arrayDiff([1, 2, 3], [2, 3, 4]);

      expect(result.added).toEqual([4]);
      expect(result.removed).toEqual([1]);
    });

    it('should handle no changes', () => {
      const result = arrayDiff([1, 2, 3], [1, 2, 3]);

      expect(result.added).toHaveLength(0);
      expect(result.removed).toHaveLength(0);
    });
  });

  describe('intersection', () => {
    it('should find common items', () => {
      const result = intersection([1, 2, 3, 4], [3, 4, 5, 6]);

      expect(result).toEqual([3, 4]);
    });

    it('should handle no intersection', () => {
      expect(intersection([1, 2], [3, 4])).toHaveLength(0);
    });
  });

  describe('union', () => {
    it('should combine arrays without duplicates', () => {
      const result = union([1, 2, 3], [3, 4, 5]);

      expect(result).toHaveLength(5);
      expect(result).toEqual(expect.arrayContaining([1, 2, 3, 4, 5]));
    });
  });

  describe('deepClone', () => {
    it('should create deep copy of object', () => {
      const original = { a: 1, b: { c: 2 } };
      const clone = deepClone(original);

      clone.b.c = 999;

      expect(original.b.c).toBe(2);
      expect(clone.b.c).toBe(999);
    });

    it('should clone arrays', () => {
      const original = [1, 2, [3, 4]];
      const clone = deepClone(original);

      clone[2][0] = 999;

      expect(original[2][0]).toBe(3);
    });
  });

  describe('pick', () => {
    it('should pick specified keys', () => {
      const obj = { a: 1, b: 2, c: 3 };
      const result = pick(obj, ['a', 'c']);

      expect(result).toEqual({ a: 1, c: 3 });
      expect('b' in result).toBe(false);
    });

    it('should handle non-existent keys', () => {
      const obj = { a: 1 };
      const result = pick(obj, ['a', 'b' as any]);

      expect(result).toEqual({ a: 1 });
    });
  });

  describe('omit', () => {
    it('should omit specified keys', () => {
      const obj = { a: 1, b: 2, c: 3 };
      const result = omit(obj, ['b']);

      expect(result).toEqual({ a: 1, c: 3 });
      expect('b' in result).toBe(false);
    });
  });

  describe('isEmpty', () => {
    it('should detect empty values', () => {
      expect(isEmpty(null)).toBe(true);
      expect(isEmpty(undefined)).toBe(true);
      expect(isEmpty('')).toBe(true);
      expect(isEmpty([])).toBe(true);
      expect(isEmpty({})).toBe(true);
    });

    it('should detect non-empty values', () => {
      expect(isEmpty('text')).toBe(false);
      expect(isEmpty([1])).toBe(false);
      expect(isEmpty({ a: 1 })).toBe(false);
      expect(isEmpty(0)).toBe(false);
    });
  });

  describe('deepMerge', () => {
    it('should merge nested objects', () => {
      const target = { a: 1, b: { x: 1, y: 2 } };
      const source = { b: { y: 3, z: 4 }, c: 5 };

      const result = deepMerge(target, source);

      expect(result.a).toBe(1);
      expect(result.b.x).toBe(1);
      expect(result.b.y).toBe(3);
      expect(result.b.z).toBe(4);
      expect(result.c).toBe(5);
    });

    it('should handle multiple sources', () => {
      const result = deepMerge({ a: 1 }, { b: 2 }, { c: 3 });

      expect(result).toEqual({ a: 1, b: 2, c: 3 });
    });
  });

  describe('flattenObject', () => {
    it('should flatten nested object', () => {
      const obj = {
        a: 1,
        b: {
          c: 2,
          d: {
            e: 3,
          },
        },
      };

      const result = flattenObject(obj);

      expect(result).toEqual({
        'a': 1,
        'b.c': 2,
        'b.d.e': 3,
      });
    });

    it('should handle arrays', () => {
      const obj = { a: [1, 2, 3] };
      const result = flattenObject(obj);

      expect(result.a).toEqual([1, 2, 3]);
    });
  });

  describe('getNestedValue', () => {
    it('should get nested value by path', () => {
      const obj = { a: { b: { c: 123 } } };

      expect(getNestedValue(obj, 'a.b.c')).toBe(123);
      expect(getNestedValue(obj, 'a.b')).toEqual({ c: 123 });
    });

    it('should return default value for missing path', () => {
      const obj = { a: 1 };

      expect(getNestedValue(obj, 'b.c', 'default')).toBe('default');
    });

    it('should handle null/undefined', () => {
      expect(getNestedValue(null, 'a.b', 'default')).toBe('default');
    });
  });

  describe('setNestedValue', () => {
    it('should set nested value by path', () => {
      const obj: any = {};

      setNestedValue(obj, 'a.b.c', 123);

      expect(obj.a.b.c).toBe(123);
    });

    it('should create missing intermediate objects', () => {
      const obj: any = { a: {} };

      setNestedValue(obj, 'a.b.c.d', 'value');

      expect(obj.a.b.c.d).toBe('value');
    });

    it('should handle empty path', () => {
      const obj: any = {};

      setNestedValue(obj, '', 123);

      expect(obj).toEqual({});
    });
  });

  describe('objectsEqual', () => {
    it('should compare objects', () => {
      expect(objectsEqual({ a: 1, b: 2 }, { a: 1, b: 2 })).toBe(true);
      expect(objectsEqual({ a: 1 }, { a: 2 })).toBe(false);
    });

    it('should handle nested objects', () => {
      const obj1 = { a: { b: 1 } };
      const obj2 = { a: { b: 1 } };

      expect(objectsEqual(obj1, obj2)).toBe(true);
    });
  });

  describe('filterObject', () => {
    it('should filter object by predicate', () => {
      const obj = { a: 1, b: 2, c: 3, d: 4 };
      const result = filterObject(obj, (key, value) => value > 2);

      expect(result).toEqual({ c: 3, d: 4 });
    });

    it('should handle empty result', () => {
      const obj = { a: 1, b: 2 };
      const result = filterObject(obj, () => false);

      expect(result).toEqual({});
    });
  });

  describe('mapObject', () => {
    it('should map object values', () => {
      const obj = { a: 1, b: 2, c: 3 };
      const result = mapObject(obj, (key, value) => value * 2);

      expect(result).toEqual({ a: 2, b: 4, c: 6 });
    });

    it('should allow changing value types', () => {
      const obj = { a: 1, b: 2 };
      const result = mapObject(obj, (key, value) => `${value}`);

      expect(result).toEqual({ a: '1', b: '2' });
    });
  });

  describe('compact', () => {
    it('should remove falsy values', () => {
      const result = compact([1, 0, '', false, null, undefined, 2, 'text']);

      expect(result).toEqual([1, 2, 'text']);
    });

    it('should handle empty array', () => {
      expect(compact([])).toEqual([]);
    });
  });

  describe('debounce', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    it('should delay function execution', () => {
      const fn = jest.fn();
      const debounced = debounce(fn, 100);

      debounced('test');
      expect(fn).not.toHaveBeenCalled();

      jest.advanceTimersByTime(50);
      expect(fn).not.toHaveBeenCalled();

      jest.advanceTimersByTime(50);
      expect(fn).toHaveBeenCalledWith('test');
    });

    it('should reset delay on multiple calls', () => {
      const fn = jest.fn();
      const debounced = debounce(fn, 100);

      debounced('first');
      jest.advanceTimersByTime(50);

      debounced('second');
      jest.advanceTimersByTime(50);

      expect(fn).not.toHaveBeenCalled();

      jest.advanceTimersByTime(50);
      expect(fn).toHaveBeenCalledTimes(1);
      expect(fn).toHaveBeenCalledWith('second');
    });
  });

  describe('throttle', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    it('should limit function calls', () => {
      const fn = jest.fn();
      const throttled = throttle(fn, 100);

      throttled('first');
      expect(fn).toHaveBeenCalledTimes(1);

      throttled('second');
      expect(fn).toHaveBeenCalledTimes(1);

      jest.advanceTimersByTime(100);

      throttled('third');
      expect(fn).toHaveBeenCalledTimes(2);
    });
  });
});
