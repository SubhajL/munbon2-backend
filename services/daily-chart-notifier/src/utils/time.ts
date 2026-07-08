import { subHours } from "date-fns";
import { formatInTimeZone, utcToZonedTime } from "date-fns-tz";

const DEFAULT_TIMEZONE = "Asia/Bangkok";

export function bangkokNow(timezone: string = DEFAULT_TIMEZONE): Date {
  return utcToZonedTime(new Date(), timezone);
}

export function twentyFourHoursAgo(
  now: Date,
  timezone: string = DEFAULT_TIMEZONE,
): Date {
  const zonedNow = utcToZonedTime(now, timezone);
  return subHours(zonedNow, 24);
}

export function formatBangkokTime(
  date: Date,
  formatStr: string = "yyyy-MM-dd HH:mm:ss",
  timezone: string = DEFAULT_TIMEZONE,
): string {
  return formatInTimeZone(date, timezone, formatStr);
}

export function formatForEmailSubject(
  date: Date,
  timezone: string = DEFAULT_TIMEZONE,
): string {
  return formatInTimeZone(date, timezone, "yyyy-MM-dd");
}

export function formatForLogTimestamp(
  date: Date,
  timezone: string = DEFAULT_TIMEZONE,
): string {
  return formatInTimeZone(date, timezone, "yyyy-MM-dd HH:mm:ss zzz");
}
