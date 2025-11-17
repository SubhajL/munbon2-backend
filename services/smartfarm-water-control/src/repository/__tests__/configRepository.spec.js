const { describe, it, expect, beforeEach } = require('@jest/globals');

// Import after mocking
let ConfigRepository;

// Minimal fake logger to avoid requiring real logger
const logger = { info: jest.fn(), warn: jest.fn(), error: jest.fn() };

describe('ConfigRepository (unit)', () => {
  let pool;

  beforeEach(() => {
    // Fresh mock pool for every test
    pool = { query: jest.fn().mockResolvedValue({ rows: [], rowCount: 1 }) };
    jest.isolateModules(() => {
      ConfigRepository = require('../configRepository');
    });
  });

  it('upsertPlotBoundary issues correct SQL and params', async () => {
    const repo = new ConfigRepository({ pool, logger, schemas: { smartfarm: 'ros_gis_smartfarm', control: 'water_control_smartfarm' } });

    await repo.upsertPlotBoundary({
      plotId: 'test-plot-001',
      plotName: 'Smart Farm Plot 1',
      areaRai: 2.51,
      geojson: { type: 'Polygon', coordinates: [[[102.1, 14.49],[102.11,14.49],[102.11,14.5],[102.1,14.5],[102.1,14.49]]] }
    });

    expect(pool.query).toHaveBeenCalledTimes(1);
    const [sql, params] = pool.query.mock.calls[0];
    expect(sql).toMatch(/INSERT INTO ros_gis_smartfarm\.plot_boundaries/i);
    expect(params[0]).toBe('test-plot-001');
    expect(params[1]).toBe('Smart Farm Plot 1');
    expect(params[2]).toBe(2.51);
    expect(typeof params[3]).toBe('string'); // GeoJSON stringified
  });

  it('upsertDevice rejects unknown deviceType', async () => {
    const repo = new ConfigRepository({ pool, logger, schemas: { smartfarm: 'ros_gis_smartfarm', control: 'water_control_smartfarm' } });

    await expect(repo.upsertDevice({
      deviceName: 'X-1',
      deviceType: 'unknown',
      zone: 'upper',
      metadata: { a: 1 }
    })).rejects.toThrow(/deviceType/i);
  });

  it('upsertPlotConfiguration rejects invalid controlMode', async () => {
    const repo = new ConfigRepository({ pool, logger, schemas: { smartfarm: 'ros_gis_smartfarm', control: 'water_control_smartfarm' } });

    await expect(repo.upsertPlotConfiguration({
      plotId: 'p1', cropType: 'rice', controlMode: 'BAD', valveId: 'SV-U1', flowmeterId: 'F-U1', areaRai: 2.0
    })).rejects.toThrow(/controlMode/i);
  });

  it('upsertSensorMapping uses expected unique key', async () => {
    const repo = new ConfigRepository({ pool, logger, schemas: { smartfarm: 'ros_gis_smartfarm', control: 'water_control_smartfarm' } });

    await repo.upsertSensorMapping({ sensorId: '00000007', plotId: 'plot-1', sensorType: 'moisture' });
    const [sql] = pool.query.mock.calls[0];
    expect(sql).toMatch(/INSERT INTO water_control_smartfarm\.sensor_plot_mapping/i);
    expect(sql).toMatch(/ON CONFLICT \(sensor_id\)/i);
  });

  it('upsertSensorLocation links to plot when provided', async () => {
    const repo = new ConfigRepository({ pool, logger, schemas: { smartfarm: 'ros_gis_smartfarm', control: 'water_control_smartfarm' } });

    await repo.upsertSensorLocation({
      deviceId: '00000007',
      deviceName: 'H-P1-00000007',
      deviceType: 'moisture_sensor',
      lng: 102.149018, lat: 14.49563,
      plotId: 'fbd7920c-1a05-487c-a79e-a4003ab30be9'
    });

    const [sql, params] = pool.query.mock.calls[0];
    expect(sql).toMatch(/INSERT INTO ros_gis_smartfarm\.sensor_locations/i);
    expect(params).toEqual([
      '00000007', 'H-P1-00000007', 'moisture_sensor', 102.149018, 14.49563, 'fbd7920c-1a05-487c-a79e-a4003ab30be9'
    ]);
  });
});