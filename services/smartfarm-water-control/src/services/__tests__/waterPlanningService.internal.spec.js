const { WaterPlanningService } = require('../waterPlanningService');

describe('WaterPlanningService (internal daily demand)', () => {
function makeService() {
    const repo = {
      saveWaterDemand: jest.fn(),
      getAreaRai: jest.fn(),
      getPlantingDate: jest.fn(),
      getKcFromRosSmartfarm: jest.fn(),
      getEt0FromRosSmartfarm: jest.fn(),
      getEffectiveRainfallFromRosSmartfarm: jest.fn(),
      getPlotConfiguration: jest.fn()
    };
    const configRepo = {
      pool: {
        query: jest.fn()
      },
      schemas: {
        control: 'water_control_smartfarm'
      }
    };
    const svc = new WaterPlanningService({
      timescaleRepository: repo,
      configRepository: configRepo,
      waterPlanningUrl: 'n/a',
      waterPlanningApiKey: 'n/a',
      waterPlanningEndpoint: '/n/a',
      timeout: 1000,
      plotConfigs: [{ plotId: 'P1', cropType: 'rice', controlMode: 'MOISTURE', areaRai: 2.5 }]
    });
    return { svc, repo, configRepo };
  }

  test('compute_cropWeek_from_planting_date', async () => {
    const { svc, repo, configRepo } = makeService();
    const targetDate = new Date('2025-06-29'); // 28 days after 2025-06-01 => week 5
    
    // Mock configRepo database queries
    configRepo.pool.query
      .mockResolvedValueOnce({ rows: [{ planting_date: new Date('2025-06-01') }] }) // planting_date query
      .mockResolvedValueOnce({ rows: [{ area_rai: 2.5 }] }) // area_rai query
      .mockResolvedValueOnce({ rows: [{ kc_value: 1.1 }] }) // kc query
      .mockResolvedValueOnce({ rows: [{ v: 30 }] }) // et0 query
      .mockResolvedValueOnce({ rows: [{ v: 0 }] }); // effective rainfall query

    await svc.calculateDailyDemandInternal('P1', targetDate);

    // Implicitly validates no throw; demand saved once
    expect(repo.saveWaterDemand).toHaveBeenCalledTimes(1);
    const arg = repo.saveWaterDemand.mock.calls[0][0];
    expect(arg.plotId).toBe('P1');
    expect(arg.date).toEqual(targetDate);
    // demand_m3 ~ (30*1.1)*2.5*1.6 = 132 m3
    expect(arg.demandCubicMeters).toBeCloseTo(132, 5);
  });

  test('clamp_negative_net_demand_to_zero', async () => {
    const { svc, repo, configRepo } = makeService();
    
    // Mock configRepo database queries
    configRepo.pool.query
      .mockResolvedValueOnce({ rows: [{ planting_date: new Date('2025-06-01') }] }) // planting_date query
      .mockResolvedValueOnce({ rows: [{ area_rai: 2.0 }] }) // area_rai query
      .mockResolvedValueOnce({ rows: [{ kc_value: 0.6 }] }) // kc query
      .mockResolvedValueOnce({ rows: [{ v: 20 }] }) // et0 query
      .mockResolvedValueOnce({ rows: [{ v: 500 }] }); // effective rainfall query (huge rain)

    await svc.calculateDailyDemandInternal('P2', new Date('2025-06-15'));

    const arg = repo.saveWaterDemand.mock.calls[0][0];
    expect(arg.demandCubicMeters).toBe(0);
  });
});