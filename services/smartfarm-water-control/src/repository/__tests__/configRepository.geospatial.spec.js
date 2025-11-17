const ConfigRepository = require('../configRepository');

describe('ConfigRepository geospatial and mapping helpers', () => {
  test('returns plot id when point inside polygon', async () => {
    const mockRows = [{ plot_id: 'SF-U3' }];
    const pool = { query: jest.fn().mockResolvedValue({ rows: mockRows }) };
    const repo = new ConfigRepository({ pool, schemas: { smartfarm: 'ros_gis_smartfarm', control: 'water_control_smartfarm' } });

    const plot = await repo.findPlotByCoordinates(pool, 102.14915, 14.49570);

    expect(pool.query).toHaveBeenCalledWith(expect.stringContaining('ST_SetSRID'), [102.14915, 14.4957]);
    expect(plot).toBe('SF-U3');
  });

  test('returns null when outside all plots', async () => {
    const pool = { query: jest.fn().mockResolvedValue({ rows: [] }) };
    const repo = new ConfigRepository({ pool, schemas: { smartfarm: 'ros_gis_smartfarm', control: 'water_control_smartfarm' } });

    const plot = await repo.findPlotByCoordinates(pool, 0.0, 0.0);

    expect(plot).toBeNull();
  });
  test('listMappedSensorsForPlot returns ids for plot', async () => {
    const rows = [{ sensor_id: '00000001' }, { sensor_id: '00000002' }];
    const pool = { query: jest.fn().mockResolvedValue({ rows }) };
    const repo = new ConfigRepository({ pool, schemas: { smartfarm: 'ros_gis_smartfarm', control: 'water_control_smartfarm' } });

    const ids = await repo.listMappedSensorsForPlot('SF-U1', 'moisture');
    expect(ids).toEqual(['00000001', '00000002']);
  });
});
