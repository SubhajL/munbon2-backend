/**
 * Translates an operator intent into the concrete Modbus writes required by the
 * spec's "Control Behavior" section. Pure: produces a plan, performs no I/O.
 */
import type { GateLevel } from './gate-level';
import { REGISTERS, type PointName } from './registers';

export type CoilValue = 0 | 1;

export type ModbusWrite =
  | {
      readonly kind: 'writeHoldingRegister';
      readonly point: PointName;
      readonly address: number;
      readonly value: number;
    }
  | {
      readonly kind: 'writeCoil';
      readonly point: PointName;
      readonly address: number;
      readonly value: CoilValue;
    };

/**
 * Gate command: Write Holding Register 108 = targetValue, then Write Coil 17 = 1.
 * Order is significant — the target is staged before the confirmation bit.
 * No GateCF reset is required; the PLC handles confirmation behaviour (spec).
 */
export function buildGateLevelCommand(target: GateLevel): ModbusWrite[] {
  return [
    {
      kind: 'writeHoldingRegister',
      point: 'Op_gate',
      address: REGISTERS.Op_gate.address,
      value: target,
    },
    { kind: 'writeCoil', point: 'GateCF', address: REGISTERS.GateCF.address, value: 1 },
  ];
}

/** Siren command: Write Coil 15 = 1 (เปิดไซเรน) or 0 (ปิดไซเรน). No confirmation bit. */
export function buildHornCommand(enabled: boolean): ModbusWrite[] {
  return [
    { kind: 'writeCoil', point: 'Horn', address: REGISTERS.Horn.address, value: enabled ? 1 : 0 },
  ];
}
