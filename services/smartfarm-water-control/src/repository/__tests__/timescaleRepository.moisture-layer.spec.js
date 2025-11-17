const { TimescaleRepository, moistureColumnForLayer } = require('../timescaleRepository');

describe('TimescaleRepository moisture layer selection', () => {
  test('moistureColumnForLayer returns correct column', () => {
    expect(moistureColumnForLayer('surface')).toBe('moisture_surface_pct');
    expect(moistureColumnForLayer('deep')).toBe('moisture_deep_pct');
  });

  test('getControlThresholds returns moistureLayer from DB', async () => {
    const repo = new TimescaleRepository({ query: jest.fn() });
    const fakeDb = {
      query: jest.fn().mockResolvedValue({
        rows: [
          {
            plot_id: 'P001',
            moisture_lower_threshold: 10,
            moisture_upper_threshold: 15,
            water_level_lower_threshold: 5,
            water_level_upper_threshold: 12,
            moisture_layer: 'deep'
          }
        ]
      })
    };

    const t = await repo.getControlThresholds(fakeDb, 'P001');
    expect(fakeDb.query).toHaveBeenCalled();
    expect(t.moistureLayer).toBe('deep');
  });

  test('getLatestMoistureReading uses selected layer column', async () => {
    const pool = { query: jest.fn().mockResolvedValue({ rows: [{
      sensor_id: '0001-0001',
      value: 42.5,
      time: new Date(),
      location_lat: 14.1,
      location_lng: 100.2
    }] }) };
    const repo = new TimescaleRepository(pool);

    await repo.getLatestMoistureReading('0001-0001', 'deep');

    const lastQuery = pool.query.mock.calls[0][0];
    expect(lastQuery).toMatch(/moisture_deep_pct\s+as\s+value/);
  });

  test('getFreshSensorReadingsForPlot uses deep column when layer=deep', async () => {
    const db = {
      query: jest.fn()
        // First call: mappingQuery
        .mockResolvedValueOnce({ rows: [{ sensor_id: '0001-0001' }] })
        // Second call: readingsQuery
        .mockResolvedValueOnce({ rows: [{ sensor_id: '0001-0001', value: 55.0, timestamp: new Date() }] })
    };
    const repo = new TimescaleRepository({ query: jest.fn() });

    const rows = await repo.getFreshSensorReadingsForPlot(db, { plotId: 'P001', sensorType: 'moisture', moistureLayer: 'deep' });

    const secondQuery = db.query.mock.calls[1][0];
    expect(secondQuery).toMatch(/moisture_deep_pct\s+as\s+value/);
    expect(rows[0].value).toBe(55.0);
  });
});