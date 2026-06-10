import { describe, expect, test } from 'vitest';
import {
  confirmBody,
  confirmTechnical,
  currentLevelInfo,
  sensorActionLabel,
} from './control';
import type { GateLevel } from './api';

describe('sensorActionLabel', () => {
  test.each<[GateLevel, string]>([
    [1, 'ปิดประตูน้ำ อัตราไหลน้ำ = 0.0 ลบ.ม./วินาที'],
    [2, 'เปิดประตูน้ำที่ระดับ 1 อัตราไหลน้ำ = 0.5 ลบ.ม./วินาที'],
    [3, 'เปิดประตูน้ำที่ระดับ 2 อัตราไหลน้ำ = 0.8 ลบ.ม./วินาที'],
    [4, 'เปิดประตูน้ำ 100% อัตราไหลน้ำ = 1.0 ลบ.ม./วินาที'],
  ])('level %i action label', (level, expected) => {
    expect(sensorActionLabel(level)).toBe(expected);
  });
});

describe('currentLevelInfo', () => {
  test('describes the current open level and flow', () => {
    expect(currentLevelInfo(2)).toBe('ระดับประตูน้ำปัจจุบัน: เปิดระดับ 1 อัตราไหลน้ำ = 0.5 ลบ.ม./วินาที');
  });
});

describe('confirmBody', () => {
  test('names the gate and the target level', () => {
    expect(confirmBody('Waste Way', 3)).toBe('ต้องการสั่ง Waste Way ไปที่ เปิดระดับ 2 ใช่หรือไม่?');
  });
});

describe('confirmTechnical', () => {
  test('shows the Op_gate register value and the GateCF confirmation bit', () => {
    expect(confirmTechnical(4)).toEqual({
      opGate: 'Op_gate Address 108 = 4',
      gateCf: 'GateCF Address 17 = 1',
    });
  });
});
