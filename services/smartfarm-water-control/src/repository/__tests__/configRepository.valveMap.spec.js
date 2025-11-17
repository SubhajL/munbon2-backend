const ConfigRepository = require('../configRepository');

describe('ConfigRepository valve_plot_mapping DAO', () => {
  const schemas = { smartfarm: 'ros_gis_smartfarm', control: 'water_control_smartfarm' };

  test('upsertValvePlotMapping inserts then updates', async () => {
    const calls = [];
    const pool = { query: jest.fn(async (sql, params) => { calls.push({ sql, params }); return { rows: [{ plot_id: params[0], smartfarm_valve_name: params[1] }] }; }) };
    const repo = new ConfigRepository({ pool, schemas });

    await repo.upsertValvePlotMapping({ plotId: 'SF-U1', valveName: 'SV-U1', updatedBy: 'test', notes: 'seed' });
    await repo.upsertValvePlotMapping({ plotId: 'SF-U1', valveName: 'SV-U1X', updatedBy: 'test2', notes: 'update' });

    expect(pool.query).toHaveBeenCalled();
    const first = calls[0];
    expect(first.sql).toMatch(/INSERT INTO water_control_smartfarm\.valve_plot_mapping/i);
    const second = calls[1];
expect(second.sql).toMatch(/ON CONFLICT \(plot_id\)[\s\S]*DO UPDATE/i);
  });

  test('getValveForPlot returns valve or null', async () => {
    const pool = { query: jest.fn().mockResolvedValueOnce({ rows: [{ smartfarm_valve_name: 'SV-L2' }] }).mockResolvedValueOnce({ rows: [] }) };
    const repo = new ConfigRepository({ pool, schemas });

    await expect(repo.getValveForPlot('SF-L2')).resolves.toBe('SV-L2');
    await expect(repo.getValveForPlot('SF-ZZ')).resolves.toBeNull();
  });

  test('getAllValvePlotMappings returns normalized list', async () => {
    const rows = [
      { plot_id: 'SF-U1', smartfarm_valve_name: 'SV-U1' },
      { plot_id: 'SF-L2', smartfarm_valve_name: 'SV-L2' }
    ];
    const pool = { query: jest.fn().mockResolvedValue({ rows }) };
    const repo = new ConfigRepository({ pool, schemas });
    const all = await repo.getAllValvePlotMappings();
    expect(all).toEqual([
      { plotId: 'SF-U1', valveName: 'SV-U1' },
      { plotId: 'SF-L2', valveName: 'SV-L2' }
    ]);
  });
});