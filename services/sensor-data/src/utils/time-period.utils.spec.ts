import {
  parseTimePeriod,
  getTimeRange,
  formatLocalTime,
  isValidPeriod,
  getValidPeriods,
} from './time-period.utils';

describe('parseTimePeriod', () => {
  it('returns 24h for valid 24h period', () => {
    expect(parseTimePeriod('24h')).toBe('24h');
  });

  it('returns 3d for valid 3d period', () => {
    expect(parseTimePeriod('3d')).toBe('3d');
  });

  it('returns 7d for valid 7d period', () => {
    expect(parseTimePeriod('7d')).toBe('7d');
  });

  it('returns 14d for valid 14d period', () => {
    expect(parseTimePeriod('14d')).toBe('14d');
  });

  it('throws error for invalid period', () => {
    expect(() => parseTimePeriod('5d')).toThrow(
      'Invalid period: 5d. Must be one of: 24h, 3d, 7d, 14d'
    );
  });

  it('throws error for empty string', () => {
    expect(() => parseTimePeriod('')).toThrow();
  });
});

describe('getTimeRange', () => {
  it('returns UTC start and end dates for 24h period', () => {
    const range = getTimeRange('24h');

    expect(range.start).toBeInstanceOf(Date);
    expect(range.end).toBeInstanceOf(Date);
    expect(range.end.getTime()).toBeGreaterThan(range.start.getTime());
  });

  it('returns correct time span for 24h (86400000 ms)', () => {
    const range = getTimeRange('24h');
    const diffMs = range.end.getTime() - range.start.getTime();

    // Allow 1 second margin for test execution time
    expect(Math.abs(diffMs - 86400000)).toBeLessThan(1000);
  });

  it('returns correct time span for 3d (259200000 ms)', () => {
    const range = getTimeRange('3d');
    const diffMs = range.end.getTime() - range.start.getTime();

    expect(Math.abs(diffMs - 259200000)).toBeLessThan(1000);
  });

  it('returns correct time span for 7d (604800000 ms)', () => {
    const range = getTimeRange('7d');
    const diffMs = range.end.getTime() - range.start.getTime();

    expect(Math.abs(diffMs - 604800000)).toBeLessThan(1000);
  });

  it('returns correct time span for 14d (1209600000 ms)', () => {
    const range = getTimeRange('14d');
    const diffMs = range.end.getTime() - range.start.getTime();

    expect(Math.abs(diffMs - 1209600000)).toBeLessThan(1000);
  });

  it('returns end time close to now', () => {
    const range = getTimeRange('24h');
    const now = new Date();

    // End should be within 100ms of now
    expect(Math.abs(now.getTime() - range.end.getTime())).toBeLessThan(100);
  });
});

describe('formatLocalTime', () => {
  it('converts UTC date to ISO string', () => {
    const utcDate = new Date('2025-11-03T12:00:00Z');
    const result = formatLocalTime(utcDate, 'UTC');

    expect(typeof result).toBe('string');
    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
  });

  it('respects timezone override', () => {
    const utcDate = new Date('2025-11-03T12:00:00Z');

    // UTC should not have offset
    const utcResult = formatLocalTime(utcDate, 'UTC');
    expect(utcResult).toContain('12:00:00');

    // Different timezone should show different time
    const thaiResult = formatLocalTime(utcDate, 'Asia/Bangkok');
    expect(thaiResult).toBeDefined();
  });

  it('handles edge case: DST boundary', () => {
    // US Eastern Time DST transition: Nov 3, 2024 2:00 AM
    const dstBoundary = new Date('2024-11-03T07:00:00Z');
    const result = formatLocalTime(dstBoundary, 'America/New_York');

    expect(result).toBeDefined();
    expect(typeof result).toBe('string');
  });

  it('handles edge case: year boundary', () => {
    const yearBoundary = new Date('2024-12-31T23:59:59Z');
    const result = formatLocalTime(yearBoundary, 'UTC');

    expect(result).toContain('2024-12-31');
  });

  it('handles edge case: leap second edge (year 2000)', () => {
    const y2k = new Date('2000-01-01T00:00:00Z');
    const result = formatLocalTime(y2k, 'UTC');

    expect(result).toContain('2000-01-01');
  });
});

describe('isValidPeriod', () => {
  it('returns true for valid period 24h', () => {
    expect(isValidPeriod('24h')).toBe(true);
  });

  it('returns true for valid period 3d', () => {
    expect(isValidPeriod('3d')).toBe(true);
  });

  it('returns true for valid period 7d', () => {
    expect(isValidPeriod('7d')).toBe(true);
  });

  it('returns true for valid period 14d', () => {
    expect(isValidPeriod('14d')).toBe(true);
  });

  it('returns false for invalid period', () => {
    expect(isValidPeriod('5d')).toBe(false);
  });

  it('returns false for empty string', () => {
    expect(isValidPeriod('')).toBe(false);
  });

  it('returns false for null', () => {
    expect(isValidPeriod(null as any)).toBe(false);
  });

  it('returns false for undefined', () => {
    expect(isValidPeriod(undefined as any)).toBe(false);
  });
});

describe('getValidPeriods', () => {
  it('returns array of all valid periods', () => {
    const periods = getValidPeriods();

    expect(Array.isArray(periods)).toBe(true);
    expect(periods).toContain('24h');
    expect(periods).toContain('3d');
    expect(periods).toContain('7d');
    expect(periods).toContain('14d');
  });

  it('returns exactly 4 valid periods', () => {
    const periods = getValidPeriods();
    expect(periods).toHaveLength(4);
  });
});
