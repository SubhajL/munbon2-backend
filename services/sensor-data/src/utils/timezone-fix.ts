/**
 * Timezone fix for PostgreSQL timestamp storage
 * Ensures timestamps are stored as UTC regardless of server timezone
 */

/**
 * Convert a Date object to PostgreSQL-compatible UTC timestamp string
 * This prevents double timezone conversion issues
 */
export function toUTCTimestamp(date: Date): string {
  // Convert to ISO string and remove the 'Z' to make it a naive timestamp
  // PostgreSQL will interpret this as UTC since the database timezone is UTC
  return date.toISOString().replace('Z', '');
}

/**
 * Parse timestamp components and return UTC timestamp string
 */
export function parseToUTCTimestamp(dateStr: string, timeStr: string): string {
  // Parse as UTC by adding 'Z'
  const utcDate = new Date(`${dateStr}T${timeStr}Z`);
  
  if (isNaN(utcDate.getTime())) {
    throw new Error(`Invalid date/time: ${dateStr} ${timeStr}`);
  }
  
  // Return as UTC timestamp string for PostgreSQL
  return toUTCTimestamp(utcDate);
}