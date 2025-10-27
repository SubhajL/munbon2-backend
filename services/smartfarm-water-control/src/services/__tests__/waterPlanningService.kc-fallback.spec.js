'use strict';

const { WaterPlanningService } = require('../waterPlanningService');

function makePool(queryImpl) {
  return { query: jest.fn(queryImpl) };
}

function makeServiceWithQuery(queryImpl) {
  const pool = makePool(queryImpl);
  const planningRepository = {
    saveWaterDemand: jest.fn().mockResolvedValue(undefined)
  };
  const configRepository = {
    pool,
    schemas: { control: 'water_control_smartfarm' }
  };
  return new WaterPlanningService({
    planningRepository,
    configRepository,
    waterPlanningUrl: '',
    plotConfigs: [{ plotId: 'SF-U4', cropType: 'ข้าวโพดหวาน ข้าวโพดข้าวเหนียว' }],
    mode: 'internal'
  });
}

// Helpers to stub SQL patterns used by WaterPlanningService
function isKcAtWeek(sql) {
  return /FROM\s+ros_smartfarm\.kc_weekly/.test(sql) && /JOIN\s+ros_smartfarm\.crop_ros_mapping/.test(sql) && /kc\.crop_week/.test(sql);
}
function isMaxWeek(sql) {
  return /MAX\(kc\.crop_week\)/.test(sql);
}
function isPlanting(sql) {
  return /FROM\s+water_control_smartfarm\.plot_configurations/.test(sql) && /SELECT\s+planting_date/.test(sql);
}
function isArea(sql) {
  return /FROM\s+water_control_smartfarm\.v_plot_configurations_enriched/.test(sql);
}
function isEto(sql) {
  return /FROM\s+ros_smartfarm\.eto_weekly/.test(sql);
}
function isEff(sql) {
  return /FROM\s+ros_smartfarm\.weekly_effective_rainfall/.test(sql);
}

describe('WaterPlanningService Kc fallback + over-max policy', () => {
  test('getKcForExactCrop_returns_value_when_present', async () => {
    const svc = makeServiceWithQuery((sql, params) => {
      if (isKcAtWeek(sql) && params[0] === 'ข้าวโพดหวาน' && params[1] === 5) {
        return Promise.resolve({ rows: [{ kc_value: 1.16 }] });
      }
      return Promise.resolve({ rows: [] });
    });

    const kc = await svc.getKcForExactCrop('ข้าวโพดหวาน', 5);
    expect(kc).toBe(1.16);
  });

  test('resolveKcWithTokens_uses_second_token_when_first_missing', async () => {
    const svc = makeServiceWithQuery((sql, params) => {
      if (isMaxWeek(sql)) {
        // Exact string not mapped
        if (params[0] === 'ข้าวโพดหวาน ข้าวโพดข้าวเหนียว') return Promise.resolve({ rows: [] });
        // Token 1 mapped with max week 14
        if (params[0] === 'ข้าวโพดหวาน') return Promise.resolve({ rows: [{ max_week: 14 }] });
      }
      if (isKcAtWeek(sql) && params[0] === 'ข้าวโพดหวาน' && params[1] === 5) {
        return Promise.resolve({ rows: [{ kc_value: 1.16 }] });
      }
      return Promise.resolve({ rows: [] });
    });

    const r = await svc.resolveKcWithTokens('ข้าวโพดหวาน ข้าวโพดข้าวเหนียว', 5);
    expect(r.kc).toBe(1.16);
    expect(r.reason).toMatch(/exact|token/);
  });

  test('resolveKcWithTokens_over_max_week_returns_zero', async () => {
    const svc = makeServiceWithQuery((sql, params) => {
      if (isMaxWeek(sql) && params[0] === 'ข้าวขาวดอกมะลิ105') {
        return Promise.resolve({ rows: [{ max_week: 14 }] });
      }
      return Promise.resolve({ rows: [] });
    });

    const r = await svc.resolveKcWithTokens('ข้าวขาวดอกมะลิ105', 15);
    expect(r.kc).toBe(0);
    expect(r.reason).toBe('over-max-week');
  });

  test('resolveKcWithTokens_unknown_mapping_defaults_to_1_1', async () => {
    const svc = makeServiceWithQuery(() => Promise.resolve({ rows: [] }));
    const r = await svc.resolveKcWithTokens('พืชทดลอง', 5);
    expect(r.kc).toBe(1.1);
    expect(r.reason).toBe('default');
  });

  test('calculateDailyDemandInternal_uses_tokenized_kc_in_demand', async () => {
    const svc = makeServiceWithQuery((sql, params) => {
      if (isPlanting(sql)) {
        return Promise.resolve({ rows: [{ planting_date: '2025-09-19' }] });
      }
      if (isArea(sql)) {
        return Promise.resolve({ rows: [{ area_rai: 2.0 }] });
      }
      if (isMaxWeek(sql)) {
        if (params[0] === 'ข้าวโพดหวาน ข้าวโพดข้าวเหนียว') return Promise.resolve({ rows: [] });
        if (params[0] === 'ข้าวโพดหวาน') return Promise.resolve({ rows: [{ max_week: 14 }] });
      }
      if (isKcAtWeek(sql) && params[0] === 'ข้าวโพดหวาน' && params[1] === 5) {
        return Promise.resolve({ rows: [{ kc_value: 1.16 }] });
      }
      if (isEto(sql)) {
        return Promise.resolve({ rows: [{ v: 31.04 }] });
      }
      if (isEff(sql)) {
        return Promise.resolve({ rows: [] });
      }
      return Promise.resolve({ rows: [] });
    });

    // plot config for SF-U4
    svc.plotConfigs = [{ plotId: 'SF-U4', cropType: 'ข้าวโพดหวาน ข้าวโพดข้าวเหนียว' }];
    const out = await svc.calculateDailyDemandInternal('SF-U4', new Date('2025-10-22'));
    expect(out.kc).toBe(1.16);
    // demand = 31.04 * 1.16 * 2 * 1.6 = 115.2256
    expect(Number(out.demandCubicMeters.toFixed(2))).toBe(115.23);
  });

  test('calculateDailyDemandInternal_over_max_week_zeroes_demand', async () => {
    const svc = makeServiceWithQuery((sql, params) => {
      if (isPlanting(sql)) {
        return Promise.resolve({ rows: [{ planting_date: '2025-07-12' }] });
      }
      if (isArea(sql)) {
        return Promise.resolve({ rows: [{ area_rai: 2.0 }] });
      }
      if (isMaxWeek(sql) && params[0] === 'ข้าวขาวดอกมะลิ105') {
        return Promise.resolve({ rows: [{ max_week: 14 }] });
      }
      if (isEto(sql)) {
        return Promise.resolve({ rows: [{ v: 31.04 }] });
      }
      if (isEff(sql)) {
        return Promise.resolve({ rows: [] });
      }
      return Promise.resolve({ rows: [] });
    });

    svc.plotConfigs = [{ plotId: 'SF-L1', cropType: 'ข้าวหอมมะลิ 105' }];
    const out = await svc.calculateDailyDemandInternal('SF-L1', new Date('2025-10-22'));
    expect(out.kc).toBe(0);
    expect(out.demandCubicMeters).toBe(0);
  });
});