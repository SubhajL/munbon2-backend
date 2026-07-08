/**
 * In-process Modbus TCP simulator built on `modbus-serial`'s ServerTCP. It is a
 * real Modbus server (real protocol on a real socket) with controllable
 * register/coil state — used by integration tests and for local development
 * when the field PLC is not reachable. It is NOT mock data: the transport under
 * test speaks genuine Modbus to it.
 */
import { createServer } from 'net';
import { ServerTCP, type IServiceVector } from 'modbus-serial';

export type SimulatorWrite = {
  readonly kind: 'coil' | 'register';
  readonly address: number;
  readonly value: number | boolean;
};

export type SimulatorState = {
  readonly holdingRegisters: Map<number, number>;
  readonly coils: Map<number, boolean>;
  readonly writes: SimulatorWrite[];
};

export type Simulator = {
  readonly state: SimulatorState;
  readonly port: number;
  readonly close: () => Promise<void>;
};

export type SimulatorInit = {
  readonly holdingRegisters?: Record<number, number>;
  readonly coils?: Record<number, boolean>;
  readonly unitId?: number;
  readonly host?: string;
  readonly port?: number;
};

const MAX_BIND_ATTEMPTS = 5;

/** Ask the OS for an unused TCP port on `host`. */
export function freePort(host: string): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.once('error', reject);
    server.listen(0, host, () => {
      const address = server.address();
      if (address && typeof address === 'object') {
        const { port } = address;
        server.close(() => resolve(port));
      } else {
        server.close(() => reject(new Error('could not allocate a free port')));
      }
    });
  });
}

function toMap<T>(record: Record<number, T> | undefined): Map<number, T> {
  return new Map(Object.entries(record ?? {}).map(([key, value]) => [Number(key), value]));
}

function isAddrInUse(error: unknown): boolean {
  return (error as { code?: string } | null)?.code === 'EADDRINUSE';
}

function bindServer(
  vector: IServiceVector,
  host: string,
  port: number,
  unitId: number,
): Promise<ServerTCP> {
  return new Promise<ServerTCP>((resolve, reject) => {
    const server = new ServerTCP(vector, { host, port, unitID: unitId });
    server.on('initialized', () => resolve(server));
    server.on('serverError', (error) => reject(error));
  });
}

export async function startSimulator(init: SimulatorInit = {}): Promise<Simulator> {
  const host = init.host ?? '127.0.0.1';
  const unitId = init.unitId ?? 1;
  const state: SimulatorState = {
    holdingRegisters: toMap(init.holdingRegisters),
    coils: toMap(init.coils),
    writes: [],
  };

  const vector: IServiceVector = {
    getHoldingRegister: (addr: number): number => state.holdingRegisters.get(addr) ?? 0,
    getCoil: (addr: number): boolean => state.coils.get(addr) ?? false,
    setRegister: (addr: number, value: number): void => {
      state.holdingRegisters.set(addr, value);
      state.writes.push({ kind: 'register', address: addr, value });
    },
    setCoil: (addr: number, value: boolean): void => {
      state.coils.set(addr, value);
      state.writes.push({ kind: 'coil', address: addr, value });
    },
  };

  // Retry on EADDRINUSE to absorb the freePort check-then-bind race. If the
  // caller pinned an explicit port, respect it without retrying.
  const attempts = init.port !== undefined ? 1 : MAX_BIND_ATTEMPTS;
  let lastError: unknown;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const port = init.port ?? (await freePort(host));
    try {
      const server = await bindServer(vector, host, port, unitId);
      return {
        state,
        port,
        close: () => new Promise<void>((resolve) => server.close(() => resolve())),
      };
    } catch (error) {
      lastError = error;
      if (!isAddrInUse(error)) throw error;
    }
  }
  throw lastError ?? new Error('could not start Modbus simulator');
}
