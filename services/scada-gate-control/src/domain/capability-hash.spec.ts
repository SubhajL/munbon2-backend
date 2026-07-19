import { existsSync, readFileSync } from 'fs';
import { dirname, join } from 'path';

import { describe, expect, it } from 'vitest';

import {
  CAPABILITY_HASH_DOMAIN_PREFIX,
  canonicalizeSnapshot,
  computeCapabilityHash,
} from './capability-hash';

// The FROZEN (PR 6.0) golden cross-language vector — a Python producer/verifier
// (4.3c/6.2) MUST reproduce this exact canonical JSON + hash.
function goldenPath(): string {
  let dir = __dirname;
  for (let i = 0; i < 8; i += 1) {
    const candidate = join(
      dir,
      'contracts',
      'machine-boundary',
      'golden',
      'device-capability-hash.golden.json',
    );
    if (existsSync(candidate)) return candidate;
    dir = dirname(dir);
  }
  throw new Error('device-capability-hash.golden.json not found');
}

const golden = JSON.parse(readFileSync(goldenPath(), 'utf-8')) as {
  domain_prefix: string;
  snapshot: Record<string, unknown>;
  canonical_json: string;
  capability_hash: string;
  number_canonicalization_vectors: {
    cases: { raw: number; canonical: string; python_json_dumps?: string }[];
  };
};

describe('capability-hash', () => {
  it('pins the golden domain prefix', () => {
    expect(CAPABILITY_HASH_DOMAIN_PREFIX).toBe(golden.domain_prefix);
    expect(CAPABILITY_HASH_DOMAIN_PREFIX).toBe('munbon:device-capability-snapshot:v1\n');
  });

  it('reproduces the golden canonical JSON (keys sorted, array order kept)', () => {
    expect(canonicalizeSnapshot(golden.snapshot)).toBe(golden.canonical_json);
  });

  it('reproduces the golden capability hash', () => {
    expect(computeCapabilityHash(golden.snapshot)).toBe(golden.capability_hash);
  });

  it('is key-order independent (canonicalization, not insertion order)', () => {
    const reordered: Record<string, unknown> = {
      capabilities: golden.snapshot.capabilities,
      schema_version: golden.snapshot.schema_version,
      capability_release_id: golden.snapshot.capability_release_id,
    };
    expect(computeCapabilityHash(reordered)).toBe(golden.capability_hash);
  });

  // The capability_hash is only cross-language-stable if every producer serializes
  // numbers with RFC-8785 / ES6 `Number.prototype.toString` semantics. A Python
  // producer using `json.dumps` diverges on the marked cases (2.0, 1e-6, 1e-7, -0.0)
  // and would compute a different hash — this pins the required output for both.
  describe('number canonicalization (cross-language conformance vectors)', () => {
    for (const c of golden.number_canonicalization_vectors.cases) {
      const label =
        c.python_json_dumps === undefined
          ? `${JSON.stringify(c.raw)} -> ${c.canonical}`
          : `${JSON.stringify(c.raw)} -> ${c.canonical} (Python json.dumps would wrongly emit ${c.python_json_dumps})`;
      it(label, () => {
        expect(canonicalizeSnapshot({ v: c.raw })).toBe(`{"v":${c.canonical}}`);
      });
    }
  });

  it('hashes the empty dark-default snapshot to a distinct pinned value', () => {
    const empty: Record<string, unknown> = {
      schema_version: 1,
      capability_release_id: '__empty__',
      capabilities: {},
    };
    expect(computeCapabilityHash(empty)).toBe(
      '6ec86898f64a3ff50038727c976a036db033685bce861c2ba160ea0a2d32798b',
    );
    expect(computeCapabilityHash(empty)).not.toBe(golden.capability_hash);
  });
});
