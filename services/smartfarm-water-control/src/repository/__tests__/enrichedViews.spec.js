const { TimescaleRepository } = require('../timescaleRepository');

describe('TimescaleRepository enriched views', () => {
  function makeRepo() {
    const pool = { query: jest.fn() };
    const repo = new TimescaleRepository(pool, { planning: 'ros_gis_smartfarm', control: 'water_control_smartfarm' });
    return { repo, pool };
  }

  test('getEnrichedPlotConfigurations queries v_plot_configurations_enriched', async () => {
    const { repo, pool } = makeRepo();
    pool.query.mockResolvedValueOnce({ rows: [{ plot_id: 'P1' }] });
    const rows = await repo.getEnrichedPlotConfigurations(pool);
    expect(rows).toEqual([{ plot_id: 'P1' }]);
    const calledSql = pool.query.mock.calls[0][0];
    expect(calledSql).toEqual(expect.stringContaining('v_plot_configurations_enriched'));
  });

  test('getEnrichedSensorMappings queries v_sensor_plot_mapping_enriched', async () => {
    const { repo, pool } = makeRepo();
    pool.query.mockResolvedValueOnce({ rows: [{ plot_id: 'P1', sensor_type: 'moisture', sensor_id: 'MS-1' }] });
    const rows = await repo.getEnrichedSensorMappings(pool);
    expect(rows[0].sensor_id).toBe('MS-1');
    const calledSql = pool.query.mock.calls[0][0];
    expect(calledSql).toEqual(expect.stringContaining('v_sensor_plot_mapping_enriched'));
  });
});