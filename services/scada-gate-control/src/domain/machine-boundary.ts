/**
 * TypeScript mirror of the shared machine-boundary v1 contracts (PR 6.0).
 *
 * These readonly types mirror `contracts/machine-boundary/v1/*.schema.json`. The
 * `*_FIELDS` tuples and enum tuples are asserted against the schema by the
 * contract spec so a drift fails a test. Type/library surface only in PR 6.0: no
 * route, CommandService, GateController, transport, or audit code imports it. 6.2
 * consumes the command-intent + emits the receipt; 6.1a produces the snapshot.
 */
import type { Brand } from '../types';

export type DeviceId = Brand<string, 'DeviceId'>;
export type AdapterGateId = Brand<string, 'AdapterGateId'>;
export type CanonicalGateId = Brand<string, 'CanonicalGateId'>;
export type IntentId = Brand<string, 'IntentId'>;
export type CorrelationId = Brand<string, 'CorrelationId'>;
export type ReceiptId = Brand<string, 'ReceiptId'>;
export type CampaignId = Brand<string, 'CampaignId'>;
export type PlanId = Brand<string, 'PlanId'>;
export type RequirementRunId = Brand<string, 'RequirementRunId'>;
export type ModelSnapshotId = Brand<string, 'ModelSnapshotId'>;
export type PredictionRunId = Brand<string, 'PredictionRunId'>;
export type CapabilityReleaseId = Brand<string, 'CapabilityReleaseId'>;
export type Sha256 = Brand<string, 'Sha256'>;
export type UtcInstant = Brand<string, 'UtcInstant'>;
export type RequestId = Brand<string, 'RequestId'>;
export type IdempotencyKey = Brand<string, 'IdempotencyKey'>;

export const MACHINE_BOUNDARY_SCHEMA_VERSION = 1 as const;
// Must equal contracts/machine-boundary/v1/manifest.json:contract_set_sha256 and
// the Scheduler MACHINE_BOUNDARY_CONTRACT_SET_SHA256 constant.
export const MACHINE_BOUNDARY_CONTRACT_SET_SHA256 =
  '155606e21b0e15dc674a4fb3e5a9e2f40b94d6e1078ae09c973944731f3db0e4';

export const EVENT_KINDS = ['open', 'trim', 'close'] as const;
export type EventKind = (typeof EVENT_KINDS)[number];

export const COMMAND_MODES = ['shadow', 'operator_approved'] as const;
export type CommandMode = (typeof COMMAND_MODES)[number];

export const VALIDATION_STATUSES = ['validation_accepted', 'validation_rejected'] as const;
export type ValidationStatus = (typeof VALIDATION_STATUSES)[number];

export const VALIDATION_REJECTION_REASONS = [
  'schema_invalid',
  'capability_mismatch',
  'target_invalid',
  'not_before_violation',
  'deadline_expired',
  'lineage_mismatch',
  'freshness_failed',
  'idempotency_conflict',
] as const;
export type ValidationRejectionReason = (typeof VALIDATION_REJECTION_REASONS)[number];

export type DeviceTargetCapability = {
  readonly target_position_m: number;
  readonly target_level: number;
};

export type DeviceCapability = {
  readonly device_id: DeviceId;
  readonly adapter_gate_id: AdapterGateId;
  readonly targets: readonly DeviceTargetCapability[];
};

export type DeviceCapabilitySnapshot = {
  readonly schema_version: 1;
  readonly capability_release_id: CapabilityReleaseId;
  readonly capability_hash: Sha256;
  // Keyed by canonical_gate_id -> capability: one gate maps to at most one device.
  readonly capabilities: Readonly<Record<CanonicalGateId, DeviceCapability>>;
};

export type CommandLineage = {
  readonly campaign_id: CampaignId;
  readonly plan_id: PlanId;
  readonly plan_version: number;
  readonly input_content_hash: Sha256;
  readonly draft_content_hash: Sha256;
  readonly requirement_run_id: RequirementRunId;
  readonly requirement_version: number;
  readonly requirement_set_sha256: Sha256;
  readonly model_snapshot_id: ModelSnapshotId;
  readonly model_release_id: string;
  readonly model_release_content_hash: Sha256;
  readonly prediction_run_id: PredictionRunId;
  readonly prediction_identity_version: 2;
  readonly engine_descriptor_content_hash: Sha256;
  readonly artifact_sha256: Sha256;
};

export type CommandIntent = {
  readonly schema_version: 1;
  readonly intent_id: IntentId;
  readonly correlation_id: CorrelationId;
  readonly request_id: RequestId;
  readonly idempotency_key: IdempotencyKey;
  readonly canonical_gate_id: CanonicalGateId;
  readonly event_kind: EventKind;
  readonly event_sequence: number;
  readonly gate_event_sequence: number;
  readonly device_id: DeviceId;
  readonly adapter_gate_id: AdapterGateId;
  readonly capability_release_id: CapabilityReleaseId;
  readonly capability_hash: Sha256;
  readonly target_position_m: number;
  readonly target_level: number;
  readonly not_before: UtcInstant;
  readonly deadline: UtcInstant;
  readonly mode: CommandMode;
  readonly lineage: CommandLineage;
};

export type ValidationReceipt = {
  readonly schema_version: 1;
  readonly receipt_id: ReceiptId;
  readonly intent_id: IntentId;
  readonly correlation_id: CorrelationId;
  readonly request_id: RequestId;
  readonly idempotency_key: IdempotencyKey;
  readonly intent_content_hash: Sha256;
  readonly capability_hash: Sha256;
  readonly status: ValidationStatus;
  readonly validated_at: UtcInstant;
  readonly reason_code: ValidationRejectionReason | null;
};

// Field-key rosters asserted against the schema properties by the contract spec.
export const COMMAND_INTENT_FIELDS = [
  'schema_version',
  'intent_id',
  'correlation_id',
  'request_id',
  'idempotency_key',
  'canonical_gate_id',
  'event_kind',
  'event_sequence',
  'gate_event_sequence',
  'device_id',
  'adapter_gate_id',
  'capability_release_id',
  'capability_hash',
  'target_position_m',
  'target_level',
  'not_before',
  'deadline',
  'mode',
  'lineage',
] as const;

export const COMMAND_LINEAGE_FIELDS = [
  'campaign_id',
  'plan_id',
  'plan_version',
  'input_content_hash',
  'draft_content_hash',
  'requirement_run_id',
  'requirement_version',
  'requirement_set_sha256',
  'model_snapshot_id',
  'model_release_id',
  'model_release_content_hash',
  'prediction_run_id',
  'prediction_identity_version',
  'engine_descriptor_content_hash',
  'artifact_sha256',
] as const;

export const VALIDATION_RECEIPT_FIELDS = [
  'schema_version',
  'receipt_id',
  'intent_id',
  'correlation_id',
  'request_id',
  'idempotency_key',
  'intent_content_hash',
  'capability_hash',
  'status',
  'validated_at',
  'reason_code',
] as const;

export const DEVICE_CAPABILITY_SNAPSHOT_FIELDS = [
  'schema_version',
  'capability_release_id',
  'capability_hash',
  'capabilities',
] as const;

export const DEVICE_CAPABILITY_FIELDS = ['device_id', 'adapter_gate_id', 'targets'] as const;

export const DEVICE_TARGET_FIELDS = ['target_position_m', 'target_level'] as const;
