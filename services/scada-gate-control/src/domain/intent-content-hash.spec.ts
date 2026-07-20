import { existsSync, readFileSync } from 'fs';
import { dirname, join } from 'path';

import { describe, expect, it } from 'vitest';

import { intentContentHash } from './intent-content-hash';
import type { CommandIntent } from './machine-boundary';

// The golden cross-language vector: Node `canonicalize` + sha256 over the shadow
// fixture equals the scheduler's Python `command_intent_content_hash`
// (`sha256(canonicalize(model_dump()))`, NO domain prefix). If either side's
// canonicalization drifts, this fails — the single guard against silent
// cross-service hash divergence.
const GOLDEN_SHADOW_HASH = '3ef5a28c4937e5b4d541b214a8b89c8b8a6a088807371634c87d5142f2804216';
// Additional golden vectors, each recomputed from the scheduler's Python
// canonicalize+sha256 over the same fixture. `close` pins the 0.0-position (target
// exactly 0) number formatting; `operator-approved` pins the alternate mode. They
// harden the guard against a future `canonicalize` library swap.
const GOLDEN_VECTORS: ReadonlyArray<readonly [string, string]> = [
  ['command-intent.shadow.valid.json', GOLDEN_SHADOW_HASH],
  [
    'command-intent.close.valid.json',
    '276401790b652409fb5ee4f58fb6dd6b687b993c7f6d5ea2c15c406b99abf1eb',
  ],
  [
    'command-intent.operator-approved.valid.json',
    '04d65b76af2432a8dc680eb5fe612e73a465feaac2dace899a0790f2c90c4867',
  ],
];

function fixturesDir(): string {
  let dir = __dirname;
  for (let i = 0; i < 8; i += 1) {
    const candidate = join(dir, 'contracts', 'machine-boundary', 'v1', 'fixtures', 'valid');
    if (existsSync(join(candidate, 'command-intent.shadow.valid.json'))) return candidate;
    dir = dirname(dir);
  }
  throw new Error('command-intent.shadow.valid.json fixture not found');
}

function loadIntent(name: string): CommandIntent {
  return JSON.parse(readFileSync(join(fixturesDir(), name), 'utf-8')) as CommandIntent;
}

describe('intentContentHash', () => {
  it.each(GOLDEN_VECTORS)('reproduces the golden cross-language hash of %s', (name, hash) => {
    expect(intentContentHash(loadIntent(name))).toBe(hash);
  });

  it('is invariant to input key order (canonicalization sorts keys)', () => {
    const intent = loadIntent('command-intent.shadow.valid.json') as unknown as Record<
      string,
      unknown
    >;
    // Rebuild the same object with keys inserted in reverse order.
    const reordered = Object.fromEntries(
      Object.entries(intent).reverse(),
    ) as unknown as CommandIntent;
    expect(intentContentHash(reordered)).toBe(GOLDEN_SHADOW_HASH);
  });

  it('changes when any field changes (binds the whole intent)', () => {
    const intent = loadIntent('command-intent.shadow.valid.json');
    const mutated = { ...intent, target_level: intent.target_level + 1 } as CommandIntent;
    expect(intentContentHash(mutated)).not.toBe(GOLDEN_SHADOW_HASH);
  });

  it('is a lowercase 64-hex sha256 digest', () => {
    expect(intentContentHash(loadIntent('command-intent.close.valid.json'))).toMatch(
      /^[0-9a-f]{64}$/,
    );
  });
});
