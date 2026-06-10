/**
 * Pure decoders: raw Modbus values -> domain values, per the spec's
 * "Gate Level Mapping" and "Boolean Mapping" tables. A raw value that cannot
 * be interpreted yields a `decode_error` outcome rather than throwing, so the
 * poll loop can record it as a quality without crashing.
 */
import { gateLevelInfo, isGateLevel, type GateLevelInfo } from './gate-level';

export type DecodeOk<T> = { ok: true; value: T };
export type DecodeError = { ok: false; error: string };
export type DecodeResult<T> = DecodeOk<T> | DecodeError;

export type DoorState = {
  readonly raw: 0 | 1;
  /** Door_SW: 1 = ปิด (closed), 0 = เปิด (open). */
  readonly closed: boolean;
  readonly thaiLabel: 'ปิด' | 'เปิด';
};

export type HornState = {
  readonly raw: 0 | 1;
  /** Horn: 1 = เปิด (on), 0 = ปิด (off). */
  readonly on: boolean;
  readonly thaiLabel: 'เปิด' | 'ปิด';
};

export type GateCfState = {
  readonly raw: 0 | 1;
  /** GateCF: 1 = ยืนยันการสั่งงาน (command confirmed). */
  readonly confirmed: boolean;
};

function decodeBit(raw: number): DecodeResult<0 | 1> {
  if (raw === 0 || raw === 1) {
    return { ok: true, value: raw };
  }
  return { ok: false, error: `expected coil value 0 or 1, got ${raw}` };
}

export function decodeGateLevel(raw: number): DecodeResult<GateLevelInfo> {
  if (!isGateLevel(raw)) {
    return { ok: false, error: `Gate_Level out of range 1..4: ${raw}` };
  }
  return { ok: true, value: gateLevelInfo(raw) };
}

export function decodeDoorSw(raw: number): DecodeResult<DoorState> {
  const bit = decodeBit(raw);
  if (!bit.ok) return bit;
  const closed = bit.value === 1;
  return { ok: true, value: { raw: bit.value, closed, thaiLabel: closed ? 'ปิด' : 'เปิด' } };
}

export function decodeHorn(raw: number): DecodeResult<HornState> {
  const bit = decodeBit(raw);
  if (!bit.ok) return bit;
  const on = bit.value === 1;
  return { ok: true, value: { raw: bit.value, on, thaiLabel: on ? 'เปิด' : 'ปิด' } };
}

export function decodeGateCf(raw: number): DecodeResult<GateCfState> {
  const bit = decodeBit(raw);
  if (!bit.ok) return bit;
  return { ok: true, value: { raw: bit.value, confirmed: bit.value === 1 } };
}
