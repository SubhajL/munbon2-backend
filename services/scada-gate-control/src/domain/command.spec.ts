import { describe, expect, test } from 'vitest';
import { buildGateLevelCommand, buildHornCommand } from './command';
import type { GateLevel } from './gate-level';

describe('buildGateLevelCommand', () => {
  // Oracle from the spec's worked examples table (Op_gate 108, GateCF 17 = 1).
  test.each<[GateLevel]>([[1], [2], [3], [4]])(
    'level %i stages HR108=value then sets coil17=1',
    (target) => {
      expect(buildGateLevelCommand(target)).toEqual([
        { kind: 'writeHoldingRegister', point: 'Op_gate', address: 108, value: target },
        { kind: 'writeCoil', point: 'GateCF', address: 17, value: 1 },
      ]);
    },
  );

  test('writes the target register before the confirmation coil', () => {
    const [first, second] = buildGateLevelCommand(3);
    expect([first?.point, second?.point]).toEqual(['Op_gate', 'GateCF']);
  });
});

describe('buildHornCommand', () => {
  test('enabled writes coil15=1 (เปิดไซเรน)', () => {
    expect(buildHornCommand(true)).toEqual([
      { kind: 'writeCoil', point: 'Horn', address: 15, value: 1 },
    ]);
  });

  test('disabled writes coil15=0 (ปิดไซเรน) and needs no confirmation coil', () => {
    expect(buildHornCommand(false)).toEqual([
      { kind: 'writeCoil', point: 'Horn', address: 15, value: 0 },
    ]);
  });
});
