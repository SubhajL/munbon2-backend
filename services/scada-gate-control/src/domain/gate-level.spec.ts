import { describe, expect, test } from 'vitest';
import { GATE_LEVEL_VALUES, gateLevelInfo, isGateLevel, type GateLevel } from './gate-level';

describe('gateLevelInfo', () => {
  // Oracle table copied from the spec, independent of the implementation map.
  const expected: Record<
    GateLevel,
    { thaiLabel: string; technicalLabel: string; flowRate: number }
  > = {
    1: { thaiLabel: 'ปิด', technicalLabel: 'Level 1 / Closed', flowRate: 0.0 },
    2: { thaiLabel: 'เปิดระดับ 1', technicalLabel: 'Level 2', flowRate: 0.5 },
    3: { thaiLabel: 'เปิดระดับ 2', technicalLabel: 'Level 3', flowRate: 0.8 },
    4: { thaiLabel: 'เปิด 100%', technicalLabel: 'Level 4 / Fully Open', flowRate: 1.0 },
  };

  // Enumerate from a literal spec oracle so coverage cannot shrink if the
  // implementation's GATE_LEVEL_VALUES is mistakenly narrowed.
  test.each([1, 2, 3, 4] as const)('level %i maps to its spec label and flow rate', (level) => {
    expect(gateLevelInfo(level)).toEqual({ level, ...expected[level] });
  });
});

describe('GATE_LEVEL_VALUES', () => {
  test('lists exactly the four spec levels in order', () => {
    expect(GATE_LEVEL_VALUES).toEqual([1, 2, 3, 4]);
  });
});

describe('isGateLevel', () => {
  test.each([1, 2, 3, 4])('accepts in-range raw value %i', (value) => {
    expect(isGateLevel(value)).toBe(true);
  });

  test.each([0, 5, -1, 1.5, Number.NaN])('rejects out-of-range value %p', (value) => {
    expect(isGateLevel(value)).toBe(false);
  });
});
