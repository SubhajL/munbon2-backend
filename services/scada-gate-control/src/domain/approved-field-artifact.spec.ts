import { mkdtempSync, readFileSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

import canonicalize from 'canonicalize';
import { describe, expect, it } from 'vitest';

import {
  buildDeviceRegistryArtifact,
  extractApprovedLineageAnchor,
  lineageMatchesAnchor,
  loadApprovedLineageAnchor,
  parseApprovedFieldArtifact,
  validateApprovedRegistryCoverage,
  type ApprovedLineageAnchor,
} from './approved-field-artifact';
import { computeCapabilityHash } from './capability-hash';
import { loadDeviceCapabilitySnapshot } from './device-registry';
import type { CommandLineage } from './machine-boundary';

const EXAMPLE_PATH = join(__dirname, '__fixtures__', 'approved-field-artifact.example.json');
/** Fresh untyped clone of the raw example JSON — safe to mutate per negative test. */
function rawExample() {
  return JSON.parse(readFileSync(EXAMPLE_PATH, 'utf-8'));
}
function example() {
  return parseApprovedFieldArtifact(rawExample());
}
function tmpFile(name: string, body: string): string {
  const dir = mkdtempSync(join(tmpdir(), 'scada-6-1b-'));
  const p = join(dir, name);
  writeFileSync(p, body);
  return p;
}

// Build a full CommandLineage from the shared command-intent fixture so the pinned
// fields are real (the example artifact's anchor matches this fixture's lineage).
function fixtureLineage(): CommandLineage {
  let dir = __dirname;
  for (let i = 0; i < 8; i += 1) {
    const candidate = join(
      dir,
      'contracts',
      'machine-boundary',
      'v1',
      'fixtures',
      'valid',
      'command-intent.shadow.valid.json',
    );
    try {
      return (JSON.parse(readFileSync(candidate, 'utf-8')) as { lineage: CommandLineage }).lineage;
    } catch {
      dir = join(dir, '..');
    }
  }
  throw new Error('command-intent fixture not found');
}
const BASE_LINEAGE = fixtureLineage();

describe('parseApprovedFieldArtifact', () => {
  it('accepts the committed example artifact', () => {
    expect(example().artifact_version).toBe(1);
  });

  it('rejects an artifact missing a required top-level key', () => {
    const raw = rawExample();
    delete raw.gates;
    expect(() => parseApprovedFieldArtifact(raw)).toThrow(/gates|contract|schema/i);
  });

  it('rejects an unexpected additional property (a smuggled credential key)', () => {
    const raw = rawExample();
    raw.gates[0].password = 'hunter2';
    expect(() => parseApprovedFieldArtifact(raw)).toThrow(/contract|schema|additional/i);
  });

  it('rejects a transport endpoint/credential smuggled into device_id', () => {
    const raw = rawExample();
    raw.gates[0].device_id = 'tcp://admin:secret@10.0.0.1';
    // Tightened: prove the endpoint-hygiene guard fired (device_id is schema-valid `[!-~]+`,
    // so only that specific guard can throw here).
    expect(() => parseApprovedFieldArtifact(raw)).toThrow(/endpoint or credential/i);
  });

  it('rejects a __proto__ canonical_gate_id (projection prototype-pollution guard)', () => {
    const raw = rawExample();
    raw.gates[0].canonical_gate_id = '__proto__';
    expect(() => parseApprovedFieldArtifact(raw)).toThrow(/reserved/i);
  });

  it('the committed example carries a loud non-field-approved marker', () => {
    expect(example().approval.approval_reference).toMatch(/EXAMPLE/i);
  });
});

describe('buildDeviceRegistryArtifact (projection to the 6.1a device registry)', () => {
  it('projects to exactly {capability_release_id, capabilities}', () => {
    const doc = buildDeviceRegistryArtifact(example());
    expect(Object.keys(doc).sort()).toEqual(['capabilities', 'capability_release_id']);
    expect(doc.capability_release_id).toBe('cap-2026-07-19-a');
  });

  it('emits each capability as exactly {device_id, adapter_gate_id, targets}, dropping register/readback/evidence', () => {
    const doc = buildDeviceRegistryArtifact(example());
    const cap = doc.capabilities['M(0,0;1,0)'];
    expect(Object.keys(cap).sort()).toEqual(['adapter_gate_id', 'device_id', 'targets']);
    expect(cap.device_id).toBe('scada-rtu-07');
    expect(cap.adapter_gate_id).toBe('ch3');
  });

  it('sorts targets by target_level ascending regardless of artifact order', () => {
    const doc = buildDeviceRegistryArtifact(example());
    expect(doc.capabilities['M(0,0;1,0)'].targets).toEqual([
      { target_position_m: 0.0, target_level: 0 },
      { target_position_m: 0.45, target_level: 3 },
      { target_position_m: 1.2, target_level: 8 },
    ]);
  });

  it('regenerates byte-exactly (data lineage is reproducible)', () => {
    const a = canonicalize(buildDeviceRegistryArtifact(example()));
    const b = canonicalize(buildDeviceRegistryArtifact(parseApprovedFieldArtifact(rawExample())));
    expect(a).toBe(b);
  });

  it('projection loads cleanly through the 6.1a loader with a matching capability_hash', () => {
    const doc = buildDeviceRegistryArtifact(example());
    const path = tmpFile('registry.json', JSON.stringify(doc));
    const snapshot = loadDeviceCapabilitySnapshot({ SCADA_DEVICE_REGISTRY_PATH: path });
    // Independent oracle: recompute the hash from the assembled snapshot base.
    const expected = computeCapabilityHash({
      schema_version: 1,
      capability_release_id: doc.capability_release_id,
      capabilities: doc.capabilities,
    });
    expect(snapshot.capability_hash).toBe(expected);
    expect(snapshot.capabilities['M(0,0;1,0)'].device_id).toBe('scada-rtu-07');
  });

  it('projected capability_hash is idempotent across regenerations', () => {
    const h1 = computeCapabilityHash({
      schema_version: 1,
      ...buildDeviceRegistryArtifact(example()),
    });
    const h2 = computeCapabilityHash({
      schema_version: 1,
      ...buildDeviceRegistryArtifact(example()),
    });
    expect(h1).toBe(h2);
  });

  // Self-safety: `build` must enforce its own preconditions, not trust that the caller ran
  // parse/coverage first (a projection that silently drops or leaks a device is a control-plane
  // hazard). These construct artifacts that bypass parseApprovedFieldArtifact.
  it('THROWS on a duplicate canonical_gate_id (never silently keeps only the last device)', () => {
    const base = example();
    const dup = { ...base, gates: [base.gates[0], base.gates[0]] };
    expect(() => buildDeviceRegistryArtifact(dup)).toThrow(/duplicate/i);
  });

  it('THROWS on an endpoint/credential in a device id even if parse was bypassed', () => {
    const base = example();
    const smuggled = {
      ...base,
      gates: [{ ...base.gates[0], device_id: 'tcp://admin:secret@10.0.0.1' }],
    };
    expect(() => buildDeviceRegistryArtifact(smuggled)).toThrow(/endpoint or credential/i);
  });

  it('THROWS on a reserved __proto__ canonical_gate_id even if parse was bypassed', () => {
    const base = example();
    const hostile = { ...base, gates: [{ ...base.gates[0], canonical_gate_id: '__proto__' }] };
    expect(() => buildDeviceRegistryArtifact(hostile)).toThrow(/reserved/i);
  });
});

describe('validateApprovedRegistryCoverage', () => {
  it('covers the exact approved gate scope (no extra/missing devices)', () => {
    expect(() =>
      validateApprovedRegistryCoverage(example(), new Set(['M(0,0;1,0)'])),
    ).not.toThrow();
  });

  it('rejects a missing approved gate', () => {
    expect(() =>
      validateApprovedRegistryCoverage(example(), new Set(['M(0,0;1,0)', 'M(9,9;9,9)'])),
    ).toThrow(/missing|M\(9,9;9,9\)/);
  });

  it('rejects a device present but not in the approved scope', () => {
    expect(() => validateApprovedRegistryCoverage(example(), new Set())).toThrow(
      /not in the approved scope|unexpected|extra|M\(0,0;1,0\)/,
    );
  });

  it('rejects duplicate canonical_gate_id gates', () => {
    const raw = rawExample();
    raw.gates.push(JSON.parse(JSON.stringify(raw.gates[0])));
    const dup = parseApprovedFieldArtifact(raw);
    expect(() => validateApprovedRegistryCoverage(dup, new Set(['M(0,0;1,0)']))).toThrow(
      /duplicate/i,
    );
  });

  it('accepts a monotone quantizer that round-trips readback', () => {
    // The example: positions 0<0.45<1.2, levels 0<3<8, gaps >> 2x tolerance(0.02).
    expect(() =>
      validateApprovedRegistryCoverage(example(), new Set(['M(0,0;1,0)'])),
    ).not.toThrow();
  });

  it('rejects a non-monotone quantizer where two positions map to one level', () => {
    const raw = rawExample();
    raw.gates[0].quantizer.targets = [
      { target_position_m: 0.0, target_level: 0 },
      { target_position_m: 0.45, target_level: 3 },
      { target_position_m: 1.2, target_level: 3 },
    ];
    const art = parseApprovedFieldArtifact(raw);
    expect(() => validateApprovedRegistryCoverage(art, new Set(['M(0,0;1,0)']))).toThrow(
      /monoton|level/i,
    );
  });

  it('rejects a quantizer where position increases but level decreases', () => {
    const raw = rawExample();
    raw.gates[0].quantizer.targets = [
      { target_position_m: 0.0, target_level: 5 },
      { target_position_m: 0.45, target_level: 3 },
    ];
    const art = parseApprovedFieldArtifact(raw);
    expect(() => validateApprovedRegistryCoverage(art, new Set(['M(0,0;1,0)']))).toThrow(
      /monoton/i,
    );
  });

  it('rejects adjacent targets closer than 2x the readback tolerance', () => {
    const raw = rawExample();
    raw.gates[0].readback.tolerance_m = 0.02;
    raw.gates[0].quantizer.targets = [
      { target_position_m: 0.45, target_level: 3 },
      { target_position_m: 0.46, target_level: 4 },
    ];
    const art = parseApprovedFieldArtifact(raw);
    expect(() => validateApprovedRegistryCoverage(art, new Set(['M(0,0;1,0)']))).toThrow(
      /readback|separab|tolerance/i,
    );
  });
});

describe('extractApprovedLineageAnchor', () => {
  it('extracts exactly the 3 pinned fields', () => {
    expect(extractApprovedLineageAnchor(example())).toEqual({
      model_release_id: 'engineering-prior-v3-v1',
      model_release_content_hash: '5'.repeat(64),
      engine_descriptor_content_hash: '7'.repeat(64),
    });
  });

  it('round-trips with a loaded standalone anchor JSON', () => {
    const anchor = extractApprovedLineageAnchor(example());
    const path = tmpFile('anchor.json', JSON.stringify(anchor));
    expect(loadApprovedLineageAnchor({ SCADA_APPROVED_LINEAGE_ANCHOR_PATH: path })).toEqual(anchor);
  });
});

describe('loadApprovedLineageAnchor (dark-by-default)', () => {
  it('returns null when the env var is entirely unset (undefined → dark)', () => {
    expect(loadApprovedLineageAnchor({})).toBeNull();
  });

  it('THROWS when the env var is set-but-blank (never silently runs dark)', () => {
    // Opposite safety valence to 6.1a's registry: an empty anchor path would DISABLE a safety
    // check, so a configured-to-blank path must fail fast rather than fall back to dark.
    expect(() => loadApprovedLineageAnchor({ SCADA_APPROVED_LINEAGE_ANCHOR_PATH: '   ' })).toThrow(
      /set but blank/i,
    );
    expect(() => loadApprovedLineageAnchor({ SCADA_APPROVED_LINEAGE_ANCHOR_PATH: '' })).toThrow(
      /set but blank/i,
    );
  });

  it('throws when a configured anchor file cannot be read', () => {
    expect(() =>
      loadApprovedLineageAnchor({ SCADA_APPROVED_LINEAGE_ANCHOR_PATH: '/no/such/anchor.json' }),
    ).toThrow(/cannot be read/i);
  });

  it('throws on malformed JSON', () => {
    const path = tmpFile('bad.json', '{not json');
    expect(() => loadApprovedLineageAnchor({ SCADA_APPROVED_LINEAGE_ANCHOR_PATH: path })).toThrow(
      /valid JSON/i,
    );
  });

  it('throws on a contract-violating anchor (bad hash length)', () => {
    const path = tmpFile(
      'short.json',
      JSON.stringify({
        model_release_id: 'engineering-prior-v3-v1',
        model_release_content_hash: 'abc',
        engine_descriptor_content_hash: '7'.repeat(64),
      }),
    );
    expect(() => loadApprovedLineageAnchor({ SCADA_APPROVED_LINEAGE_ANCHOR_PATH: path })).toThrow(
      /contract|schema/i,
    );
  });

  it('throws when the anchor file exceeds the size cap', () => {
    const path = tmpFile('big.json', ' '.repeat(200_000));
    expect(() => loadApprovedLineageAnchor({ SCADA_APPROVED_LINEAGE_ANCHOR_PATH: path })).toThrow(
      /cap|size/i,
    );
  });
});

describe('lineageMatchesAnchor', () => {
  const anchor: ApprovedLineageAnchor = {
    model_release_id: BASE_LINEAGE.model_release_id,
    model_release_content_hash: BASE_LINEAGE.model_release_content_hash,
    engine_descriptor_content_hash: BASE_LINEAGE.engine_descriptor_content_hash,
  };

  it('is true when all 3 pinned fields match', () => {
    expect(lineageMatchesAnchor(BASE_LINEAGE, anchor)).toBe(true);
  });

  it('is false when model_release_id differs', () => {
    expect(lineageMatchesAnchor(BASE_LINEAGE, { ...anchor, model_release_id: 'other-v1' })).toBe(
      false,
    );
  });

  it('is false when model_release_content_hash differs', () => {
    expect(
      lineageMatchesAnchor(BASE_LINEAGE, { ...anchor, model_release_content_hash: 'a'.repeat(64) }),
    ).toBe(false);
  });

  it('is false when engine_descriptor_content_hash differs', () => {
    expect(
      lineageMatchesAnchor(BASE_LINEAGE, {
        ...anchor,
        engine_descriptor_content_hash: 'b'.repeat(64),
      }),
    ).toBe(false);
  });
});
