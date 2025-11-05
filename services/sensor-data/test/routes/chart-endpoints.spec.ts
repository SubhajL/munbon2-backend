import express from 'express';
import request from 'supertest';
import type { Logger } from 'pino';
import { createMoistureRoutes } from '../../src/routes/moisture.routes';
import { createWaterLevelRoutes } from '../../src/routes/water-level.routes';
import type { TimescaleRepository } from '../../src/repository/timescale.repository';

const mockLogger: Logger = {
  error: jest.fn(),
  info: jest.fn(),
  warn: jest.fn(),
  debug: jest.fn()
} as unknown as Logger;

const mockRepository = {
  query: jest.fn()
} as unknown as TimescaleRepository;

const mockSmartRepo = {
  getPlotMappingsBySensorIds: jest.fn(),
  getThresholdsByPlotIds: jest.fn(),
};

describe('chart-endpoints', () => {
  let app: express.Express;

  beforeEach(() => {
    jest.clearAllMocks();
    app = express();
    app.use(express.json());
    (mockSmartRepo.getPlotMappingsBySensorIds as jest.Mock).mockResolvedValue({});
    (mockSmartRepo.getThresholdsByPlotIds as jest.Mock).mockResolvedValue({});
    app.use('/api/v1', createMoistureRoutes({ repository: mockRepository, logger: mockLogger, smartFarmRepository: mockSmartRepo as any }));
    app.use('/api/v1', createWaterLevelRoutes({ repository: mockRepository, logger: mockLogger, smartFarmRepository: mockSmartRepo as any }));
  });

  describe('GET /api/v1/moisture/chart', () => {
    test('returns structured response with sensors grouped by ID', async () => {
      const mockData = Array.from({ length: 96 }, (_, i) => ({
        time: new Date(Date.now() - (95 - i) * 15 * 60 * 1000),
        sensor_id: 'MS-00001-00001',
        avg_moisture_surface: 45.5 + Math.random() * 10,
        avg_moisture_deep: 50.2 + Math.random() * 10,
        min_moisture_surface: 40.0,
        max_moisture_surface: 60.0,
        min_moisture_deep: 45.0,
        max_moisture_deep: 65.0,
        sample_count: 15
      }));

      (mockRepository.query as jest.Mock).mockResolvedValue({ rows: mockData } as any);

      const response = await request(app).get('/api/v1/moisture/chart');

      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty('aggregation');
      expect(response.body).toHaveProperty('period', '24h');
      expect(response.body).toHaveProperty('sensors');
      expect(response.body.aggregation.interval).toBe('15 minutes');
      expect(response.body.sensors['MS-00001-00001']).toBeDefined();
      expect(response.body.sensors['MS-00001-00001'].dataPoints).toHaveLength(96);
    });

    test('data points have correct structure', async () => {
      const mockData = [{
        time: new Date('2025-11-03T12:00:00Z'),
        sensor_id: 'MS-00001-00001',
        avg_moisture_surface: 45.5,
        avg_moisture_deep: 50.2,
        min_moisture_surface: 40.0,
        max_moisture_surface: 60.0,
        min_moisture_deep: 45.0,
        max_moisture_deep: 65.0,
        sample_count: 15
      }];

      (mockRepository.query as jest.Mock).mockResolvedValue({ rows: mockData } as any);

      const response = await request(app).get('/api/v1/moisture/chart');

      expect(response.status).toBe(200);
      const dataPoint = response.body.sensors['MS-00001-00001'].dataPoints[0];
      expect(dataPoint).toMatchObject({
        time: expect.any(String),
        avgMoistureSurface: 45.5,
        avgMoistureDeep: 50.2,
        sampleCount: 15
      });
    });

    test('includes plotId and thresholds when metadata exists', async () => {
      const mockData = [{
        time: new Date('2025-11-03T12:00:00Z'),
        sensor_id: 'MS-00001-00001',
        avg_moisture_surface: 45.5,
        avg_moisture_deep: 50.2,
        min_moisture_surface: 40.0,
        max_moisture_surface: 60.0,
        min_moisture_deep: 45.0,
        max_moisture_deep: 65.0,
        sample_count: 15
      }];
      (mockRepository.query as jest.Mock).mockResolvedValue({ rows: mockData } as any);
      (mockSmartRepo.getPlotMappingsBySensorIds as jest.Mock).mockResolvedValue({ 'MS-00001-00001': 'plot-1' });
      (mockSmartRepo.getThresholdsByPlotIds as jest.Mock).mockResolvedValue({ 'plot-1': { moistureLower: 20, moistureUpper: 30, waterLevelLower: null, waterLevelUpper: null } });

      const response = await request(app).get('/api/v1/moisture/chart');
      expect(response.status).toBe(200);
      const sensor = response.body.sensors['MS-00001-00001'];
      expect(sensor.plotId).toBe('plot-1');
      expect(sensor.thresholds).toEqual({ lower: 20, upper: 30 });
    });

    test('handles empty database gracefully', async () => {
      (mockRepository.query as jest.Mock).mockResolvedValue({ rows: [] } as any);

      const response = await request(app).get('/api/v1/moisture/chart');

      expect(response.status).toBe(200);
      expect(response.body.sensors).toEqual({});
      expect(response.body.summary.totalSensors).toBe(0);
    });
  });

  describe('GET /api/v1/water-levels/chart', () => {
    test('returns structured response with sensors grouped by ID', async () => {
      const mockData = Array.from({ length: 96 }, (_, i) => ({
        time: new Date(Date.now() - (95 - i) * 15 * 60 * 1000),
        sensor_id: 'AWD-B89D',
        avg_level: 125.5 + Math.random() * 5,
        min_level: 120.0,
        max_level: 135.0,
        avg_quality: 95.5,
        sample_count: 12
      }));

      (mockRepository.query as jest.Mock).mockResolvedValue({ rows: mockData } as any);

      const response = await request(app).get('/api/v1/water-levels/chart');

      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty('aggregation');
      expect(response.body).toHaveProperty('period', '24h');
      expect(response.body).toHaveProperty('timeRange');
      expect(response.body).toHaveProperty('localTimeZone', 'UTC');
      expect(response.body).toHaveProperty('sensors');
      expect(response.body).toHaveProperty('summary');
      
      expect(response.body.aggregation).toEqual({
        interval: '15 minutes',
        method: 'average'
      });
      
      expect(response.body.sensors['AWD-B89D']).toBeDefined();
      expect(response.body.sensors['AWD-B89D'].dataPoints).toHaveLength(96);
      expect(response.body.summary.totalSensors).toBe(1);
      expect(response.body.summary.totalDataPoints).toBe(96);
    });

    test('respects period query parameter', async () => {
      const mockData = [{
        time: new Date(),
        sensor_id: 'AWD-558F',
        avg_level: 125.5,
        min_level: 120.0,
        max_level: 130.0,
        avg_quality: 95.5,
        sample_count: 12
      }];

      (mockRepository.query as jest.Mock).mockResolvedValue({ rows: mockData } as any);

      const response = await request(app).get('/api/v1/water-levels/chart?period=7d');

      expect(response.status).toBe(200);
      expect(response.body.period).toBe('7d');
    });

    test('returns 400 for invalid period', async () => {
      const response = await request(app).get('/api/v1/water-levels/chart?period=invalid');

      expect(response.status).toBe(400);
      expect(response.body).toHaveProperty('error');
      expect(response.body.error).toContain('Invalid period');
    });

    test('filters by sensor IDs when provided', async () => {
      const mockData = [
        {
          time: new Date(),
          sensor_id: 'AWD-B89D',
          avg_level: 125.5,
          min_level: 120.0,
          max_level: 130.0,
          avg_quality: 95.5,
          sample_count: 12
        },
        {
          time: new Date(),
          sensor_id: 'AWD-558F',
          avg_level: 127.0,
          min_level: 122.0,
          max_level: 132.0,
          avg_quality: 96.0,
          sample_count: 10
        }
      ];

      (mockRepository.query as jest.Mock).mockResolvedValue({ rows: mockData } as any);

      const response = await request(app)
        .get('/api/v1/water-levels/chart?sensorIds=AWD-B89D,AWD-558F');

      expect(response.status).toBe(200);
      expect(mockRepository.query).toHaveBeenCalled();
      
      const callArgs = (mockRepository.query as jest.Mock).mock.calls[0];
      const params = callArgs[1];
      
      expect(params).toHaveLength(3);
      expect(params[2]).toEqual(['AWD-B89D', 'AWD-558F']);
    });

    test('supports multiple sensors in response', async () => {
      const mockData = [
        {
          time: new Date(),
          sensor_id: 'AWD-B89D',
          avg_level: 125.5,
          min_level: 120.0,
          max_level: 130.0,
          avg_quality: 95.5,
          sample_count: 12
        },
        {
          time: new Date(),
          sensor_id: 'AWD-558F',
          avg_level: 127.0,
          min_level: 122.0,
          max_level: 132.0,
          avg_quality: 96.0,
          sample_count: 10
        },
        {
          time: new Date(),
          sensor_id: 'AWD-A4F8',
          avg_level: 124.0,
          min_level: 119.0,
          max_level: 129.0,
          avg_quality: 94.0,
          sample_count: 11
        }
      ];

      (mockRepository.query as jest.Mock).mockResolvedValue({ rows: mockData } as any);

      const response = await request(app).get('/api/v1/water-levels/chart');

      expect(response.status).toBe(200);
      expect(Object.keys(response.body.sensors)).toHaveLength(3);
      expect(response.body.sensors['AWD-B89D']).toBeDefined();
      expect(response.body.sensors['AWD-558F']).toBeDefined();
      expect(response.body.sensors['AWD-A4F8']).toBeDefined();
      expect(response.body.summary.totalSensors).toBe(3);
    });

    test('data points have correct structure', async () => {
      const mockData = [{
        time: new Date('2025-11-03T12:00:00Z'),
        sensor_id: 'AWD-B89D',
        avg_level: 125.5,
        min_level: 120.0,
        max_level: 130.0,
        avg_quality: 95.5,
        sample_count: 12
      }];

      (mockRepository.query as jest.Mock).mockResolvedValue({ rows: mockData } as any);

      const response = await request(app).get('/api/v1/water-levels/chart');

      expect(response.status).toBe(200);
      
      const dataPoint = response.body.sensors['AWD-B89D'].dataPoints[0];
      expect(dataPoint).toMatchObject({
        time: expect.any(String),
        avgLevel: 125.5,
        minLevel: 120.0,
        maxLevel: 130.0,
        avgQuality: 95.5,
        sampleCount: 12
      });
    });

    test('handles empty database gracefully', async () => {
      (mockRepository.query as jest.Mock).mockResolvedValue({ rows: [] } as any);

      const response = await request(app).get('/api/v1/water-levels/chart');

      expect(response.status).toBe(200);
      expect(response.body.sensors).toEqual({});
      expect(response.body.summary.totalSensors).toBe(0);
      expect(response.body.summary.totalDataPoints).toBe(0);
    });

    test('supports all valid periods', async () => {
      const periods = ['24h', '3d', '7d', '14d'];
      
      for (const period of periods) {
        jest.clearAllMocks();
        (mockRepository.query as jest.Mock).mockResolvedValue({ rows: [] } as any);
        
        const response = await request(app)
          .get(`/api/v1/water-levels/chart?period=${period}`);
        
        expect(response.status).toBe(200);
        expect(response.body.period).toBe(period);
      }
    });

    test('respects timeZone query parameter', async () => {
      const mockData = [{
        time: new Date('2025-11-03T12:00:00Z'),
        sensor_id: 'AWD-B89D',
        avg_level: 125.5,
        min_level: 120.0,
        max_level: 130.0,
        avg_quality: 95.5,
        sample_count: 12
      }];

      (mockRepository.query as jest.Mock).mockResolvedValue({ rows: mockData } as any);

      const response = await request(app)
        .get('/api/v1/water-levels/chart?timeZone=America/New_York');

      expect(response.status).toBe(200);
      expect(response.body.localTimeZone).toBe('America/New_York');
    });

    test('verifies 15-minute time bucket in SQL query', async () => {
      (mockRepository.query as jest.Mock).mockResolvedValue({ rows: [] } as any);

      await request(app).get('/api/v1/water-levels/chart');

      expect(mockRepository.query).toHaveBeenCalled();
      const sqlQuery = (mockRepository.query as jest.Mock).mock.calls[0][0];
      
      expect(sqlQuery).toContain("time_bucket('15 minutes'");
      expect(sqlQuery).toContain('AVG(level_cm)');
      expect(sqlQuery).toContain('MIN(level_cm)');
      expect(sqlQuery).toContain('MAX(level_cm)');
      expect(sqlQuery).toContain('AVG(quality_score)');
      expect(sqlQuery).toContain('GROUP BY');
      expect(sqlQuery).toContain('ORDER BY time ASC');
    });

    test('includes plot thresholds for water level when metadata exists', async () => {
      const mockData = [{
        time: new Date(),
        sensor_id: 'AWD-558F',
        avg_level: 125.5,
        min_level: 120.0,
        max_level: 130.0,
        avg_quality: 95.5,
        sample_count: 12
      }];
      (mockRepository.query as jest.Mock).mockResolvedValue({ rows: mockData } as any);
      (mockSmartRepo.getPlotMappingsBySensorIds as jest.Mock).mockResolvedValue({ 'AWD-558F': 'plot-2' });
      (mockSmartRepo.getThresholdsByPlotIds as jest.Mock).mockResolvedValue({ 'plot-2': { moistureLower: null, moistureUpper: null, waterLevelLower: 5, waterLevelUpper: 15 } });

      const response = await request(app).get('/api/v1/water-levels/chart');
      expect(response.status).toBe(200);
      const sensor = response.body.sensors['AWD-558F'];
      expect(sensor.plotId).toBe('plot-2');
      expect(sensor.thresholds).toEqual({ lower: 5, upper: 15 });
    });
  });
});
