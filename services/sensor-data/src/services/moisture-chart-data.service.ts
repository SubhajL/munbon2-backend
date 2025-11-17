import { Logger } from 'pino';
import { TimescaleRepository } from '../repository/timescale.repository';
import { MoistureReadingRow } from '../types/moisture-chart.types';
import {
  parseTimePeriod,
  getTimeRange,
} from '../utils/time-period.utils';

export class MoistureChartDataService {
  constructor(
    private readonly repository: TimescaleRepository,
    private readonly logger: Logger
  ) {}

  /**
   * Get moisture chart data for given period, optionally filtered by sensor IDs.
   * Returns raw database rows ordered chronologically.
   */
  async getMoistureChartData(
    period: string,
    sensorIds?: string[]
  ): Promise<MoistureReadingRow[]> {
    try {
      // Validate and parse period
      const validatedPeriod = parseTimePeriod(period);
      const timeRange = getTimeRange(validatedPeriod);

      // Build query with optional sensor filter
      let query = `
        SELECT 
          time_bucket('15 minutes'::interval, time) AS time,
          sensor_id,
          AVG(moisture_surface_pct) as avg_moisture_surface,
          MIN(moisture_surface_pct) as min_moisture_surface,
          MAX(moisture_surface_pct) as max_moisture_surface,
          AVG(moisture_deep_pct) as avg_moisture_deep,
          MIN(moisture_deep_pct) as min_moisture_deep,
          MAX(moisture_deep_pct) as max_moisture_deep,
          COUNT(*) as sample_count
        FROM moisture_readings
        WHERE time >= $1 AND time <= $2
      `;

      const params: any[] = [timeRange.start, timeRange.end];

      if (sensorIds && sensorIds.length > 0) {
        const normalizedIds = this.normalizeSensorIds(sensorIds);
        query += ' AND sensor_id = ANY($3)';
        params.push(normalizedIds);
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
        'Failed to get moisture chart data'
      );
      throw error;
    }
  }

  /**
   * Normalize sensor IDs from short form (e.g., "0001-0001") to full form (e.g., "MS-00001-00001").
   * Already full-form IDs are returned unchanged.
   * 
   * Note: Water level sensors (AWD-XXXX) don't need this because they're stored in canonical
   * form in the database. Moisture sensors accept user-provided short-form IDs in the API.
   */
  normalizeSensorIds(rawIds: string[]): string[] {
    return rawIds.map((id) => {
      // Already in full form
      if (id.startsWith('MS-')) {
        return id;
      }

      // Short form: "1-1" or "0001-0001" -> "MS-00001-00001"
      const match = id.match(/^(\d{1,5})-(\d{1,5})$/);
      if (match) {
        const gw = match[1].padStart(5, '0');
        const sn = match[2].padStart(5, '0');
        return `MS-${gw}-${sn}`;
      }

      // Return as-is if not recognized
      return id;
    });
  }
}
