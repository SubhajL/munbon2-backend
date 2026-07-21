import { Pool } from 'pg';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

import { PostgresCommandExecutionRepository } from './pg-repository';
import type { ExecutionReservation } from './types';

const URL = process.env.SCADA_TEST_POSTGRES_URL;
const isLoopback = !!URL && /@(127\.0\.0\.1|localhost|\[::1\]):/.test(URL);
const suite = URL ? (isLoopback ? describe : describe.skip) : describe.skip;

if (URL && !isLoopback) {
  throw new Error('SCADA_TEST_POSTGRES_URL must be a loopback DB');
}

const reservation = (overrides: Partial<ExecutionReservation> = {}): ExecutionReservation => ({
  idempotency_key: 'campaign-gate-seq-1',
  intent_id: '11111111-1111-4111-8111-111111111111',
  grant_id: '77777777-7777-4777-8777-777777777777',
  authority_not_after: '2026-07-21T03:05:00.000Z',
  original_intent_content_hash: 'a'.repeat(64),
  execution_intent_content_hash: 'b'.repeat(64),
  purpose: 'operator_approved',
  reserved_at: '2026-07-21T03:00:00.000Z',
  ...overrides,
});

suite('PostgresCommandExecutionRepository (real Postgres)', () => {
  const pool = new Pool({ connectionString: URL });
  const repository = new PostgresCommandExecutionRepository(pool);

  beforeAll(async () => {
    await repository.ensureSchema();
    await repository.ensureSchema();
  });

  beforeEach(async () => {
    await pool.query(
      'TRUNCATE scada_command_execution_outcomes, scada_command_execution_reservations',
    );
  });

  afterAll(async () => {
    await pool.query('DROP TABLE IF EXISTS scada_command_execution_outcomes');
    await pool.query('DROP TABLE IF EXISTS scada_command_execution_reservations');
    await pool.end();
  });

  it('keeps the first durable reservation for an idempotency key', async () => {
    const first = await repository.reserveIfAbsent(reservation());
    const replay = await repository.reserveIfAbsent(
      reservation({ execution_intent_content_hash: 'c'.repeat(64) }),
    );

    expect({ first, replay }).toEqual({
      first: { inserted: true, stored: reservation() },
      replay: { inserted: false, stored: reservation() },
    });
  });

  it('keeps the first durable outcome so a retry replays one receipt', async () => {
    await repository.reserveIfAbsent(reservation());
    const first = await repository.insertOutcomeIfAbsent({
      idempotency_key: reservation().idempotency_key,
      receipt_document: '{"receipt_id":"first"}',
    });
    const replay = await repository.insertOutcomeIfAbsent({
      idempotency_key: reservation().idempotency_key,
      receipt_document: '{"receipt_id":"second"}',
    });

    expect({ first, replay }).toEqual({
      first: {
        idempotency_key: reservation().idempotency_key,
        receipt_document: '{"receipt_id":"first"}',
      },
      replay: {
        idempotency_key: reservation().idempotency_key,
        receipt_document: '{"receipt_id":"first"}',
      },
    });
  });

  it('makes reservation and outcome evidence immutable in the database', async () => {
    await repository.reserveIfAbsent(reservation());
    await repository.insertOutcomeIfAbsent({
      idempotency_key: reservation().idempotency_key,
      receipt_document: '{"receipt_id":"first"}',
    });

    await expect(
      pool.query(
        `UPDATE scada_command_execution_reservations SET purpose = 'fail_safe_close'
         WHERE idempotency_key = $1`,
        [reservation().idempotency_key],
      ),
    ).rejects.toThrow(/immutable/);
    await expect(
      pool.query('DELETE FROM scada_command_execution_outcomes WHERE idempotency_key = $1', [
        reservation().idempotency_key,
      ]),
    ).rejects.toThrow(/immutable/);
  });
});
