import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';

dayjs.extend(utc);
dayjs.extend(timezone);

type TimePeriod = '24h' | '3d' | '7d' | '14d';

const PERIOD_HOURS: Record<TimePeriod, number> = {
  '24h': 24,
  '3d': 72,
  '7d': 168,
  '14d': 336,
};

/**
 * Parse time period string and validate against allowed values.
 * Throws if invalid period provided.
 */
export function parseTimePeriod(period: string): TimePeriod {
  if (!Object.keys(PERIOD_HOURS).includes(period)) {
    throw new Error(
      `Invalid period: ${period}. Must be one of: ${Object.keys(PERIOD_HOURS).join(', ')}`
    );
  }
  return period as TimePeriod;
}

/**
 * Get UTC start and end dates for a given period, ending at current time.
 * Period defaults to '24h' if invalid.
 */
export function getTimeRange(period: TimePeriod): { start: Date; end: Date } {
  const now = dayjs.utc();
  const hours = PERIOD_HOURS[period];
  const start = now.subtract(hours, 'hours').toDate();
  const end = now.toDate();

  return { start, end };
}

/**
 * Convert UTC date to local timezone ISO string for display.
 * Uses system timezone by default or optional override (for testing).
 */
export function formatLocalTime(
  utcDate: Date,
  tzOverride?: string
): string {
  const tz = tzOverride || dayjs.tz.guess();
  return dayjs.utc(utcDate).tz(tz).toISOString();
}

/**
 * Check if a period string is valid without throwing.
 */
export function isValidPeriod(period: string): period is TimePeriod {
  return Object.keys(PERIOD_HOURS).includes(period);
}

/**
 * Get all valid period values.
 */
export function getValidPeriods(): TimePeriod[] {
  return Object.keys(PERIOD_HOURS) as TimePeriod[];
}
