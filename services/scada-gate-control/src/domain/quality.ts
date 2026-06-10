/**
 * Quality classifies how much we trust the latest reading of a point.
 * Ordering matches the spec's enumeration in the polling section.
 */
export type Quality = 'ok' | 'stale' | 'offline' | 'modbus_exception' | 'decode_error';

export const QUALITIES: readonly Quality[] = [
  'ok',
  'stale',
  'offline',
  'modbus_exception',
  'decode_error',
];

/** Only fresh, successfully-decoded data ('ok') is trustworthy enough to act on. */
export function isWritableQuality(quality: Quality): boolean {
  return quality === 'ok';
}

/** Severity ordering — higher is worse. Used to aggregate per-point qualities. */
const QUALITY_RANK: Record<Quality, number> = {
  ok: 0,
  stale: 1,
  decode_error: 2,
  modbus_exception: 3,
  offline: 4,
};

/** Returns the worse (higher-severity) of two qualities; ties return the first. */
export function worseQuality(a: Quality, b: Quality): Quality {
  return QUALITY_RANK[a] >= QUALITY_RANK[b] ? a : b;
}

export type MarkerColor = 'green' | 'yellow' | 'red';

/** Map marker colour per spec: green = ok, yellow = stale, red = anything worse. */
export function markerColor(quality: Quality): MarkerColor {
  if (quality === 'ok') return 'green';
  if (quality === 'stale') return 'yellow';
  return 'red';
}
