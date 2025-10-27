const { SensorDataService } = require('../sensorDataService');

describe('SensorDataService.determineSensorType', () => {
  test('returns water_level for AWD/WL ids', () => {
    const svc = new SensorDataService({ timescaleRepository: {} });
    expect(svc.determineSensorType('AWD-01')).toBe('water_level');
    expect(svc.determineSensorType('WL-2')).toBe('water_level');
    expect(svc.determineSensorType('sensor_wl_3')).toBe('water_level');
  });

  test('returns moisture for typical moisture ids', () => {
    const svc = new SensorDataService({ timescaleRepository: {} });
    expect(svc.determineSensorType('MOIST-01')).toBe('moisture');
    expect(svc.determineSensorType('MS-33')).toBe('moisture');
    expect(svc.determineSensorType('H-P4')).toBe('moisture');
  });

  test('throws on unknown type', () => {
    const svc = new SensorDataService({ timescaleRepository: {} });
    expect(() => svc.determineSensorType('XYZ-UNKNOWN')).toThrow(/Unknown sensor type/);
  });
});