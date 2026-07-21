import { existsSync, readFileSync } from 'fs';
import { dirname, join } from 'path';
import { describe, expect, it } from 'vitest';

import { InMemoryCommandExecutionRepository } from '../command-executions/memory-repository';
import type { ExecuteCommandIntentRequest } from '../command-executions/types';
import type { ApprovedLineageAnchor } from '../domain/approved-field-artifact';
import { intentContentHash } from '../domain/intent-content-hash';
import type { CommandIntent, DeviceCapabilitySnapshot } from '../domain/machine-boundary';
import type { ModbusWrite } from '../domain/command';
import type { GateActuator } from '../state/gate-controller';
import { buildSnapshot, emptyState, recordPoll, type GateSnapshot } from '../state/store';
import { MachineExecutionService } from './machine-execution-service';

function fixture(rel: string): unknown {
  let dir = __dirname;
  for (let i = 0; i < 8; i += 1) {
    const candidate = join(dir, 'contracts', 'machine-boundary', 'v1', rel);
    if (existsSync(candidate)) return JSON.parse(readFileSync(candidate, 'utf-8'));
    dir = dirname(dir);
  }
  throw new Error(`fixture not found: ${rel}`);
}

const NOW = Date.parse('2026-07-20T03:00:00Z');
const TOKEN_EXPIRES_AT = NOW + 300_000;
const GRANT_ID = '77777777-7777-4777-8777-777777777777';
const AUTHORITY_NOT_AFTER = new Date(TOKEN_EXPIRES_AT).toISOString();
const original = fixture('fixtures/valid/command-intent.shadow.valid.json') as CommandIntent;
const promoted = { ...original, mode: 'operator_approved' } as CommandIntent;
const request: ExecuteCommandIntentRequest = {
  intent: promoted,
  grant_id: GRANT_ID,
  authority_not_after: AUTHORITY_NOT_AFTER,
  original_intent_content_hash: intentContentHash(original),
  execution_intent_content_hash: intentContentHash(promoted),
  purpose: 'operator_approved',
};
const capabilities = {
  schema_version: 1,
  capability_release_id: promoted.capability_release_id,
  capability_hash: promoted.capability_hash,
  capabilities: {
    [promoted.canonical_gate_id]: {
      device_id: promoted.device_id,
      adapter_gate_id: promoted.adapter_gate_id,
      targets: [
        { target_position_m: promoted.target_position_m, target_level: promoted.target_level },
      ],
    },
  },
} as DeviceCapabilitySnapshot;
const approvedLineageAnchor: ApprovedLineageAnchor = {
  model_release_id: promoted.lineage.model_release_id,
  model_release_content_hash: promoted.lineage.model_release_content_hash,
  engine_descriptor_content_hash: promoted.lineage.engine_descriptor_content_hash,
};

function snapshot(level: number, qualityAt = NOW) {
  return buildSnapshot(
    recordPoll(emptyState(), {
      ok: true,
      atMs: qualityAt,
      reads: { gateLevel: level, doorSw: 1, horn: 0, gateCf: 0 },
    }),
    NOW,
    { staleAfterMs: 10_000, offlineAfterMs: 20_000 },
  );
}

function harness(
  opts: {
    enabled?: boolean;
    observed?: number;
    fail?: boolean;
    receiptId?: string;
    readback?: GateSnapshot;
    siteCanonicalGateId?: string | null;
    approvedLineageAnchor?: ApprovedLineageAnchor | null;
    clock?: () => number;
    beforeWrite?: () => void;
  } = {},
) {
  const writes: ModbusWrite[] = [];
  const actuator: GateActuator = {
    snapshot: () => snapshot(2),
    executeWrites: async (planned, _provenance, precondition) => {
      opts.beforeWrite?.();
      const locked = snapshot(2);
      if (precondition && !precondition(locked)) {
        return { succeeded: [], failed: null, snapshot: locked, blocked: true };
      }
      writes.push(...planned);
      return {
        succeeded: opts.fail ? [] : planned,
        failed: opts.fail ? { write: planned[0]!, error: 'PLC timeout' } : null,
        snapshot: opts.readback ?? snapshot(opts.observed ?? promoted.target_level),
      };
    },
  };
  const repository = new InMemoryCommandExecutionRepository();
  const service = new MachineExecutionService({
    actuator,
    repository,
    capabilities,
    approvedLineageAnchor:
      'approvedLineageAnchor' in opts
        ? (opts.approvedLineageAnchor ?? null)
        : approvedLineageAnchor,
    siteCanonicalGateId: opts.siteCanonicalGateId ?? promoted.canonical_gate_id,
    allowMachineCommands: opts.enabled ?? true,
    clock: opts.clock ?? (() => NOW),
    randomId: () => opts.receiptId ?? '11111111-1111-1111-1111-111111111111',
  });
  return { service, repository, writes };
}

