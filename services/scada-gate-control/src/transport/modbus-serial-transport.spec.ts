import { afterEach, beforeEach, describe, expect, test } from 'vitest';
import { createServer } from 'node:net';
import {
  ModbusSerialTransport,
  mapPointReads,
  type ModbusClientLike,
} from './modbus-serial-transport';
import { startSimulator, type Simulator } from './simulator';

type FakeClient = ModbusClientLike & { closed: boolean; destroyed: boolean };

/** A controllable in-memory client used to test the socket lifecycle deterministically. */
function makeFakeClient(opts: { failReadOnce?: boolean; hangConnect?: boolean }): FakeClient {
  let failRead = opts.failReadOnce ?? false;
  const client: FakeClient = {
    closed: false,
    destroyed: false,
    connectTCP: () => (opts.hangConnect ? new Promise<void>(() => undefined) : Promise.resolve()),
    setID: () => undefined,
    setTimeout: () => undefined,
    readHoldingRegisters: async () => {
      if (failRead) {
        failRead = false;
        throw new Error('read fail');
      }
      return { data: [3] };
    },
    readCoils: async () => ({ data: [true, false, true] }),
    writeRegister: async () => undefined,
    writeCoil: async () => undefined,
    close: (cb: () => void) => {
      client.closed = true;
      cb();
    },
    destroy: (cb: () => void) => {
      client.closed = true;
      client.destroyed = true;
      cb();
    },
  };
  return client;
}

const cfg = { host: 'fake', port: 1, unitId: 1, timeoutMs: 100 };

describe('mapPointReads', () => {
  test('maps holding-register + coil block onto the four points', () => {
    expect(mapPointReads([3], [true, false, true])).toEqual({
      gateLevel: 3,
      horn: 1,
      doorSw: 0,
      gateCf: 1,
    });
  });

  test('throws "short Modbus read" when the holding register is missing', () => {
    expect(() => mapPointReads([], [true, false, true])).toThrow('short Modbus read');
  });

  test('throws "short Modbus read" when fewer than three coils came back', () => {
    expect(() => mapPointReads([3], [true, false])).toThrow('short Modbus read');
  });
});

describe('ModbusSerialTransport against an in-process Modbus simulator', () => {
  let sim: Simulator;
  let transport: ModbusSerialTransport;

  beforeEach(async () => {
    // Device state: Gate_Level(104)=3, Horn(15)=on, Door_SW(16)=open, GateCF(17)=on.
    sim = await startSimulator({
      holdingRegisters: { 104: 3, 108: 0 },
      coils: { 15: true, 16: false, 17: true },
      unitId: 1,
    });
    transport = new ModbusSerialTransport({
      host: '127.0.0.1',
      port: sim.port,
      unitId: 1,
      timeoutMs: 1_000,
    });
  });

  afterEach(async () => {
    await transport.close();
    await sim.close();
  });

  test('readAll maps holding register + coil block onto the four points', async () => {
    await transport.connect();
    expect(await transport.readAll()).toEqual({ gateLevel: 3, horn: 1, doorSw: 0, gateCf: 1 });
  });

  test('writeHoldingRegister actuates Op_gate (108) on the device', async () => {
    await transport.connect();
    await transport.writeHoldingRegister(108, 2);
    expect(sim.state.holdingRegisters.get(108)).toBe(2);
  });

  test('writeCoil actuates Horn (15) on the device', async () => {
    await transport.connect();
    await transport.writeCoil(15, false);
    expect(sim.state.coils.get(15)).toBe(false);
  });

  test('readAll auto-connects if connect() was not called explicitly', async () => {
    const fresh = new ModbusSerialTransport({
      host: '127.0.0.1',
      port: sim.port,
      unitId: 1,
      timeoutMs: 1_000,
    });
    try {
      expect((await fresh.readAll()).gateLevel).toBe(3);
    } finally {
      await fresh.close();
    }
  });
});

describe('ModbusSerialTransport socket lifecycle', () => {
  test('a refused TCP connection rejects instead of hanging during cleanup', async () => {
    const server = createServer();
    await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
    const address = server.address();
    if (!address || typeof address === 'string') {
      throw new Error('test TCP port unavailable');
    }
    await new Promise<void>((resolve, reject) =>
      server.close((error) => (error ? reject(error) : resolve())),
    );
    const transport = new ModbusSerialTransport({
      host: '127.0.0.1',
      port: address.port,
      unitId: 1,
      timeoutMs: 100,
    });

    let cleanupTimer: ReturnType<typeof setTimeout> | undefined;
    const result = await Promise.race([
      transport.readAll().then(
        () => 'unexpected-success',
        (error: unknown) => error,
      ),
      new Promise<string>((resolve) => {
        cleanupTimer = setTimeout(() => resolve('cleanup-timeout'), 2_000);
      }),
    ]).finally(() => clearTimeout(cleanupTimer));

    expect(result).toBeInstanceOf(Error);
  });

  test('destroys the client on a read failure and creates a fresh one next time', async () => {
    const created: FakeClient[] = [];
    const factory = (): ModbusClientLike => {
      const client = makeFakeClient({ failReadOnce: created.length === 0 });
      created.push(client);
      return client;
    };
    const transport = new ModbusSerialTransport(cfg, factory);

    await expect(transport.readAll()).rejects.toThrow('read fail');
    expect(created).toHaveLength(1);
    expect(created[0]?.closed).toBe(true);
    expect(created[0]?.destroyed).toBe(true);

    expect(await transport.readAll()).toEqual({ gateLevel: 3, horn: 1, doorSw: 0, gateCf: 1 });
    expect(created).toHaveLength(2); // a fresh client was created for the retry
  });

  test('reuses the same client across successful reads', async () => {
    const created: FakeClient[] = [];
    const transport = new ModbusSerialTransport(cfg, () => {
      const client = makeFakeClient({});
      created.push(client);
      return client;
    });

    await transport.readAll();
    await transport.readAll();
    expect(created).toHaveLength(1);
  });

  test('a hanging connect is bounded by the connect timeout', async () => {
    const created: FakeClient[] = [];
    const transport = new ModbusSerialTransport({ ...cfg, timeoutMs: 50 }, () => {
      const client = makeFakeClient({ hangConnect: true });
      created.push(client);
      return client;
    });

    await expect(transport.readAll()).rejects.toThrow('Modbus connect timeout');
    expect(created[0]?.closed).toBe(true);
    expect(created[0]?.destroyed).toBe(true);
  });
});
