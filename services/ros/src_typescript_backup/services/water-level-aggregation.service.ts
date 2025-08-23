import { pool } from '@config/database';
import { logger } from '@utils/logger';
import dayjs from 'dayjs';
import weekOfYear from 'dayjs/plugin/weekOfYear';
import isoWeek from 'dayjs/plugin/isoWeek';

dayjs.extend(weekOfYear);
dayjs.extend(isoWeek);

export interface WeeklyWaterLevel {
  areaId: string;
  areaType: string;
  calendarWeek: number;
  calendarYear: number;
  weekStartDate: Date;
  weekEndDate: Date;
  avgWaterLevelM: number | null;
  minWaterLevelM: number | null;
  maxWaterLevelM: number | null;
  stdDevWaterLevelM: number | null;
  measurementCount: number;
  dataQualityScore: number;
}

export interface WaterLevelAdjustment {
  factor: number;
  method: string;
  quality: number;
}

export class WaterLevelAggregationService {
  /**
   * Aggregate water level data for a specific week
   */
  async aggregateWeeklyWaterLevel(
    areaId: string,
    areaType: string,
    calendarWeek: number,
    calendarYear: number
  ): Promise<WeeklyWaterLevel | null> {
    try {
      // Calculate ISO week boundaries (Monday 00:00 to Sunday 23:59)
      const weekStart = dayjs()
        .year(calendarYear)
        .isoWeek(calendarWeek)
        .startOf('isoWeek');
      const weekEnd = dayjs()
        .year(calendarYear)
        .isoWeek(calendarWeek)
        .endOf('isoWeek');

      logger.info('Aggregating water levels', {
        areaId,
        areaType,
        week: calendarWeek,
        year: calendarYear,
        weekStart: weekStart.format('YYYY-MM-DD'),
        weekEnd: weekEnd.format('YYYY-MM-DD')
      });

      // Fetch water level data from TimescaleDB
      const query = `
        WITH hourly_data AS (
          SELECT 
            time_bucket('1 hour', timestamp) as hour,
            AVG(water_level_m) as avg_level,
            COUNT(*) as reading_count
          FROM water_level_readings
          WHERE sensor_id IN (
            SELECT sensor_id 
            FROM sensor_registrations 
            WHERE area_id = $1 
              AND area_type = $2
              AND status = 'active'
          )
          AND timestamp >= $3
          AND timestamp < $4
          AND quality_score >= 0.7  -- Only use quality data
          GROUP BY hour
        ),
        weekly_stats AS (
          SELECT
            AVG(avg_level) as avg_water_level_m,
            MIN(avg_level) as min_water_level_m,
            MAX(avg_level) as max_water_level_m,
            STDDEV(avg_level) as std_dev_water_level_m,
            COUNT(*) as hourly_count
          FROM hourly_data
        )
        SELECT 
          avg_water_level_m,
          min_water_level_m,
          max_water_level_m,
          std_dev_water_level_m,
          hourly_count,
          -- Quality score: percentage of hours with data (168 hours per week)
          LEAST(100, (hourly_count::numeric / 168) * 100) as data_quality_score
        FROM weekly_stats
      `;

      const result = await pool.query(query, [
        areaId,
        areaType,
        weekStart.toDate(),
        weekEnd.toDate()
      ]);

      if (result.rows.length === 0 || !result.rows[0].avg_water_level_m) {
        logger.warn('No water level data found for week', {
          areaId,
          week: calendarWeek,
          year: calendarYear
        });
        return null;
      }

      const data = result.rows[0];

      // Store aggregated data
      const insertQuery = `
        INSERT INTO ros.weekly_water_levels (
          area_id, area_type, calendar_week, calendar_year,
          week_start_date, week_end_date,
          avg_water_level_m, min_water_level_m, max_water_level_m,
          std_dev_water_level_m, measurement_count, data_quality_score
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        ON CONFLICT (area_id, area_type, calendar_week, calendar_year)
        DO UPDATE SET
          avg_water_level_m = EXCLUDED.avg_water_level_m,
          min_water_level_m = EXCLUDED.min_water_level_m,
          max_water_level_m = EXCLUDED.max_water_level_m,
          std_dev_water_level_m = EXCLUDED.std_dev_water_level_m,
          measurement_count = EXCLUDED.measurement_count,
          data_quality_score = EXCLUDED.data_quality_score,
          updated_at = CURRENT_TIMESTAMP
        RETURNING *
      `;

      const insertResult = await pool.query(insertQuery, [
        areaId,
        areaType,
        calendarWeek,
        calendarYear,
        weekStart.toDate(),
        weekEnd.toDate(),
        data.avg_water_level_m,
        data.min_water_level_m,
        data.max_water_level_m,
        data.std_dev_water_level_m,
        data.hourly_count,
        data.data_quality_score
      ]);

      return this.mapToWeeklyWaterLevel(insertResult.rows[0]);
    } catch (error) {
      logger.error('Failed to aggregate weekly water level', error);
      throw error;
    }
  }

