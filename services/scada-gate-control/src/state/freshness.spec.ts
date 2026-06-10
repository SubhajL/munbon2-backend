import { describe, expect, test } from 'vitest';
import { classifyFreshness, type FreshnessThresholds } from './freshness';

const thresholds: FreshnessThresholds = { staleAfterMs: 10_000, offlineAfterMs: 20_000 };

describe('classifyFreshness', () => {
  test.each<[number, string]>([
    [0, 'ok'],
    [9_999, 'ok'],
    [10_000, 'stale'],
    [19_999, 'stale'],
    [20_000, 'offline'],
    [60_000, 'offline'],
  ])('age %ims -> %s at the spec boundaries', (ageMs, expected) => {
    expect(classifyFreshness(ageMs, thresholds)).toBe(expected);
  });

  test('treats negative age (clock skew) as ok', () => {
    expect(classifyFreshness(-5_000, thresholds)).toBe('ok');
  });
});
