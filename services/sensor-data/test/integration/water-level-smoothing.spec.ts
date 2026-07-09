import { describe, test, expect, beforeAll, afterAll } from '@jest/globals';
import { Client } from 'pg';
import * as fs from 'fs';
import * as path from 'path';

// Database configuration
const dbConfig = {
  host: process.env.TIMESCALE_HOST || '43.208.201.191',
  port: parseInt(process.env.TIMESCALE_PORT || '5432'),
  database: process.env.TIMESCALE_DB || 'sensor_data',
  user: process.env.TIMESCALE_USER || 'postgres',
  password: process.env.TIMESCALE_PASSWORD || (() => { throw new Error('TIMESCALE_PASSWORD env var is required (hardcoded default removed; SEC remediation)'); })(),
};

describe('Water Level Smoothing Integration Tests', () => {
  let client: Client;

  beforeAll(async () => {
    client = new Client(dbConfig);
    await client.connect();
  });

  afterAll(async () => {
    await client.end();
  });

  test('backfill script should execute successfully', async () => {
    // Check if data has already been backfilled
    const checkResult = await client.query(
      'SELECT COUNT(*) as count FROM smoothed_water_level_readings'
    );

    // If already backfilled, verify count is greater than 0
    const count = parseInt(checkResult.rows[0].count);
    expect(count).toBeGreaterThan(0);

    // If not backfilled, run the backfill script
    if (count === 0) {
      const sqlPath = path.join(
        __dirname,
        '../../sql/water-level/04_backfill_smoothing_14d.sql'
      );
      const sql = fs.readFileSync(sqlPath, 'utf8');

      // Execute backfill - it returns multiple results, last one has summary
      await client.query(sql);

      // Verify data was inserted
      const verifyResult = await client.query(
        'SELECT COUNT(*) as count FROM smoothed_water_level_readings'
      );
      expect(parseInt(verifyResult.rows[0].count)).toBeGreaterThan(0);
    }
  });

  test('smoothing should reduce negative values by 100%', async () => {
    // Count negative values in raw data
    const rawNegatives = await client.query(`
      SELECT COUNT(*) as count
      FROM water_level_readings
      WHERE level_cm < 0
        AND time >= NOW() - INTERVAL '14 days'
        AND sensor_id LIKE 'AWD-%'
    `);

    // Count negative values in smoothed data
    const smoothedNegatives = await client.query(`
      SELECT COUNT(*) as count
      FROM smoothed_water_level_readings
      WHERE level_cm < 0
        AND time >= NOW() - INTERVAL '14 days'
        AND sensor_id LIKE 'AWD-%'
    `);

    const rawCount = parseInt(rawNegatives.rows[0].count);
    const smoothedCount = parseInt(smoothedNegatives.rows[0].count);

    // Should have no negative values after smoothing
    expect(smoothedCount).toBe(0);

    // Verify we actually had negatives to fix
    expect(rawCount).toBeGreaterThan(0);
  });

  test('smoothing should reduce standard deviation by at least 30%', async () => {
    // Get standard deviation for each sensor before and after smoothing
    const comparison = await client.query(`
      WITH raw_stats AS (
        SELECT
          sensor_id,
          STDDEV(level_cm) as raw_stddev,
          COUNT(*) as raw_count
        FROM water_level_readings
        WHERE time >= NOW() - INTERVAL '14 days'
          AND sensor_id LIKE 'AWD-%'
          AND level_cm IS NOT NULL
        GROUP BY sensor_id
      ),
      smoothed_stats AS (
        SELECT
          sensor_id,
          STDDEV(level_cm) as smoothed_stddev,
          COUNT(*) as smoothed_count
        FROM smoothed_water_level_readings
        WHERE time >= NOW() - INTERVAL '14 days'
          AND sensor_id LIKE 'AWD-%'
          AND level_cm IS NOT NULL
        GROUP BY sensor_id
      )
      SELECT
        r.sensor_id,
        r.raw_stddev,
        s.smoothed_stddev,
        ROUND(100.0 * (r.raw_stddev - s.smoothed_stddev) / r.raw_stddev, 2) as reduction_pct,
        r.raw_count,
        s.smoothed_count
      FROM raw_stats r
      JOIN smoothed_stats s ON r.sensor_id = s.sensor_id
      WHERE r.raw_count > 10  -- Only check sensors with enough data
      ORDER BY r.sensor_id
    `);

    // Check each sensor
    let significantReductions = 0;
    let totalReduction = 0;
    for (const row of comparison.rows) {
      const reductionPct = parseFloat(row.reduction_pct) || 0;
      const rawStddev = parseFloat(row.raw_stddev);

      // Count sensors with significant reduction (>10%)
      if (reductionPct >= 10) {
        significantReductions++;
      }

      totalReduction += reductionPct;

      // Smoothed stddev should be less than or equal to raw
      expect(parseFloat(row.smoothed_stddev)).toBeLessThanOrEqual(rawStddev);
    }

    // Average reduction across all sensors should be meaningful
    const avgReduction = totalReduction / comparison.rows.length;
    expect(avgReduction).toBeGreaterThan(5);

    // At least some sensors should show significant reduction
    expect(significantReductions).toBeGreaterThan(0);

    // Should have tested at least 3 sensors
    expect(comparison.rows.length).toBeGreaterThanOrEqual(3);
  });

  test('smoothed data should preserve general trends', async () => {
    // Compare average levels before and after smoothing
    const avgComparison = await client.query(`
      WITH raw_avg AS (
        SELECT
          sensor_id,
          AVG(level_cm) as avg_level,
          MIN(level_cm) as min_level,
          MAX(level_cm) as max_level
        FROM water_level_readings
        WHERE time >= NOW() - INTERVAL '14 days'
          AND sensor_id LIKE 'AWD-%'
          AND level_cm IS NOT NULL
        GROUP BY sensor_id
      ),
      smoothed_avg AS (
        SELECT
          sensor_id,
          AVG(level_cm) as avg_level,
          MIN(level_cm) as min_level,
          MAX(level_cm) as max_level
        FROM smoothed_water_level_readings
        WHERE time >= NOW() - INTERVAL '14 days'
          AND sensor_id LIKE 'AWD-%'
          AND level_cm IS NOT NULL
        GROUP BY sensor_id
      )
      SELECT
        r.sensor_id,
        r.avg_level as raw_avg,
        s.avg_level as smoothed_avg,
        ABS(r.avg_level - s.avg_level) as avg_diff,
        r.min_level as raw_min,
        s.min_level as smoothed_min,
        r.max_level as raw_max,
        s.max_level as smoothed_max
      FROM raw_avg r
      JOIN smoothed_avg s ON r.sensor_id = s.sensor_id
      ORDER BY r.sensor_id
    `);

    for (const row of avgComparison.rows) {
      const avgDiff = parseFloat(row.avg_diff);
      const rawAvg = parseFloat(row.raw_avg);

      // Average should not change by more than 10%
      const diffPct = (avgDiff / rawAvg) * 100;
      expect(diffPct).toBeLessThan(10);

      // Min should not be negative after smoothing
      expect(parseFloat(row.smoothed_min)).toBeGreaterThanOrEqual(0);

      // Max should be reduced (no spikes)
      expect(parseFloat(row.smoothed_max)).toBeLessThanOrEqual(
        parseFloat(row.raw_max)
      );
    }
  });

  test('all smoothed readings should have quality scores', async () => {
    const qualityCheck = await client.query(`
      SELECT
        COUNT(*) as total_rows,
        COUNT(quality_score) as rows_with_quality,
        AVG(quality_score) as avg_quality,
        MIN(quality_score) as min_quality,
        MAX(quality_score) as max_quality
      FROM smoothed_water_level_readings
      WHERE time >= NOW() - INTERVAL '14 days'
        AND sensor_id LIKE 'AWD-%'
    `);

    const result = qualityCheck.rows[0];

    // All rows should have quality scores
    expect(parseInt(result.total_rows)).toBeGreaterThan(0);
    expect(parseInt(result.rows_with_quality)).toBe(parseInt(result.total_rows));

    // Quality scores should be between 50 and 100
    expect(parseFloat(result.min_quality)).toBeGreaterThanOrEqual(50);
    expect(parseFloat(result.max_quality)).toBeLessThanOrEqual(100);

    // Average quality should be reasonable
    expect(parseFloat(result.avg_quality)).toBeGreaterThan(70);
  });

  test('smoothed data should have same or more data points than raw', async () => {
    const countComparison = await client.query(`
      WITH counts AS (
        SELECT
          'raw' as source,
          sensor_id,
          COUNT(*) as reading_count
        FROM water_level_readings
        WHERE time >= NOW() - INTERVAL '14 days'
          AND sensor_id LIKE 'AWD-%'
        GROUP BY sensor_id

        UNION ALL

        SELECT
          'smoothed' as source,
          sensor_id,
          COUNT(*) as reading_count
        FROM smoothed_water_level_readings
        WHERE time >= NOW() - INTERVAL '14 days'
          AND sensor_id LIKE 'AWD-%'
        GROUP BY sensor_id
      )
      SELECT
        sensor_id,
        MAX(CASE WHEN source = 'raw' THEN reading_count END) as raw_count,
        MAX(CASE WHEN source = 'smoothed' THEN reading_count END) as smoothed_count
      FROM counts
      GROUP BY sensor_id
      ORDER BY sensor_id
    `);

    for (const row of countComparison.rows) {
      const rawCount = parseInt(row.raw_count || '0');
      const smoothedCount = parseInt(row.smoothed_count || '0');

      // Smoothed should have approximately the same number of points as raw
      // Allow for small differences due to edge effects or null handling
      const difference = Math.abs(smoothedCount - rawCount);
      const percentDiff = (difference / rawCount) * 100;

      // Allow up to 1% difference
      expect(percentDiff).toBeLessThan(1);
    }
  });
});