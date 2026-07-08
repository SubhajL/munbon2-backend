/**
 * Age-based freshness classification. A reading that succeeded but is now old
 * degrades from ok -> stale -> offline. Pure: caller supplies the age.
 */

export type FreshnessThresholds = {
  /** Reading age (ms) at or beyond which data is considered stale (yellow). */
  readonly staleAfterMs: number;
  /** Reading age (ms) at or beyond which data is considered offline (red). */
  readonly offlineAfterMs: number;
};

/** Subset of Quality that pure age classification can produce. */
export type Freshness = 'ok' | 'stale' | 'offline';

export function classifyFreshness(ageMs: number, thresholds: FreshnessThresholds): Freshness {
  if (ageMs >= thresholds.offlineAfterMs) return 'offline';
  if (ageMs >= thresholds.staleAfterMs) return 'stale';
  return 'ok';
}
