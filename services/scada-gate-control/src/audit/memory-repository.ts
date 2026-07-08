import type { AuditEntry, AuditRepository } from './types';

/** In-memory audit sink for tests and local development. */
export class InMemoryAuditRepository implements AuditRepository {
  readonly entries: AuditEntry[] = [];

  async record(entry: AuditEntry): Promise<void> {
    this.entries.push(entry);
  }
}
