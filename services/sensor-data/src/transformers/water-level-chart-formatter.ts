import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import {
  WaterLevelReadingRow,
  WaterLevelDataPoint,
  WaterLevelSensorData,
  WaterLevelChartResponse,
} from '../types/water-level-chart.types';
import { getTimeRange } from '../utils/time-period.utils';

dayjs.extend(utc);
dayjs.extend(timezone);

export class WaterLevelChartFormatter {
  /**
   * Format raw database rows into per-sensor chart structure with local timestamps.
   * Each sensor gets its own dataset with independent data points.
   */
  formatChartDataBySensor(
    rows: WaterLevelReadingRow[],
    period: '24h' | '3d' | '7d' | '14d',
    timeZone: string,
    meta?: Record<string, { plotId?: string | null; thresholds?: { lower: number | null; upper: number | null } }>
  ): WaterLevelChartResponse {
    const sensorMap = new Map<string, WaterLevelReadingRow[]>();
    for (const row of rows) {
      const sensorId = row.sensor_id;
      if (!sensorMap.has(sensorId)) {
        sensorMap.set(sensorId, []);
      }
      sensorMap.get(sensorId)!.push(row);
    }

    const sensors: Record<string, WaterLevelSensorData> = {};
    let totalDataPoints = 0;

    for (const [sensorId, sensorRows] of sensorMap.entries()) {
      const dataPoints: WaterLevelDataPoint[] = sensorRows.map((row) => ({
        time: this.formatTimestamp(row.time, timeZone),
        avgLevel: this.safeParseFloat(row.avg_level),
        minLevel: this.safeParseFloat(row.min_level),
        maxLevel: this.safeParseFloat(row.max_level),
        avgQuality: this.safeParseFloat(row.avg_quality),
        sampleCount: parseInt(String(row.sample_count), 10),
      }));

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
        stats: {
          totalSamples,
          timeRange: {
            start: this.formatTimestamp(timeRange.start, timeZone),
            end: this.formatTimestamp(timeRange.end, timeZone),
          },
        },
      };

      totalDataPoints += dataPoints.length;
    }

    const timeRange = getTimeRange(period);

    return {
      aggregation: {
        interval: '15 minutes',
        method: 'average',
      },
      period,
      timeRange: {
        start: timeRange.start.toISOString(),
        end: timeRange.end.toISOString(),
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
  formatTimestamp(timestamp: Date | string, timeZone: string): string {
    const date =
      typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
    return dayjs.utc(date).tz(timeZone).toISOString();
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
