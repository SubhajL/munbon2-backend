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
    // Separate raw and smoothed data by sensor
    const rawSensorMap = new Map<string, WaterLevelReadingRow[]>();
    const smoothedSensorMap = new Map<string, WaterLevelReadingRow[]>();

    for (const row of rows) {
      const sensorId = row.sensor_id;
      const source = row.source || 'raw';

      if (source === 'smoothed') {
        if (!smoothedSensorMap.has(sensorId)) {
          smoothedSensorMap.set(sensorId, []);
        }
        smoothedSensorMap.get(sensorId)!.push(row);
      } else {
        if (!rawSensorMap.has(sensorId)) {
          rawSensorMap.set(sensorId, []);
        }
        rawSensorMap.get(sensorId)!.push(row);
      }
    }

    const sensors: Record<string, WaterLevelSensorData> = {};
    let totalDataPoints = 0;

    // Get all unique sensor IDs
    const allSensorIds = new Set([
      ...rawSensorMap.keys(),
      ...smoothedSensorMap.keys(),
    ]);

    for (const sensorId of allSensorIds) {
      const rawRows = rawSensorMap.get(sensorId) || [];
      const smoothedRows = smoothedSensorMap.get(sensorId) || [];

      // Format raw data points
      const dataPoints: WaterLevelDataPoint[] = rawRows.map((row) => ({
        time: this.formatTimestamp(row.time, timeZone),
        avgLevel: this.safeParseFloat(row.avg_level),
        minLevel: this.safeParseFloat(row.min_level),
        maxLevel: this.safeParseFloat(row.max_level),
        avgQuality: this.safeParseFloat(row.avg_quality),
        sampleCount: parseInt(String(row.sample_count), 10),
      }));

      // Format smoothed data points (if any)
      const smoothedDataPoints: WaterLevelDataPoint[] = smoothedRows.map((row) => ({
        time: this.formatTimestamp(row.time, timeZone),
        avgLevel: this.safeParseFloat(row.avg_level),
        minLevel: this.safeParseFloat(row.min_level),
        maxLevel: this.safeParseFloat(row.max_level),
        avgQuality: this.safeParseFloat(row.avg_quality),
        sampleCount: parseInt(String(row.sample_count), 10),
      }));

      const totalSamples =
        rawRows.reduce((sum, row) => sum + parseInt(String(row.sample_count), 10), 0) +
        smoothedRows.reduce((sum, row) => sum + parseInt(String(row.sample_count), 10), 0);

      const timeRange = getTimeRange(period);

      const sensorMeta = meta?.[sensorId];
      sensors[sensorId] = {
        sensorId,
        plotId: sensorMeta?.plotId ?? null,
        thresholds: sensorMeta?.thresholds ?? undefined,
        dataPoints,
        ...(smoothedDataPoints.length > 0 && { smoothedDataPoints }),
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
        totalSensors: allSensorIds.size,
        totalDataPoints,
      },
    };
  }

  /**
   * Format a date/timestamp to local timezone ISO string.
   */
  formatTimestamp(timestamp: Date | string, timeZone: string): string {
    const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
    // Include explicit offset for the requested timezone
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
