import { describe, test, expect, beforeEach, jest } from '@jest/globals';
import express from 'express';
import request from 'supertest';
import { Logger } from 'pino';
import { createWaterLevelRoutes } from './water-level.routes';
import { TimescaleRepository } from '../repository/timescale.repository';
import { WaterLevelChartDataService } from '../services/water-level-chart-data.service';
import { WaterLevelChartFormatter } from '../transformers/water-level-chart-formatter';

// Mock the dependencies
jest.mock('../services/water-level-chart-data.service');
jest.mock('../transformers/water-level-chart-formatter');

describe('Water Level Routes', () => {
  let app: express.Application;
  let mockRepository: jest.Mocked<TimescaleRepository>;
  let mockLogger: jest.Mocked<Logger>;
  let mockService: jest.Mocked<WaterLevelChartDataService>;
  let mockFormatter: jest.Mocked<WaterLevelChartFormatter>;

  beforeEach(() => {
    // Clear all mocks
    jest.clearAllMocks();

    // Setup express app
    app = express();

    // Create mocks
    mockRepository = {
      query: jest.fn(),
    } as any;

    mockLogger = {
      info: jest.fn(),
      error: jest.fn(),
      warn: jest.fn(),
      debug: jest.fn(),
    } as any;

    // Mock service instance
    mockService = {
      getWaterLevelChartData: jest.fn(),
    } as any;

    // Mock formatter instance
    mockFormatter = {
      formatChartDataBySensor: jest.fn(),
    } as any;

    // Mock the constructors
    (WaterLevelChartDataService as any).mockImplementation(() => mockService);
    (WaterLevelChartFormatter as any).mockImplementation(() => mockFormatter);

    // Create routes
    const router = createWaterLevelRoutes({
      repository: mockRepository,
      logger: mockLogger,
    });

    app.use('/api/v1', router);
  });

  describe('GET /api/v1/water-levels/chart', () => {
    test('should return raw data only when includeSmoothed is false', async () => {
      // Mock service response
      const mockRows = [
        {
          time: new Date('2025-11-17T12:00:00Z'),
          sensor_id: 'AWD-6D47',
          avg_level: '15.5',
          min_level: '15.0',
          max_level: '16.0',
          avg_quality: '98.5',
          sample_count: '4',
          source: 'raw' as const,
        },
      ];

      // Mock formatter response
      const formattedResponse = {
        aggregation: {
          interval: '15 minutes',
          method: 'average',
        },
        period: '24h' as const,
        timeRange: {
          start: '2025-11-16T12:00:00Z',
          end: '2025-11-17T12:00:00Z',
        },
        localTimeZone: 'UTC',
        sensors: {
          'AWD-6D47': {
            sensorId: 'AWD-6D47',
            dataPoints: [
              {
                time: '2025-11-17T12:00:00Z',
                avgLevel: 15.5,
                minLevel: 15.0,
                maxLevel: 16.0,
                avgQuality: 98.5,
                sampleCount: 4,
              },
            ],
            stats: {
              totalSamples: 4,
              timeRange: {
                start: '2025-11-16T12:00:00Z',
                end: '2025-11-17T12:00:00Z',
              },
            },
          },
        },
        summary: {
          totalSensors: 1,
          totalDataPoints: 1,
        },
      };

      mockService.getWaterLevelChartData.mockResolvedValueOnce(mockRows);
      mockFormatter.formatChartDataBySensor.mockReturnValueOnce(formattedResponse);

      const response = await request(app)
        .get('/api/v1/water-levels/chart')
        .query({
          period: '24h',
          sensorIds: 'AWD-6D47',
          includeSmoothed: 'false',
        });

      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty('sensors');
      expect(response.body.sensors['AWD-6D47']).toHaveProperty('dataPoints');
      expect(response.body.sensors['AWD-6D47']).not.toHaveProperty('smoothedDataPoints');

      // Verify service was called with correct parameters
      expect(mockService.getWaterLevelChartData).toHaveBeenCalledWith(
        '24h',
        ['AWD-6D47'],
        false
      );
    });

    test('should return both raw and smoothed data when includeSmoothed is true', async () => {
      // Mock service response with mixed source data
      const mockRows = [
        {
          time: new Date('2025-11-17T12:00:00Z'),
          sensor_id: 'AWD-6D47',
          avg_level: '15.5',
          min_level: '15.0',
          max_level: '16.0',
          avg_quality: '98.5',
          sample_count: '4',
          source: 'raw' as const,
        },
        {
          time: new Date('2025-11-17T12:00:00Z'),
          sensor_id: 'AWD-6D47',
          avg_level: '15.3',
          min_level: '15.1',
          max_level: '15.5',
          avg_quality: '99.0',
          sample_count: '4',
          source: 'smoothed' as const,
        },
      ];

      const formattedResponse = {
        aggregation: { interval: '15 minutes', method: 'average' },
        period: '24h' as const,
        timeRange: { start: '2025-11-16T12:00:00Z', end: '2025-11-17T12:00:00Z' },
        localTimeZone: 'UTC',
        sensors: {
          'AWD-6D47': {
            sensorId: 'AWD-6D47',
            dataPoints: [mockRows[0]],
            smoothedDataPoints: [mockRows[1]],
          },
        },
        summary: { totalSensors: 1, totalDataPoints: 2 },
      };

      mockService.getWaterLevelChartData.mockResolvedValueOnce(mockRows);
      mockFormatter.formatChartDataBySensor.mockReturnValueOnce(formattedResponse);

      const response = await request(app)
        .get('/api/v1/water-levels/chart')
        .query({
          period: '24h',
          sensorIds: 'AWD-6D47',
          includeSmoothed: 'true',
        });

      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty('sensors');
      expect(response.body.sensors['AWD-6D47']).toHaveProperty('dataPoints');
      expect(response.body.sensors['AWD-6D47']).toHaveProperty('smoothedDataPoints');
    });

    test('should handle multiple sensors with includeSmoothed', async () => {
      const mockRows = [
        // AWD-6D47 raw
        {
          time: new Date('2025-11-17T12:00:00Z'),
          sensor_id: 'AWD-6D47',
          avg_level: '15.5',
          source: 'raw' as const,
        },
        // AWD-6D47 smoothed
        {
          time: new Date('2025-11-17T12:00:00Z'),
          sensor_id: 'AWD-6D47',
          avg_level: '15.3',
          source: 'smoothed' as const,
        },
        // AWD-9950 raw
        {
          time: new Date('2025-11-17T12:00:00Z'),
          sensor_id: 'AWD-9950',
          avg_level: '19.2',
          source: 'raw' as const,
        },
        // AWD-9950 smoothed
        {
          time: new Date('2025-11-17T12:00:00Z'),
          sensor_id: 'AWD-9950',
          avg_level: '19.1',
          source: 'smoothed' as const,
        },
      ];

      const formattedResponse = {
        aggregation: { interval: '15 minutes', method: 'average' },
        period: '24h' as const,
        timeRange: { start: '2025-11-16T12:00:00Z', end: '2025-11-17T12:00:00Z' },
        localTimeZone: 'UTC',
        sensors: {
          'AWD-6D47': {
            sensorId: 'AWD-6D47',
            dataPoints: [mockRows[0]],
            smoothedDataPoints: [mockRows[1]],
          },
          'AWD-9950': {
            sensorId: 'AWD-9950',
            dataPoints: [mockRows[2]],
            smoothedDataPoints: [mockRows[3]],
          },
        },
        summary: { totalSensors: 2, totalDataPoints: 4 },
      };

      mockService.getWaterLevelChartData.mockResolvedValueOnce(mockRows);
      mockFormatter.formatChartDataBySensor.mockReturnValueOnce(formattedResponse);

      const response = await request(app)
        .get('/api/v1/water-levels/chart')
        .query({
          period: '24h',
          sensorIds: 'AWD-6D47,AWD-9950',
          includeSmoothed: 'true',
        });

      expect(response.status).toBe(200);
      expect(response.body.sensors).toHaveProperty('AWD-6D47');
      expect(response.body.sensors).toHaveProperty('AWD-9950');
      expect(response.body.sensors['AWD-6D47']).toHaveProperty('smoothedDataPoints');
      expect(response.body.sensors['AWD-9950']).toHaveProperty('smoothedDataPoints');
      expect(response.body.summary.totalSensors).toBe(2);
    });

    test('should default to raw data only when includeSmoothed is not specified', async () => {
      const mockRows = [
        {
          time: new Date('2025-11-17T12:00:00Z'),
          sensor_id: 'AWD-6D47',
          avg_level: '15.5',
          source: 'raw' as const,
        },
      ];

      const formattedResponse = {
        aggregation: { interval: '15 minutes', method: 'average' },
        period: '24h' as const,
        timeRange: { start: '2025-11-16T12:00:00Z', end: '2025-11-17T12:00:00Z' },
        localTimeZone: 'UTC',
        sensors: {
          'AWD-6D47': {
            sensorId: 'AWD-6D47',
            dataPoints: [mockRows[0]],
          },
        },
        summary: { totalSensors: 1, totalDataPoints: 1 },
      };

      mockService.getWaterLevelChartData.mockResolvedValueOnce(mockRows);
      mockFormatter.formatChartDataBySensor.mockReturnValueOnce(formattedResponse);

      const response = await request(app)
        .get('/api/v1/water-levels/chart')
        .query({
          period: '24h',
          sensorIds: 'AWD-6D47',
        });

      expect(response.status).toBe(200);
      expect(response.body.sensors['AWD-6D47']).not.toHaveProperty('smoothedDataPoints');
    });

    test('should return 400 for invalid period', async () => {
      const response = await request(app)
        .get('/api/v1/water-levels/chart')
        .query({
          period: 'invalid',
        });

      expect(response.status).toBe(400);
      expect(response.body.error).toContain('Invalid period');
    });
  });
});