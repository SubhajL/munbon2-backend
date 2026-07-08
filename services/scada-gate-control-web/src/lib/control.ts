/**
 * Pure builders for the gate-control UI text, transcribed from the spec's
 * "Screen 2 / Control Behavior" section. No React — fully unit-testable.
 */
import type { GateLevel } from "./api";

export type LevelMeta = {
  readonly level: GateLevel;
  readonly thaiLabel: string;
  readonly flowRate: number;
  /** Imperative phrasing used in the right-click action menu. */
  readonly actionLabel: string;
};

export const LEVELS: Record<GateLevel, LevelMeta> = {
  1: { level: 1, thaiLabel: "ปิด", flowRate: 0.0, actionLabel: "ปิดประตูน้ำ" },
  2: {
    level: 2,
    thaiLabel: "เปิดระดับ 1",
    flowRate: 0.5,
    actionLabel: "เปิดประตูน้ำที่ระดับ 1",
  },
  3: {
    level: 3,
    thaiLabel: "เปิดระดับ 2",
    flowRate: 0.8,
    actionLabel: "เปิดประตูน้ำที่ระดับ 2",
  },
  4: {
    level: 4,
    thaiLabel: "เปิด 100%",
    flowRate: 1.0,
    actionLabel: "เปิดประตูน้ำ 100%",
  },
};

export const LEVEL_VALUES: readonly GateLevel[] = [1, 2, 3, 4];

function flowPhrase(flowRate: number): string {
  return `อัตราไหลน้ำ = ${flowRate.toFixed(1)} ลบ.ม./วินาที`;
}

/** Right-click action label for an OFF sensor (level 1 closes, others open). */
export function sensorActionLabel(level: GateLevel): string {
  const meta = LEVELS[level];
  return `${meta.actionLabel} ${flowPhrase(meta.flowRate)}`;
}

/** Info popup text for the currently-ON sensor. */
export function currentLevelInfo(level: GateLevel): string {
  const meta = LEVELS[level];
  return `ระดับประตูน้ำปัจจุบัน: ${meta.thaiLabel} ${flowPhrase(meta.flowRate)}`;
}

/** Confirmation modal body: "ต้องการสั่ง <gate> ไปที่ <ระดับ> ใช่หรือไม่?" */
export function confirmBody(gateName: string, level: GateLevel): string {
  return `ต้องการสั่ง ${gateName} ไปที่ ${LEVELS[level].thaiLabel} ใช่หรือไม่?`;
}

/** Raw Modbus details shown in the confirmation modal. */
export function confirmTechnical(level: GateLevel): {
  opGate: string;
  gateCf: string;
} {
  return {
    opGate: `Op_gate Address 108 = ${level}`,
    gateCf: "GateCF Address 17 = 1",
  };
}
