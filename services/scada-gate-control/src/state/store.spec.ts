import { describe, expect, test } from 'vitest';
import { buildSnapshot, emptyState, recordPoll } from './store';
import type { FreshnessThresholds } from './freshness';
import type { PointReads } from '../transport/types';

const thresholds: FreshnessThresholds = { staleAfterMs: 10_000, offlineAfterMs: 20_000 };
const T0 = 1_000;
const iso = (ms: number) => new Date(ms).toISOString();

// raw device values that all decode cleanly (gate level 3 = "Level 3").
const validReads: PointReads = { gateLevel: 3, doorSw: 1, horn: 1, gateCf: 1 };

const success = (atMs: number, reads: PointReads = validReads) =>
  recordPoll(emptyState(), { ok: true, atMs, reads });

describe('buildSnapshot — never polled', () => {
  test('reports everything offline with null values', () => {
    const snap = buildSnapshot(emptyState(), T0, thresholds);
    expect(snap.connection).toBe('offline');
    expect(snap.markerColor).toBe('red');
    expect(snap.lastUpdated).toBeNull();
    expect(snap.gateLevel).toEqual({
      raw: null,
      value: null,
      quality: 'offline',
      lastUpdated: null,
      lastError: null,
    });
  });
});

describe('buildSnapshot — first poll failed before any success', () => {
  test.each<['offline' | 'modbus_exception']>([['offline'], ['modbus_exception']])(
    'propagates %s to every point',
    (quality) => {
      const state = recordPoll(emptyState(), { ok: false, atMs: T0, quality, error: 'boom' });
      const snap = buildSnapshot(state, T0, thresholds);
      expect(snap.connection).toBe(quality);
      expect(snap.markerColor).toBe('red');
      expect(snap.horn).toEqual({
        raw: null,
        value: null,
        quality,
        lastUpdated: null,
        lastError: 'boom',
      });
    },
  );
});

describe('buildSnapshot — fresh successful read', () => {
  test('decodes every point and reports ok/green', () => {
    const snap = buildSnapshot(success(T0), T0, thresholds);
    expect(snap).toEqual({
      connection: 'ok',
      markerColor: 'green',
      lastUpdated: iso(T0),
      lastError: null,
      gateLevel: {
        raw: 3,
        value: { level: 3, thaiLabel: 'เปิดระดับ 2', technicalLabel: 'Level 3', flowRate: 0.8 },
        quality: 'ok',
        lastUpdated: iso(T0),
        lastError: null,
      },
      doorSw: {
        raw: 1,
        value: { raw: 1, closed: true, thaiLabel: 'ปิด' },
        quality: 'ok',
        lastUpdated: iso(T0),
        lastError: null,
      },
      horn: {
        raw: 1,
        value: { raw: 1, on: true, thaiLabel: 'เปิด' },
        quality: 'ok',
        lastUpdated: iso(T0),
        lastError: null,
      },
      gateCf: {
        raw: 1,
        value: { raw: 1, confirmed: true },
        quality: 'ok',
        lastUpdated: iso(T0),
        lastError: null,
      },
    });
  });
});

describe('buildSnapshot — one point fails to decode', () => {
  test('marks only that point decode_error and aggregates worst to connection', () => {
    const snap = buildSnapshot(success(T0, { ...validReads, gateLevel: 9 }), T0, thresholds);
    expect(snap.gateLevel).toEqual({
      raw: 9,
      value: null,
      quality: 'decode_error',
      lastUpdated: iso(T0),
      lastError: 'Gate_Level out of range 1..4: 9',
    });
    expect(snap.horn.quality).toBe('ok');
    expect(snap.connection).toBe('decode_error');
    expect(snap.markerColor).toBe('red');
  });
});

describe('buildSnapshot — aging a successful read', () => {
  test.each<[number, string, string]>([
    [9_999, 'ok', 'green'],
    [10_000, 'stale', 'yellow'],
    [20_000, 'offline', 'red'],
  ])('age %ims -> %s/%s', (age, quality, color) => {
    const snap = buildSnapshot(success(T0), T0 + age, thresholds);
    expect([snap.connection, snap.markerColor]).toEqual([quality, color]);
    expect(snap.gateLevel.quality).toBe(quality);
  });
});

describe('buildSnapshot — failure after a prior success', () => {
  test('retains last good values but degrades quality to the failure severity', () => {
    const afterSuccess = success(T0);
    const state = recordPoll(afterSuccess, {
      ok: false,
      atMs: T0 + 500,
      quality: 'offline',
      error: 'ECONNRESET',
    });
    const snap = buildSnapshot(state, T0 + 500, thresholds); // still fresh by age, but link is down
    expect(snap.connection).toBe('offline');
    expect(snap.lastError).toBe('ECONNRESET');
    expect(snap.gateLevel.value).toEqual({
      level: 3,
      thaiLabel: 'เปิดระดับ 2',
      technicalLabel: 'Level 3',
      flowRate: 0.8,
    });
    expect(snap.gateLevel.quality).toBe('offline');
  });

  test('a transient modbus_exception while fresh degrades ok -> modbus_exception', () => {
    const state = recordPoll(success(T0), {
      ok: false,
      atMs: T0 + 100,
      quality: 'modbus_exception',
      error: 'illegal data address',
    });
    const snap = buildSnapshot(state, T0 + 100, thresholds);
    expect(snap.connection).toBe('modbus_exception');
    expect(snap.markerColor).toBe('red');
  });
});
