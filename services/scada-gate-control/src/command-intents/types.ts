/**
 * PR 6.2b — durable validation-receipt store contract.
 *
 * One row per idempotency_key (the dedup arbiter, matching the Scheduler outbox's
 * UNIQUE idempotency_key). The row is written once, at first validation, and is
 * immutable thereafter: a replay returns the stored `receipt_document` byte-for-byte,
 * and a same-key/different-intent request is an idempotency_conflict that never mutates
 * the winning row. `intent_content_hash` is the replay-vs-conflict discriminator.
 */
import type { ValidationRejectionReason, ValidationStatus } from '../domain/machine-boundary';

export type ValidationReceiptRecord = {
  readonly idempotency_key: string;
  readonly intent_id: string;
  readonly correlation_id: string;
  readonly request_id: string;
  readonly intent_content_hash: string;
  readonly capability_hash: string;
  readonly receipt_id: string;
  readonly status: ValidationStatus;
  readonly reason_code: ValidationRejectionReason | null;
  readonly validated_at: string;
  /** The exact ValidationReceipt JSON returned verbatim on every replay. */
  readonly receipt_document: string;
};

export type InsertOutcome = {
  /** true if THIS call won the insert; false if a row for the key already existed. */
  readonly inserted: boolean;
  /** The durable row — the freshly-inserted one, or the pre-existing winner on a race. */
  readonly stored: ValidationReceiptRecord;
};

export interface CommandIntentReceiptRepository {
  ensureSchema(): Promise<void>;
  getByIdempotencyKey(idempotencyKey: string): Promise<ValidationReceiptRecord | null>;
  /**
   * Atomically insert the record IF its idempotency_key is absent; otherwise return the
   * pre-existing row. Never overwrites — the first writer for a key wins permanently.
   */
  insertIfAbsent(record: ValidationReceiptRecord): Promise<InsertOutcome>;
}
