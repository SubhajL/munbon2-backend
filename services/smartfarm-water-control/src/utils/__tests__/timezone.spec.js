const {
  convertUTCToLocalTime,
  formatDateForMSSQL,
  getTimezoneOffsetMinutes
} = require('../timezone');

describe('getTimezoneOffsetMinutes', () => {
  test('Asia/Bangkok returns +420 minutes UTC offset', () => {
    const date = new Date('2024-01-15T12:00:00Z');
    const offset = getTimezoneOffsetMinutes('Asia/Bangkok', date);
    expect(offset).toBe(420);
  });

  test('invalid timezone returns zero offset gracefully', () => {
    const date = new Date('2024-01-15T12:00:00Z');
    const offset = getTimezoneOffsetMinutes('Invalid/Timezone', date);
    expect(offset).toBe(0);
  });

  test('offset remains constant across year for Bangkok', () => {
    const winter = new Date('2024-01-15T12:00:00Z');
    const summer = new Date('2024-07-15T12:00:00Z');
    expect(getTimezoneOffsetMinutes('Asia/Bangkok', winter)).toBe(420);
    expect(getTimezoneOffsetMinutes('Asia/Bangkok', summer)).toBe(420);
  });
});

describe('convertUTCToLocalTime', () => {
  test('UTC midnight converts to Bangkok 7am same day', () => {
    const utc = new Date('2024-01-15T00:00:00Z');
    const local = convertUTCToLocalTime(utc, 'Asia/Bangkok');
    expect(local.getUTCFullYear()).toBe(2024);
    expect(local.getUTCMonth()).toBe(0);
    expect(local.getUTCDate()).toBe(15);
    expect(local.getUTCHours()).toBe(7);
    expect(local.getUTCMinutes()).toBe(0);
    expect(local.getUTCSeconds()).toBe(0);
  });

  test('Bangkok midnight requires UTC 5pm previous day', () => {
    const utc = new Date('2024-01-15T17:00:00Z');
    const local = convertUTCToLocalTime(utc, 'Asia/Bangkok');
    expect(local.getUTCFullYear()).toBe(2024);
    expect(local.getUTCMonth()).toBe(0);
    expect(local.getUTCDate()).toBe(16);
    expect(local.getUTCHours()).toBe(0);
    expect(local.getUTCMinutes()).toBe(0);
  });

  test('preserves milliseconds precision in conversion', () => {
    const utc = new Date('2024-01-15T12:30:45.123Z');
    const local = convertUTCToLocalTime(utc, 'Asia/Bangkok');
    expect(local.getUTCMilliseconds()).toBe(123);
  });

  test('returns new Date instance without mutating input', () => {
    const utc = new Date('2024-01-15T12:00:00Z');
    const original = utc.getTime();
    const local = convertUTCToLocalTime(utc, 'Asia/Bangkok');
    expect(utc.getTime()).toBe(original);
    expect(local).not.toBe(utc);
  });
});

describe('formatDateForMSSQL', () => {
  test('single-digit months and days get zero-padded', () => {
    const date = new Date('2024-01-05T03:02:01Z');
    const formatted = formatDateForMSSQL(date);
    expect(formatted).toBe('2024-01-05 03:02:01');
  });

  test('formats midnight as 00:00:00 not 24:00:00', () => {
    const date = new Date('2024-01-15T00:00:00Z');
    const formatted = formatDateForMSSQL(date);
    expect(formatted).toMatch(/00:00:00$/);
  });

  test('preserves exact seconds without rounding', () => {
    const date = new Date('2024-01-15T12:30:59Z');
    const formatted = formatDateForMSSQL(date);
    expect(formatted).toBe('2024-01-15 12:30:59');
  });

  test('returns string format YYYY-MM-DD HH:MM:SS', () => {
    const date = new Date('2024-12-31T23:59:59Z');
    const formatted = formatDateForMSSQL(date);
    expect(formatted).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);
    expect(formatted).toBe('2024-12-31 23:59:59');
  });

  test('double-digit values remain unpadded correctly', () => {
    const date = new Date('2024-11-25T15:45:30Z');
    const formatted = formatDateForMSSQL(date);
    expect(formatted).toBe('2024-11-25 15:45:30');
  });
});
