const { parseNumeric, sanitizeMoistureSensor, parseBody, buildMoistureInsert, formatMoistureSensorId, toVoltage } = require('../moisture-parse');

describe('moisture-parse utilities', () => {
  describe('parseNumeric', () => {
    test('keeps zero as 0 (string and number)', () => {
      expect(parseNumeric('0', 0, 100)).toBe(0);
      expect(parseNumeric(0, 0, 100)).toBe(0);
    });

    test('returns null for blank or non-numeric', () => {
      expect(parseNumeric('', 0, 100)).toBeNull();
      expect(parseNumeric(null, 0, 100)).toBeNull();
      expect(parseNumeric(undefined, 0, 100)).toBeNull();
      expect(parseNumeric('abc', 0, 100)).toBeNull();
    });

    test('rejects out-of-range values', () => {
      expect(parseNumeric(-1, 0, 100)).toBeNull();
      expect(parseNumeric(101, 0, 100)).toBeNull();
    });
  });

  describe('sanitizeMoistureSensor', () => {
    test('maps fields and preserves zero', () => {
      const s = sanitizeMoistureSensor({ humid_hi: '0', humid_low: '0', temp_hi: '0', temp_low: '0', amb_humid: '0', amb_temp: '0', sensor_batt: '400', flood: 'no' });
      expect(s.moistureSurfacePct).toBe(0);
      expect(s.moistureDeepPct).toBe(0);
      expect(s.tempSurfaceC).toBe(0);
      expect(s.tempDeepC).toBe(0);
      expect(s.ambientHumidityPct).toBe(0);
      expect(s.ambientTempC).toBe(0);
      expect(s.voltage).toBeCloseTo(4.0, 3);
      expect(s.floodStatus).toBe(false);
    });

    test('invalid humidity gets clamped to [0,100]', () => {
      const s = sanitizeMoistureSensor({ humid_hi: '102', humid_low: '-1', amb_humid: '150' });
      expect(s.moistureSurfacePct).toBe(100);
      expect(s.moistureDeepPct).toBe(0);
      expect(s.ambientHumidityPct).toBe(100);
    });
  });

  describe('formatMoistureSensorId', () => {
    test('pads gateway and sensor ids', () => {
      const { formatMoistureSensorId } = require('../moisture-parse');
      expect(formatMoistureSensorId('1', '7')).toBe('0001-0007');
    });
  });

  describe('buildMoistureInsert', () => {
    test('produces ordered values for INSERT', () => {
      const { buildMoistureInsert } = require('../moisture-parse');
      const ts = new Date();
      const { sensorId, values } = buildMoistureInsert('1', { sensor_id: '7', humid_hi: '66', humid_low: '44', sensor_batt: '404', flood: 'yes' }, { lat: '14.1', lng: '100.2' }, ts);
      expect(sensorId).toBe('0001-0007');
      expect(values[0]).toBeInstanceOf(Date);
      expect(values[1]).toBe('0001-0007');
      expect(values[4]).toBe(66);
      expect(values[5]).toBe(44);
      expect(values[10]).toBeCloseTo(4.04, 3);
      expect(values[11]).toBe(true);
    });
  });
});