  /**
   * Get aggregated water level for a specific week
   */
  async getWeeklyWaterLevel(
    areaId: string,
    areaType: string,
    calendarWeek: number,
    calendarYear: number
  ): Promise<WeeklyWaterLevel | null> {
    try {
      const query = `
        SELECT * FROM ros.weekly_water_levels
        WHERE area_id = $1 
          AND area_type = $2
          AND calendar_week = $3 
          AND calendar_year = $4
      `;

      const result = await pool.query(query, [
        areaId,
        areaType,
        calendarWeek,
        calendarYear
      ]);

      if (result.rows.length === 0) {
        // Try to aggregate on-demand
        return await this.aggregateWeeklyWaterLevel(
          areaId,
          areaType,
          calendarWeek,
          calendarYear
        );
      }

      return this.mapToWeeklyWaterLevel(result.rows[0]);
    } catch (error) {
      logger.error('Failed to get weekly water level', error);
      throw error;
    }
  }

  /**
   * Calculate water demand adjustment factor based on water level
   */
  async calculateAdjustmentFactor(
    cropType: string,
    cropWeek: number,
    avgWaterLevelM: number | null
  ): Promise<WaterLevelAdjustment> {
    try {
      if (avgWaterLevelM === null) {
        return {
          factor: 1.0,
          method: 'no_data',
          quality: 0
        };
      }

      // Get adjustment factor from configuration table
      const query = `
        SELECT adjustment_factor, adjustment_type, notes
        FROM ros.water_level_adjustment_factors
        WHERE crop_type = $1
          AND crop_week = $2
          AND (water_level_range_min IS NULL OR $3 >= water_level_range_min)
          AND (water_level_range_max IS NULL OR $3 < water_level_range_max)
        ORDER BY 
          CASE 
            WHEN water_level_range_min IS NULL THEN 0 
            ELSE water_level_range_min 
          END DESC
        LIMIT 1
      `;

      const result = await pool.query(query, [
        cropType,
        cropWeek,
        avgWaterLevelM
      ]);

      if (result.rows.length === 0) {
        logger.warn('No adjustment factor found, using default', {
          cropType,
          cropWeek,
          waterLevel: avgWaterLevelM
        });
        return {
          factor: 1.0,
          method: 'default',
          quality: 50
        };
      }

      return {
        factor: parseFloat(result.rows[0].adjustment_factor),
        method: result.rows[0].adjustment_type || 'configured',
        quality: 100
      };
    } catch (error) {
      logger.error('Failed to calculate adjustment factor', error);
      return {
        factor: 1.0,
        method: 'error',
        quality: 0
      };
    }
  }

  /**
   * Aggregate water levels for multiple areas
   */
  async aggregateMultipleAreas(
    areas: Array<{ areaId: string; areaType: string }>,
    calendarWeek: number,
    calendarYear: number
  ): Promise<Map<string, WeeklyWaterLevel | null>> {
    const results = new Map<string, WeeklyWaterLevel | null>();

    // Process in parallel with concurrency limit
    const batchSize = 10;
    for (let i = 0; i < areas.length; i += batchSize) {
      const batch = areas.slice(i, i + batchSize);
      const batchResults = await Promise.all(
        batch.map(area =>
          this.aggregateWeeklyWaterLevel(
            area.areaId,
            area.areaType,
            calendarWeek,
            calendarYear
          )
        )
      );

      batch.forEach((area, index) => {
        results.set(`${area.areaId}_${area.areaType}`, batchResults[index]);
      });
    }

    return results;
  }

  /**
   * Backfill historical weekly aggregations
   */
  async backfillHistoricalData(
    areaId: string,
    areaType: string,
    startWeek: number,
    startYear: number,
    endWeek: number,
    endYear: number
  ): Promise<number> {
    let processedCount = 0;

    try {
      let currentDate = dayjs()
        .year(startYear)
        .isoWeek(startWeek)
        .startOf('isoWeek');
      const endDate = dayjs()
        .year(endYear)
        .isoWeek(endWeek)
        .endOf('isoWeek');

      while (currentDate.isBefore(endDate)) {
        const week = currentDate.isoWeek();
        const year = currentDate.year();

        const result = await this.aggregateWeeklyWaterLevel(
          areaId,
          areaType,
          week,
          year
        );

        if (result) {
          processedCount++;
        }

        currentDate = currentDate.add(1, 'week');
      }

      logger.info('Backfill completed', {
        areaId,
        areaType,
        processedCount
      });

      return processedCount;
    } catch (error) {
      logger.error('Failed to backfill historical data', error);
      throw error;
    }
  }

  private mapToWeeklyWaterLevel(row: any): WeeklyWaterLevel {
    return {
      areaId: row.area_id,
      areaType: row.area_type,
      calendarWeek: row.calendar_week,
      calendarYear: row.calendar_year,
      weekStartDate: row.week_start_date,
      weekEndDate: row.week_end_date,
      avgWaterLevelM: row.avg_water_level_m ? parseFloat(row.avg_water_level_m) : null,
      minWaterLevelM: row.min_water_level_m ? parseFloat(row.min_water_level_m) : null,
      maxWaterLevelM: row.max_water_level_m ? parseFloat(row.max_water_level_m) : null,
      stdDevWaterLevelM: row.std_dev_water_level_m ? parseFloat(row.std_dev_water_level_m) : null,
      measurementCount: parseInt(row.measurement_count || '0'),
      dataQualityScore: parseFloat(row.data_quality_score || '0')
    };
  }
}

export const waterLevelAggregationService = new WaterLevelAggregationService();