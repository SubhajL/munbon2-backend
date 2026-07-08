import { describe, expect, test } from 'vitest';
import { DEFAULT_UNIT_ID, REGISTERS } from './registers';

describe('REGISTERS', () => {
  test('maps every spec point to its address and Modbus kind with no offset', () => {
    expect(REGISTERS).toEqual({
      Gate_Level: { name: 'Gate_Level', address: 104, kind: 'holdingRegister' },
      Door_SW: { name: 'Door_SW', address: 16, kind: 'coil' },
      Horn: { name: 'Horn', address: 15, kind: 'coil' },
      Op_gate: { name: 'Op_gate', address: 108, kind: 'holdingRegister' },
      GateCF: { name: 'GateCF', address: 17, kind: 'coil' },
    });
  });
});

describe('DEFAULT_UNIT_ID', () => {
  test('defaults to 1 until vendor confirms', () => {
    expect(DEFAULT_UNIT_ID).toBe(1);
  });
});
