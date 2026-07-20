import { describe, expect, it } from 'vitest';

import { InMemoryCommandIntentReceiptRepository } from './memory-repository';
import type { ValidationReceiptRecord } from './types';

const record = (over: Partial<ValidationReceiptRecord> = {}): ValidationReceiptRecord => ({
  idempotency_key: 'cmd.k1',
  intent_id: '11111111-1111-4111-8111-111111111111',
  correlation_id: '22222222-2222-4222-8222-222222222222',
  request_id: 'req-1',
  intent_content_hash: 'a'.repeat(64),
  capability_hash: 'b'.repeat(64),
  receipt_id: '33333333-3333-4333-8333-333333333333',
  status: 'validation_accepted',
  reason_code: null,
  validated_at: '2026-07-20T03:00:00.000Z',
  receipt_document: '{"schema_version":1}',
  ...over,
});

describe('InMemoryCommandIntentReceiptRepository', () => {
  it('inserts a new key and reads it back', async () => {
    const repo = new InMemoryCommandIntentReceiptRepository();
    const res = await repo.insertIfAbsent(record());
    expect(res.inserted).toBe(true);
    expect(await repo.getByIdempotencyKey('cmd.k1')).toEqual(record());
  });

  it('first writer wins: a second insert on the same key keeps the original row', async () => {
    const repo = new InMemoryCommandIntentReceiptRepository();
    await repo.insertIfAbsent(record({ receipt_id: 'first' }));
    const res = await repo.insertIfAbsent(record({ receipt_id: 'second' }));
    expect(res.inserted).toBe(false);
    expect(res.stored.receipt_id).toBe('first');
    expect((await repo.getByIdempotencyKey('cmd.k1'))?.receipt_id).toBe('first');
  });

  it('returns null for an unknown key', async () => {
    expect(
      await new InMemoryCommandIntentReceiptRepository().getByIdempotencyKey('nope'),
    ).toBeNull();
  });
});
