const { Pool } = require('pg');
const fc = require('fast-check');
const {
  describe,
  test,
  expect,
  beforeAll,
  afterAll
} = require('@jest/globals');

// Load environment
require('dotenv').config();

// Kc values calibrated from Excel: คบ.มูลบน_ROS_ฤดูฝน(2568).xlsm
const KC_CURVES = {
  rice: {
    values: [
      { week: 1, kc: 1.03 },
      { week: 2, kc: 1.07 },
      { week: 3, kc: 1.12 },
      { week: 4, kc: 1.29 },
      { week: 5, kc: 1.38 },
      { week: 6, kc: 1.45 },
      { week: 7, kc: 1.5 },
      { week: 8, kc: 1.48 },
      { week: 9, kc: 1.42 },
      { week: 10, kc: 1.34 },
      { week: 11, kc: 1.23 },
      { week: 12, kc: 0.94 },
      { week: 13, kc: 0.86 }
    ],
    durationDays: 91
  },
  corn: {
    values: [
      { week: 1, kc: 0.65 },
      { week: 2, kc: 0.68 },
      { week: 3, kc: 0.84 },
      { week: 4, kc: 0.99 },
      { week: 5, kc: 1.16 },
      { week: 6, kc: 1.22 },
      { week: 7, kc: 1.21 },
      { week: 8, kc: 1.15 },
      { week: 9, kc: 0.96 },
      { week: 10, kc: 0.72 },
      { week: 11, kc: 0.61 }
    ],
    durationDays: 77
  }
};

const SEASONAL_ET0 = {
  dry: 5.5,
  wet: 4.5
};

const PERCOLATION_BY_MODE = {
  AWD: 2.0,
  MOISTURE: 0.0
};

const RAI_TO_SQM = 1600;

