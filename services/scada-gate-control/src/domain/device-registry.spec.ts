import { mkdtempSync, rmSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { computeCapabilityHash } from './capability-hash';
import { emptyDeviceCapabilitySnapshot, loadDeviceCapabilitySnapshot } from './device-registry';

const CAPABILITY = {
  device_id: 'scada-rtu-07',
  adapter_gate_id: 'ch3',
  targets: [
    { target_position_m: 0.45, target_level: 3 },
    { target_position_m: 0, target_level: 0 },
  ],
};
const VALID_REGISTRY = {
  capability_release_id: 'cap-2026-07-19-a',
  capabilities: { 'M(0,0;1,0)': CAPABILITY },
};

let dir: string;
function writeRegistry(content: string): string {
  const p = join(dir, 'registry.json');
  writeFileSync(p, content);
  return p;
}

describe('loadDeviceCapabilitySnapshot', () => {
  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), 'scada-reg-'));
  });
  afterEach(() => {
    rmSync(dir, { recursive: true, force: true });
  });

  it('returns the empty dark default when the path is unset (zero machine-capable gates)', () => {
    const snap = loadDeviceCapabilitySnapshot({});
    expect(snap.capabilities).toEqual({});
    expect(snap.capability_release_id).toBe('__empty__');
    expect(snap.capability_hash).toBe(
      computeCapabilityHash({
        schema_version: 1,
        capability_release_id: '__empty__',
        capabilities: {},
      }),
    );
  });

  it('returns the empty default for a blank path', () => {
    expect(
      loadDeviceCapabilitySnapshot({ SCADA_DEVICE_REGISTRY_PATH: '   ' }).capabilities,
    ).toEqual({});
  });

  it('loads + validates a registry and computes the frozen capability_hash', () => {
    const snap = loadDeviceCapabilitySnapshot({
      SCADA_DEVICE_REGISTRY_PATH: writeRegistry(JSON.stringify(VALID_REGISTRY)),
    });
    expect(snap.schema_version).toBe(1);
    expect(Object.keys(snap.capabilities)).toEqual(['M(0,0;1,0)']);
    expect(snap.capability_hash).toBe(
      computeCapabilityHash({
        schema_version: 1,
        capability_release_id: VALID_REGISTRY.capability_release_id,
        capabilities: VALID_REGISTRY.capabilities,
      }),
    );
  });

  it('throws when the path is set but the file is missing', () => {
    expect(() =>
      loadDeviceCapabilitySnapshot({ SCADA_DEVICE_REGISTRY_PATH: join(dir, 'nope.json') }),
    ).toThrow(/cannot be read/);
  });

  it('throws on malformed JSON', () => {
    expect(() =>
      loadDeviceCapabilitySnapshot({ SCADA_DEVICE_REGISTRY_PATH: writeRegistry('{not json') }),
    ).toThrow(/not valid JSON/);
  });

  it('throws on an extra top-level key (no smuggled endpoint/hash)', () => {
    const p = writeRegistry(JSON.stringify({ ...VALID_REGISTRY, modbus_host: '10.0.0.5' }));
    expect(() => loadDeviceCapabilitySnapshot({ SCADA_DEVICE_REGISTRY_PATH: p })).toThrow(
      /exactly capability_release_id and capabilities/,
    );
  });

  it('throws on a contract-violating capability (target_level overflow)', () => {
    const bad = JSON.parse(JSON.stringify(VALID_REGISTRY));
    bad.capabilities['M(0,0;1,0)'].targets[0].target_level = 65536;
    expect(() =>
      loadDeviceCapabilitySnapshot({
        SCADA_DEVICE_REGISTRY_PATH: writeRegistry(JSON.stringify(bad)),
      }),
    ).toThrow(/does not satisfy the device-capability-snapshot v1 contract/);
  });

  it('throws on a bad gate key (not an id_token)', () => {
    const bad = { capability_release_id: 'r', capabilities: { 'bad gate key': CAPABILITY } };
    expect(() =>
      loadDeviceCapabilitySnapshot({
        SCADA_DEVICE_REGISTRY_PATH: writeRegistry(JSON.stringify(bad)),
      }),
    ).toThrow(/does not satisfy the device-capability-snapshot v1 contract/);
  });

  it('throws on a prototype-pollution gate key (__proto__ from JSON.parse)', () => {
    // Written as a raw JSON string: an object literal `{ __proto__: ... }` sets the
    // prototype, but JSON.parse defines an OWN enumerable "__proto__" key — the vector.
    const raw =
      '{"capability_release_id":"r","capabilities":{"__proto__":' +
      JSON.stringify(CAPABILITY) +
      '}}';
    expect(() =>
      loadDeviceCapabilitySnapshot({ SCADA_DEVICE_REGISTRY_PATH: writeRegistry(raw) }),
    ).toThrow(/reserved property name/);
  });

  it('throws when a device_id smuggles a transport endpoint + credential', () => {
    const bad = JSON.parse(JSON.stringify(VALID_REGISTRY));
    bad.capabilities['M(0,0;1,0)'].device_id = 'tcp://admin:secret@10.0.0.5:502';
    expect(() =>
      loadDeviceCapabilitySnapshot({
        SCADA_DEVICE_REGISTRY_PATH: writeRegistry(JSON.stringify(bad)),
      }),
    ).toThrow(/must not embed a transport endpoint or credential/);
  });

  it('throws when the capability_release_id smuggles an @ credential', () => {
    const bad = { ...VALID_REGISTRY, capability_release_id: 'admin@host' };
    expect(() =>
      loadDeviceCapabilitySnapshot({
        SCADA_DEVICE_REGISTRY_PATH: writeRegistry(JSON.stringify(bad)),
      }),
    ).toThrow(/must not embed a transport endpoint or credential/);
  });

  it('throws when the registry file exceeds the size cap', () => {
    const huge = `{"capability_release_id":"${'a'.repeat(1_100_000)}","capabilities":{}}`;
    expect(() =>
      loadDeviceCapabilitySnapshot({ SCADA_DEVICE_REGISTRY_PATH: writeRegistry(huge) }),
    ).toThrow(/exceeds the 1 MiB cap/);
  });

  it('emptyDeviceCapabilitySnapshot is itself a valid snapshot', () => {
    const snap = emptyDeviceCapabilitySnapshot();
    expect(snap.capability_hash).toMatch(/^[0-9a-f]{64}$/);
    expect(snap.capabilities).toEqual({});
  });
});
