import { createHash } from 'crypto';
import { existsSync, readFileSync, readdirSync, statSync } from 'fs';
import { basename, dirname, join, relative, sep } from 'path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { describe, expect, it } from 'vitest';

import {
  COMMAND_INTENT_FIELDS,
  COMMAND_LINEAGE_FIELDS,
  COMMAND_MODES,
  DEVICE_CAPABILITY_FIELDS,
  DEVICE_CAPABILITY_SNAPSHOT_FIELDS,
  DEVICE_TARGET_FIELDS,
  EVENT_KINDS,
  MACHINE_BOUNDARY_CONTRACT_SET_SHA256,
  VALIDATION_RECEIPT_FIELDS,
  VALIDATION_REJECTION_REASONS,
  VALIDATION_STATUSES,
} from './machine-boundary';

const SET_PREFIX = 'munbon:machine-boundary-contract-set:v1\n';

interface SchemaEntry {
  readonly relative_path: string;
  readonly sha256: string;
}
interface FixtureEntry extends SchemaEntry {
  readonly schema: string;
  readonly expected_valid: boolean;
}
interface Manifest {
  readonly schemas: readonly SchemaEntry[];
  readonly fixtures: readonly FixtureEntry[];
  readonly contract_set_sha256: string;
}
interface SchemaNode {
  readonly enum?: readonly string[];
  readonly properties?: Readonly<Record<string, SchemaNode>>;
}
interface SchemaDoc extends SchemaNode {
  readonly $id: string;
  readonly properties: Readonly<Record<string, SchemaNode>>;
  readonly $defs: Readonly<Record<string, SchemaNode>>;
}

function contractsRoot(): string {
  let dir = __dirname;
  for (let i = 0; i < 8; i += 1) {
    const candidate = join(dir, 'contracts', 'machine-boundary', 'v1');
    if (existsSync(join(candidate, 'manifest.json'))) return candidate;
    dir = dirname(dir);
  }
  throw new Error('contracts/machine-boundary/v1/manifest.json not found');
}

const ROOT = contractsRoot();

// JSON.parse natively rejects NaN/Infinity, matching the Python strict loader.
function loadJson<T>(relativePath: string): T {
  return JSON.parse(readFileSync(join(ROOT, relativePath), 'utf-8')) as T;
}

function fileSha256Norm(relativePath: string): string {
  const raw = readFileSync(join(ROOT, relativePath));
  const normalized = Buffer.from(raw.toString('latin1').replace(/\r\n/g, '\n'), 'latin1');
  return createHash('sha256').update(normalized).digest('hex');
}

// Canonical JSON matching Python json.dumps(sort_keys=True, separators=(',',':')).
function canon(obj: Record<string, unknown>): string {
  const parts = Object.keys(obj)
    .sort()
    .map((k) => `${JSON.stringify(k)}:${JSON.stringify(obj[k])}`);
  return `{${parts.join(',')}}`;
}

function allJsonRelative(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) out.push(...allJsonRelative(full));
    else if (name.endsWith('.json')) out.push(relative(ROOT, full).split(sep).join('/'));
  }
  return out;
}

const manifest = loadJson<Manifest>('manifest.json');

const ajv = new Ajv2020({ strict: true, allErrors: true, validateFormats: true });
addFormats(ajv);
const validators = new Map<string, ReturnType<typeof ajv.compile>>();
for (const s of manifest.schemas) {
  validators.set(
    basename(s.relative_path),
    ajv.compile(loadJson<Record<string, unknown>>(s.relative_path)),
  );
}

function schema(name: string): SchemaDoc {
  return loadJson<SchemaDoc>(name);
}

function keys(node: SchemaNode | undefined): Set<string> {
  return new Set(Object.keys(node?.properties ?? {}));
}

