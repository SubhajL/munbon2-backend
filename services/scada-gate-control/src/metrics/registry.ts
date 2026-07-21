/**
 * Prometheus metrics for the SCADA gate-control service (PR 6.4).
 *
 * Two roadmap metrics live here:
 *   - machine_modbus_writes_total{mode}       — physical Modbus writes, by provenance.
 *       The zero-shadow-write alert watches the non-`operator` series (they must stay 0;
 *       the machine boundary holds no actuator, so nothing can produce them today).
 *   - command_intent_rejections_total{reason} — machine-boundary rejections. SCADA emits
 *       ONLY `schema_invalid`: that 422 is rejected before any receipt is minted, so it is
 *       invisible to the scheduler's receipt-derived metric. The merit-based reasons
 *       (capability_mismatch, target_invalid, …) are counted scheduler-side from receipts.
 *
 * Each build gets its OWN Registry (never the prom-client global `register`) so counters
 * cannot leak across colocated tests and make the zero-write assertion order-dependent.
 */
import { Counter, Registry } from 'prom-client';
import type { ExecutionPurpose, ExecutionStatus } from '../command-executions/types';
import type { WriteMeter, WriteProvenance } from '../state/gate-controller';

const WRITE_PROVENANCES: readonly WriteProvenance[] = ['operator', 'shadow', 'operator_approved'];
const EXECUTION_PURPOSES: readonly ExecutionPurpose[] = ['operator_approved', 'fail_safe_close'];
const EXECUTION_STATUSES: readonly ExecutionStatus[] = [
  'execution_succeeded',
  'execution_rejected',
  'execution_failed',
  'readback_mismatch',
  'execution_in_doubt',
];

/** The narrow capability the machine-boundary router needs: it may count a schema_invalid
 * rejection but MUST NOT be able to record a Modbus write (it holds no actuator). */
export type RejectionRecorder = {
  recordSchemaInvalidRejection(): void;
};

export type ExecutionOutcomeRecorder = {
  recordExecutionOutcome(status: ExecutionStatus, purpose: ExecutionPurpose): void;
};

export type ScadaMetrics = WriteMeter &
  RejectionRecorder & {
    recordExecutionOutcome(status: ExecutionStatus, purpose: ExecutionPurpose): void;
    render(): Promise<string>;
    readonly contentType: string;
  };

export function createScadaMetrics(): ScadaMetrics {
  const registry = new Registry();

  const modbusWrites = new Counter({
    name: 'machine_modbus_writes_total',
    help: 'Physical Modbus writes issued, labeled by command provenance (mode). Under shadow the non-operator series must remain 0.',
    labelNames: ['mode'] as const,
    registers: [registry],
  });
  const rejections = new Counter({
    name: 'command_intent_rejections_total',
    help: 'Machine-boundary command-intent rejections by reason. SCADA emits only schema_invalid (rejected before a receipt is minted).',
    labelNames: ['reason'] as const,
    registers: [registry],
  });
  const executionOutcomes = new Counter({
    name: 'machine_execution_outcomes_total',
    help: 'Machine execution receipts returned, labeled by bounded execution purpose and outcome status.',
    labelNames: ['purpose', 'status'] as const,
    registers: [registry],
  });

  // Pre-register every bounded series at 0 so alerts written as `== 0` see a present series
  // rather than absent() on a fresh deployment.
  for (const mode of WRITE_PROVENANCES) modbusWrites.inc({ mode }, 0);
  rejections.inc({ reason: 'schema_invalid' }, 0);
  for (const purpose of EXECUTION_PURPOSES) {
    for (const status of EXECUTION_STATUSES) executionOutcomes.inc({ purpose, status }, 0);
  }

  return {
    recordModbusWrite: (provenance) => modbusWrites.inc({ mode: provenance }),
    recordSchemaInvalidRejection: () => rejections.inc({ reason: 'schema_invalid' }),
    recordExecutionOutcome: (status, purpose) => executionOutcomes.inc({ purpose, status }),
    render: () => registry.metrics(),
    contentType: registry.contentType,
  };
}
