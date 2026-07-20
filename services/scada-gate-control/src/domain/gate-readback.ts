/**
 * PR 6.3b — pure projection of the live gate poll into a machine-boundary readback snapshot.
 *
 * The scheduler's shadow reconciler reads this (service-authed) and compares each gate's
 * observed level against the plan's baseline. SCADA polls ONE site gate, so a machine-capable
 * gate carries a live reading ONLY when its canonical_gate_id equals the configured
 * `SCADA_SITE_CANONICAL_GATE_ID`; every other machine gate is `observed_level: null,
 * quality: 'unavailable'` (no live source — the real per-gate mapping needs D6). Empty
 * capabilities (the dark default) → an empty gates map. NOTHING here actuates or writes.
 */
import type { GateSnapshot } from '../state/store';
import type { DeviceCapability, DeviceCapabilitySnapshot } from './machine-boundary';

export type MachineGateReadback = {
  readonly device_id: string;
  readonly adapter_gate_id: string;
  /** The raw holding-register level (1..4 for the Waste Way gate), or null when unavailable. */
  readonly observed_level: number | null;
  readonly quality: string;
};

export type GateReadbackSnapshot = {
  readonly capability_release_id: string;
  readonly capability_hash: string;
  readonly observed_at: string;
  readonly gates: Readonly<Record<string, MachineGateReadback>>;
};

export function projectGateReadback(
  snapshot: DeviceCapabilitySnapshot,
  gate: GateSnapshot,
  siteCanonicalGateId: string | null,
  observedAtIso: string,
): GateReadbackSnapshot {
  const capabilities = snapshot.capabilities as Readonly<Record<string, DeviceCapability>>;
  const entries = Object.entries(capabilities).map(([gateId, capability]) => {
    const isSiteGate = siteCanonicalGateId !== null && gateId === siteCanonicalGateId;
    const readback: MachineGateReadback = isSiteGate
      ? {
          device_id: capability.device_id,
          adapter_gate_id: capability.adapter_gate_id,
          observed_level: gate.gateLevel.raw,
          quality: gate.gateLevel.quality,
        }
      : {
          device_id: capability.device_id,
          adapter_gate_id: capability.adapter_gate_id,
          observed_level: null,
          quality: 'unavailable',
        };
    return [gateId, readback] as const;
  });
  return {
    capability_release_id: snapshot.capability_release_id,
    capability_hash: snapshot.capability_hash,
    observed_at: observedAtIso,
    // Object.fromEntries writes OWN properties — a hostile gate id (already rejected by the
    // 6.1a loader) cannot pollute the prototype.
    gates: Object.fromEntries(entries),
  };
}
