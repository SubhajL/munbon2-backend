const { WaterPlanningService } = require('../waterPlanningService');

describe('WaterPlanningService.extractDemandM3', () => {
  function makeService() {
    return new WaterPlanningService({
      timescaleRepository: { saveWaterDemand: jest.fn(), getPlannedDemand: jest.fn() },
      waterPlanningUrl: 'http://localhost:4002',
      waterPlanningApiKey: 'key',
      waterPlanningEndpoint: '/api/v1/water-demand/calculate',
      timeout: 1000,
      plotConfigs: []
    });
  }

  test('returns numeric m3 from netIrrigation.amount_m3', () => {
    const svc = makeService();
    const value = svc.extractDemandM3({ netIrrigation: { amount_m3: 12.34 } });
    expect(value).toBe(12.34);
  });

  test('throws when netIrrigation.amount_m3 missing', () => {
    const svc = makeService();
    expect(() => svc.extractDemandM3({})).toThrow(/netIrrigation.amount_m3/);
  });

  test('throws when netIrrigation.amount_m3 is NaN', () => {
    const svc = makeService();
    expect(() => svc.extractDemandM3({ netIrrigation: { amount_m3: 'abc' } })).toThrow(/netIrrigation.amount_m3/);
  });
});