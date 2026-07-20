import { existsSync, readFileSync } from 'fs';
import { dirname, join } from 'path';

import { describe, expect, it } from 'vitest';

import { VALIDATION_RECEIPT_SCHEMA_V1 } from './validation-receipt.schema';

// Drift-guard: the embedded receipt schema (used at runtime to self-check every
// emitted receipt) MUST stay structurally identical to the PR 6.0 source of truth.
function contractSchemaPath(): string {
  let dir = __dirname;
  for (let i = 0; i < 8; i += 1) {
    const candidate = join(
      dir,
      'contracts',
      'machine-boundary',
      'v1',
      'validation-receipt.schema.json',
    );
    if (existsSync(candidate)) return candidate;
    dir = dirname(dir);
  }
  throw new Error('validation-receipt.schema.json not found under contracts/machine-boundary/v1');
}

describe('VALIDATION_RECEIPT_SCHEMA_V1', () => {
  it('is structurally identical to the contracts/ v1 source of truth (no drift)', () => {
    const onDisk = JSON.parse(readFileSync(contractSchemaPath(), 'utf-8')) as unknown;
    expect(VALIDATION_RECEIPT_SCHEMA_V1).toEqual(onDisk);
  });
});
