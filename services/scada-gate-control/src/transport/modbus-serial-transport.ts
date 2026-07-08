/**
 * Real Modbus TCP transport backed by `modbus-serial`. Maps the spec's points
 * onto Modbus function codes:
 *   - Gate_Level: read holding register 104 (0x03)
 *   - Horn(15)/Door_SW(16)/GateCF(17): one contiguous read-coils (0x01) at 15
 *   - Op_gate(108): write single register (0x06)
 *   - Horn(15)/GateCF(17): write single coil (0x05)
 * Addresses are used as-is (no -1 offset), per the spec.
 *
 * Socket lifecycle: the client is created lazily and DESTROYED on any failure,
 * so the next attempt reconnects with a fresh socket rather than reusing a
 * half-open port. A connect timeout bounds the wait so an unreachable device
 * surfaces as offline within `timeoutMs` instead of hanging on the OS TCP
 * timeout (~75s).
 */
import ModbusRTU from 'modbus-serial';
import { REGISTERS } from '../domain/registers';
import type { ModbusTransport, PointReads } from './types';

export type ModbusConnectionConfig = {
  readonly host: string;
  readonly port: number;
  readonly unitId: number;
  readonly timeoutMs: number;
};

/** The slice of modbus-serial's client we use. Seam for deterministic tests. */
export interface ModbusClientLike {
  connectTCP(host: string, options: { port: number }): Promise<void>;
  setID(id: number): void;
  setTimeout(ms: number): void;
  readHoldingRegisters(address: number, length: number): Promise<{ data: number[] }>;
  readCoils(address: number, length: number): Promise<{ data: boolean[] }>;
  writeRegister(address: number, value: number): Promise<unknown>;
  writeCoil(address: number, value: boolean): Promise<unknown>;
  close(callback: () => void): void;
}

export type ModbusClientFactory = () => ModbusClientLike;

const COIL_BLOCK_START = REGISTERS.Horn.address; // 15 -> [Horn(15), Door_SW(16), GateCF(17)]
const COIL_BLOCK_LENGTH = 3;

/** Pure: fold a holding-register read + coil-block read into the four points. */
export function mapPointReads(gateData: number[], coilData: boolean[]): PointReads {
  const gateLevel = gateData[0];
  if (gateLevel === undefined || coilData.length < COIL_BLOCK_LENGTH) {
    throw new Error('short Modbus read');
  }
  return {
    gateLevel,
    horn: coilData[0] ? 1 : 0,
    doorSw: coilData[1] ? 1 : 0,
    gateCf: coilData[2] ? 1 : 0,
  };
}

export class ModbusSerialTransport implements ModbusTransport {
  private client: ModbusClientLike | null = null;

  constructor(
    private readonly config: ModbusConnectionConfig,
    private readonly createClient: ModbusClientFactory = () => new ModbusRTU(),
  ) {}

  private async connectWithTimeout(client: ModbusClientLike): Promise<void> {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const timeout = new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new Error('Modbus connect timeout')), this.config.timeoutMs);
      timer.unref?.();
    });
    try {
      await Promise.race([
        client.connectTCP(this.config.host, { port: this.config.port }),
        timeout,
      ]);
    } finally {
      if (timer) clearTimeout(timer);
    }
  }

  private async ensureClient(): Promise<ModbusClientLike> {
    if (this.client) return this.client;
    const client = this.createClient();
    try {
      await this.connectWithTimeout(client);
    } catch (error) {
      await new Promise<void>((resolve) => client.close(() => resolve()));
      throw error;
    }
    client.setID(this.config.unitId);
    client.setTimeout(this.config.timeoutMs);
    this.client = client;
    return client;
  }

  private async destroy(): Promise<void> {
    const client = this.client;
    this.client = null;
    if (client) {
      await new Promise<void>((resolve) => client.close(() => resolve()));
    }
  }

  async connect(): Promise<void> {
    await this.ensureClient();
  }

  async readAll(): Promise<PointReads> {
    const client = await this.ensureClient();
    try {
      const gate = await client.readHoldingRegisters(REGISTERS.Gate_Level.address, 1);
      const coils = await client.readCoils(COIL_BLOCK_START, COIL_BLOCK_LENGTH);
      return mapPointReads(gate.data, coils.data);
    } catch (error) {
      await this.destroy(); // drop the socket so the next poll reconnects cleanly
      throw error;
    }
  }

  async writeHoldingRegister(address: number, value: number): Promise<void> {
    const client = await this.ensureClient();
    try {
      await client.writeRegister(address, value);
    } catch (error) {
      await this.destroy();
      throw error;
    }
  }

  async writeCoil(address: number, value: boolean): Promise<void> {
    const client = await this.ensureClient();
    try {
      await client.writeCoil(address, value);
    } catch (error) {
      await this.destroy();
      throw error;
    }
  }

  async close(): Promise<void> {
    await this.destroy();
  }
}
