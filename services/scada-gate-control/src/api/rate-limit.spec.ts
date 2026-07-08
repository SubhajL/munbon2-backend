import { describe, expect, test } from 'vitest';
import { SlidingWindowRateLimiter } from './rate-limit';

describe('SlidingWindowRateLimiter', () => {
  test('allows up to max within the window, then blocks', () => {
    const now = 0;
    const limiter = new SlidingWindowRateLimiter({ windowMs: 1_000, max: 2 }, () => now);

    expect(limiter.check('u:g')).toBe(true);
    expect(limiter.check('u:g')).toBe(true);
    expect(limiter.check('u:g')).toBe(false); // 3rd within window is blocked
  });

  test('keys are independent', () => {
    const now = 0;
    const limiter = new SlidingWindowRateLimiter({ windowMs: 1_000, max: 1 }, () => now);
    expect(limiter.check('a')).toBe(true);
    expect(limiter.check('b')).toBe(true); // different key, own budget
    expect(limiter.check('a')).toBe(false);
  });

  test('budget recovers after the window slides past old hits', () => {
    let now = 0;
    const limiter = new SlidingWindowRateLimiter({ windowMs: 1_000, max: 1 }, () => now);
    expect(limiter.check('u')).toBe(true);
    expect(limiter.check('u')).toBe(false);
    now = 1_001; // first hit now outside the window
    expect(limiter.check('u')).toBe(true);
  });
});
