import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import {
  MoistureReadingRow,
  SensorDataPoint,
  SensorChartData,
  MoistureChartResponse,
} from '../types/moisture-chart.types';
import { getTimeRange } from '../utils/time-period.utils';

dayjs.extend(utc);
dayjs.extend(timezone);

export class MoistureChartFormatter {
  /**
   * Format raw database rows into per-sensor chart structure with local timestamps.
   * Each sensor gets its own dataset with independent data points.
   */
  formatChartDataBySensor(
    rows: MoistureReadingRow[],
    period: '24h' | '3d' | '7d' | '14d',
    timeZone: string,
    meta?: Record<string, { plotId?: string | null; thresholds?: { lower: number | null; upper: number | null } }>
  ): MoistureChartResponse {
    // Group rows by sensor_id
    const sensorMap = new Map<string, MoistureReadingRow[]>();
    for (const row of rows) {
      const sensorId = row.sensor_id;
      if (!sensorMap.has(sensorId)) {
        sensorMap.set(sensorId, []);
      }
      sensorMap.get(sensorId)!.push(row);
    }

    // Transform each sensor's rows into chart data
    const sensors: Record<string, SensorChartData> = {};
    let totalDataPoints = 0;

    for (const [sensorId, sensorRows] of sensorMap.entries()) {
      const toPoint = (row: MoistureReadingRow): SensorDataPoint => ({
        time: this.formatTimestamp(row.time, timeZone),
        avgMoistureSurface: this.safeParseFloat(row.avg_moisture_surface),
        minMoistureSurface: this.safeParseFloat(row.min_moisture_surface),
        maxMoistureSurface: this.safeParseFloat(row.max_moisture_surface),
        avgMoistureDeep: this.safeParseFloat(row.avg_moisture_deep),
        minMoistureDeep: this.safeParseFloat(row.min_moisture_deep),
        maxMoistureDeep: this.safeParseFloat(row.max_moisture_deep),
        sampleCount: parseInt(String(row.sample_count), 10),
      });

      const rawRows = sensorRows.filter((r) => !r.source || r.source === 'raw');
      const smoothedRows = sensorRows.filter((r) => r.source === 'smoothed');

      const dataPoints: SensorDataPoint[] = rawRows.map(toPoint);
      const smoothedDataPoints: SensorDataPoint[] = smoothedRows.map(toPoint);

      const totalSamples = sensorRows.reduce(
        (sum, row) => sum + parseInt(String(row.sample_count), 10),
        0
      );

      const timeRange = getTimeRange(period);

      const sensorMeta = meta?.[sensorId];
      sensors[sensorId] = {
        sensorId,
        plotId: sensorMeta?.plotId ?? null,
        thresholds: sensorMeta?.thresholds ?? undefined,
        dataPoints,
        smoothedDataPoints: smoothedDataPoints.length ? smoothedDataPoints : undefined,
        stats: {
          totalSamples,
          timeRange: {
            start: this.formatTimestamp(timeRange.start, timeZone),
            end: this.formatTimestamp(timeRange.end, timeZone),
          },
        },
      };

      totalDataPoints += dataPoints.length + smoothedDataPoints.length;
    }

    const timeRange = getTimeRange(period);

    return {
      aggregation: {
        interval: '15 minutes',
        method: 'average',
      },
      period,
      timeRange: {
        start: this.formatTimestamp(timeRange.start, timeZone),
        end: this.formatTimestamp(timeRange.end, timeZone),
      },
      localTimeZone: timeZone,
      sensors,
      summary: {
        totalSensors: sensorMap.size,
        totalDataPoints,
      },
    };
  }

  /**
   * Format a date/timestamp to local timezone ISO string.
   */
  formatTimestamp(
    timestamp: Date | string,
    timeZone: string
  ): string {
    // Convert to the requested timezone and include the explicit offset in the string
    // so clients can render wall-time correctly without extra shifting.
    const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
    return dayjs.utc(date).tz(timeZone).format();
  }

  /**
   * Safely parse string/number to float, returning null for null/undefined/NaN.
   */
  private safeParseFloat(value: any): number | null {
    if (value === null || value === undefined) {
      return null;
    }

    const num = parseFloat(String(value));
    return Number.isNaN(num) ? null : num;
  }
}
