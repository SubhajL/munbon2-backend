const { pool } = require('@config/database');
const { logger } = require('@utils/logger');
const dayjs = require('dayjs');
const weekOfYear = require('dayjs/plugin/weekOfYear');
const isoWeek = require('dayjs/plugin/isoWeek');

dayjs.extend(weekOfYear);
dayjs.extend(isoWeek);

class WaterLevelAggregationService {
  /**
   * Aggregate water level data for a specific week
   */
  async aggregateWeeklyWaterLevel(areaId, areaType, calendarWeek, calendarYear) {
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

      // Check if we already have aggregated data for this week
      const existingData = await this.getWeeklyWaterLevel(
        areaId, 
        areaType, 
        calendarWeek, 
        calendarYear
      );

      if (existingData) {
        logger.info('Weekly water level already aggregated', {
          areaId,
          week: calendarWeek,
          year: calendarYear
        });
        return existingData;
      }

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

      if (result.rows.length === 0 || result.rows[0].avg_water_level_m === null) {
        logger.warn('No water level data found for aggregation', {
          areaId,
          week: calendarWeek,
          year: calendarYear
        });
        return null;
      }

      const data = result.rows[0];

      // Store the aggregated data
      await this.storeWeeklyWaterLevel({
        areaId,
        areaType,
        calendarWeek,
        calendarYear,
        weekStartDate: weekStart.toDate(),
        weekEndDate: weekEnd.toDate(),
        avgWaterLevelM: data.avg_water_level_m,
        minWaterLevelM: data.min_water_level_m,
        maxWaterLevelM: data.max_water_level_m,
        stdDevWaterLevelM: data.std_dev_water_level_m,
        measurementCount: parseInt(data.hourly_count),
        dataQualityScore: parseFloat(data.data_quality_score)
      });

      return {
        areaId,
        areaType,
        calendarWeek,
        calendarYear,
        weekStartDate: weekStart.toDate(),
        weekEndDate: weekEnd.toDate(),
        avgWaterLevelM: parseFloat(data.avg_water_level_m),
        minWaterLevelM: parseFloat(data.min_water_level_m),
        maxWaterLevelM: parseFloat(data.max_water_level_m),
        stdDevWaterLevelM: data.std_dev_water_level_m ? parseFloat(data.std_dev_water_level_m) : null,
        measurementCount: parseInt(data.hourly_count),
        dataQualityScore: parseFloat(data.data_quality_score)
      };

    } catch (error) {
      logger.error('Failed to aggregate weekly water level', {
        areaId,
        week: calendarWeek,
        year: calendarYear,
        error: error.message
      });
      throw error;
    }
  }

  /**
   * Get stored weekly water level data
   */
  async getWeeklyWaterLevel(areaId, areaType, calendarWeek, calendarYear) {
    try {
      const query = `
        SELECT 
          area_id,
          area_type,
          calendar_week,
          calendar_year,
          week_start_date,
          week_end_date,
          avg_water_level_m,
          min_water_level_m,
          max_water_level_m,
          std_dev_water_level_m,
          measurement_count,
          data_quality_score,
          created_at
        FROM ros.weekly_water_levels
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
        return null;
      }

      const row = result.rows[0];
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
        measurementCount: row.measurement_count,
        dataQualityScore: parseFloat(row.data_quality_score)
      };

    } catch (error) {
      logger.error('Failed to get weekly water level', error);
      throw error;
    }
  }

  /**
   * Store weekly water level aggregation
   */
  async storeWeeklyWaterLevel(data) {
    try {
      const query = `
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
      `;

      await pool.query(query, [
        data.areaId,
        data.areaType,
        data.calendarWeek,
        data.calendarYear,
        data.weekStartDate,
        data.weekEndDate,
        data.avgWaterLevelM,
        data.minWaterLevelM,
        data.maxWaterLevelM,
        data.stdDevWaterLevelM,
        data.measurementCount,
        data.dataQualityScore
      ]);

      logger.info('Stored weekly water level aggregation', {
        areaId: data.areaId,
        week: data.calendarWeek,
        year: data.calendarYear
      });

    } catch (error) {
      logger.error('Failed to store weekly water level', error);
      throw error;
    }
  }

  /**
   * Aggregate water levels for multiple areas
   */
  async aggregateMultipleAreas(areas, calendarWeek, calendarYear) {
    const results = [];
    
    for (const area of areas) {
      try {
        const result = await this.aggregateWeeklyWaterLevel(
          area.areaId,
          area.areaType,
          calendarWeek,
          calendarYear
        );
        
        if (result) {
          results.push(result);
        }
      } catch (error) {
        logger.error('Failed to aggregate water level for area', {
          areaId: area.areaId,
          error: error.message
        });
      }
    }
    
    logger.info('Completed water level aggregation', {
      totalAreas: areas.length,
      successfulAggregations: results.length,
      week: calendarWeek,
      year: calendarYear
    });
    
    return results;
  }

  /**
   * Calculate water level adjustment factor
   */
  calculateAdjustmentFactor(waterLevelM, thresholds = {}) {
    const {
      criticalLow = 0.3,
      low = 0.5,
      optimal = 1.0,
      high = 1.5,
      flood = 2.0
    } = thresholds;

    let factor = 1.0;
    let method = 'optimal';
    let quality = 100;

    if (waterLevelM === null || waterLevelM === undefined) {
      return { factor: 1.0, method: 'no_data', quality: 0 };
    }

    if (waterLevelM < criticalLow) {
      factor = 1.3; // Increase demand by 30%
      method = 'critical_low';
      quality = 80;
    } else if (waterLevelM < low) {
      factor = 1.15; // Increase demand by 15%
      method = 'low';
      quality = 90;
    } else if (waterLevelM > flood) {
      factor = 0; // No irrigation needed
      method = 'flood';
      quality = 100;
    } else if (waterLevelM > high) {
      factor = 0.5; // Reduce demand by 50%
      method = 'high';
      quality = 100;
    } else {
      factor = 1.0; // Normal demand
      method = 'optimal';
      quality = 100;
    }

    return { factor, method, quality };
  }
}

const waterLevelAggregationService = new WaterLevelAggregationService();

module.exports = {
  WaterLevelAggregationService,
  waterLevelAggregationService
};