describe('MachineExecutionService.executeCommandIntent', () => {
  it('requires the independent SCADA machine-command flag before any reservation or write', async () => {
    const { service, repository, writes } = harness({ enabled: false });
    const receipt = await service.executeCommandIntent(request, TOKEN_EXPIRES_AT);
    expect(receipt.status).toBe('execution_rejected');
    expect(receipt.reason_code).toBe('machine_commands_disabled');
    expect(await repository.getOutcome(promoted.idempotency_key)).toBeNull();
    expect(writes).toEqual([]);
  });

  it('serializes the write, reads back target, and durably replays one success', async () => {
    const { service, writes } = harness();
    const first = await service.executeCommandIntent(request, TOKEN_EXPIRES_AT);
    const replay = await service.executeCommandIntent(request, TOKEN_EXPIRES_AT);
    expect(first).toEqual(replay);
    expect(first.status).toBe('execution_succeeded');
    expect(first.observed_level).toBe(promoted.target_level);
    expect(writes).toHaveLength(2);
  });

  it('records mismatch and never optimistically reports success', async () => {
    const { service } = harness({ observed: 2 });
    const receipt = await service.executeCommandIntent(request, TOKEN_EXPIRES_AT);
    expect(receipt.status).toBe('readback_mismatch');
    expect(receipt.reason_code).toBe('readback_mismatch');
  });

  it('records an offline post-write readback as in-doubt even when its cached level matches', async () => {
    let state = recordPoll(emptyState(), {
      ok: true,
      atMs: NOW,
      reads: { gateLevel: promoted.target_level, doorSw: 1, horn: 0, gateCf: 0 },
    });
    state = recordPoll(state, {
      ok: false,
      atMs: NOW + 1,
      quality: 'offline',
      error: 'readback timeout',
    });
    const readback = buildSnapshot(state, NOW + 1, {
      staleAfterMs: 10_000,
      offlineAfterMs: 20_000,
    });
    const { service } = harness({ readback });
    const receipt = await service.executeCommandIntent(request, TOKEN_EXPIRES_AT);
    expect({
      status: receipt.status,
      reason: receipt.reason_code,
      quality: receipt.readback_quality,
    }).toEqual({
      status: 'execution_in_doubt',
      reason: 'readback_unavailable',
      quality: 'offline',
    });
  });

  it('never routes another capability-valid gate through this process local actuator', async () => {
    const otherOriginal = { ...original, canonical_gate_id: 'OTHER-GATE' } as CommandIntent;
    const otherPromoted = { ...otherOriginal, mode: 'operator_approved' } as CommandIntent;
    const otherRequest: ExecuteCommandIntentRequest = {
      intent: otherPromoted,
      grant_id: GRANT_ID,
      authority_not_after: AUTHORITY_NOT_AFTER,
      original_intent_content_hash: intentContentHash(otherOriginal),
      execution_intent_content_hash: intentContentHash(otherPromoted),
      purpose: 'operator_approved',
    };
    const otherCapabilities = {
      ...capabilities,
      capabilities: {
        'OTHER-GATE': {
          device_id: otherPromoted.device_id,
          adapter_gate_id: otherPromoted.adapter_gate_id,
          targets: [
            {
              target_position_m: otherPromoted.target_position_m,
              target_level: otherPromoted.target_level,
            },
          ],
        },
      },
    } as DeviceCapabilitySnapshot;
    const writes: ModbusWrite[] = [];
    const service = new MachineExecutionService({
      actuator: {
        snapshot: () => snapshot(2),
        executeWrites: async (planned) => {
          writes.push(...planned);
          return {
            succeeded: planned,
            failed: null,
            snapshot: snapshot(otherPromoted.target_level),
          };
        },
      },
      repository: new InMemoryCommandExecutionRepository(),
      capabilities: otherCapabilities,
      approvedLineageAnchor,
      siteCanonicalGateId: promoted.canonical_gate_id,
      allowMachineCommands: true,
      clock: () => NOW,
      randomId: () => '11111111-1111-1111-1111-111111111111',
    });
    const receipt = await service.executeCommandIntent(otherRequest, TOKEN_EXPIRES_AT);
    expect({ status: receipt.status, reason: receipt.reason_code, writes }).toEqual({
      status: 'execution_rejected',
      reason: 'capability_mismatch',
      writes: [],
    });
  });

  it('keeps machine execution dark without an approved lineage anchor', async () => {
    const { service, writes } = harness({ approvedLineageAnchor: null });
    const receipt = await service.executeCommandIntent(request, TOKEN_EXPIRES_AT);
    expect({ status: receipt.status, reason: receipt.reason_code, writes }).toEqual({
      status: 'execution_rejected',
      reason: 'lineage_mismatch',
      writes: [],
    });
  });

  it('replays the durable outcome before mutable deadline policy is reevaluated', async () => {
    let now = NOW;
    const { service, writes } = harness({ clock: () => now });
    const first = await service.executeCommandIntent(request, TOKEN_EXPIRES_AT);
    now = Date.parse(promoted.deadline) + 1;
    const replay = await service.executeCommandIntent(request, TOKEN_EXPIRES_AT);
    expect({ replay, first, writeCount: writes.length }).toEqual({
      replay: first,
      first,
      writeCount: 2,
    });
  });

  it('rechecks the token-capped authority deadline inside the locked pre-write predicate', async () => {
    let now = NOW;
    const { service, writes } = harness({
      clock: () => now,
      beforeWrite: () => {
        now = TOKEN_EXPIRES_AT;
      },
    });
    const receipt = await service.executeCommandIntent(request, TOKEN_EXPIRES_AT);
    expect({ status: receipt.status, reason: receipt.reason_code, writes }).toEqual({
      status: 'execution_rejected',
      reason: 'authority_binding_mismatch',
      writes: [],
    });
  });

  it('does not actuate a reservation whose prior outcome is unknown', async () => {
    const { service, repository, writes } = harness();
    await repository.reserveIfAbsent({
      idempotency_key: promoted.idempotency_key,
      intent_id: promoted.intent_id,
      grant_id: request.grant_id,
      authority_not_after: request.authority_not_after,
      original_intent_content_hash: request.original_intent_content_hash,
      execution_intent_content_hash: request.execution_intent_content_hash,
      purpose: request.purpose,
      reserved_at: new Date(NOW - 1_000).toISOString(),
    });
    const receipt = await service.executeCommandIntent(request, TOKEN_EXPIRES_AT);
    expect(receipt.status).toBe('execution_in_doubt');
    expect(receipt.reason_code).toBe('prior_attempt_in_doubt');
    expect(writes).toEqual([]);
  });

  it('rejects a same-key request bound to a different promoted hash without writing', async () => {
    const { service, repository, writes } = harness();
    await repository.reserveIfAbsent({
      idempotency_key: promoted.idempotency_key,
      intent_id: promoted.intent_id,
      grant_id: request.grant_id,
      authority_not_after: request.authority_not_after,
      original_intent_content_hash: request.original_intent_content_hash,
      execution_intent_content_hash: 'f'.repeat(64),
      purpose: request.purpose,
      reserved_at: new Date(NOW).toISOString(),
    });
    const receipt = await service.executeCommandIntent(request, TOKEN_EXPIRES_AT);
    expect(receipt.status).toBe('execution_rejected');
    expect(receipt.reason_code).toBe('idempotency_conflict');
    expect(writes).toEqual([]);
  });

  it('never lets fail-safe authority execute an open or trim intent', async () => {
    const { service, writes } = harness();
    const receipt = await service.executeCommandIntent(
      { ...request, purpose: 'fail_safe_close' },
      TOKEN_EXPIRES_AT,
    );
    expect(receipt.status).toBe('execution_rejected');
    expect(receipt.reason_code).toBe('authority_binding_mismatch');
    expect(writes).toEqual([]);
  });

  it('fails closed instead of emitting a receipt that violates the shared contract', async () => {
    const { service, writes } = harness({ receiptId: 'not-a-uuid' });
    await expect(service.executeCommandIntent(request, TOKEN_EXPIRES_AT)).rejects.toThrow(
      /execution receipt violates the v1 contract/,
    );
    expect(writes).toEqual([]);
  });
});
