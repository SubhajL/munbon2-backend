import type { ModbusWrite } from '../domain/command';
import type { CommandIntent } from '../domain/machine-boundary';

export type ExecutionPurpose = 'operator_approved' | 'fail_safe_close';

export type ExecutionStatus =
  | 'execution_succeeded'
  | 'execution_rejected'
  | 'execution_failed'
  | 'readback_mismatch'
  | 'execution_in_doubt';

export type ExecutionReason =
  | 'machine_commands_disabled'
  | 'authority_binding_mismatch'
  | 'idempotency_conflict'
  | 'capability_mismatch'
  | 'target_invalid'
  | 'lineage_mismatch'
  | 'not_yet_due'
  | 'deadline_expired'
  | 'freshness_failed'
  | 'write_failed'
  | 'readback_mismatch'
  | 'readback_unavailable'
  | 'prior_attempt_in_doubt';

export type ExecuteCommandIntentRequest = {
  readonly intent: CommandIntent;
  readonly grant_id: string;
  readonly authority_not_after: string;
  readonly original_intent_content_hash: string;
  readonly execution_intent_content_hash: string;
  readonly purpose: ExecutionPurpose;
};

export type ExecutionReceipt = {
  readonly schema_version: 1;
  readonly receipt_id: string;
  readonly intent_id: string;
  readonly idempotency_key: string;
  readonly grant_id: string;
  readonly authority_not_after: string;
  readonly original_intent_content_hash: string;
  readonly execution_intent_content_hash: string;
  readonly capability_hash: string;
  readonly purpose: ExecutionPurpose;
  readonly status: ExecutionStatus;
  readonly reason_code: ExecutionReason | null;
  readonly target_level: number;
  readonly observed_level: number | null;
  readonly readback_quality: string;
  readonly writes: readonly ModbusWrite[];
  readonly executed_at: string;
};

export type ExecutionReservation = {
  readonly idempotency_key: string;
  readonly intent_id: string;
  readonly grant_id: string;
  readonly authority_not_after: string;
  readonly original_intent_content_hash: string;
  readonly execution_intent_content_hash: string;
  readonly purpose: ExecutionPurpose;
  readonly reserved_at: string;
};

export type ExecutionOutcomeRecord = {
  readonly idempotency_key: string;
  readonly receipt_document: string;
};

export type ReserveOutcome = {
  readonly inserted: boolean;
  readonly stored: ExecutionReservation;
};

export interface CommandExecutionRepository {
  ensureSchema(): Promise<void>;
  getReservation(idempotencyKey: string): Promise<ExecutionReservation | null>;
  reserveIfAbsent(reservation: ExecutionReservation): Promise<ReserveOutcome>;
  getOutcome(idempotencyKey: string): Promise<ExecutionOutcomeRecord | null>;
  insertOutcomeIfAbsent(outcome: ExecutionOutcomeRecord): Promise<ExecutionOutcomeRecord>;
}
