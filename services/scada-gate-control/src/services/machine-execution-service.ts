import type {
  CommandExecutionRepository,
  ExecuteCommandIntentRequest,
  ExecutionReason,
  ExecutionReceipt,
  ExecutionReservation,
  ExecutionStatus,
} from '../command-executions/types';
import type { ApprovedLineageAnchor } from '../domain/approved-field-artifact';
import { EXECUTION_RECEIPT_SCHEMA_V1 } from '../domain/execution-receipt.schema';
import { intentContentHash } from '../domain/intent-content-hash';
import { newMachineBoundaryAjv } from '../domain/machine-boundary-ajv';
import type { DeviceCapabilitySnapshot } from '../domain/machine-boundary';
import { parseUtcInstant, validateCommandIntent } from '../domain/command-intent-validation';
import { planGateLevelCommand } from '../domain/plan';
import type { GateActuator } from '../state/gate-controller';
import { isWritableQuality } from '../domain/quality';

type MachineExecutionDeps = {
  readonly actuator: GateActuator;
  readonly repository: CommandExecutionRepository;
  readonly capabilities: DeviceCapabilitySnapshot;
  readonly approvedLineageAnchor: ApprovedLineageAnchor | null;
  readonly siteCanonicalGateId: string | null;
  readonly allowMachineCommands: boolean;
  readonly clock: () => number;
  readonly randomId: () => string;
};

const validateExecutionReceipt = newMachineBoundaryAjv().compile(
  EXECUTION_RECEIPT_SCHEMA_V1 as unknown as Record<string, unknown>,
);

function requireExecutionReceipt(value: unknown): ExecutionReceipt {
  if (!validateExecutionReceipt(value)) {
    throw new Error('execution receipt violates the v1 contract');
  }
  const receipt = value as ExecutionReceipt;
  if (
    receipt.status === 'execution_succeeded' &&
    (receipt.readback_quality !== 'ok' || receipt.observed_level !== receipt.target_level)
  ) {
    throw new Error('execution receipt violates the v1 contract');
  }
  return receipt;
}

function parseExecutionReceipt(document: string): ExecutionReceipt {
  return requireExecutionReceipt(JSON.parse(document) as unknown);
}

function sameBinding(a: ExecutionReservation, b: ExecutionReservation): boolean {
  return (
    a.intent_id === b.intent_id &&
    a.grant_id === b.grant_id &&
    parseUtcInstant(a.authority_not_after) === parseUtcInstant(b.authority_not_after) &&
    a.original_intent_content_hash === b.original_intent_content_hash &&
    a.execution_intent_content_hash === b.execution_intent_content_hash &&
    a.purpose === b.purpose
  );
}

export class MachineExecutionService {
  constructor(private readonly deps: MachineExecutionDeps) {}

