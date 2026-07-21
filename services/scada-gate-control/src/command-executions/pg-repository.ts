import type { Pool } from 'pg';

import type {
  CommandExecutionRepository,
  ExecutionOutcomeRecord,
  ExecutionPurpose,
  ExecutionReservation,
  ReserveOutcome,
} from './types';

const SCHEMA_SQL = `
CREATE TABLE IF NOT EXISTS scada_command_execution_reservations (
  idempotency_key TEXT PRIMARY KEY,
  intent_id UUID NOT NULL,
  grant_id UUID NOT NULL,
  authority_not_after TIMESTAMPTZ NOT NULL,
  original_intent_content_hash CHAR(64) NOT NULL,
  execution_intent_content_hash CHAR(64) NOT NULL,
  purpose TEXT NOT NULL CHECK (purpose IN ('operator_approved', 'fail_safe_close')),
  reserved_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS scada_command_execution_outcomes (
  idempotency_key TEXT PRIMARY KEY REFERENCES scada_command_execution_reservations(idempotency_key),
  receipt_document TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE OR REPLACE FUNCTION scada_command_execution_rows_are_immutable()
RETURNS trigger AS $function$
BEGIN
  RAISE EXCEPTION 'machine execution evidence is immutable';
END;
$function$ LANGUAGE plpgsql;
DO $triggers$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgname = 'scada_command_execution_reservations_immutable'
      AND tgrelid = 'scada_command_execution_reservations'::regclass
  ) THEN
    CREATE TRIGGER scada_command_execution_reservations_immutable
      BEFORE UPDATE OR DELETE ON scada_command_execution_reservations
      FOR EACH ROW EXECUTE FUNCTION scada_command_execution_rows_are_immutable();
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgname = 'scada_command_execution_outcomes_immutable'
      AND tgrelid = 'scada_command_execution_outcomes'::regclass
  ) THEN
    CREATE TRIGGER scada_command_execution_outcomes_immutable
      BEFORE UPDATE OR DELETE ON scada_command_execution_outcomes
      FOR EACH ROW EXECUTE FUNCTION scada_command_execution_rows_are_immutable();
  END IF;
END;
$triggers$;`;

type ReservationRow = {
  idempotency_key: string;
  intent_id: string;
  grant_id: string;
  authority_not_after: Date | string;
  original_intent_content_hash: string;
  execution_intent_content_hash: string;
  purpose: string;
  reserved_at: Date | string;
};

const RESERVATION_COLUMNS = `idempotency_key, intent_id, grant_id, authority_not_after,
  original_intent_content_hash, execution_intent_content_hash, purpose, reserved_at`;

function reservationFromRow(row: ReservationRow): ExecutionReservation {
  return {
    ...row,
    authority_not_after:
      row.authority_not_after instanceof Date
        ? row.authority_not_after.toISOString()
        : String(row.authority_not_after),
    purpose: row.purpose as ExecutionPurpose,
    reserved_at:
      row.reserved_at instanceof Date ? row.reserved_at.toISOString() : String(row.reserved_at),
  };
}

export class PostgresCommandExecutionRepository implements CommandExecutionRepository {
  constructor(private readonly pool: Pool) {}

  async ensureSchema(): Promise<void> {
    await this.pool.query(SCHEMA_SQL);
  }

  async getReservation(idempotencyKey: string): Promise<ExecutionReservation | null> {
    const row = (
      await this.pool.query<ReservationRow>(
        `SELECT ${RESERVATION_COLUMNS} FROM scada_command_execution_reservations
         WHERE idempotency_key = $1`,
        [idempotencyKey],
      )
    ).rows[0];
    return row ? reservationFromRow(row) : null;
  }

  async reserveIfAbsent(reservation: ExecutionReservation): Promise<ReserveOutcome> {
    const values = [
      reservation.idempotency_key,
      reservation.intent_id,
      reservation.grant_id,
      reservation.authority_not_after,
      reservation.original_intent_content_hash,
      reservation.execution_intent_content_hash,
      reservation.purpose,
      reservation.reserved_at,
    ];
    const inserted = (
      await this.pool.query<ReservationRow>(
        `INSERT INTO scada_command_execution_reservations (${RESERVATION_COLUMNS})
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
         ON CONFLICT (idempotency_key) DO NOTHING
         RETURNING ${RESERVATION_COLUMNS}`,
        values,
      )
    ).rows[0];
    if (inserted) return { inserted: true, stored: reservationFromRow(inserted) };
    const existing = await this.getReservation(reservation.idempotency_key);
    if (!existing) throw new Error('reservation conflicted but winner could not be read');
    return { inserted: false, stored: existing };
  }

  async getOutcome(idempotencyKey: string): Promise<ExecutionOutcomeRecord | null> {
    const row = (
      await this.pool.query<ExecutionOutcomeRecord>(
        `SELECT idempotency_key, receipt_document FROM scada_command_execution_outcomes
         WHERE idempotency_key = $1`,
        [idempotencyKey],
      )
    ).rows[0];
    return row ?? null;
  }

  async insertOutcomeIfAbsent(outcome: ExecutionOutcomeRecord): Promise<ExecutionOutcomeRecord> {
    const inserted = (
      await this.pool.query<ExecutionOutcomeRecord>(
        `INSERT INTO scada_command_execution_outcomes (idempotency_key, receipt_document)
         VALUES ($1, $2) ON CONFLICT (idempotency_key) DO NOTHING
         RETURNING idempotency_key, receipt_document`,
        [outcome.idempotency_key, outcome.receipt_document],
      )
    ).rows[0];
    if (inserted) return inserted;
    const existing = await this.getOutcome(outcome.idempotency_key);
    if (!existing) throw new Error('outcome conflicted but winner could not be read');
    return existing;
  }
}
