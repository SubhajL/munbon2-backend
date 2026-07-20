/**
 * PR 6.1b — OFFLINE ops CLI that projects a rich approved field artifact into the two small
 * runtime inputs an operator deploys: the endpoint-free device registry (6.1a's
 * `SCADA_DEVICE_REGISTRY_PATH`) and the standalone lineage anchor
 * (`SCADA_APPROVED_LINEAGE_ANCHOR_PATH`). Pure and side-effect-free except the thin argv/IO
 * shell — no Modbus, no network, never run in the service process. Fail-closed: any coverage,
 * monotonicity, readback, or contract violation aborts with a nonzero exit and NO output.
 *
 *   npx ts-node src/ops/build-device-registry.ts <approved-artifact.json> [expectedGateId ...]
 */
import { readFileSync } from 'fs';

import {
  buildDeviceRegistryArtifact,
  extractApprovedLineageAnchor,
  parseApprovedFieldArtifact,
  validateApprovedRegistryCoverage,
  type ApprovedLineageAnchor,
  type DeviceRegistryDocument,
} from '../domain/approved-field-artifact';

export type ApprovedOutputs = {
  readonly registry: DeviceRegistryDocument;
  readonly anchor: ApprovedLineageAnchor;
};

/**
 * Parse untrusted artifact JSON, validate coverage against the EXPECTED approved scope
 * (defaults to the artifact's own gate set when the operator supplies none), then project the
 * two offline outputs. Throws (fail-closed) on any violation.
 */
export function projectApprovedArtifact(
  raw: unknown,
  expectedApprovedGateIds?: readonly string[],
): ApprovedOutputs {
  const artifact = parseApprovedFieldArtifact(raw);
  const expected = new Set(
    expectedApprovedGateIds ?? artifact.gates.map((g) => g.canonical_gate_id),
  );
  validateApprovedRegistryCoverage(artifact, expected);
  return {
    registry: buildDeviceRegistryArtifact(artifact),
    anchor: extractApprovedLineageAnchor(artifact),
  };
}

export type CliIo = {
  readonly readFile: (path: string) => string;
  readonly log: (line: string) => void;
  readonly err: (line: string) => void;
};

/** Thin CLI shell over `projectApprovedArtifact`. Returns the process exit code. */
export function main(argv: readonly string[], io: CliIo): number {
  const path = argv[2];
  if (!path) {
    io.err('usage: build-device-registry <approved-artifact.json> [expectedGateId ...]');
    return 2;
  }
  let raw: unknown;
  try {
    raw = JSON.parse(io.readFile(path));
  } catch {
    io.err(`cannot read or parse the approved artifact at ${path}`);
    return 1;
  }
  try {
    const outputs = projectApprovedArtifact(raw, argv.length > 3 ? argv.slice(3) : undefined);
    io.log(JSON.stringify(outputs, null, 2));
    return 0;
  } catch (error) {
    io.err(error instanceof Error ? error.message : String(error));
    return 1;
  }
}

/* istanbul ignore next -- entrypoint, exercised via main() in tests */
if (require.main === module) {
  process.exit(
    main(process.argv, {
      readFile: (p) => readFileSync(p, 'utf-8'),
      log: (s) => process.stdout.write(`${s}\n`),
      err: (s) => process.stderr.write(`${s}\n`),
    }),
  );
}
