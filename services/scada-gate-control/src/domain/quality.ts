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
