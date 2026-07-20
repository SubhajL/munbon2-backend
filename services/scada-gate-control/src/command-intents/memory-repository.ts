import type {
  CommandIntentReceiptRepository,
  InsertOutcome,
  ValidationReceiptRecord,
} from './types';

/**
 * In-memory receipt store for tests and dev. The single-threaded JS event loop makes the
 * `has`→`set` in `insertIfAbsent` atomic within a request, matching the Postgres
 * `INSERT … ON CONFLICT DO NOTHING` first-writer-wins semantics.
 */
export class InMemoryCommandIntentReceiptRepository implements CommandIntentReceiptRepository {
  private readonly rows = new Map<string, ValidationReceiptRecord>();

  async ensureSchema(): Promise<void> {
    // no-op
  }

  async getByIdempotencyKey(idempotencyKey: string): Promise<ValidationReceiptRecord | null> {
    return this.rows.get(idempotencyKey) ?? null;
  }

  async insertIfAbsent(record: ValidationReceiptRecord): Promise<InsertOutcome> {
    const existing = this.rows.get(record.idempotency_key);
    if (existing !== undefined) {
      return { inserted: false, stored: existing };
    }
    this.rows.set(record.idempotency_key, record);
    return { inserted: true, stored: record };
  }
}
