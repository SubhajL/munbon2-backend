import { readFileSync, statSync } from 'fs';

import { computeCapabilityHash } from './capability-hash';
import { DEVICE_CAPABILITY_SNAPSHOT_SCHEMA_V1 } from './device-capability-snapshot.schema';
import { newMachineBoundaryAjv } from './machine-boundary-ajv';
import type { DeviceCapabilitySnapshot } from './machine-boundary';

/**
 * PR 6.1a — strict, content-hashed device registry loader.
 *
 * Reads the operator-owned registry at `SCADA_DEVICE_REGISTRY_PATH`, assembles the
 * PR 6.0 device-capability-snapshot (`schema_version` + computed `capability_hash`),
 * and validates it against the EMBEDDED single source-of-truth schema
 * (`device-capability-snapshot.schema.ts`, drift-guarded against
 * `contracts/machine-boundary/v1/…`) via Ajv 2020 — the same setup as the 6.0
 * gate, but with NO runtime dependency on the repo-root `contracts/` tree (the dist
 * deploy ships only `dist/`). FAIL-CLOSED: an unset/empty path yields the empty dark
 * default (zero machine-capable gates); a present-but-unreadable, oversized,
 * malformed, or contract-violating registry THROWS (fail-fast at startup — never
 * boot SCADA on a broken registry). The registry is endpoint-free; register maps /
 * quantizer come from 6.1b.
 */
const EMPTY_RELEASE_ID = '__empty__';

/** A capability registry is small; cap the raw file to guard startup against a huge input. */
const MAX_REGISTRY_BYTES = 1_048_576; // 1 MiB

/**
 * Object keys that, coming from `JSON.parse`, are landmines for any consumer:
 * `__proto__` reads back as the prototype (not the value), and `constructor` /
 * `prototype` shadow structural machinery. No canonical_gate_id uses them.
 */
const RESERVED_GATE_KEYS = new Set(['__proto__', 'constructor', 'prototype']);

/** A transport endpoint or credential embedded in an id value (e.g. `tcp://u:p@host`). */
const ENDPOINT_OR_CREDENTIAL = /:\/\/|@/;

let cachedValidate: ((data: unknown) => boolean) | null = null;
function snapshotValidator(): (data: unknown) => boolean {
  if (cachedValidate) return cachedValidate;
  cachedValidate = newMachineBoundaryAjv().compile(
    DEVICE_CAPABILITY_SNAPSHOT_SCHEMA_V1 as unknown as Record<string, unknown>,
  );
  return cachedValidate;
}

function assemble(releaseId: unknown, capabilities: unknown): DeviceCapabilitySnapshot {
  const base: Record<string, unknown> = {
    schema_version: 1,
    capability_release_id: releaseId,
    capabilities,
  };
  const snapshot = { ...base, capability_hash: computeCapabilityHash(base) };
  if (!snapshotValidator()(snapshot)) {
    throw new Error('device registry does not satisfy the device-capability-snapshot v1 contract');
  }
  return snapshot as unknown as DeviceCapabilitySnapshot;
}

function assertNoEndpoint(field: string, value: unknown): void {
  if (typeof value === 'string' && ENDPOINT_OR_CREDENTIAL.test(value)) {
    throw new Error(`device registry ${field} must not embed a transport endpoint or credential`);
  }
}

/**
 * Defense-in-depth beyond the shape schema (which permits any printable ASCII id):
 * reject prototype-pollution gate keys and any id value that smuggles a `://` or `@`
 * endpoint/credential. Runs before assembly so hostile input never reaches the hash.
 */
function assertRegistryHygiene(releaseId: unknown, capabilities: unknown): void {
  assertNoEndpoint('capability_release_id', releaseId);
  if (typeof capabilities !== 'object' || capabilities === null || Array.isArray(capabilities)) {
    return; // Ajv rejects the wrong shape
  }
  for (const gateId of Object.keys(capabilities)) {
    if (RESERVED_GATE_KEYS.has(gateId)) {
      throw new Error(`device registry gate id '${gateId}' is a reserved property name`);
    }
    assertNoEndpoint(`gate id '${gateId}'`, gateId);
    const cap = (capabilities as Record<string, unknown>)[gateId];
    if (cap !== null && typeof cap === 'object') {
      const c = cap as Record<string, unknown>;
      assertNoEndpoint(`device_id for gate '${gateId}'`, c.device_id);
      assertNoEndpoint(`adapter_gate_id for gate '${gateId}'`, c.adapter_gate_id);
    }
  }
}

/** The dark default: zero machine-capable gates. */
export function emptyDeviceCapabilitySnapshot(): DeviceCapabilitySnapshot {
  return assemble(EMPTY_RELEASE_ID, {});
}

export function loadDeviceCapabilitySnapshot(
  env: NodeJS.ProcessEnv = process.env,
): DeviceCapabilitySnapshot {
  const path = env.SCADA_DEVICE_REGISTRY_PATH?.trim();
  if (!path) return emptyDeviceCapabilitySnapshot();

  // Bound peak memory BEFORE reading the whole file into a string (an oversized
  // file would otherwise OOM during the read, before any cap could fire).
  let sizeBytes: number;
  try {
    sizeBytes = statSync(path).size;
  } catch {
    throw new Error('SCADA_DEVICE_REGISTRY_PATH is set but the registry file cannot be read');
  }
  if (sizeBytes > MAX_REGISTRY_BYTES) {
    throw new Error('device registry file exceeds the 1 MiB cap');
  }

  let raw: string;
  try {
    raw = readFileSync(path, 'utf-8');
  } catch {
    throw new Error('SCADA_DEVICE_REGISTRY_PATH is set but the registry file cannot be read');
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error('device registry is not valid JSON');
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    throw new Error('device registry must be a JSON object');
  }
  const keys = Object.keys(parsed as Record<string, unknown>).sort();
  if (keys.length !== 2 || keys[0] !== 'capabilities' || keys[1] !== 'capability_release_id') {
    throw new Error(
      'device registry must contain exactly capability_release_id and capabilities (no capability_hash/schema_version)',
    );
  }
  const input = parsed as { capability_release_id: unknown; capabilities: unknown };
  assertRegistryHygiene(input.capability_release_id, input.capabilities);
  return assemble(input.capability_release_id, input.capabilities);
}
