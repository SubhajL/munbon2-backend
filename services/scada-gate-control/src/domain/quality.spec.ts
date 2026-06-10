import { describe, expect, test } from 'vitest';
import {
  isWritableQuality,
  markerColor,
  worseQuality,
  type MarkerColor,
  type Quality,
} from './quality';

describe('isWritableQuality', () => {
  test.each<[Quality, boolean]>([
    ['ok', true],
    ['stale', false],
    ['offline', false],
    ['modbus_exception', false],
    ['decode_error', false],
  ])('%s -> writable=%s', (quality, expected) => {
    expect(isWritableQuality(quality)).toBe(expected);
  });
});

describe('worseQuality', () => {
  test('returns the higher-severity quality', () => {
    expect(worseQuality('ok', 'offline')).toBe('offline');
    expect(worseQuality('stale', 'decode_error')).toBe('decode_error');
    expect(worseQuality('modbus_exception', 'stale')).toBe('modbus_exception');
  });

  test('is order-independent in the value it selects', () => {
    expect(worseQuality('offline', 'ok')).toBe(worseQuality('ok', 'offline'));
  });

  test('returns the first argument on an equal-severity tie', () => {
    expect(worseQuality('ok', 'ok')).toBe('ok');
  });
});

describe('markerColor', () => {
  test.each<[Quality, MarkerColor]>([
    ['ok', 'green'],
    ['stale', 'yellow'],
    ['offline', 'red'],
    ['modbus_exception', 'red'],
    ['decode_error', 'red'],
  ])('%s -> %s', (quality, color) => {
    expect(markerColor(quality)).toBe(color);
  });
});