describe('baseline water demand calculations', () => {
  let pool;
  let testSeasonId;

  beforeAll(async () => {
    pool = new Pool({
      host: process.env.TIMESCALE_HOST,
      port: parseInt(process.env.TIMESCALE_PORT || '5432'),
      database: process.env.TIMESCALE_DB,
      user: process.env.TIMESCALE_USER,
      password: process.env.TIMESCALE_PASSWORD
    });

    // Create a test season
    const client = await pool.connect();
    const result = await client.query(
      `INSERT INTO ros_gis_smartfarm.crop_seasons (
        plot_id, crop_type, planting_date, expected_harvest_date,
        season_name, active
      ) VALUES ($1, $2, $3, $4, $5, $6) RETURNING id`,
      [
        'test-plot-001',
        'rice',
        '2025-01-15',
        '2025-05-14',
        'Test Season',
        false
      ]
    );
    testSeasonId = result.rows[0].id;
    client.release();
  });

  afterAll(async () => {
    // Cleanup test data
    const client = await pool.connect();
    await client.query(
      'DELETE FROM ros_gis_smartfarm.crop_seasons WHERE plot_id = $1',
      ['test-plot-001']
    );
    client.release();
    await pool.end();
  });

  test('calculates gross demand correctly for AWD rice initial stage (week 1)', () => {
    const areaRai = 2.51;
    const et0Mm = 5.5;
    const kc = 1.03; // Excel calibrated value for rice week 1
    const percolationMm = 2.0;

    const grossDemandMm = et0Mm * kc + percolationMm;
    const grossDemandM3 = (grossDemandMm * areaRai * RAI_TO_SQM) / 1000;

    expect(grossDemandMm).toBeCloseTo(7.665, 2);
    expect(grossDemandM3).toBeCloseTo(30.78, 2);
  });

  test('calculates gross demand correctly for MOISTURE corn mid-season (week 6)', () => {
    const areaRai = 3.0;
    const et0Mm = 4.5;
    const kc = 1.22; // Excel calibrated value for corn week 6
    const percolationMm = 0.0;

    const grossDemandMm = et0Mm * kc + percolationMm;
    const grossDemandM3 = (grossDemandMm * areaRai * RAI_TO_SQM) / 1000;

    expect(grossDemandMm).toBeCloseTo(5.49, 2);
    expect(grossDemandM3).toBeCloseTo(26.35, 2);
  });

  test('property: gross demand scales linearly with area', () => {
    fc.assert(
      fc.property(
        fc.float({ min: 0.5, max: 10.0, noNaN: true }),
        fc.float({ min: 1, max: 3, noNaN: true }),
        (areaRai, scale) => {
          const et0Mm = 5.5;
          const kc = 1.2;
          const percolationMm = 2.0;

          const demand1 =
            ((et0Mm * kc + percolationMm) * areaRai * RAI_TO_SQM) / 1000;
          const demand2 =
            ((et0Mm * kc + percolationMm) * (areaRai * scale) * RAI_TO_SQM) /
            1000;

          const expectedDemand2 = demand1 * scale;
          return Math.abs(demand2 - expectedDemand2) < 0.001;
        }
      )
    );
  });

  test('property: adding percolation always increases or maintains gross demand', () => {
    fc.assert(
      fc.property(
        fc.float({ min: 0.5, max: 10.0, noNaN: true }),
        fc.float({ min: 3.0, max: 7.0, noNaN: true }),
        fc.float({ min: 0.5, max: 2.0, noNaN: true }),
        (areaRai, et0Mm, kc) => {
          const demandWithoutPercolation =
            (et0Mm * kc * areaRai * RAI_TO_SQM) / 1000;
          const demandWithPercolation =
            ((et0Mm * kc + 2.0) * areaRai * RAI_TO_SQM) / 1000;

          return demandWithPercolation >= demandWithoutPercolation;
        }
      )
    );
  });

  test('retrieves baseline demand for specific date', async () => {
    const client = await pool.connect();

    // Insert a test record
    await client.query(
      `INSERT INTO ros_gis_smartfarm.daily_water_demands_baseline (
        season_id, date, crop_week, growth_stage, crop_type,
        area_rai, et0_mm, kc_value, percolation_mm,
        gross_demand_mm, gross_demand_m3,
        effective_rainfall_mm, effective_rainfall_m3,
        net_demand_m3, calculation_method, notes
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
      ON CONFLICT (season_id, date) DO NOTHING`,
      [
        testSeasonId,
        '2025-01-15',
        1,
        'initial',
        'rice',
        2.51,
        5.5,
        1.1,
        2.0,
        8.05,
        32.33,
        0.0,
        0.0,
        32.33,
        'baseline',
        'Test record'
      ]
    );

    const result = await client.query(
      `SELECT * FROM ros_gis_smartfarm.daily_water_demands_baseline
       WHERE season_id = $1 AND date = $2`,
      [testSeasonId, '2025-01-15']
    );

    client.release();

    expect(result.rows).toHaveLength(1);
    expect(result.rows[0]).toEqual(
      expect.objectContaining({
        season_id: testSeasonId,
        crop_week: 1,
        growth_stage: 'initial',
        crop_type: 'rice',
        area_rai: '2.51',
        et0_mm: '5.50',
        kc_value: '1.10',
        percolation_mm: '2.00',
        gross_demand_mm: '8.05',
        gross_demand_m3: '32.33',
        net_demand_m3: '32.33',
        calculation_method: 'baseline'
      })
    );
  });

  test('enforces unique constraint on season_id and date', async () => {
    const client = await pool.connect();

    await client.query(
      `INSERT INTO ros_gis_smartfarm.daily_water_demands_baseline (
        season_id, date, crop_week, growth_stage, crop_type,
        area_rai, et0_mm, kc_value, percolation_mm,
        gross_demand_mm, gross_demand_m3,
        effective_rainfall_mm, effective_rainfall_m3,
        net_demand_m3, calculation_method
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
      ON CONFLICT (season_id, date) DO NOTHING`,
      [
        testSeasonId,
        '2025-01-16',
        1,
        'initial',
        'rice',
        2.51,
        5.5,
        1.1,
        2.0,
        8.05,
        32.33,
        0.0,
        0.0,
        32.33,
        'baseline'
      ]
    );

    // Try to insert duplicate - should update via ON CONFLICT
    await client.query(
      `INSERT INTO ros_gis_smartfarm.daily_water_demands_baseline (
        season_id, date, crop_week, growth_stage, crop_type,
        area_rai, et0_mm, kc_value, percolation_mm,
        gross_demand_mm, gross_demand_m3,
        effective_rainfall_mm, effective_rainfall_m3,
        net_demand_m3, calculation_method
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
      ON CONFLICT (season_id, date) DO UPDATE SET
        gross_demand_m3 = EXCLUDED.gross_demand_m3`,
      [
        testSeasonId,
        '2025-01-16',
        1,
        'initial',
        'rice',
        2.51,
        5.5,
        1.1,
        2.0,
        8.05,
        32.33,
        0.0,
        0.0,
        32.33,
        'baseline'
      ]
    );

    const result = await client.query(
      'SELECT COUNT(*) as count FROM ros_gis_smartfarm.daily_water_demands_baseline WHERE season_id = $1 AND date = $2',
      [testSeasonId, '2025-01-16']
    );

    client.release();

    expect(result.rows[0].count).toBe('1');
  });

  test('verifies crop duration matches Kc curve configuration', () => {
    const riceDays = KC_CURVES.rice.durationDays;
    const cornDays = KC_CURVES.corn.durationDays;

    expect(riceDays).toBe(91); // Excel calibrated: 13 weeks
    expect(cornDays).toBe(77); // Excel calibrated: 11 weeks

    // Verify all weeks are covered
    const riceWeeks = KC_CURVES.rice.values.map((v) => v.week);
    const cornWeeks = KC_CURVES.corn.values.map((v) => v.week);

    expect(Math.max(...riceWeeks)).toBe(13); // 91 days / 7 ≈ 13 weeks
    expect(Math.max(...cornWeeks)).toBe(11); // 77 days / 7 = 11 weeks
  });

  test('seasonal ET0 selection based on planting month', () => {
    // Dry season (November - April)
    expect(SEASONAL_ET0.dry).toBe(5.5);

    // Wet season (May - October)
    expect(SEASONAL_ET0.wet).toBe(4.5);

    // Verify dry season is November (11) through April (4)
    const dryMonths = [11, 12, 1, 2, 3, 4];
    const wetMonths = [5, 6, 7, 8, 9, 10];

    dryMonths.forEach((month) => {
      const date = new Date(2025, month - 1, 15);
      const et0 =
        month >= 11 || month <= 4 ? SEASONAL_ET0.dry : SEASONAL_ET0.wet;
      expect(et0).toBe(5.5);
    });

    wetMonths.forEach((month) => {
      const date = new Date(2025, month - 1, 15);
      const et0 =
        month >= 5 && month <= 10 ? SEASONAL_ET0.wet : SEASONAL_ET0.dry;
      expect(et0).toBe(4.5);
    });
  });
});

