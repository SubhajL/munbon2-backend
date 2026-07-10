import { describe, test, expect, beforeEach, jest } from '@jest/globals';
import express from 'express';
import request from 'supertest';
import { createWaterLevelRoutes } from './water-level.routes';
import type { WaterLevelReadingRow } from '../types/water-level-chart.types';

// Create mock implementations
const mockGetWaterLevelChartData = jest.fn<() => Promise<WaterLevelReadingRow[]>>();
const mockFormatChartDataBySensor = jest.fn();

// Mock the dependencies
jest.mock('../services/water-level-chart-data.service', () => ({
  WaterLevelChartDataService: jest.fn().mockImplementation(() => ({
    getWaterLevelChartData: mockGetWaterLevelChartData,
  })),
}));

jest.mock('../transformers/water-level-chart-formatter', () => ({
  WaterLevelChartFormatter: jest.fn().mockImplementation(() => ({
    formatChartDataBySensor: mockFormatChartDataBySensor,
  })),
}));

describe('Water Level Routes - Chart Endpoint', () => {
  let app: express.Application;

  beforeEach(() => {
    // Clear all mocks
    jest.clearAllMocks();

    // Setup express app
    app = express();

    // Create routes
    const router = createWaterLevelRoutes({
      repository: {} as any,
      logger: {
        info: jest.fn(),
        error: jest.fn(),
        warn: jest.fn(),
        debug: jest.fn(),
      } as any,
    });

    app.use('/api/v1', router);
  });

  test('should return raw data only when includeSmoothed is false', async () => {
    const mockRows: WaterLevelReadingRow[] = [
      {
        time: new Date('2025-11-17T12:00:00Z'),
        sensor_id: 'AWD-6D47',
        avg_level: '15.5',
        source: 'raw' as const,
      },
    ];

    const formattedResponse = {
      sensors: {
        'AWD-6D47': {
          sensorId: 'AWD-6D47',
          dataPoints: [{ time: '2025-11-17T12:00:00Z', avgLevel: 15.5 }],
        },
      },
    };

    mockGetWaterLevelChartData.mockResolvedValueOnce(mockRows);
    mockFormatChartDataBySensor.mockReturnValueOnce(formattedResponse);

    const response = await request(app)
      .get('/api/v1/water-levels/chart')
      .query({
        period: '24h',
        sensorIds: 'AWD-6D47',
        includeSmoothed: 'false',
      });

    expect(response.status).toBe(200);
    expect(response.body).toEqual(formattedResponse);
    expect(mockGetWaterLevelChartData).toHaveBeenCalledWith('24h', ['AWD-6D47'], false);
  });

  test('should return both raw and smoothed data when includeSmoothed is true', async () => {
    const mockRows: WaterLevelReadingRow[] = [
      {
        time: new Date('2025-11-17T12:00:00Z'),
        sensor_id: 'AWD-6D47',
        avg_level: '15.5',
        source: 'raw' as const,
      },
      {
        time: new Date('2025-11-17T12:00:00Z'),
        sensor_id: 'AWD-6D47',
        avg_level: '15.3',
        source: 'smoothed' as const,
      },
    ];

    const formattedResponse = {
      sensors: {
        'AWD-6D47': {
          sensorId: 'AWD-6D47',
          dataPoints: [{ time: '2025-11-17T12:00:00Z', avgLevel: 15.5 }],
          smoothedDataPoints: [{ time: '2025-11-17T12:00:00Z', avgLevel: 15.3 }],
        },
      },
    };

    mockGetWaterLevelChartData.mockResolvedValueOnce(mockRows);
    mockFormatChartDataBySensor.mockReturnValueOnce(formattedResponse);

    const response = await request(app)
      .get('/api/v1/water-levels/chart')
      .query({
        period: '24h',
        sensorIds: 'AWD-6D47',
        includeSmoothed: 'true',
      });

    expect(response.status).toBe(200);
    expect(response.body).toEqual(formattedResponse);
    expect(mockGetWaterLevelChartData).toHaveBeenCalledWith('24h', ['AWD-6D47'], true);
  });

  test('should default to raw data only when includeSmoothed is not specified', async () => {
    mockGetWaterLevelChartData.mockResolvedValueOnce([]);
    mockFormatChartDataBySensor.mockReturnValueOnce({ sensors: {} });

    await request(app)
      .get('/api/v1/water-levels/chart')
      .query({ period: '24h' });

    expect(mockGetWaterLevelChartData).toHaveBeenCalledWith('24h', undefined, false);
  });

  test('should handle multiple sensors', async () => {
    mockGetWaterLevelChartData.mockResolvedValueOnce([]);
    mockFormatChartDataBySensor.mockReturnValueOnce({ sensors: {} });

    await request(app)
      .get('/api/v1/water-levels/chart')
      .query({
        period: '24h',
        sensorIds: 'AWD-6D47,AWD-9950',
        includeSmoothed: 'true',
      });

    expect(mockGetWaterLevelChartData).toHaveBeenCalledWith(
      '24h',
      ['AWD-6D47', 'AWD-9950'],
      true
    );
  });

  test('should return 400 for invalid period', async () => {
    const response = await request(app)
      .get('/api/v1/water-levels/chart')
      .query({ period: 'invalid' });

    expect(response.status).toBe(400);
    expect(response.body.error).toContain('Invalid period');
    expect(mockGetWaterLevelChartData).not.toHaveBeenCalled();
  });
});