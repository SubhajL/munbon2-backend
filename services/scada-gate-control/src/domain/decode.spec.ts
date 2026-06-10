import { describe, expect, test } from 'vitest';
import {
  decodeDoorSw,
  decodeGateCf,
  decodeGateLevel,
  decodeHorn,
  type DecodeResult,
} from './decode';

describe('decodeGateLevel', () => {
  test('decodes an in-range value into its full level info', () => {
    expect(decodeGateLevel(2)).toEqual({
      ok: true,
      value: { level: 2, thaiLabel: 'เปิดระดับ 1', technicalLabel: 'Level 2', flowRate: 0.5 },
    });
  });

  test.each([0, 5, -1, 1.5, Number.NaN, 0xff00])(
    'reports decode_error for out-of-range raw %p',
    (raw) => {
      expect(decodeGateLevel(raw)).toEqual({
        ok: false,
        error: `Gate_Level out of range 1..4: ${raw}`,
      });
    },
  );
});

describe('decodeDoorSw', () => {
  test('raw 1 means closed (ปิด) per spec', () => {
    expect(decodeDoorSw(1)).toEqual({
      ok: true,
      value: { raw: 1, closed: true, thaiLabel: 'ปิด' },
    });
  });

  test('raw 0 means open (เปิด) per spec', () => {
    expect(decodeDoorSw(0)).toEqual({
      ok: true,
      value: { raw: 0, closed: false, thaiLabel: 'เปิด' },
    });
  });

  test('pins the exact decode_error message for a non-bit raw', () => {
    expect(decodeDoorSw(2)).toEqual({ ok: false, error: 'expected coil value 0 or 1, got 2' });
  });
});

describe('decodeHorn', () => {
  test('raw 1 means siren on (เปิด) per spec', () => {
    expect(decodeHorn(1)).toEqual({ ok: true, value: { raw: 1, on: true, thaiLabel: 'เปิด' } });
  });

  test('raw 0 means siren off (ปิด) per spec', () => {
    expect(decodeHorn(0)).toEqual({ ok: true, value: { raw: 0, on: false, thaiLabel: 'ปิด' } });
  });
});

describe('decodeGateCf', () => {
  test('raw 1 means command confirmed', () => {
    expect(decodeGateCf(1)).toEqual({ ok: true, value: { raw: 1, confirmed: true } });
  });

  test('raw 0 means not confirmed', () => {
    expect(decodeGateCf(0)).toEqual({ ok: true, value: { raw: 0, confirmed: false } });
  });
});

describe('boolean decoders reject any non-bit raw value', () => {
  const decoders: ReadonlyArray<[string, (raw: number) => DecodeResult<unknown>]> = [
    ['decodeDoorSw', decodeDoorSw],
    ['decodeHorn', decodeHorn],
    ['decodeGateCf', decodeGateCf],
  ];
  const invalidRaws = [2, -1, 0.5, Number.NaN, 0xff00];

  for (const [name, decode] of decoders) {
    test.each(invalidRaws)(`${name} rejects raw %p as decode_error`, (raw) => {
      expect(decode(raw).ok).toBe(false);
    });
  }
});
