import { describe, test, expect, beforeEach, jest } from '@jest/globals';
import { Logger } from 'pino';
import { TimescaleRepository } from '../repository/timescale.repository';
import { WaterLevelChartDataService } from './water-level-chart-data.service';

describe('WaterLevelChartDataService - includeSmoothed feature', () => {
  let service: WaterLevelChartDataService;
  let mockRepository: jest.Mocked<TimescaleRepository>;
  let mockLogger: jest.Mocked<Logger>;

  beforeEach(() => {
    mockRepository = {
      query: jest.fn(),
    } as any;

    mockLogger = {
      info: jest.fn(),
      error: jest.fn(),
      warn: jest.fn(),
      debug: jest.fn(),
    } as any;

    service = new WaterLevelChartDataService(mockRepository, mockLogger);
  });

  describe('getWaterLevelChartData', () => {
    test('should query raw data only when includeSmoothed is false', async () => {
      const mockResult = {
        rows: [
          {
            time: new Date('2025-11-17T12:00:00Z'),
            sensor_id: 'AWD-6D47',
            avg_level: '15.5',
            source: 'raw',
          },
        ],
      };

      mockRepository.query.mockResolvedValueOnce(mockResult);

      const result = await service.getWaterLevelChartData('24h', ['AWD-6D47'], false);

      // Check that query was called
      expect(mockRepository.query).toHaveBeenCalledTimes(1);

      // Verify the query contains only raw table
      const query = mockRepository.query.mock.calls[0][0] as string;
      expect(query).toContain('FROM water_level_readings');
      expect(query).not.toContain('smoothed_water_level_readings');
      expect(query).not.toContain('UNION ALL');

      // Verify result
      expect(result).toEqual(mockResult.rows);
    });

    test('should query both raw and smoothed data when includeSmoothed is true', async () => {
      const mockResult = {
        rows: [
          {
            time: new Date('2025-11-17T12:00:00Z'),
            sensor_id: 'AWD-6D47',
            avg_level: '15.5',
            source: 'raw',
          },
          {
            time: new Date('2025-11-17T12:00:00Z'),
            sensor_id: 'AWD-6D47',
            avg_level: '15.3',
            source: 'smoothed',
          },
        ],
      };

      mockRepository.query.mockResolvedValueOnce(mockResult);

      const result = await service.getWaterLevelChartData('24h', ['AWD-6D47'], true);

      // Check that query was called
      expect(mockRepository.query).toHaveBeenCalledTimes(1);

      // Verify the query contains UNION ALL
      const query = mockRepository.query.mock.calls[0][0] as string;
      expect(query).toContain('water_level_readings');
      expect(query).toContain('smoothed_water_level_readings');
      expect(query).toContain('UNION ALL');
      expect(query).toContain("'raw' as source");
      expect(query).toContain("'smoothed' as source");

      // Verify result
      expect(result).toEqual(mockResult.rows);
      expect(result).toHaveLength(2);
    });

    test('should handle sensor ID filtering with includeSmoothed', async () => {
      const mockResult = { rows: [] };
      mockRepository.query.mockResolvedValueOnce(mockResult);

      const sensorIds = ['AWD-6D47', 'AWD-9950'];
      await service.getWaterLevelChartData('7d', sensorIds, true);

      // Verify query parameters
      expect(mockRepository.query).toHaveBeenCalledWith(
        expect.any(String),
        expect.arrayContaining([
          expect.any(Date), // start time
          expect.any(Date), // end time
          sensorIds,        // sensor IDs array
        ])
      );

      // Verify the query has sensor filtering
      const query = mockRepository.query.mock.calls[0][0] as string;
      expect(query).toContain('sensor_id = ANY($3)');
    });

    test('should handle no sensor ID filtering', async () => {
      const mockResult = { rows: [] };
      mockRepository.query.mockResolvedValueOnce(mockResult);

      await service.getWaterLevelChartData('3d', undefined, true);

      // Verify query parameters (no sensor IDs)
      expect(mockRepository.query).toHaveBeenCalledWith(
        expect.any(String),
        expect.arrayContaining([
          expect.any(Date), // start time
          expect.any(Date), // end time
        ])
      );

      // Verify the query doesn't have sensor filtering
      const query = mockRepository.query.mock.calls[0][0] as string;
      expect(query).not.toContain('sensor_id = ANY($3)');
    });

    test('should default to includeSmoothed=false when not specified', async () => {
      const mockResult = { rows: [] };
      mockRepository.query.mockResolvedValueOnce(mockResult);

      await service.getWaterLevelChartData('24h');

      const query = mockRepository.query.mock.calls[0][0] as string;
      expect(query).not.toContain('UNION ALL');
      expect(query).not.toContain('smoothed_water_level_readings');
    });

    test('should handle errors gracefully', async () => {
      const error = new Error('Database error');
      mockRepository.query.mockRejectedValueOnce(error);

      await expect(service.getWaterLevelChartData('24h', undefined, true))
        .rejects.toThrow('Database error');

      expect(mockLogger.error).toHaveBeenCalledWith(
        expect.objectContaining({
          error,
          period: '24h',
          sensorIds: undefined,
        }),
        'Failed to get water level chart data'
      );
    });

    test('should use 15-minute time buckets', async () => {
      const mockResult = { rows: [] };
      mockRepository.query.mockResolvedValueOnce(mockResult);

      await service.getWaterLevelChartData('24h', undefined, true);

      const query = mockRepository.query.mock.calls[0][0] as string;
      expect(query).toContain("time_bucket('15 minutes'::interval, time)");
    });

    test('should order results by time, sensor_id, and source', async () => {
      const mockResult = { rows: [] };
      mockRepository.query.mockResolvedValueOnce(mockResult);

      await service.getWaterLevelChartData('24h', undefined, true);

      const query = mockRepository.query.mock.calls[0][0] as string;
      expect(query).toContain('ORDER BY time ASC, sensor_id, source');
    });
  });
});