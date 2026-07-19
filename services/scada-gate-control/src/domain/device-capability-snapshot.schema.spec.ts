import { existsSync, readFileSync } from 'fs';
import { dirname, join } from 'path';

import { describe, expect, it } from 'vitest';

import { DEVICE_CAPABILITY_SNAPSHOT_SCHEMA_V1 } from './device-capability-snapshot.schema';

// The embedded schema (used at runtime because the dist deploy has no repo-root
// contracts/) MUST stay byte-for-byte structurally identical to the PR 6.0 single
// source of truth. This drift-guard runs in dev/CI where contracts/ IS present.
function contractSchemaPath(): string {
  let dir = __dirname;
  for (let i = 0; i < 8; i += 1) {
    const candidate = join(
      dir,
      'contracts',
      'machine-boundary',
      'v1',
      'device-capability-snapshot.schema.json',
    );
    if (existsSync(candidate)) return candidate;
    dir = dirname(dir);
  }
  throw new Error(
    'device-capability-snapshot.schema.json not found under contracts/machine-boundary/v1',
  );
}

describe('DEVICE_CAPABILITY_SNAPSHOT_SCHEMA_V1', () => {
  it('is structurally identical to the contracts/ v1 source of truth (no drift)', () => {
    const onDisk = JSON.parse(readFileSync(contractSchemaPath(), 'utf-8')) as unknown;
    expect(DEVICE_CAPABILITY_SNAPSHOT_SCHEMA_V1).toEqual(onDisk);
  });
});
