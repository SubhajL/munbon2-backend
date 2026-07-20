import { readFileSync } from 'fs';
import { join } from 'path';

import { describe, expect, it } from 'vitest';

import { computeCapabilityHash } from '../domain/capability-hash';
import { main, projectApprovedArtifact, type CliIo } from './build-device-registry';

const EXAMPLE_PATH = join(
  __dirname,
  '..',
  'domain',
  '__fixtures__',
  'approved-field-artifact.example.json',
);
function raw() {
  return JSON.parse(readFileSync(EXAMPLE_PATH, 'utf-8'));
}

function captureIo(files: Record<string, string> = {}): CliIo & { out: string[]; errs: string[] } {
  const out: string[] = [];
  const errs: string[] = [];
  return {
    out,
    errs,
    readFile: (p: string) => {
      if (p in files) return files[p]!;
      return readFileSync(p, 'utf-8');
    },
    log: (s: string) => out.push(s),
    err: (s: string) => errs.push(s),
  };
}

describe('projectApprovedArtifact', () => {
  it('projects the registry + anchor from the example artifact', () => {
    const { registry, anchor } = projectApprovedArtifact(raw());
    expect(registry.capability_release_id).toBe('cap-2026-07-19-a');
    expect(anchor.model_release_id).toBe('engineering-prior-v3-v1');
  });

  it('the projected registry is exactly the 2-key 6.1a snapshot base (hashable)', () => {
    const { registry } = projectApprovedArtifact(raw());
    expect(Object.keys(registry).sort()).toEqual(['capabilities', 'capability_release_id']);
    expect(computeCapabilityHash({ schema_version: 1, ...registry })).toMatch(/^[0-9a-f]{64}$/);
  });

  it('validates against an explicit approved scope and rejects a mismatch', () => {
    expect(() => projectApprovedArtifact(raw(), ['M(0,0;1,0)'])).not.toThrow();
    expect(() => projectApprovedArtifact(raw(), ['M(9,9;9,9)'])).toThrow(/missing|scope/i);
  });

  it('throws (fail-closed) on a malformed artifact', () => {
    const bad = raw();
    delete bad.approved_lineage_anchor;
    expect(() => projectApprovedArtifact(bad)).toThrow(/contract|schema/i);
  });
});

describe('build-device-registry CLI main()', () => {
  it('prints {registry, anchor} JSON and exits 0 for a valid artifact', () => {
    const io = captureIo();
    const code = main(['node', 'cli', EXAMPLE_PATH], io);
    expect(code).toBe(0);
    const printed = JSON.parse(io.out.join('\n'));
    expect(printed.registry.capability_release_id).toBe('cap-2026-07-19-a');
    expect(printed.anchor.engine_descriptor_content_hash).toBe('7'.repeat(64));
    expect(io.errs).toEqual([]);
  });

  it('exits 2 with a usage message when no artifact path is given', () => {
    const io = captureIo();
    expect(main(['node', 'cli'], io)).toBe(2);
    expect(io.errs.join(' ')).toMatch(/usage/i);
  });

  it('exits 1 when the artifact file cannot be read/parsed', () => {
    const io = captureIo();
    expect(main(['node', 'cli', '/no/such/file.json'], io)).toBe(1);
    expect(io.errs.join(' ')).toMatch(/cannot read or parse/i);
  });

  it('exits 1 (fail-closed) when the artifact violates coverage', () => {
    const io = captureIo();
    const code = main(['node', 'cli', EXAMPLE_PATH, 'M(9,9;9,9)'], io);
    expect(code).toBe(1);
    expect(io.out).toEqual([]);
    expect(io.errs.join(' ')).toMatch(/missing|scope/i);
  });
});
