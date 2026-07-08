/**
 * Postgres-backed audit repository. The schema lives in ./schema.sql; call
 * ensureSchema() once at startup (or run the SQL via a migration).
 *
 * Not unit-tested here (requires a live Postgres); exercised against a real DB
 * in deployment / Slice 6 integration.
 */
import type { Pool } from 'pg';
import type { AuditEntry, AuditRepository } from './types';

const INSERT_SQL = `
INSERT INTO scada_gate_audit
  (timestamp, user_id, user_role, gate_id, gate_name, command_type,
   requested_target, modbus_host, modbus_port, unit_id, writes, result, error)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)`;

const SCHEMA_SQL = `
CREATE TABLE IF NOT EXISTS scada_gate_audit (
  id               BIGSERIAL PRIMARY KEY,
  timestamp        TIMESTAMPTZ NOT NULL,
  user_id          TEXT NOT NULL,
  user_role        TEXT NOT NULL,
  gate_id          TEXT NOT NULL,
  gate_name        TEXT NOT NULL,
  command_type     TEXT NOT NULL,
  requested_target TEXT NOT NULL,
  modbus_host      TEXT NOT NULL,
  modbus_port      INTEGER NOT NULL,
  unit_id          INTEGER NOT NULL,
  writes           JSONB NOT NULL,
  result           TEXT NOT NULL,
  error            TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_scada_gate_audit_gate_time
  ON scada_gate_audit (gate_id, timestamp DESC);`;

export class PostgresAuditRepository implements AuditRepository {
  constructor(private readonly pool: Pool) {}

  async ensureSchema(): Promise<void> {
    await this.pool.query(SCHEMA_SQL);
  }

  async record(entry: AuditEntry): Promise<void> {
    await this.pool.query(INSERT_SQL, [
      entry.timestamp,
      entry.userId,
      entry.userRole,
      entry.gateId,
      entry.gateName,
      entry.commandType,
      String(entry.requestedTarget),
      entry.modbusHost,
      entry.modbusPort,
      entry.unitId,
      JSON.stringify(entry.writes),
      entry.result,
      entry.error,
    ]);
  }
}
