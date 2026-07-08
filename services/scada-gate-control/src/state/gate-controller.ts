/**
 * GateController owns the single point of Modbus access for one gate: the
 * transport, a serialization Mutex, and the latest-state store. Every read
 * (poll) and every write (command) goes through the SAME queue, so the
 * non-reentrant modbus-serial client never sees overlapping transactions and
 * each multi-write command is executed atomically (writes + read-back as one
 * critical section).
 */
import type { ModbusWrite } from '../domain/command';
import type { ModbusTransport, PollResult } from '../transport/types';
import { Mutex } from '../transport/mutex';
import { buildSnapshot, emptyState, recordPoll, type GateSnapshot, type StoreState } from './store';
import type { FreshnessThresholds } from './freshness';

/** A device exception (answered with an error code) vs no answer at all. */
export function classifyReadError(error: unknown): 'modbus_exception' | 'offline' {
  const code = (error as { modbusCode?: unknown } | null)?.modbusCode;
  return typeof code === 'number' ? 'modbus_exception' : 'offline';
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export type WriteFailure = { readonly write: ModbusWrite; readonly error: string };

export type WriteExecution = {
  readonly succeeded: readonly ModbusWrite[];
  readonly failed: WriteFailure | null;
  readonly snapshot: GateSnapshot;
};

/** The capability the command service needs: read state + actuate atomically. */
export interface GateActuator {
  snapshot(): GateSnapshot;
  executeWrites(writes: readonly ModbusWrite[]): Promise<WriteExecution>;
}

export type GateControllerOptions = {
  readonly transport: ModbusTransport;
  readonly thresholds: FreshnessThresholds;
  readonly intervalMs: number;
  readonly now?: () => number;
  readonly onSnapshot?: (snapshot: GateSnapshot) => void;
  readonly onError?: (error: unknown) => void;
};

export class GateController implements GateActuator {
  private state: StoreState = emptyState();
  private readonly queue = new Mutex();
  private timer: ReturnType<typeof setInterval> | null = null;
  private polling = false;
  private readonly now: () => number;

  constructor(private readonly opts: GateControllerOptions) {
    this.now = opts.now ?? (() => Date.now());
  }

  snapshot(): GateSnapshot {
    return buildSnapshot(this.state, this.now(), this.opts.thresholds);
  }

  /** Read all points; classify any failure. Never throws. */
  private async read(): Promise<PollResult> {
    try {
      const reads = await this.opts.transport.readAll();
      return { ok: true, atMs: this.now(), reads };
    } catch (error) {
      this.opts.onError?.(error);
      return {
        ok: false,
        atMs: this.now(),
        quality: classifyReadError(error),
        error: errorMessage(error),
      };
    }
  }

  async poll(): Promise<GateSnapshot> {
    if (this.polling) return this.snapshot(); // don't stack poll ticks
    this.polling = true;
    try {
      const result = await this.queue.run(() => this.read());
      this.state = recordPoll(this.state, result);
    } finally {
      this.polling = false;
    }
    const snapshot = this.snapshot();
    this.opts.onSnapshot?.(snapshot);
    return snapshot;
  }

  async executeWrites(writes: readonly ModbusWrite[]): Promise<WriteExecution> {
    const succeeded: ModbusWrite[] = [];
    let failed: WriteFailure | null = null;
    const result = await this.queue.run(async () => {
      for (const write of writes) {
        try {
          await this.applyWrite(write);
          succeeded.push(write);
        } catch (error) {
          failed = { write, error: errorMessage(error) };
          break; // stop on first failure; still read back the hazard state below
        }
      }
      return this.read();
    });
    this.state = recordPoll(this.state, result);
    return { succeeded, failed, snapshot: this.snapshot() };
  }

  private async applyWrite(write: ModbusWrite): Promise<void> {
    if (write.kind === 'writeHoldingRegister') {
      await this.opts.transport.writeHoldingRegister(write.address, write.value);
    } else {
      await this.opts.transport.writeCoil(write.address, write.value === 1);
    }
  }

  start(): void {
    if (this.timer) return;
    void this.poll();
    this.timer = setInterval(() => void this.poll(), this.opts.intervalMs);
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }
}
