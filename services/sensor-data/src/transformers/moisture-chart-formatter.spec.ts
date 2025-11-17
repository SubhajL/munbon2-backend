import { MoistureChartFormatter } from './moisture-chart-formatter';
import { MoistureReadingRow } from '../types/moisture-chart.types';

describe('MoistureChartFormatter', () => {
  let formatter: MoistureChartFormatter;

  beforeEach(() => {
    formatter = new MoistureChartFormatter();
  });

describe('formatChartDataBySensor', () => {
    it('groups 12 sensors into separate datasets', () => {
      const rows: MoistureReadingRow[] = [];
      for (let i = 1; i <= 12; i++) {
        rows.push({
          time: new Date('2025-11-03T12:00:00Z'),
          sensor_id: `MS-00001-0000${i}`,
          moisture_surface_pct: 65.5,
          moisture_deep_pct: 50.2,
          avg_moisture_surface: 65.5,
          min_moisture_surface: 60,
          max_moisture_surface: 70,
          avg_moisture_deep: 50.2,
          min_moisture_deep: 45,
          max_moisture_deep: 55,
          sample_count: 1,
        });
      }

      const response = formatter.formatChartDataBySensor(rows, '24h', 'UTC');

      expect(Object.keys(response.sensors)).toHaveLength(12);
      for (let i = 1; i <= 12; i++) {
        expect(response.sensors[`MS-00001-0000${i}`]).toBeDefined();
      }
    });

    it('converts UTC timestamps to local timezone', () => {
      const rows: MoistureReadingRow[] = [
        {
          time: new Date('2025-11-03T12:00:00Z'),
          sensor_id: 'MS-00001-00001',
          moisture_surface_pct: 65.5,
          moisture_deep_pct: 50.2,
          avg_moisture_surface: 65.5,
          min_moisture_surface: 60,
          max_moisture_surface: 70,
          avg_moisture_deep: 50.2,
          min_moisture_deep: 45,
          max_moisture_deep: 55,
          sample_count: 1,
        },
      ];

      const response = formatter.formatChartDataBySensor(rows, '24h', 'UTC');
      const dataPoint = response.sensors['MS-00001-00001'].dataPoints[0];

      // UTC time should be preserved in format
      expect(dataPoint.time).toMatch(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
    });

    it('handles null moisture values gracefully', () => {
      const rows: MoistureReadingRow[] = [
        {
          time: new Date('2025-11-03T12:00:00Z'),
          sensor_id: 'MS-00001-00001',
          moisture_surface_pct: 0,
          moisture_deep_pct: 0,
          avg_moisture_surface: null as any,
          min_moisture_surface: null as any,
          max_moisture_surface: null as any,
          avg_moisture_deep: null as any,
          min_moisture_deep: null as any,
          max_moisture_deep: null as any,
          sample_count: 0,
        },
      ];

      const response = formatter.formatChartDataBySensor(rows, '24h', 'UTC');
      const dataPoint = response.sensors['MS-00001-00001'].dataPoints[0];

      expect(dataPoint.avgMoistureSurface).toBeNull();
      expect(dataPoint.avgMoistureDeep).toBeNull();
      expect(dataPoint.minMoistureSurface).toBeNull();
    });

    it('returns per-sensor data with correct structure', () => {
      const rows: MoistureReadingRow[] = [
        {
          time: new Date('2025-11-03T12:00:00Z'),
          sensor_id: 'MS-00001-00001',
          moisture_surface_pct: 65.5,
          moisture_deep_pct: 50.2,
          avg_moisture_surface: 65.5,
          min_moisture_surface: 60,
          max_moisture_surface: 70,
          avg_moisture_deep: 50.2,
          min_moisture_deep: 45,
          max_moisture_deep: 55,
          sample_count: 96,
        },
      ];

      const response = formatter.formatChartDataBySensor(rows, '24h', 'UTC');

      expect(response.aggregation).toEqual({
        interval: '15 minutes',
        method: 'average',
      });
      expect(response.period).toBe('24h');
      expect(response.localTimeZone).toBe('UTC');
      expect(response.sensors['MS-00001-00001']).toBeDefined();
      expect(response.sensors['MS-00001-00001'].sensorId).toBe(
        'MS-00001-00001'
      );
      expect(response.sensors['MS-00001-00001'].dataPoints).toHaveLength(1);
      expect(response.sensors['MS-00001-00001'].stats.totalSamples).toBe(96);
    });

    it('aggregates multiple data points per sensor', () => {
      const rows: MoistureReadingRow[] = [
        {
          time: new Date('2025-11-03T12:00:00Z'),
          sensor_id: 'MS-00001-00001',
          moisture_surface_pct: 65.5,
          moisture_deep_pct: 50.2,
          avg_moisture_surface: 65.5,
          min_moisture_surface: 60,
          max_moisture_surface: 70,
          avg_moisture_deep: 50.2,
          min_moisture_deep: 45,
          max_moisture_deep: 55,
          sample_count: 96,
        },
        {
          time: new Date('2025-11-03T12:15:00Z'),
          sensor_id: 'MS-00001-00001',
          moisture_surface_pct: 66.0,
          moisture_deep_pct: 50.5,
          avg_moisture_surface: 66.0,
          min_moisture_surface: 61,
          max_moisture_surface: 71,
          avg_moisture_deep: 50.5,
          min_moisture_deep: 46,
          max_moisture_deep: 56,
          sample_count: 96,
        },
      ];

      const response = formatter.formatChartDataBySensor(rows, '24h', 'UTC');

      expect(
        response.sensors['MS-00001-00001'].dataPoints
      ).toHaveLength(2);
      expect(
        response.sensors['MS-00001-00001'].stats.totalSamples
      ).toBe(192);
    });

    it('calculates summary with total sensors and data points', () => {
      const rows: MoistureReadingRow[] = [
        {
          time: new Date('2025-11-03T12:00:00Z'),
          sensor_id: 'MS-00001-00001',
          moisture_surface_pct: 65.5,
          moisture_deep_pct: 50.2,
          avg_moisture_surface: 65.5,
          min_moisture_surface: 60,
          max_moisture_surface: 70,
          avg_moisture_deep: 50.2,
          min_moisture_deep: 45,
          max_moisture_deep: 55,
          sample_count: 10,
        },
        {
          time: new Date('2025-11-03T12:00:00Z'),
          sensor_id: 'MS-00001-00002',
          moisture_surface_pct: 64.5,
          moisture_deep_pct: 49.2,
          avg_moisture_surface: 64.5,
          min_moisture_surface: 59,
          max_moisture_surface: 69,
          avg_moisture_deep: 49.2,
          min_moisture_deep: 44,
          max_moisture_deep: 54,
          sample_count: 10,
        },
      ];

      const response = formatter.formatChartDataBySensor(rows, '24h', 'UTC');

      expect(response.summary.totalSensors).toBe(2);
      expect(response.summary.totalDataPoints).toBe(2);
    });

    it('handles empty row array', () => {
      const response = formatter.formatChartDataBySensor([], '24h', 'UTC');

      expect(Object.keys(response.sensors)).toHaveLength(0);
      expect(response.summary.totalSensors).toBe(0);
      expect(response.summary.totalDataPoints).toBe(0);
    });

    it('respects all 4 period values', () => {
      const rows: MoistureReadingRow[] = [];
      const periods = ['24h', '3d', '7d', '14d'] as const;

      periods.forEach((period) => {
        const response = formatter.formatChartDataBySensor(rows, period, 'UTC');
        expect(response.period).toBe(period);
      });
    });

    it('includes time range in response', () => {
      const now = new Date();
      const rows: MoistureReadingRow[] = [
        {
          time: now,
          sensor_id: 'MS-00001-00001',
          moisture_surface_pct: 65.5,
          moisture_deep_pct: 50.2,
          avg_moisture_surface: 65.5,
          min_moisture_surface: 60,
          max_moisture_surface: 70,
          avg_moisture_deep: 50.2,
          min_moisture_deep: 45,
          max_moisture_deep: 55,
          sample_count: 1,
        },
      ];

      const response = formatter.formatChartDataBySensor(rows, '24h', 'UTC');

      expect(response.timeRange).toBeDefined();
      expect(response.timeRange.start).toBeDefined();
      expect(response.timeRange.end).toBeDefined();
    });

    it('includes plotId and thresholds when metadata provided', () => {
      const rows: MoistureReadingRow[] = [
        {
          time: new Date('2025-11-03T12:00:00Z'),
          sensor_id: '0001-0001',
          moisture_surface_pct: 65.5,
          moisture_deep_pct: 50.2,
          avg_moisture_surface: 65.5,
          min_moisture_surface: 60,
          max_moisture_surface: 70,
          avg_moisture_deep: 50.2,
          min_moisture_deep: 45,
          max_moisture_deep: 55,
          sample_count: 1,
        },
      ];
      const meta = {
        '0001-0001': { plotId: 'plot-abc', thresholds: { lower: 20, upper: 30 } },
      } as const;
      const response = formatter.formatChartDataBySensor(rows, '24h', 'UTC', meta as any);
      const sensor = response.sensors['0001-0001'];
      expect(sensor.plotId).toBe('plot-abc');
      expect(sensor.thresholds).toEqual({ lower: 20, upper: 30 });
    });
  });

  describe('formatTimestamp', () => {
    it('returns ISO string in UTC timezone', () => {
      const date = new Date('2025-11-03T12:00:00Z');
      const result = formatter.formatTimestamp(date, 'UTC');

      expect(result).toMatch(/^2025-11-03T12:00:00/);
    });

    it('handles date objects', () => {
      const date = new Date('2025-01-15T08:30:45Z');
      const result = formatter.formatTimestamp(date, 'UTC');

      expect(result).toMatch(/2025-01-15T08:30:45/);
    });

    it('handles string timestamps', () => {
      const result = formatter.formatTimestamp(
        '2025-11-03T12:00:00Z' as any,
        'UTC'
      );

      expect(typeof result).toBe('string');
      expect(result).toMatch(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
    });
  });
});
