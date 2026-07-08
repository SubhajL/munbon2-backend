/**
 * Transport contract between the poll loop and whatever talks Modbus.
 * The poller depends on this interface, not on modbus-serial, so it can be
 * driven by a fake in unit tests and by the real device in production.
 */

/** Raw values read from the four polled points (coils as 0/1). */
export type PointReads = {
  readonly gateLevel: number;
  readonly doorSw: number;
  readonly horn: number;
  readonly gateCf: number;
};

export interface ModbusTransport {
  connect(): Promise<void>;
  readAll(): Promise<PointReads>;
  writeHoldingRegister(address: number, value: number): Promise<void>;
  writeCoil(address: number, value: boolean): Promise<void>;
  close(): Promise<void>;
}

/** Outcome of a single poll attempt. */
export type PollResult =
  | { readonly ok: true; readonly atMs: number; readonly reads: PointReads }
  | {
      readonly ok: false;
      readonly atMs: number;
      readonly quality: 'modbus_exception' | 'offline';
      readonly error: string;
    };
