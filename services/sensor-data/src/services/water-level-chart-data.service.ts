import { Logger } from 'pino';
import { TimescaleRepository } from '../repository/timescale.repository';
import { WaterLevelReadingRow } from '../types/water-level-chart.types';
import {
  parseTimePeriod,
  getTimeRange,
} from '../utils/time-period.utils';

export class WaterLevelChartDataService {
  constructor(
    private readonly repository: TimescaleRepository,
    private readonly logger: Logger
  ) {}

  /**
   * Get water level chart data for given period, optionally filtered by sensor IDs.
   * Returns raw database rows ordered chronologically.
   *
   * Note: Unlike moisture sensors, water level sensor IDs (AWD-XXXX) are stored in
   * canonical form in the database, so no ID normalization is needed. ID normalization
   * happens at ingestion time via formatWaterLevelSensorId().
   *
   * @param includeSmoothed If true, returns both raw and smoothed data using UNION ALL
   */
  async getWaterLevelChartData(
    period: string,
    sensorIds?: string[],
    includeSmoothed = false
  ): Promise<WaterLevelReadingRow[]> {
    try {
      const validatedPeriod = parseTimePeriod(period);
      const timeRange = getTimeRange(validatedPeriod);

      let query: string;
      const params: any[] = [timeRange.start, timeRange.end];

      if (includeSmoothed) {
        // UNION ALL query to get both raw and smoothed data
        query = `
          WITH combined AS (
            SELECT
              time_bucket('15 minutes'::interval, time) AS time,
              sensor_id,
              AVG(level_cm) as avg_level,
              MIN(level_cm) as min_level,
              MAX(level_cm) as max_level,
              AVG(quality_score) as avg_quality,
              COUNT(*) as sample_count,
              'raw' as source
            FROM water_level_readings
            WHERE time >= $1 AND time <= $2
            ${sensorIds && sensorIds.length > 0 ? 'AND sensor_id = ANY($3)' : ''}
            GROUP BY time_bucket('15 minutes'::interval, time), sensor_id

            UNION ALL

            SELECT
              time_bucket('15 minutes'::interval, time) AS time,
              sensor_id,
              AVG(level_cm) as avg_level,
              MIN(level_cm) as min_level,
              MAX(level_cm) as max_level,
              AVG(quality_score) as avg_quality,
              COUNT(*) as sample_count,
              'smoothed' as source
            FROM smoothed_water_level_readings
            WHERE time >= $1 AND time <= $2
            ${sensorIds && sensorIds.length > 0 ? 'AND sensor_id = ANY($3)' : ''}
            GROUP BY time_bucket('15 minutes'::interval, time), sensor_id
          )
          SELECT * FROM combined
          ORDER BY time ASC, sensor_id, source;
        `;
      } else {
        // Original query for raw data only
        query = `
          SELECT
            time_bucket('15 minutes'::interval, time) AS time,
            sensor_id,
            AVG(level_cm) as avg_level,
            MIN(level_cm) as min_level,
            MAX(level_cm) as max_level,
            AVG(quality_score) as avg_quality,
            COUNT(*) as sample_count,
            'raw' as source
          FROM water_level_readings
          WHERE time >= $1 AND time <= $2
          ${sensorIds && sensorIds.length > 0 ? 'AND sensor_id = ANY($3)' : ''}
          GROUP BY time_bucket('15 minutes'::interval, time), sensor_id
          ORDER BY time ASC;
        `;
      }

      if (sensorIds && sensorIds.length > 0) {
        params.push(sensorIds);
      }

      const result = await this.repository.query(query, params);
      return result.rows;
    } catch (error) {
      this.logger.error(
        { error, period, sensorIds },
        'Failed to get water level chart data'
      );
      throw error;
    }
  }

}
