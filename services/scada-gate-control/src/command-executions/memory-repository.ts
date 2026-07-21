import type {
  CommandExecutionRepository,
  ExecutionOutcomeRecord,
  ExecutionReservation,
  ReserveOutcome,
} from './types';

export class InMemoryCommandExecutionRepository implements CommandExecutionRepository {
  private readonly reservations = new Map<string, ExecutionReservation>();
  private readonly outcomes = new Map<string, ExecutionOutcomeRecord>();

  async ensureSchema(): Promise<void> {}

  async getReservation(idempotencyKey: string): Promise<ExecutionReservation | null> {
    return this.reservations.get(idempotencyKey) ?? null;
  }

  async reserveIfAbsent(reservation: ExecutionReservation): Promise<ReserveOutcome> {
    const existing = this.reservations.get(reservation.idempotency_key);
    if (existing) return { inserted: false, stored: existing };
    this.reservations.set(reservation.idempotency_key, reservation);
    return { inserted: true, stored: reservation };
  }

  async getOutcome(idempotencyKey: string): Promise<ExecutionOutcomeRecord | null> {
    return this.outcomes.get(idempotencyKey) ?? null;
  }

  async insertOutcomeIfAbsent(outcome: ExecutionOutcomeRecord): Promise<ExecutionOutcomeRecord> {
    const existing = this.outcomes.get(outcome.idempotency_key);
    if (existing) return existing;
    this.outcomes.set(outcome.idempotency_key, outcome);
    return outcome;
  }
}
