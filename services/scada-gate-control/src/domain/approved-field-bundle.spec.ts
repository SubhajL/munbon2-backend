import { mkdtempSync, readFileSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

import { describe, expect, it } from 'vitest';

import { loadApprovedFieldBundle } from './approved-field-bundle';

const EXAMPLE_PATH = join(__dirname, '__fixtures__', 'approved-field-artifact.example.json');

function rawExample() {
  return JSON.parse(readFileSync(EXAMPLE_PATH, 'utf-8'));
}

function runtimeApprovedArtifact() {
  const artifact = rawExample();
  artifact.approval.approved_by_role = 'RID field authority';
  artifact.approval.approval_reference = 'RID-D6-PILOT-2026-001';
  artifact.gates[0].register.command_register = 108;
  artifact.gates[0].register.readback_register = 104;
  artifact.gates[0].quantizer.targets = [
    { target_position_m: 0.0, target_level: 1 },
    { target_position_m: 0.45, target_level: 3 },
    { target_position_m: 1.2, target_level: 4 },
  ];
  return artifact;
}

function writeArtifact(value: unknown): string {
  const directory = mkdtempSync(join(tmpdir(), 'scada-7-3a-bundle-'));
  const path = join(directory, 'approved-field-bundle.json');
  writeFileSync(path, JSON.stringify(value));
  return path;
}

const expectedGateIds = new Set(['M(0,0;1,0)']);
const runtimeRegisters = { unitId: 1, commandRegister: 108, readbackRegister: 104 };

describe('loadApprovedFieldBundle', () => {
  it('stays unconfigured when the rich bundle path is unset', () => {
    expect(loadApprovedFieldBundle({}, expectedGateIds, runtimeRegisters)).toBeNull();
  });

  it('derives the runtime capability snapshot and lineage anchor from one rich artifact', () => {
    const bundle = loadApprovedFieldBundle(
      { SCADA_APPROVED_FIELD_BUNDLE_PATH: writeArtifact(runtimeApprovedArtifact()) },
      expectedGateIds,
      runtimeRegisters,
    );

    expect(bundle).toMatchObject({
      deviceCapabilities: {
        schema_version: 1,
        capability_release_id: 'cap-2026-07-19-a',
      },
      approvedLineageAnchor: rawExample().approved_lineage_anchor,
    });
    expect(Object.keys(bundle?.deviceCapabilities.capabilities ?? {})).toEqual(['M(0,0;1,0)']);
    expect(bundle?.deviceCapabilities.capability_hash).toMatch(/^[0-9a-f]{64}$/);
  });

  it('rejects a rich artifact whose gate set differs from the configured pilot scope', () => {
    expect(() =>
      loadApprovedFieldBundle(
        { SCADA_APPROVED_FIELD_BUNDLE_PATH: writeArtifact(runtimeApprovedArtifact()) },
        new Set(['M(9,9;9,9)']),
        runtimeRegisters,
      ),
    ).toThrow(/scope|missing/i);
  });

  it('rejects a non-pilot approval at the pilot runtime boundary', () => {
    const artifact = runtimeApprovedArtifact();
    artifact.approval.scope = 'all-gate';

    expect(() =>
      loadApprovedFieldBundle(
        { SCADA_APPROVED_FIELD_BUNDLE_PATH: writeArtifact(artifact) },
        expectedGateIds,
        runtimeRegisters,
      ),
    ).toThrow(/pilot/i);
  });

  it('rejects a shared command/readback register', () => {
    const artifact = runtimeApprovedArtifact();
    artifact.gates[0].register.readback_register = artifact.gates[0].register.command_register;

    expect(() =>
      loadApprovedFieldBundle(
        { SCADA_APPROVED_FIELD_BUNDLE_PATH: writeArtifact(artifact) },
        expectedGateIds,
        runtimeRegisters,
      ),
    ).toThrow(/command.*readback|readback.*command/i);
  });

  it('rejects legacy split artifacts beside the rich single source', () => {
    expect(() =>
      loadApprovedFieldBundle(
        {
          SCADA_APPROVED_FIELD_BUNDLE_PATH: writeArtifact(rawExample()),
          SCADA_DEVICE_REGISTRY_PATH: '/legacy/registry.json',
        },
        expectedGateIds,
        runtimeRegisters,
      ),
    ).toThrow(/legacy|single source|SCADA_DEVICE_REGISTRY_PATH/i);
  });

  it('rejects the committed non-field-approved example as runtime evidence', () => {
    expect(() =>
      loadApprovedFieldBundle(
        { SCADA_APPROVED_FIELD_BUNDLE_PATH: writeArtifact(rawExample()) },
        expectedGateIds,
        runtimeRegisters,
      ),
    ).toThrow(/example|not.field.approved|do.not.deploy/i);
  });

  it('rejects a bundle whose unit or register map differs from the live runtime', () => {
    const artifact = runtimeApprovedArtifact();
    artifact.gates[0].register.unit_id = 2;

    expect(() =>
      loadApprovedFieldBundle(
        { SCADA_APPROVED_FIELD_BUNDLE_PATH: writeArtifact(artifact) },
        expectedGateIds,
        runtimeRegisters,
      ),
    ).toThrow(/unit|register|runtime/i);
  });

  it('rejects target levels the live command planner cannot write', () => {
    const artifact = runtimeApprovedArtifact();
    artifact.gates[0].quantizer.targets[2].target_level = 8;

    expect(() =>
      loadApprovedFieldBundle(
        { SCADA_APPROVED_FIELD_BUNDLE_PATH: writeArtifact(artifact) },
        expectedGateIds,
        runtimeRegisters,
      ),
    ).toThrow(/target.level|writable|planner/i);
  });
});
