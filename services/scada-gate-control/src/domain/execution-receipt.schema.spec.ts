import { existsSync, readFileSync } from 'fs';
import { dirname, join } from 'path';

import { describe, expect, it } from 'vitest';

import { EXECUTION_RECEIPT_SCHEMA_V1 } from './execution-receipt.schema';

function contractSchemaPath(): string {
  let dir = __dirname;
  for (let index = 0; index < 8; index += 1) {
    const candidate = join(
      dir,
      'contracts',
      'machine-execution',
      'v1',
      'execution-receipt.schema.json',
    );
    if (existsSync(candidate)) return candidate;
    dir = dirname(dir);
  }
  throw new Error('execution-receipt.schema.json not found');
}

describe('EXECUTION_RECEIPT_SCHEMA_V1', () => {
  it('is structurally identical to the shared v1 contract', () => {
    expect(EXECUTION_RECEIPT_SCHEMA_V1).toEqual(
      JSON.parse(readFileSync(contractSchemaPath(), 'utf-8')),
    );
  });
});
