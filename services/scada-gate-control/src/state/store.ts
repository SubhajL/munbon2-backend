/**
 * Latest-state store (pure). Folds poll results into an immutable state and
 * renders a `GateSnapshot` whose per-point quality is derived at read time from
 * (a) the last decode outcome and (b) the age of the last successful read.
 *
 * Quality resolution per point:
 *   - never decoded            -> last failure quality, or 'offline'
 *   - last decode errored      -> 'decode_error'
 *   - otherwise                -> age-based ok/stale/offline, degraded to the
 *                                 last poll failure's quality if one occurred
 */
import {
  decodeDoorSw,
  decodeGateCf,
  decodeGateLevel,
  decodeHorn,
  type DecodeResult,
  type DoorState,
  type GateCfState,
  type HornState,
} from '../domain/decode';
import type { GateLevelInfo } from '../domain/gate-level';
import { markerColor, worseQuality, type MarkerColor, type Quality } from '../domain/quality';
import { classifyFreshness, type FreshnessThresholds } from './freshness';
import type { PollResult } from '../transport/types';

export type PointSnapshot<T> = {
  readonly raw: number | null;
  readonly value: T | null;
  readonly quality: Quality;
  readonly lastUpdated: string | null;
  readonly lastError: string | null;
};

export type GateSnapshot = {
  readonly connection: Quality;
  readonly markerColor: MarkerColor;
  readonly lastUpdated: string | null;
  readonly lastError: string | null;
  readonly gateLevel: PointSnapshot<GateLevelInfo>;
  readonly doorSw: PointSnapshot<DoorState>;
  readonly horn: PointSnapshot<HornState>;
  readonly gateCf: PointSnapshot<GateCfState>;
};

type DecodedPoint<T> = { readonly raw: number; readonly result: DecodeResult<T> };

type DecodedReads = {
  readonly atMs: number;
  readonly gateLevel: DecodedPoint<GateLevelInfo>;
  readonly doorSw: DecodedPoint<DoorState>;
  readonly horn: DecodedPoint<HornState>;
  readonly gateCf: DecodedPoint<GateCfState>;
};

export type StoreState = {
  readonly lastDecoded: DecodedReads | null;
  readonly lastPoll: PollResult | null;
};

export function emptyState(): StoreState {
  return { lastDecoded: null, lastPoll: null };
}

export function recordPoll(state: StoreState, result: PollResult): StoreState {
  if (!result.ok) {
    return { ...state, lastPoll: result };
  }
  const { reads, atMs } = result;
  const lastDecoded: DecodedReads = {
    atMs,
    gateLevel: { raw: reads.gateLevel, result: decodeGateLevel(reads.gateLevel) },
    doorSw: { raw: reads.doorSw, result: decodeDoorSw(reads.doorSw) },
    horn: { raw: reads.horn, result: decodeHorn(reads.horn) },
    gateCf: { raw: reads.gateCf, result: decodeGateCf(reads.gateCf) },
  };
  return { lastDecoded, lastPoll: result };
}

function buildPoint<T>(
  decoded: DecodedReads | null,
  point: DecodedPoint<T> | null,
  nowMs: number,
  thresholds: FreshnessThresholds,
  failure: { quality: 'modbus_exception' | 'offline'; error: string } | null,
): PointSnapshot<T> {
  if (!decoded || !point) {
    return {
      raw: null,
      value: null,
      quality: failure ? failure.quality : 'offline',
      lastUpdated: null,
      lastError: failure ? failure.error : null,
    };
  }
  const lastUpdated = new Date(decoded.atMs).toISOString();
  if (!point.result.ok) {
    return {
      raw: point.raw,
      value: null,
      quality: 'decode_error',
      lastUpdated,
      lastError: point.result.error,
    };
  }
  const fresh = classifyFreshness(nowMs - decoded.atMs, thresholds);
  const quality = failure ? worseQuality(fresh, failure.quality) : fresh;
  return {
    raw: point.raw,
    value: point.result.value,
    quality,
    lastUpdated,
    lastError: failure ? failure.error : null,
  };
}

export function buildSnapshot(
  state: StoreState,
  nowMs: number,
  thresholds: FreshnessThresholds,
): GateSnapshot {
  const { lastDecoded, lastPoll } = state;
  const failure = lastPoll && !lastPoll.ok ? lastPoll : null;

  const gateLevel = buildPoint(
    lastDecoded,
    lastDecoded?.gateLevel ?? null,
    nowMs,
    thresholds,
    failure,
  );
  const doorSw = buildPoint(lastDecoded, lastDecoded?.doorSw ?? null, nowMs, thresholds, failure);
  const horn = buildPoint(lastDecoded, lastDecoded?.horn ?? null, nowMs, thresholds, failure);
  const gateCf = buildPoint(lastDecoded, lastDecoded?.gateCf ?? null, nowMs, thresholds, failure);

  const connection = [doorSw, horn, gateCf].reduce(
    (worst, p) => worseQuality(worst, p.quality),
    gateLevel.quality,
  );

  return {
    connection,
    markerColor: markerColor(connection),
    lastUpdated: lastDecoded ? new Date(lastDecoded.atMs).toISOString() : null,
    lastError: failure ? failure.error : null,
    gateLevel,
    doorSw,
    horn,
    gateCf,
  };
}
