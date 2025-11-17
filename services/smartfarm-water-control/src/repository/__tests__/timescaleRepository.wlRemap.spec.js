const { TimescaleRepository } = require('../timescaleRepository');

describe('WL remap helpers in TimescaleRepository', () => {
  test('getLatestWLGpsPerSensor returns latest rows per sensor', async () => {
    const calls = [];
    const pool = { query: jest.fn(async (sql, params) => { calls.push({ sql, params }); return { rows: [ { sensor_id: 'AWD-1234', location_lat: 14.49, location_lng: 102.15, time: new Date().toISOString() } ] }; }) };
    const repo = new TimescaleRepository(pool, { control: 'water_control_smartfarm', planning: 'ros_gis_smartfarm' });

    const rows = await repo.getLatestWLGpsPerSensor({ maxSensors: 50 });
    expect(Array.isArray(rows)).toBe(true);
    expect(rows[0]).toHaveProperty('sensor_id', 'AWD-1234');
    expect(calls[0].sql).toMatch(/DISTINCT ON \(sensor_id\)/i);
    expect(calls[0].sql).toMatch(/WHERE location_lat IS NOT NULL AND location_lng IS NOT NULL/i);
    expect(calls[0].params).toEqual([50]);
  });

  test('findPlotByCoordinates returns plot_id via ST_Contains', async () => {
    const pool = { query: jest.fn().mockResolvedValue({ rows: [ { plot_id: 'SF-L2' } ] }) };
    const repo = new TimescaleRepository(pool, { control: 'water_control_smartfarm', planning: 'ros_gis_smartfarm' });
    const plotId = await repo.findPlotByCoordinates(pool, 102.15, 14.49);
    expect(plotId).toBe('SF-L2');
  });

  test('upsertWLSensorMapping calls mapping upsert with sensor_type water_level', async () => {
    const calls = [];
    const pool = { query: jest.fn(async (sql, params) => { calls.push({ sql, params }); return { rows: [ { plot_id: 'SF-L2' } ] }; }) };
    const repo = new TimescaleRepository(pool, { control: 'water_control_smartfarm', planning: 'ros_gis_smartfarm' });
    await repo.upsertWLSensorMapping({ sensorId: 'AWD-1234', plotId: 'SF-L2' });
    expect(calls[0].sql).toMatch(/INSERT INTO\s+water_control_smartfarm\.sensor_plot_mapping/i);
    expect(calls[0].sql).toMatch(/ON CONFLICT/i);
  });

  test('deleteLegacyWLSfMappings deletes WL_SF% only', async () => {
    const calls = [];
    const pool = { query: jest.fn(async (sql) => { calls.push({ sql }); return { rowCount: 6 }; }) };
    const repo = new TimescaleRepository(pool, { control: 'water_control_smartfarm', planning: 'ros_gis_smartfarm' });
    const n = await repo.deleteLegacyWLSfMappings();
    expect(calls[0].sql).toMatch(/DELETE FROM\s+water_control_smartfarm\.sensor_plot_mapping\s+WHERE sensor_id LIKE 'WL_SF%'/i);
    expect(n).toBe(6);
  });
});