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
   */
  async getWaterLevelChartData(
    period: string,
    sensorIds?: string[]
  ): Promise<WaterLevelReadingRow[]> {
    try {
      const validatedPeriod = parseTimePeriod(period);
      const timeRange = getTimeRange(validatedPeriod);

      let query = `
        SELECT 
          time_bucket('15 minutes'::interval, time) AS time,
          sensor_id,
          AVG(level_cm) as avg_level,
          MIN(level_cm) as min_level,
          MAX(level_cm) as max_level,
          AVG(quality_score) as avg_quality,
          COUNT(*) as sample_count
        FROM water_level_readings
        WHERE time >= $1 AND time <= $2
      `;

      const params: any[] = [timeRange.start, timeRange.end];

      if (sensorIds && sensorIds.length > 0) {
        query += ' AND sensor_id = ANY($3)';
        params.push(sensorIds);
      }

      query += `
        GROUP BY time_bucket('15 minutes'::interval, time), sensor_id
        ORDER BY time ASC;
      `;

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
