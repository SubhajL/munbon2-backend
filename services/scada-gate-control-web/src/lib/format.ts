/** Formats an ISO timestamp as HH:MM:SS in Asia/Bangkok; '—' when absent/invalid. */
export function formatClockTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleTimeString('en-GB', { hour12: false, timeZone: 'Asia/Bangkok' });
}