  async executeCommandIntent(
    request: ExecuteCommandIntentRequest,
    tokenExpiresAtMs: number,
  ): Promise<ExecutionReceipt> {
    const now = this.deps.clock();
    const receiptId = this.deps.randomId();
    if (
      !/^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/.test(
        receiptId,
      )
    ) {
      throw new Error('execution receipt violates the v1 contract');
    }
    const intent = request.intent;
    const authorityNotAfter = parseUtcInstant(request.authority_not_after);
    const original = { ...intent, mode: 'shadow' as const };
    if (
      intent.mode !== 'operator_approved' ||
      authorityNotAfter === null ||
      !Number.isFinite(tokenExpiresAtMs) ||
      intentContentHash(intent) !== request.execution_intent_content_hash ||
      intentContentHash(original) !== request.original_intent_content_hash
    ) {
      return this.receipt(
        request,
        receiptId,
        now,
        'execution_rejected',
        'authority_binding_mismatch',
      );
    }
    if (
      request.purpose === 'fail_safe_close' &&
      (intent.event_kind !== 'close' || intent.target_position_m !== 0)
    ) {
      return this.receipt(
        request,
        receiptId,
        now,
        'execution_rejected',
        'authority_binding_mismatch',
      );
    }
    const replayReservation: ExecutionReservation = {
      idempotency_key: intent.idempotency_key,
      intent_id: intent.intent_id,
      grant_id: request.grant_id,
      authority_not_after: request.authority_not_after,
      original_intent_content_hash: request.original_intent_content_hash,
      execution_intent_content_hash: request.execution_intent_content_hash,
      purpose: request.purpose,
      reserved_at: new Date(now).toISOString(),
    };
    const replay = await this.replayExisting(request, replayReservation, receiptId, now);
    if (replay) return replay;
    if (!this.deps.allowMachineCommands) {
      return this.receipt(
        request,
        receiptId,
        now,
        'execution_rejected',
        'machine_commands_disabled',
      );
    }
    if (
      this.deps.siteCanonicalGateId === null ||
      intent.canonical_gate_id !== this.deps.siteCanonicalGateId
    ) {
      return this.receipt(request, receiptId, now, 'execution_rejected', 'capability_mismatch');
    }
    if (this.deps.approvedLineageAnchor === null) {
      return this.receipt(request, receiptId, now, 'execution_rejected', 'lineage_mismatch');
    }

    const verdict = validateCommandIntent(
      intent,
      this.deps.capabilities,
      now,
      this.deps.approvedLineageAnchor,
    );
    if (
      verdict.status === 'validation_rejected' &&
      !(request.purpose === 'fail_safe_close' && verdict.reason_code === 'deadline_expired')
    ) {
      const reason =
        verdict.reason_code === 'deadline_expired'
          ? 'deadline_expired'
          : verdict.reason_code === 'lineage_mismatch'
            ? 'lineage_mismatch'
            : verdict.reason_code === 'target_invalid'
              ? 'target_invalid'
              : verdict.reason_code === 'freshness_failed'
                ? 'freshness_failed'
                : 'capability_mismatch';
      return this.receipt(request, receiptId, now, 'execution_rejected', reason);
    }
    const notBefore = parseUtcInstant(intent.not_before);
    const deadline = parseUtcInstant(intent.deadline);
    if (request.purpose !== 'fail_safe_close' && (notBefore === null || now < notBefore)) {
      return this.receipt(request, receiptId, now, 'execution_rejected', 'not_yet_due');
    }
    if (request.purpose !== 'fail_safe_close' && (deadline === null || now >= deadline)) {
      return this.receipt(request, receiptId, now, 'execution_rejected', 'deadline_expired');
    }

    const current = this.deps.actuator.snapshot();
    const plan = planGateLevelCommand({
      authenticated: true,
      role: 'operator',
      quality: current.gateLevel.quality,
      confirmed: true,
      targetValue: intent.target_level,
    });
    if (!plan.allowed) {
      return this.receipt(request, receiptId, now, 'execution_rejected', 'freshness_failed');
    }

    const reservation = replayReservation;
    const reserved = await this.deps.repository.reserveIfAbsent(reservation);
    if (!sameBinding(reserved.stored, reservation)) {
      return this.receipt(request, receiptId, now, 'execution_rejected', 'idempotency_conflict');
    }
    if (!reserved.inserted) {
      const winner = await this.replayExisting(request, replayReservation, receiptId, now);
      if (winner) return winner;
      throw new Error('reservation winner was not visible after insert conflict');
    }

    let blockedReason: ExecutionReason = 'freshness_failed';
    const execution = await this.deps.actuator.executeWrites(
      plan.writes,
      'operator_approved',
      (lockedSnapshot) => {
        const writeNow = this.deps.clock();
        if (writeNow >= authorityNotAfter || writeNow >= tokenExpiresAtMs) {
          blockedReason = 'authority_binding_mismatch';
          return false;
        }
        if (request.purpose !== 'fail_safe_close' && writeNow >= (deadline ?? 0)) {
          blockedReason = 'deadline_expired';
          return false;
        }
        return isWritableQuality(lockedSnapshot.gateLevel.quality);
      },
    );
    const observed = execution.snapshot.gateLevel.raw;
    const [status, reason]: [ExecutionStatus, ExecutionReason | null] = execution.blocked
      ? ['execution_rejected', blockedReason]
      : execution.failed
        ? ['execution_failed', 'write_failed']
        : !isWritableQuality(execution.snapshot.gateLevel.quality)
          ? ['execution_in_doubt', 'readback_unavailable']
          : observed !== intent.target_level
            ? ['readback_mismatch', 'readback_mismatch']
            : ['execution_succeeded', null];
    const receipt = this.receipt(
      request,
      receiptId,
      this.deps.clock(),
      status,
      reason,
      observed,
      execution.snapshot.gateLevel.quality,
      execution.succeeded,
    );
    const stored = await this.deps.repository.insertOutcomeIfAbsent({
      idempotency_key: intent.idempotency_key,
      receipt_document: JSON.stringify(receipt),
    });
    return parseExecutionReceipt(stored.receipt_document);
  }

  private async replayExisting(
    request: ExecuteCommandIntentRequest,
    candidate: ExecutionReservation,
    receiptId: string,
    now: number,
  ): Promise<ExecutionReceipt | null> {
    const reservation = await this.deps.repository.getReservation(candidate.idempotency_key);
    if (!reservation) return null;
    if (!sameBinding(reservation, candidate)) {
      return this.receipt(request, receiptId, now, 'execution_rejected', 'idempotency_conflict');
    }
    const prior = await this.deps.repository.getOutcome(candidate.idempotency_key);
    if (prior) return parseExecutionReceipt(prior.receipt_document);
    const inDoubt = this.receipt(
      request,
      receiptId,
      now,
      'execution_in_doubt',
      'prior_attempt_in_doubt',
    );
    const stored = await this.deps.repository.insertOutcomeIfAbsent({
      idempotency_key: candidate.idempotency_key,
      receipt_document: JSON.stringify(inDoubt),
    });
    return parseExecutionReceipt(stored.receipt_document);
  }

  private receipt(
    request: ExecuteCommandIntentRequest,
    receiptId: string,
    now: number,
    status: ExecutionStatus,
    reason: ExecutionReason | null,
    observedLevel: number | null = null,
    quality = 'unavailable',
    writes: ExecutionReceipt['writes'] = [],
  ): ExecutionReceipt {
    return requireExecutionReceipt({
      schema_version: 1,
      receipt_id: receiptId,
      intent_id: request.intent.intent_id,
      idempotency_key: request.intent.idempotency_key,
      grant_id: request.grant_id,
      authority_not_after: request.authority_not_after,
      original_intent_content_hash: request.original_intent_content_hash,
      execution_intent_content_hash: request.execution_intent_content_hash,
      capability_hash: request.intent.capability_hash,
      purpose: request.purpose,
      status,
      reason_code: reason,
      target_level: request.intent.target_level,
      observed_level: observedLevel,
      readback_quality: quality,
      writes,
      executed_at: new Date(now).toISOString(),
    });
  }
}
