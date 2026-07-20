import { describe, expect, it } from 'vitest';

import { buildSnapshot, emptyState, recordPoll } from '../state/store';
import type { PointReads } from '../transport/types';
import { projectGateReadback } from './gate-readback';
import type { DeviceCapabilitySnapshot } from './machine-boundary';

const thresholds = { staleAfterMs: 10_000, offlineAfterMs: 20_000 };
const LIVE = buildSnapshot(
  recordPoll(emptyState(), {
    ok: true,
    atMs: 1_000,
    reads: { gateLevel: 2, doorSw: 1, horn: 0, gateCf: 0 } as PointReads,
  }),
  1_000,
  thresholds,
);

const CAPS = {
  schema_version: 1,
  capability_release_id: 'cap-x',
  capability_hash: 'a'.repeat(64),
  capabilities: {
    'M(0,0;1,0)': {
      device_id: 'scada-rtu-07',
      adapter_gate_id: 'ch3',
      targets: [{ target_position_m: 0.45, target_level: 3 }],
    },
  },
} as unknown as DeviceCapabilitySnapshot;

const EMPTY = {
  schema_version: 1,
  capability_release_id: '__empty__',
  capability_hash: 'e'.repeat(64),
  capabilities: {},
} as unknown as DeviceCapabilitySnapshot;

describe('projectGateReadback', () => {
  it('empty (dark) capabilities project to an empty gates map', () => {
    const rb = projectGateReadback(EMPTY, LIVE, null, '2026-07-20T03:00:00.000Z');
    expect(rb.gates).toEqual({});
    expect(rb.capability_release_id).toBe('__empty__');
  });

  it('the configured site gate carries the LIVE poll level + quality', () => {
    const rb = projectGateReadback(CAPS, LIVE, 'M(0,0;1,0)', '2026-07-20T03:00:00.000Z');
    expect(rb.gates['M(0,0;1,0)'].observed_level).toBe(2); // gateLevel.raw
    expect(rb.gates['M(0,0;1,0)'].quality).toBe('ok');
    expect(rb.gates['M(0,0;1,0)'].device_id).toBe('scada-rtu-07');
  });

  it('a machine gate that is NOT the site gate is unavailable (no live source)', () => {
    const rb = projectGateReadback(CAPS, LIVE, null, '2026-07-20T03:00:00.000Z');
    expect(rb.gates['M(0,0;1,0)'].observed_level).toBeNull();
    expect(rb.gates['M(0,0;1,0)'].quality).toBe('unavailable');
  });

  it('carries the capability_hash + observed_at for the reconciler', () => {
    const rb = projectGateReadback(CAPS, LIVE, 'M(0,0;1,0)', '2026-07-20T03:00:00.000Z');
    expect(rb.capability_hash).toBe('a'.repeat(64));
    expect(rb.observed_at).toBe('2026-07-20T03:00:00.000Z');
  });
});
