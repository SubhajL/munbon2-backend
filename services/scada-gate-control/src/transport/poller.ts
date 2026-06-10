/**
 * Poll loop: periodically reads the device through a ModbusTransport, folds the
 * result into the latest-state store, and exposes the current snapshot. The
 * orchestration is thin; all interpretation lives in the pure store.
 */
import {
  buildSnapshot,
  emptyState,
  recordPoll,
  type GateSnapshot,
  type StoreState,
} from '../state/store';
import type { FreshnessThresholds } from '../state/freshness';
import type { ModbusTransport, PollResult } from './types';

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/**
 * A protocol-level Modbus exception (the device answered, but with an error
 * code) is distinct from a connection failure (no answer at all). modbus-serial
 * tags the former with a numeric `modbusCode`.
 */
export function classifyReadError(error: unknown): 'modbus_exception' | 'offline' {
  const code = (error as { modbusCode?: unknown } | null)?.modbusCode;
  return typeof code === 'number' ? 'modbus_exception' : 'offline';
}

export type PollerOptions = {
  readonly transport: ModbusTransport;
  readonly thresholds: FreshnessThresholds;
  readonly intervalMs: number;
  readonly now?: () => number;
  readonly onSnapshot?: (snapshot: GateSnapshot) => void;
  readonly onError?: (error: unknown) => void;
};

export class GatePoller {
  private state: StoreState = emptyState();
  private timer: ReturnType<typeof setInterval> | null = null;
  private inFlight = false;
  private readonly now: () => number;

  constructor(private readonly opts: PollerOptions) {
    this.now = opts.now ?? (() => Date.now());
  }

  /**
   * Reads the device once and folds the result into the store. If a previous
   * poll is still in flight (a slow read overrunning the interval), this call
   * is skipped and returns the current snapshot — never two concurrent
   * transactions on the same Modbus client.
   */
  async pollOnce(): Promise<GateSnapshot> {
    if (this.inFlight) return this.snapshot();
    this.inFlight = true;
    let result: PollResult;
    try {
      try {
        const reads = await this.opts.transport.readAll();
        result = { ok: true, atMs: this.now(), reads };
      } catch (error) {
        result = {
          ok: false,
          atMs: this.now(),
          quality: classifyReadError(error),
          error: errorMessage(error),
        };
        this.opts.onError?.(error);
      }
      this.state = recordPoll(this.state, result);
    } finally {
      this.inFlight = false;
    }
    const snapshot = this.snapshot();
    this.opts.onSnapshot?.(snapshot);
    return snapshot;
  }

  snapshot(): GateSnapshot {
    return buildSnapshot(this.state, this.now(), this.opts.thresholds);
  }

  start(): void {
    if (this.timer) return;
    void this.pollOnce();
    this.timer = setInterval(() => void this.pollOnce(), this.opts.intervalMs);
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }
}
