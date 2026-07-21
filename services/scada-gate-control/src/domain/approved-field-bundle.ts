import {
  buildDeviceRegistryArtifact,
  extractApprovedLineageAnchor,
  parseApprovedFieldArtifact,
  validateApprovedRegistryCoverage,
  ApprovedFieldArtifactError,
  type ApprovedFieldArtifact,
  type ApprovedLineageAnchor,
} from './approved-field-artifact';
import { readCappedJsonFile } from './capped-json-file';
import { buildDeviceCapabilitySnapshot } from './device-registry';
import { isGateLevel } from './gate-level';
import type { DeviceCapabilitySnapshot } from './machine-boundary';

export type ApprovedFieldBundle = {
  readonly artifact: ApprovedFieldArtifact;
  readonly deviceCapabilities: DeviceCapabilitySnapshot;
  readonly approvedLineageAnchor: ApprovedLineageAnchor;
};

export type ApprovedFieldRuntimeRegisters = {
  readonly unitId: number;
  readonly commandRegister: number;
  readonly readbackRegister: number;
};

const MAX_BUNDLE_BYTES = 1_048_576;

export function loadApprovedFieldBundle(
  env: NodeJS.ProcessEnv = process.env,
  expectedApprovedGateIds: ReadonlySet<string>,
  runtimeRegisters: ApprovedFieldRuntimeRegisters,
): ApprovedFieldBundle | null {
  const rawPath = env.SCADA_APPROVED_FIELD_BUNDLE_PATH;
  if (rawPath === undefined) return null;
  const path = rawPath.trim();
  if (path === '') {
    throw new ApprovedFieldArtifactError(
      'SCADA_APPROVED_FIELD_BUNDLE_PATH is set but blank; unset it to remain dark',
    );
  }
  if (env.SCADA_DEVICE_REGISTRY_PATH !== undefined) {
    throw new ApprovedFieldArtifactError(
      'SCADA_DEVICE_REGISTRY_PATH is a legacy split artifact and cannot accompany the rich single source',
    );
  }
  if (env.SCADA_APPROVED_LINEAGE_ANCHOR_PATH !== undefined) {
    throw new ApprovedFieldArtifactError(
      'SCADA_APPROVED_LINEAGE_ANCHOR_PATH is a legacy split artifact and cannot accompany the rich single source',
    );
  }
  if (expectedApprovedGateIds.size === 0) {
    throw new ApprovedFieldArtifactError('configured pilot scope must contain at least one gate');
  }

  const parsed = readCappedJsonFile(
    path,
    MAX_BUNDLE_BYTES,
    {
      unreadable: 'SCADA_APPROVED_FIELD_BUNDLE_PATH is set but the artifact cannot be read',
      tooBig: 'approved field bundle exceeds the 1 MiB size cap',
      notJson: 'approved field bundle is not valid JSON',
    },
    (message) => new ApprovedFieldArtifactError(message),
  );
  const artifact = parseApprovedFieldArtifact(parsed);
  const approvalMarker = `${artifact.approval.approved_by_role} ${artifact.approval.approval_reference}`;
  if (/example|not[-_ ]?field[-_ ]?approved|do[-_ ]?not[-_ ]?deploy/i.test(approvalMarker)) {
    throw new ApprovedFieldArtifactError(
      'approved field bundle carries an example or not-field-approved runtime marker',
    );
  }
  if (artifact.approval.scope !== 'pilot') {
    throw new ApprovedFieldArtifactError(
      'SCADA approved field runtime requires an exact pilot-scope approval',
    );
  }
  validateApprovedRegistryCoverage(artifact, expectedApprovedGateIds);
  for (const gate of artifact.gates) {
    if (
      gate.register.unit_id !== runtimeRegisters.unitId ||
      gate.register.command_register !== runtimeRegisters.commandRegister ||
      gate.register.readback_register !== runtimeRegisters.readbackRegister
    ) {
      throw new ApprovedFieldArtifactError(
        `approved register map for gate '${gate.canonical_gate_id}' does not match the live runtime`,
      );
    }
    if (gate.quantizer.targets.some((target) => !isGateLevel(target.target_level))) {
      throw new ApprovedFieldArtifactError(
        `approved target level for gate '${gate.canonical_gate_id}' is not writable by the live command planner`,
      );
    }
  }
  const registry = buildDeviceRegistryArtifact(artifact);
  return {
    artifact,
    deviceCapabilities: buildDeviceCapabilitySnapshot(registry),
    approvedLineageAnchor: extractApprovedLineageAnchor(artifact),
  };
}
