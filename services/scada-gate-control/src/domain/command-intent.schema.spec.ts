import { existsSync, readFileSync } from 'fs';
import { dirname, join } from 'path';

import { describe, expect, it } from 'vitest';

import { COMMAND_INTENT_SCHEMA_V1 } from './command-intent.schema';

// The embedded schema (used at runtime because the dist deploy has no repo-root
// contracts/) MUST stay structurally identical to the PR 6.0 single source of
// truth. This drift-guard runs in dev/CI where contracts/ IS present.
function contractSchemaPath(): string {
  let dir = __dirname;
  for (let i = 0; i < 8; i += 1) {
    const candidate = join(
      dir,
      'contracts',
      'machine-boundary',
      'v1',
      'command-intent.schema.json',
    );
    if (existsSync(candidate)) return candidate;
    dir = dirname(dir);
  }
  throw new Error('command-intent.schema.json not found under contracts/machine-boundary/v1');
}

describe('COMMAND_INTENT_SCHEMA_V1', () => {
  it('is structurally identical to the contracts/ v1 source of truth (no drift)', () => {
    const onDisk = JSON.parse(readFileSync(contractSchemaPath(), 'utf-8')) as unknown;
    expect(COMMAND_INTENT_SCHEMA_V1).toEqual(onDisk);
  });
});
