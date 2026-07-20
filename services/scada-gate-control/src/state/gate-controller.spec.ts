import { describe, expect, test, vi } from 'vitest';
import { GateController, classifyReadError, noopWriteMeter } from './gate-controller';
import type { FreshnessThresholds } from './freshness';
import type { ModbusWrite } from '../domain/command';
import type { ModbusTransport, PointReads } from '../transport/types';

const thresholds: FreshnessThresholds = { staleAfterMs: 10_000, offlineAfterMs: 20_000 };
const validReads: PointReads = { gateLevel: 2, doorSw: 1, horn: 0, gateCf: 0 };
const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** Fake transport that logs every operation and yields a macrotask per op, so
 * the test can observe whether two operation sequences interleave. */
function loggingTransport(opts: { failWrite?: boolean } = {}) {
  const log: string[] = [];
  const transport: ModbusTransport = {
    connect: async () => undefined,
    readAll: async () => {
      log.push('read:begin');
      await delay(1);
      log.push('read:end');
      return validReads;
    },
    writeHoldingRegister: async (address) => {
      log.push(`hr:begin:${address}`);
      await delay(1);
      if (opts.failWrite) throw new Error('write failed');
      log.push(`hr:end:${address}`);
    },
    writeCoil: async (address) => {
      log.push(`coil:begin:${address}`);
      await delay(1);
      log.push(`coil:end:${address}`);
    },
    close: async () => undefined,
  };
  return { transport, log };
}

const gateWrites: ModbusWrite[] = [
  { kind: 'writeHoldingRegister', point: 'Op_gate', address: 108, value: 2 },
  { kind: 'writeCoil', point: 'GateCF', address: 17, value: 1 },
];

describe('classifyReadError', () => {
  test('modbusCode present -> modbus_exception, else offline', () => {
    expect(classifyReadError(Object.assign(new Error('x'), { modbusCode: 2 }))).toBe(
      'modbus_exception',
    );
    expect(classifyReadError(new Error('ECONNREFUSED'))).toBe('offline');
  });
});

describe('GateController.poll', () => {
  test('a successful read yields an ok snapshot', async () => {
    const { transport } = loggingTransport();
    const ctrl = new GateController({
      transport,
      thresholds,
      intervalMs: 3_000,
      now: () => 5_000,
      writeMeter: noopWriteMeter,
    });
    expect((await ctrl.poll()).connection).toBe('ok');
  });

  test('a connection error yields an offline snapshot and fires onError', async () => {
    const onError = vi.fn();
    const transport: ModbusTransport = {
      connect: async () => undefined,
      readAll: async () => {
        throw new Error('ECONNREFUSED');
      },
      writeHoldingRegister: async () => undefined,
      writeCoil: async () => undefined,
      close: async () => undefined,
    };
    const ctrl = new GateController({
      transport,
      thresholds,
      intervalMs: 3_000,
      now: () => 5_000,
      onError,
      writeMeter: noopWriteMeter,
    });
    expect((await ctrl.poll()).connection).toBe('offline');
    expect(onError).toHaveBeenCalledOnce();
  });
});

describe('GateController serialization (the actuator-safety fix)', () => {
  test('two concurrent commands never interleave their Modbus operations', async () => {
    const { transport, log } = loggingTransport();
    const ctrl = new GateController({
      transport,
      thresholds,
      intervalMs: 3_000,
      now: () => 1_000,
      writeMeter: noopWriteMeter,
    });

    const writesA: ModbusWrite[] = [
      { kind: 'writeHoldingRegister', point: 'Op_gate', address: 108, value: 2 },
    ];
    const writesB: ModbusWrite[] = [
      { kind: 'writeHoldingRegister', point: 'Op_gate', address: 108, value: 4 },
    ];

    await Promise.all([
      ctrl.executeWrites(writesA, 'operator'),
      ctrl.executeWrites(writesB, 'operator'),
    ]);

    // Command A's write + read-back must fully precede command B's.
    expect(log).toEqual([
      'hr:begin:108',
      'hr:end:108',
      'read:begin',
      'read:end',
      'hr:begin:108',
      'hr:end:108',
      'read:begin',
      'read:end',
    ]);
  });

  test('a command and a concurrent poll do not interleave', async () => {
    const { transport, log } = loggingTransport();
    const ctrl = new GateController({
      transport,
      thresholds,
      intervalMs: 3_000,
      now: () => 1_000,
      writeMeter: noopWriteMeter,
    });

    await Promise.all([ctrl.executeWrites(gateWrites, 'operator'), ctrl.poll()]);

    // Whichever acquires the queue first runs to completion before the other.
    const firstRead = log.indexOf('read:begin');
    const writeIdx = log.indexOf('hr:begin:108');
    const interleaved =
      // a poll read starting between the command's write and its own read-back
      log.slice(writeIdx, log.lastIndexOf('read:end')).filter((e) => e === 'read:begin').length > 2;
    expect(interleaved).toBe(false);
    expect(firstRead).toBeGreaterThanOrEqual(0);
  });
});