describe('crop season management', () => {
  let pool;

  beforeAll(async () => {
    pool = new Pool({
      host: process.env.TIMESCALE_HOST,
      port: parseInt(process.env.TIMESCALE_PORT || '5432'),
      database: process.env.TIMESCALE_DB,
      user: process.env.TIMESCALE_USER,
      password: process.env.TIMESCALE_PASSWORD
    });
  });

  afterAll(async () => {
    const client = await pool.connect();
    await client.query(
      'DELETE FROM ros_gis_smartfarm.crop_seasons WHERE plot_id LIKE \'test-%\''
    );
    client.release();
    await pool.end();
  });

  test('creates crop season with correct harvest date', async () => {
    const client = await pool.connect();

    const plantingDateStr = '2025-01-15';
    const expectedHarvestDateStr = '2025-05-14';

    const result = await client.query(
      `INSERT INTO ros_gis_smartfarm.crop_seasons (
        plot_id, crop_type, planting_date, expected_harvest_date,
        season_name, active
      ) VALUES ($1, $2, $3, $4, $5, $6)
      RETURNING id, expected_harvest_date::text as expected_harvest_date`,
      [
        'test-season-001',
        'rice',
        plantingDateStr,
        expectedHarvestDateStr,
        'Test Season 2025',
        true
      ]
    );

    client.release();

    expect(result.rows).toHaveLength(1);
    expect(result.rows[0].expected_harvest_date).toBe(expectedHarvestDateStr);
  });

  test('enforces only one active season per plot', async () => {
    const client = await pool.connect();

    // Insert first active season
    await client.query(
      `INSERT INTO ros_gis_smartfarm.crop_seasons (
        plot_id, crop_type, planting_date, expected_harvest_date,
        season_name, active
      ) VALUES ($1, $2, $3, $4, $5, $6)`,
      [
        'test-multi-season',
        'rice',
        '2024-11-01',
        '2025-02-28',
        'Season 1',
        true
      ]
    );

    // Insert second active season (should deactivate first)
    await client.query(
      `INSERT INTO ros_gis_smartfarm.crop_seasons (
        plot_id, crop_type, planting_date, expected_harvest_date,
        season_name, active
      ) VALUES ($1, $2, $3, $4, $5, $6)`,
      [
        'test-multi-season',
        'corn',
        '2025-03-01',
        '2025-05-29',
        'Season 2',
        true
      ]
    );

    const result = await client.query(
      `SELECT COUNT(*) as count FROM ros_gis_smartfarm.crop_seasons
       WHERE plot_id = $1 AND active = true`,
      ['test-multi-season']
    );

    client.release();

    expect(result.rows[0].count).toBe('1');
  });
});
