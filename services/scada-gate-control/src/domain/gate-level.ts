/**
 * Gate level mapping from RID_MUNBON_SCADA_APP_SPEC.md.
 * Levels are the raw holding-register values 1..4.
 */

export type GateLevel = 1 | 2 | 3 | 4;

export type GateLevelInfo = {
  readonly level: GateLevel;
  /** Thai label shown to operators, e.g. "ปิด". */
  readonly thaiLabel: string;
  /** English technical label, e.g. "Level 1 / Closed". */
  readonly technicalLabel: string;
  /** Flow rate in ลบ.ม./วินาที (cubic metres per second). */
  readonly flowRate: number;
};

export const GATE_LEVELS = {
  1: { level: 1, thaiLabel: 'ปิด', technicalLabel: 'Level 1 / Closed', flowRate: 0.0 },
  2: { level: 2, thaiLabel: 'เปิดระดับ 1', technicalLabel: 'Level 2', flowRate: 0.5 },
  3: { level: 3, thaiLabel: 'เปิดระดับ 2', technicalLabel: 'Level 3', flowRate: 0.8 },
  4: { level: 4, thaiLabel: 'เปิด 100%', technicalLabel: 'Level 4 / Fully Open', flowRate: 1.0 },
} as const satisfies Record<GateLevel, GateLevelInfo>;

export const GATE_LEVEL_VALUES: readonly GateLevel[] = [1, 2, 3, 4];

export function isGateLevel(value: number): value is GateLevel {
  return value === 1 || value === 2 || value === 3 || value === 4;
}

export function gateLevelInfo(level: GateLevel): GateLevelInfo {
  return GATE_LEVELS[level];
}
