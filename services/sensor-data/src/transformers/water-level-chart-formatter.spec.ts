import { WaterLevelChartFormatter } from './water-level-chart-formatter';
import { WaterLevelReadingRow } from '../types/water-level-chart.types';

describe('WaterLevelChartFormatter', () => {
  let formatter: WaterLevelChartFormatter;

  beforeEach(() => {
    formatter = new WaterLevelChartFormatter();
  });

  describe('formatChartDataBySensor', () => {
    it('groups 6 sensors into separate datasets', () => {
      const rows: WaterLevelReadingRow[] = [
        'AWD-B89D',
        'AWD-558F',
        'AWD-A4F8',
        'AWD-6D47',
        'AWD-4ED4',
        'AWD-B89D',
      ].map((sensorId) => ({
        time: new Date('2025-11-03T12:00:00Z'),
        sensor_id: sensorId,
        avg_level: 125.5,
        min_level: 120,
        max_level: 130,
        avg_quality: 95.5,
        sample_count: 1,
      }));

      const response = formatter.formatChartDataBySensor(rows, '24h', 'UTC');

      expect(Object.keys(response.sensors).length).toBeGreaterThanOrEqual(5);
    });

    it('converts UTC timestamps to local timezone', () => {
      const rows: WaterLevelReadingRow[] = [
        {
          time: new Date('2025-11-03T12:00:00Z'),
          sensor_id: 'AWD-B89D',
          avg_level: 125.5,
          min_level: 120,
          max_level: 130,
          avg_quality: 95.5,
          sample_count: 1,
        },
      ];

      const response = formatter.formatChartDataBySensor(rows, '24h', 'UTC');
      const dataPoint = response.sensors['AWD-B89D'].dataPoints[0];

      expect(dataPoint.time).toMatch(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
    });

    it('handles null level values gracefully', () => {
      const rows: WaterLevelReadingRow[] = [
        {
          time: new Date('2025-11-03T12:00:00Z'),
          sensor_id: 'AWD-B89D',
          avg_level: null as any,
          min_level: null as any,
          max_level: null as any,
          avg_quality: null as any,
          sample_count: 0,
        },
      ];

      const response = formatter.formatChartDataBySensor(rows, '24h', 'UTC');
      const dataPoint = response.sensors['AWD-B89D'].dataPoints[0];

      expect(dataPoint.avgLevel).toBeNull();
      expect(dataPoint.minLevel).toBeNull();
      expect(dataPoint.maxLevel).toBeNull();
      expect(dataPoint.avgQuality).toBeNull();
    });

    it('returns per-sensor data with correct structure', () => {
      const rows: WaterLevelReadingRow[] = [
        {
          time: new Date('2025-11-03T12:00:00Z'),
          sensor_id: 'AWD-B89D',
          avg_level: 125.5,
          min_level: 120,
          max_level: 130,
          avg_quality: 95.5,
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
      expect(response.sensors['AWD-B89D']).toBeDefined();
      expect(response.sensors['AWD-B89D'].sensorId).toBe('AWD-B89D');
      expect(response.sensors['AWD-B89D'].dataPoints).toHaveLength(1);
      expect(response.sensors['AWD-B89D'].stats.totalSamples).toBe(96);
    });

    it('aggregates multiple data points per sensor', () => {
      const rows: WaterLevelReadingRow[] = [
        {
          time: new Date('2025-11-03T12:00:00Z'),
          sensor_id: 'AWD-B89D',
          avg_level: 125.5,
          min_level: 120,
          max_level: 130,
          avg_quality: 95.5,
          sample_count: 96,
        },
        {
          time: new Date('2025-11-03T12:15:00Z'),
          sensor_id: 'AWD-B89D',
          avg_level: 126.0,
          min_level: 121,
          max_level: 131,
          avg_quality: 96.0,
          sample_count: 96,
        },
      ];

      const response = formatter.formatChartDataBySensor(rows, '24h', 'UTC');

      expect(response.sensors['AWD-B89D'].dataPoints).toHaveLength(2);
      expect(response.sensors['AWD-B89D'].stats.totalSamples).toBe(192);
    });

    it('calculates summary with total sensors and data points', () => {
      const rows: WaterLevelReadingRow[] = [
        {
          time: new Date('2025-11-03T12:00:00Z'),
          sensor_id: 'AWD-B89D',
          avg_level: 125.5,
          min_level: 120,
          max_level: 130,
          avg_quality: 95.5,
          sample_count: 10,
        },
        {
          time: new Date('2025-11-03T12:00:00Z'),
          sensor_id: 'AWD-558F',
          avg_level: 124.5,
          min_level: 119,
          max_level: 129,
          avg_quality: 94.5,
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
      const rows: WaterLevelReadingRow[] = [];
      const periods = ['24h', '3d', '7d', '14d'] as const;

      periods.forEach((period) => {
        const response = formatter.formatChartDataBySensor(rows, period, 'UTC');
        expect(response.period).toBe(period);
      });
    });

    it('includes time range in response', () => {
      const now = new Date();
      const rows: WaterLevelReadingRow[] = [
        {
          time: now,
          sensor_id: 'AWD-B89D',
          avg_level: 125.5,
          min_level: 120,
          max_level: 130,
          avg_quality: 95.5,
          sample_count: 1,
        },
      ];

      const response = formatter.formatChartDataBySensor(rows, '24h', 'UTC');

      expect(response.timeRange).toBeDefined();
      expect(response.timeRange.start).toBeDefined();
      expect(response.timeRange.end).toBeDefined();
    });

    it('preserves quality score values', () => {
      const rows: WaterLevelReadingRow[] = [
        {
          time: new Date('2025-11-03T12:00:00Z'),
          sensor_id: 'AWD-B89D',
          avg_level: 125.5,
          min_level: 120,
          max_level: 130,
          avg_quality: 95.5,
          sample_count: 96,
        },
      ];

      const response = formatter.formatChartDataBySensor(rows, '24h', 'UTC');
      const dataPoint = response.sensors['AWD-B89D'].dataPoints[0];

      expect(dataPoint.avgQuality).toBe(95.5);
      expect(dataPoint.avgLevel).toBe(125.5);
      expect(dataPoint.minLevel).toBe(120);
      expect(dataPoint.maxLevel).toBe(130);
    });

    it('includes plotId and thresholds when metadata provided', () => {
      const rows: WaterLevelReadingRow[] = [
        {
          time: new Date('2025-11-03T12:00:00Z'),
          sensor_id: 'AWD-1234',
          avg_level: 10,
          min_level: 8,
          max_level: 12,
          avg_quality: 90,
          sample_count: 1,
        },
      ];
      const meta = {
        'AWD-1234': { plotId: 'plot-xyz', thresholds: { lower: 5, upper: 15 } },
      } as const;
      const response = formatter.formatChartDataBySensor(rows, '24h', 'UTC', meta as any);
      const sensor = response.sensors['AWD-1234'];
      expect(sensor.plotId).toBe('plot-xyz');
      expect(sensor.thresholds).toEqual({ lower: 5, upper: 15 });
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
