/**
 * Postgres-backed validation-receipt store. Schema lives in ensureSchema() (called
 * once at startup, mirroring PostgresAuditRepository) — this TS service has no
 * migration runner, so a co-located idempotent DDL is the migration equivalent.
 *
 * Immutable by convention: only insert-if-absent, never UPDATE/DELETE. The
 * idempotency_key PRIMARY KEY + `ON CONFLICT DO NOTHING RETURNING` make the first
 * writer win atomically, so two concurrent first-time requests for the same key
 * collapse to one durable row and both callers observe the same receipt.
 */
import type { Pool } from 'pg';

import {
  VALIDATION_REJECTION_REASONS,
  VALIDATION_STATUSES,
  type ValidationRejectionReason,
  type ValidationStatus,
} from '../domain/machine-boundary';
import type {
  CommandIntentReceiptRepository,
  InsertOutcome,
  ValidationReceiptRecord,
} from './types';

// Build the CHECK IN-lists FROM the frozen 6.0 enum tuples (trusted constants) so the SQL
// can never silently drift from the TypeScript contract.
const sqlEnumList = (values: readonly string[]): string => values.map((v) => `'${v}'`).join(', ');

const SCHEMA_SQL = `
CREATE TABLE IF NOT EXISTS scada_command_intents (
  idempotency_key     TEXT PRIMARY KEY,
  intent_id           UUID NOT NULL,
  correlation_id      UUID NOT NULL,
  request_id          TEXT NOT NULL,
  intent_content_hash CHAR(64) NOT NULL,
  capability_hash     CHAR(64) NOT NULL,
  receipt_id          UUID NOT NULL,
  status              TEXT NOT NULL
                        CHECK (status IN (${sqlEnumList(VALIDATION_STATUSES)})),
  reason_code         TEXT
                        CHECK (reason_code IN (${sqlEnumList(VALIDATION_REJECTION_REASONS)})),
  validated_at        TIMESTAMPTZ NOT NULL,
  receipt_document    TEXT NOT NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT scada_command_intents_reason_matches_status
    CHECK ((status = 'validation_rejected') = (reason_code IS NOT NULL))
);`;

const COLUMNS = `idempotency_key, intent_id, correlation_id, request_id, intent_content_hash,
  capability_hash, receipt_id, status, reason_code, validated_at, receipt_document`;

const INSERT_SQL = `
INSERT INTO scada_command_intents
  (${COLUMNS})
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
ON CONFLICT (idempotency_key) DO NOTHING
RETURNING ${COLUMNS}`;

const SELECT_SQL = `SELECT ${COLUMNS} FROM scada_command_intents WHERE idempotency_key = $1`;

type Row = {
  idempotency_key: string;
  intent_id: string;
  correlation_id: string;
  request_id: string;
  intent_content_hash: string;
  capability_hash: string;
  receipt_id: string;
  status: string;
  reason_code: string | null;
  validated_at: Date | string;
  receipt_document: string;
};

function rowToRecord(row: Row): ValidationReceiptRecord {
  return {
    idempotency_key: row.idempotency_key,
    intent_id: row.intent_id,
    correlation_id: row.correlation_id,
    request_id: row.request_id,
    intent_content_hash: row.intent_content_hash,
    capability_hash: row.capability_hash,
    receipt_id: row.receipt_id,
    status: row.status as ValidationStatus,
    reason_code: row.reason_code as ValidationRejectionReason | null,
    validated_at:
      row.validated_at instanceof Date ? row.validated_at.toISOString() : String(row.validated_at),
    receipt_document: row.receipt_document,
  };
}

function insertValues(r: ValidationReceiptRecord): unknown[] {
  return [
    r.idempotency_key,
    r.intent_id,
    r.correlation_id,
    r.request_id,
    r.intent_content_hash,
    r.capability_hash,
    r.receipt_id,
    r.status,
    r.reason_code,
    r.validated_at,
    r.receipt_document,
  ];
}

export class PostgresCommandIntentReceiptRepository implements CommandIntentReceiptRepository {
  constructor(private readonly pool: Pool) {}

  async ensureSchema(): Promise<void> {
    await this.pool.query(SCHEMA_SQL);
  }

  async getByIdempotencyKey(idempotencyKey: string): Promise<ValidationReceiptRecord | null> {
    const row = (await this.pool.query<Row>(SELECT_SQL, [idempotencyKey])).rows[0];
    return row ? rowToRecord(row) : null;
  }

  async insertIfAbsent(record: ValidationReceiptRecord): Promise<InsertOutcome> {
    const insertedRow = (await this.pool.query<Row>(INSERT_SQL, insertValues(record))).rows[0];
    if (insertedRow) {
      return { inserted: true, stored: rowToRecord(insertedRow) };
    }
    // Lost the race (or a prior row exists): the durable winner is the existing row.
    const existingRow = (await this.pool.query<Row>(SELECT_SQL, [record.idempotency_key])).rows[0];
    if (!existingRow) {
      throw new Error('insert conflicted but the conflicting row could not be read');
    }
    return { inserted: false, stored: rowToRecord(existingRow) };
  }
}
