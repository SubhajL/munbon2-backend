const { TimescaleRepository } = require('../timescaleRepository');

describe('TimescaleRepository (internal planning readers)', () => {
  function makeRepo() {
    const pool = { query: jest.fn() };
    const repo = new TimescaleRepository(pool, { planning: 'ros_gis_smartfarm', control: 'water_control_smartfarm' });
    return { repo, pool };
  }

  test('getAreaRai reads from enriched view', async () => {
    const { repo, pool } = makeRepo();
    pool.query.mockResolvedValueOnce({ rows: [{ area_rai: 2.51 }] });
    const v = await repo.getAreaRai('PLOT-1');
    expect(pool.query).toHaveBeenCalledWith(
      expect.stringContaining('v_plot_configurations_enriched'),
      ['PLOT-1']
    );
    expect(v).toBe(2.51);
  });

  test('getPlantingDate reads plot_configurations', async () => {
    const { repo, pool } = makeRepo();
    const d = new Date('2025-06-01');
    pool.query.mockResolvedValueOnce({ rows: [{ planting_date: d }] });
    const v = await repo.getPlantingDate('PLOT-2');
    expect(pool.query).toHaveBeenCalledWith(
      expect.stringContaining('plot_configurations'),
      ['PLOT-2']
    );
    expect(v).toEqual(d);
  });

  test('getKcFromRosSmartfarm reads kc_weekly', async () => {
    const { repo, pool } = makeRepo();
    pool.query.mockResolvedValueOnce({ rows: [{ kc_value: 1.1 }] });
    const v = await repo.getKcFromRosSmartfarm('rice', 8);
    expect(pool.query).toHaveBeenCalledWith(
      expect.stringContaining('ros_smartfarm.kc_weekly'),
      ['rice', 8]
    );
    expect(v).toBe(1.1);
  });

  test('getEt0FromRosSmartfarm reads eto_weekly', async () => {
    const { repo, pool } = makeRepo();
    pool.query.mockResolvedValueOnce({ rows: [{ eto_value: 35.5 }] });
    const v = await repo.getEt0FromRosSmartfarm(25, 2025, 'นครราชสีมา', 'นครราชสีมา');
    expect(pool.query).toHaveBeenCalledWith(
      expect.stringContaining('ros_smartfarm.eto_weekly'),
      ['นครราชสีมา', 'นครราชสีมา', 25, 2025]
    );
    expect(v).toBe(35.5);
  });

  test('getEffectiveRainfallFromRosSmartfarm reads weekly_effective_rainfall', async () => {
    const { repo, pool } = makeRepo();
    pool.query.mockResolvedValueOnce({ rows: [{ effective_rainfall_mm: 12.3 }] });
    const v = await repo.getEffectiveRainfallFromRosSmartfarm(1, 25, 2025);
    expect(pool.query).toHaveBeenCalledWith(
      expect.stringContaining('ros_smartfarm.weekly_effective_rainfall'),
      [1, 25, 2025]
    );
    expect(v).toBe(12.3);
  });
});