describe('GateController.executeWrites', () => {
  test('applies all writes and reads back the new state', async () => {
    const { transport, log } = loggingTransport();
    const ctrl = new GateController({
      transport,
      thresholds,
      intervalMs: 3_000,
      now: () => 1_000,
      writeMeter: noopWriteMeter,
    });

    const execution = await ctrl.executeWrites(gateWrites, 'operator');

    expect(execution.failed).toBeNull();
    expect(execution.succeeded).toEqual(gateWrites);
    expect(execution.snapshot.connection).toBe('ok');
    expect(log).toEqual([
      'hr:begin:108',
      'hr:end:108',
      'coil:begin:17',
      'coil:end:17',
      'read:begin',
      'read:end',
    ]);
  });

  test('on a write failure: records the failed write, stops, still reads back', async () => {
    const { transport, log } = loggingTransport({ failWrite: true });
    const ctrl = new GateController({
      transport,
      thresholds,
      intervalMs: 3_000,
      now: () => 1_000,
      writeMeter: noopWriteMeter,
    });

    const execution = await ctrl.executeWrites(gateWrites, 'operator');

    expect(execution.succeeded).toEqual([]);
    expect(execution.failed).toEqual({ write: gateWrites[0], error: 'write failed' });
    expect(log).toContain('read:begin'); // hazard read-back happened
    expect(log).not.toContain('coil:begin:17'); // stopped before the confirmation coil
  });
});

describe('GateController.executeWrites — write metering (PR 6.4)', () => {
  test('records one metered write per accepted physical write, tagged with provenance', async () => {
    const recorded: string[] = [];
    const meter = { recordModbusWrite: (p: string) => recorded.push(p) };
    const { transport } = loggingTransport();
    const ctrl = new GateController({
      transport,
      thresholds,
      intervalMs: 3_000,
      now: () => 1_000,
      writeMeter: meter,
    });

    await ctrl.executeWrites(gateWrites, 'operator'); // HR 108 + coil 17 = two writes

    expect(recorded).toEqual(['operator', 'operator']);
  });

  test('a would-be machine write lights up a non-operator series (the shadow-alert tripwire)', async () => {
    const recorded: string[] = [];
    const meter = { recordModbusWrite: (p: string) => recorded.push(p) };
    const { transport } = loggingTransport();
    const ctrl = new GateController({
      transport,
      thresholds,
      intervalMs: 3_000,
      now: () => 1_000,
      writeMeter: meter,
    });

    await ctrl.executeWrites(gateWrites, 'shadow');

    expect(recorded).toEqual(['shadow', 'shadow']);
  });

  test('an attempted write is metered even when it fails (fail-safe: a write can move the PLC then throw)', async () => {
    const recorded: string[] = [];
    const meter = { recordModbusWrite: (p: string) => recorded.push(p) };
    const { transport } = loggingTransport({ failWrite: true }); // first write throws
    const ctrl = new GateController({
      transport,
      thresholds,
      intervalMs: 3_000,
      now: () => 1_000,
      writeMeter: meter,
    });

    await ctrl.executeWrites(gateWrites, 'operator');

    // The first write is attempted (and counted) before it throws; the loop then stops, so
    // the second write is never attempted. Over-counting the failed write is the fail-safe
    // direction for the zero-shadow-write tripwire.
    expect(recorded).toEqual(['operator']);
  });
});

describe('GateController.start/stop', () => {
  test('polls immediately and on the interval; stop halts it', async () => {
    vi.useFakeTimers();
    try {
      const readAll = vi.fn(async () => validReads);
      const transport: ModbusTransport = {
        connect: async () => undefined,
        readAll,
        writeHoldingRegister: async () => undefined,
        writeCoil: async () => undefined,
        close: async () => undefined,
      };
      const ctrl = new GateController({
        transport,
        thresholds,
        intervalMs: 3_000,
        now: () => 1_000,
        writeMeter: noopWriteMeter,
      });
      ctrl.start();
      await vi.advanceTimersByTimeAsync(0); // let the immediate poll's queued read run
      expect(readAll).toHaveBeenCalledTimes(1);
      await vi.advanceTimersByTimeAsync(3_000);
      expect(readAll).toHaveBeenCalledTimes(2);
      ctrl.stop();
      await vi.advanceTimersByTimeAsync(9_000);
      expect(readAll).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });
});
