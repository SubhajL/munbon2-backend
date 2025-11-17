const { TimescaleRepository } = require('../timescaleRepository');

describe('TimescaleRepository.getPersistentlyZeroMoistureSensors', () => {
  test('filters by window and epsilon; returns sensor ids', async () => {
    const calls = [];
    const pool = { query: jest.fn(async (sql, params) => { calls.push({ sql, params }); return { rows: [{ sensor_id: '00000007' }, { sensor_id: '00000008' }] }; }) };
    const repo = new TimescaleRepository(pool, { control: 'water_control_smartfarm', planning: 'ros_gis_smartfarm' });

    const result = await repo.getPersistentlyZeroMoistureSensors({ days: 7, epsilon: 1.0 });

    expect(Array.isArray(result)).toBe(true);
    expect(result).toEqual(['00000007', '00000008']);
    expect(calls[0].sql).toMatch(/FROM\s+moisture_readings/i);
    expect(calls[0].sql).toMatch(/moisture_surface_pct/i);
expect(calls[0].sql).toMatch(/max_value <= \$1/i);
expect(calls[0].params).toEqual([1.0]);
  });
});

describe('TimescaleRepository.deactivateSensorsTx', () => {
  test('inserts into deactivated_sensors and deletes from mapping in one tx', async () => {
    const calls = [];
    const pool = { query: jest.fn(async (sql, params) => { calls.push({ sql, params }); return { rowCount: 2, rows: [] }; }) };
    const repo = new TimescaleRepository(pool, { control: 'water_control_smartfarm', planning: 'ros_gis_smartfarm' });

    const res = await repo.deactivateSensorsTx({ sensorIds: ['00000007', '00000008'], reason: 'persistently_zero', performedBy: 'maintenance' });

    expect(calls[0].sql).toMatch(/BEGIN/i);
    expect(calls[1].sql).toMatch(/INSERT INTO\s+water_control_smartfarm\.deactivated_sensors/i);
    expect(calls[2].sql).toMatch(/DELETE FROM\s+water_control_smartfarm\.sensor_plot_mapping/i);
    expect(calls[calls.length - 1].sql).toMatch(/COMMIT/i);
    expect(res).toEqual({ deactivated: 2, removed: 2 });
  });
});