/**
 * Integration test for the Postgres receipt store, env-gated on
 * `SCADA_TEST_POSTGRES_URL` (LOOPBACK ONLY — these tests write a real table). Skipped
 * in bare CI; run against a DISPOSABLE local Postgres:
 *
 *   docker run -d --name munbon-pr62b-testpg -p 55441:5432 -e POSTGRES_PASSWORD=pw postgres:14
 *   SCADA_TEST_POSTGRES_URL=postgres://postgres:pw@127.0.0.1:55441/postgres npx vitest run src/command-intents/pg-repository.spec.ts
 */
import { Pool } from 'pg';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

import { PostgresCommandIntentReceiptRepository } from './pg-repository';
import type { ValidationReceiptRecord } from './types';

const URL = process.env.SCADA_TEST_POSTGRES_URL;
const isLoopback = !!URL && /@(127\.0\.0\.1|localhost|\[::1\]):/.test(URL);
const suite = URL ? (isLoopback ? describe : describe.skip) : describe.skip;

if (URL && !isLoopback) {
  throw new Error('SCADA_TEST_POSTGRES_URL must be a loopback DB — these tests write a real table');
}

const record = (over: Partial<ValidationReceiptRecord> = {}): ValidationReceiptRecord => ({
  idempotency_key: 'test.cmd.k1',
  intent_id: '11111111-1111-4111-8111-111111111111',
  correlation_id: '22222222-2222-4222-8222-222222222222',
  request_id: 'req-1',
  intent_content_hash: 'a'.repeat(64),
  capability_hash: 'b'.repeat(64),
  receipt_id: '33333333-3333-4333-8333-333333333333',
  status: 'validation_accepted',
  reason_code: null,
  validated_at: '2026-07-20T03:00:00.000Z',
  receipt_document: '{"schema_version":1,"status":"validation_accepted"}',
  ...over,
});

suite('PostgresCommandIntentReceiptRepository (real Postgres)', () => {
  const pool = new Pool({ connectionString: URL });
  const repo = new PostgresCommandIntentReceiptRepository(pool);

  beforeAll(async () => {
    await repo.ensureSchema();
    await repo.ensureSchema(); // idempotent: running twice must not throw
  });
  beforeEach(async () => {
    await pool.query('TRUNCATE scada_command_intents');
  });
  afterAll(async () => {
    await pool.query('DROP TABLE IF EXISTS scada_command_intents');
    await pool.end();
  });

  it('inserts a fresh key and reads it back', async () => {
    const res = await repo.insertIfAbsent(record());
    expect(res.inserted).toBe(true);
    const got = await repo.getByIdempotencyKey('test.cmd.k1');
    expect(got?.receipt_id).toBe('33333333-3333-4333-8333-333333333333');
    expect(got?.receipt_document).toBe(record().receipt_document);
  });

  it('first writer wins on a duplicate key (never overwrites)', async () => {
    await repo.insertIfAbsent(record({ receipt_id: '44444444-4444-4444-8444-444444444444' }));
    const res = await repo.insertIfAbsent(
      record({ receipt_id: '55555555-5555-4555-8555-555555555555' }),
    );
    expect(res.inserted).toBe(false);
    expect(res.stored.receipt_id).toBe('44444444-4444-4444-8444-444444444444');
  });

  it('a concurrent race collapses to exactly one durable row (both see the winner)', async () => {
    const [a, b] = await Promise.all([
      repo.insertIfAbsent(record({ receipt_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa' })),
      repo.insertIfAbsent(record({ receipt_id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb' })),
    ]);
    expect([a.inserted, b.inserted].filter(Boolean)).toHaveLength(1);
    expect(a.stored.receipt_id).toBe(b.stored.receipt_id);
    const count = await pool.query('SELECT count(*)::int AS n FROM scada_command_intents');
    expect(count.rows[0].n).toBe(1);
  });

  it('enforces the accepted-has-no-reason CHECK constraint', async () => {
    await expect(
      repo.insertIfAbsent(
        record({ status: 'validation_accepted', reason_code: 'freshness_failed' }),
      ),
    ).rejects.toThrow();
  });
});
