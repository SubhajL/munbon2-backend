import { describe, expect, test, vi } from 'vitest';
import { GatePoller, classifyReadError } from './poller';
import type { FreshnessThresholds } from '../state/freshness';
import type { ModbusTransport, PointReads } from './types';

const thresholds: FreshnessThresholds = { staleAfterMs: 10_000, offlineAfterMs: 20_000 };
const validReads: PointReads = { gateLevel: 4, doorSw: 0, horn: 0, gateCf: 0 };

/** Minimal fake transport whose readAll behaviour the test controls. */
function fakeTransport(readAll: () => Promise<PointReads>): ModbusTransport {
  return {
    connect: vi.fn(async () => undefined),
    readAll: vi.fn(readAll),
    writeHoldingRegister: vi.fn(async () => undefined),
    writeCoil: vi.fn(async () => undefined),
    close: vi.fn(async () => undefined),
  };
}

describe('classifyReadError', () => {
  test('a Modbus protocol exception (has modbusCode) -> modbus_exception', () => {
    expect(classifyReadError(Object.assign(new Error('illegal'), { modbusCode: 2 }))).toBe(
      'modbus_exception',
    );
  });

  test('a plain connection error -> offline', () => {
    expect(classifyReadError(new Error('ECONNREFUSED'))).toBe('offline');
  });
});

describe('GatePoller.pollOnce', () => {
  test('a successful read produces an ok/green snapshot with decoded values', async () => {
    const poller = new GatePoller({
      transport: fakeTransport(async () => validReads),
      thresholds,
      intervalMs: 3_000,
      now: () => 5_000,
    });
    const snap = await poller.pollOnce();
    expect(snap.connection).toBe('ok');
    expect(snap.gateLevel.value?.technicalLabel).toBe('Level 4 / Fully Open');
  });

  test('a thrown connection error yields an offline snapshot and fires onError', async () => {
    const onError = vi.fn();
    const poller = new GatePoller({
      transport: fakeTransport(async () => {
        throw new Error('ECONNREFUSED');
      }),
      thresholds,
      intervalMs: 3_000,
      now: () => 5_000,
      onError,
    });
    const snap = await poller.pollOnce();
    expect(snap.connection).toBe('offline');
    expect(snap.lastError).toBe('ECONNREFUSED');
    expect(onError).toHaveBeenCalledOnce();
  });

  test('a Modbus exception yields a modbus_exception snapshot', async () => {
    const poller = new GatePoller({
      transport: fakeTransport(async () => {
        throw Object.assign(new Error('illegal data address'), { modbusCode: 2 });
      }),
      thresholds,
      intervalMs: 3_000,
      now: () => 5_000,
    });
    expect((await poller.pollOnce()).connection).toBe('modbus_exception');
  });

  test('after a success, a later failure degrades quality but keeps last values', async () => {
    let mode: 'ok' | 'fail' = 'ok';
    let clock = 1_000;
    const poller = new GatePoller({
      transport: fakeTransport(async () => {
        if (mode === 'fail') throw new Error('ECONNRESET');
        return validReads;
      }),
      thresholds,
      intervalMs: 3_000,
      now: () => clock,
    });

    await poller.pollOnce(); // success at 1000
    mode = 'fail';
    clock = 1_500;
    const snap = await poller.pollOnce(); // failure at 1500

    expect(snap.connection).toBe('offline');
    expect(snap.gateLevel.value?.technicalLabel).toBe('Level 4 / Fully Open');
  });
});

describe('GatePoller.start/stop', () => {
  test('start polls immediately then on the interval; stop halts it', async () => {
    vi.useFakeTimers();
    try {
      const readAll = vi.fn(async () => validReads);
      const poller = new GatePoller({
        transport: fakeTransport(readAll),
        thresholds,
        intervalMs: 3_000,
        now: () => 1_000,
      });

      poller.start();
      expect(readAll).toHaveBeenCalledTimes(1); // immediate poll
      await vi.advanceTimersByTimeAsync(3_000);
      expect(readAll).toHaveBeenCalledTimes(2);
      poller.stop();
      await vi.advanceTimersByTimeAsync(9_000);
      expect(readAll).toHaveBeenCalledTimes(2); // no further polls after stop
    } finally {
      vi.useRealTimers();
    }
  });

  test('skips interval ticks while a slow read is still in flight', async () => {
    vi.useFakeTimers();
    try {
      let resolveFirst: (reads: PointReads) => void = () => undefined;
      let calls = 0;
      const readAll = vi.fn((): Promise<PointReads> => {
        calls += 1;
        if (calls === 1) {
          return new Promise<PointReads>((resolve) => {
            resolveFirst = resolve;
          });
        }
        return Promise.resolve(validReads);
      });
      const poller = new GatePoller({
        transport: fakeTransport(readAll),
        thresholds,
        intervalMs: 3_000,
        now: () => 1_000,
      });

      poller.start(); // immediate poll #1 begins and hangs
      expect(readAll).toHaveBeenCalledTimes(1);
      await vi.advanceTimersByTimeAsync(3_000); // tick fires but poll #1 still in flight
      expect(readAll).toHaveBeenCalledTimes(1); // skipped, no concurrent transaction

      resolveFirst(validReads); // poll #1 completes, guard clears
      await vi.advanceTimersByTimeAsync(3_000); // next tick now allowed to poll
      expect(readAll).toHaveBeenCalledTimes(2);
      poller.stop();
    } finally {
      vi.useRealTimers();
    }
  });
});
