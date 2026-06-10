/**
 * Audit log contract. Every gate/horn command attempt — accepted, rejected, or
 * errored — produces one entry, per the spec's "Audit Log" section.
 */
import type { Role } from '../domain/write-safety';

export type AuditCommandType = 'command-level' | 'horn';
export type AuditResult = 'ok' | 'rejected' | 'error';

/** Raw Modbus write recorded for traceability (coils recorded as 0/1). */
export type AuditWrite = { readonly address: number; readonly value: number };

export type AuditEntry = {
  readonly timestamp: string; // ISO 8601
  readonly userId: string;
  readonly userRole: Role;
  readonly gateId: string;
  readonly gateName: string;
  readonly commandType: AuditCommandType;
  readonly requestedTarget: number | boolean;
  readonly modbusHost: string;
  readonly modbusPort: number;
  readonly unitId: number;
  readonly writes: readonly AuditWrite[];
  readonly result: AuditResult;
  readonly error: string | null;
};

export interface AuditRepository {
  record(entry: AuditEntry): Promise<void>;
}
