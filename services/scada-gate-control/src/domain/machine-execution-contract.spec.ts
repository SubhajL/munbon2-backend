import { createHash } from 'crypto';
import { existsSync, readFileSync } from 'fs';
import { dirname, join } from 'path';

import Ajv2020 from 'ajv/dist/2020';
import { describe, expect, it } from 'vitest';

function contract(name: string): unknown {
  let dir = __dirname;
  for (let i = 0; i < 8; i += 1) {
    const path = join(dir, 'contracts', 'machine-execution', 'v1', name);
    if (existsSync(path)) return JSON.parse(readFileSync(path, 'utf-8'));
    dir = dirname(dir);
  }
  throw new Error(`contract not found: ${name}`);
}

function fileHash(name: string): string {
  let dir = __dirname;
  for (let index = 0; index < 8; index += 1) {
    const path = join(dir, 'contracts', 'machine-execution', 'v1', name);
    if (existsSync(path)) {
      const normalized = readFileSync(path).toString('utf-8').replace(/\r\n/g, '\n');
      return createHash('sha256').update(normalized).digest('hex');
    }
    dir = dirname(dir);
  }
  throw new Error(`contract not found: ${name}`);
}

describe('machine execution v1 contract', () => {
  it('validates the shared receipt example with the SCADA runtime engine', () => {
    const validate = new Ajv2020({ strict: true }).compile(
      contract('execution-receipt.schema.json') as object,
    );
    expect(validate(contract('execution-receipt.example.json'))).toBe(true);
  });

  it('pins every file and the canonical contract-set digest', () => {
    const manifest = contract('manifest.json') as {
      contract_set_sha256: string;
      schemas: Array<{ relative_path: string; sha256: string }>;
      fixtures: Array<{
        relative_path: string;
        schema: string;
        expected_valid: boolean;
        sha256: string;
      }>;
    };
    const records = [...manifest.schemas, ...manifest.fixtures].map((entry) => {
      const sha256 = fileHash(entry.relative_path);
      expect(sha256).toBe(entry.sha256);
      return 'schema' in entry
        ? {
            relative_path: entry.relative_path,
            schema: entry.schema,
            expected_valid: entry.expected_valid,
            sha256,
          }
        : { relative_path: entry.relative_path, sha256 };
    });
    const canonical = records
      .map((record) => JSON.stringify(record, Object.keys(record).sort()))
      .sort();
    const content = `munbon:machine-execution-contract-set:v1\n${canonical.join('\n')}\n`;
    expect(createHash('sha256').update(content).digest('hex')).toBe(manifest.contract_set_sha256);
  });
});