describe('machine-boundary v1 cross-language contract', () => {
  it('pins the same machine-boundary v1 content set as the manifest and Scheduler', () => {
    for (const entry of [...manifest.schemas, ...manifest.fixtures]) {
      expect(fileSha256Norm(entry.relative_path)).toBe(entry.sha256);
    }
    const records: Array<Record<string, unknown>> = [
      ...manifest.schemas.map((s) => ({
        relative_path: s.relative_path,
        sha256: fileSha256Norm(s.relative_path),
      })),
      ...manifest.fixtures.map((f) => ({
        relative_path: f.relative_path,
        schema: f.schema,
        expected_valid: f.expected_valid,
        sha256: fileSha256Norm(f.relative_path),
      })),
    ];
    const lines = records.map(canon).sort();
    let acc = SET_PREFIX;
    for (const line of lines) acc += `${line}\n`;
    const recomputed = createHash('sha256').update(Buffer.from(acc, 'utf-8')).digest('hex');
    expect(recomputed).toBe(manifest.contract_set_sha256);
    expect(recomputed).toBe(MACHINE_BOUNDARY_CONTRACT_SET_SHA256);
  });

  it('lists exactly the on-disk contract files in the manifest', () => {
    const listed = new Set([
      ...manifest.schemas.map((s) => s.relative_path),
      ...manifest.fixtures.map((f) => f.relative_path),
    ]);
    const onDisk = new Set(allJsonRelative(ROOT).filter((p) => p !== 'manifest.json'));
    expect(onDisk).toEqual(listed);
  });

  it('classifies every manifest fixture exactly as expected_valid', () => {
    for (const f of manifest.fixtures) {
      const validate = validators.get(f.schema);
      expect(validate, `no validator for ${f.schema}`).toBeTruthy();
      const ok = validate!(loadJson<unknown>(f.relative_path));
      expect(ok, `${f.relative_path} expected_valid=${f.expected_valid}`).toBe(f.expected_valid);
    }
  });

  it('matches exported field-key rosters to the schema properties', () => {
    const ci = schema('command-intent.schema.json');
    expect(keys(ci)).toEqual(new Set(COMMAND_INTENT_FIELDS));
    expect(keys(ci.$defs.lineage)).toEqual(new Set(COMMAND_LINEAGE_FIELDS));

    const vr = schema('validation-receipt.schema.json');
    expect(keys(vr)).toEqual(new Set(VALIDATION_RECEIPT_FIELDS));

    const dcs = schema('device-capability-snapshot.schema.json');
    expect(keys(dcs)).toEqual(new Set(DEVICE_CAPABILITY_SNAPSHOT_FIELDS));
    expect(keys(dcs.$defs.capability)).toEqual(new Set(DEVICE_CAPABILITY_FIELDS));
    expect(keys(dcs.$defs.target)).toEqual(new Set(DEVICE_TARGET_FIELDS));
  });

  it('pins mode, status, event-kind, and rejection-reason enums to the schema', () => {
    const ci = schema('command-intent.schema.json');
    expect(new Set(ci.properties.mode.enum)).toEqual(new Set(COMMAND_MODES));
    expect(new Set(ci.properties.event_kind.enum)).toEqual(new Set(EVENT_KINDS));

    const vr = schema('validation-receipt.schema.json');
    expect(new Set(vr.properties.status.enum)).toEqual(new Set(VALIDATION_STATUSES));
    expect(new Set(vr.$defs.reason_code.enum)).toEqual(new Set(VALIDATION_REJECTION_REASONS));
  });

  it('rejects non-UTC and impossible machine timestamps', () => {
    const naive = validators.get('command-intent.schema.json')!(
      loadJson<unknown>('fixtures/invalid/command-intent.naive-not-before.invalid.json'),
    );
    const impossible = validators.get('command-intent.schema.json')!(
      loadJson<unknown>('fixtures/invalid/command-intent.impossible-date-not-before.invalid.json'),
    );
    expect(naive).toBe(false);
    expect(impossible).toBe(false);
  });
});
