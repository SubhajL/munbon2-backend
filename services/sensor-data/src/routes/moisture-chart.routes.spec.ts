import express from 'express';
import { createMoistureRoutes } from './moisture.routes';
import { TimescaleRepository } from '../repository/timescale.repository';
import { Logger } from 'pino';
import { MoistureReadingRow } from '../types/moisture-chart.types';
import request from 'supertest';

const mockRepository = {
  query: jest.fn(),
} as unknown as TimescaleRepository;

const mockLogger = {
  error: jest.fn(),
  warn: jest.fn(),
  info: jest.fn(),
} as unknown as Logger;

describe('Moisture Chart Routes', () => {
  let app: express.Application;

  beforeEach(() => {
    jest.clearAllMocks();
    app = express();
    app.use(express.json());

    const router = createMoistureRoutes({
      repository: mockRepository,
      logger: mockLogger,
    });

    app.use('/', router);
  });

  describe('GET /moisture/chart', () => {
    it('returns valid JSON for default period=24h', async () => {
      const mockRows: MoistureReadingRow[] = [
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

      (mockRepository.query as jest.Mock).mockResolvedValueOnce({
        rows: mockRows,
      });

      const res = await request(app)
        .get('/moisture/chart')
        .expect(200);

      expect(res.body).toHaveProperty('aggregation');
      expect(res.body).toHaveProperty('period', '24h');
      expect(res.body).toHaveProperty('timeRange');
      expect(res.body).toHaveProperty('localTimeZone', 'UTC');
      expect(res.body).toHaveProperty('sensors');
      expect(res.body).toHaveProperty('summary');
    });

    it('accepts period=7d query parameter', async () => {
      (mockRepository.query as jest.Mock).mockResolvedValueOnce({
        rows: [],
      });

      const res = await request(app)
        .get('/moisture/chart?period=7d')
        .expect(200);

      expect(res.body.period).toBe('7d');
    });

    it('returns 400 for invalid period', async () => {
      const res = await request(app)
        .get('/moisture/chart?period=invalid')
        .expect(400);

      expect(res.body).toHaveProperty('error');
      expect(res.body.error).toContain('Invalid period');
    });

    it('returns 12 sensors as separate entries without overlay', async () => {
      const mockRows: MoistureReadingRow[] = [];
      for (let i = 1; i <= 12; i++) {
        mockRows.push({
          time: new Date('2025-11-03T12:00:00Z'),
          sensor_id: `MS-00001-0000${i}`,
          moisture_surface_pct: 65,
          moisture_deep_pct: 50,
          avg_moisture_surface: 65,
          min_moisture_surface: 60,
          max_moisture_surface: 70,
          avg_moisture_deep: 50,
          min_moisture_deep: 45,
          max_moisture_deep: 55,
          sample_count: 1,
        });
      }

      (mockRepository.query as jest.Mock).mockResolvedValueOnce({
        rows: mockRows,
      });

      const res = await request(app)
        .get('/moisture/chart')
        .expect(200);

      expect(Object.keys(res.body.sensors)).toHaveLength(12);
      for (let i = 1; i <= 12; i++) {
        const sensorId = `MS-00001-0000${i}`;
        expect(res.body.sensors[sensorId]).toBeDefined();
        expect(res.body.sensors[sensorId].dataPoints).toBeInstanceOf(Array);
      }
    });

    it('converts timestamps to local timezone', async () => {
      const mockRows: MoistureReadingRow[] = [
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

      (mockRepository.query as jest.Mock).mockResolvedValueOnce({
        rows: mockRows,
      });

      const res = await request(app)
        .get('/moisture/chart?timeZone=UTC')
        .expect(200);

      const dataPoint =
        res.body.sensors['MS-00001-00001'].dataPoints[0];
      expect(dataPoint.time).toMatch(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
      expect(res.body.localTimeZone).toBe('UTC');
    });

    it('filters by sensor IDs when provided', async () => {
      (mockRepository.query as jest.Mock).mockResolvedValueOnce({
        rows: [],
      });

      await request(app)
        .get('/moisture/chart?sensorIds=0001-0001,0001-0002')
        .expect(200);

      expect(mockRepository.query).toHaveBeenCalled();
      const callArgs = (mockRepository.query as jest.Mock).mock.calls[0];
      const params = callArgs[1];

      expect(params.length).toBeGreaterThan(2);
    });

    it('handles all 4 period values', async () => {
      const periods = ['24h', '3d', '7d', '14d'] as const;

      for (const period of periods) {
        jest.clearAllMocks();
        (mockRepository.query as jest.Mock).mockResolvedValueOnce({
          rows: [],
        });

        const res = await request(app)
          .get(`/moisture/chart?period=${period}`)
          .expect(200);

        expect(res.body.period).toBe(period);
      }
    });

    it('includes correct sensor and data point summary', async () => {
      const mockRows: MoistureReadingRow[] = [
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
          sample_count: 1,
        },
      ];

      (mockRepository.query as jest.Mock).mockResolvedValueOnce({
        rows: mockRows,
      });

      const res = await request(app)
        .get('/moisture/chart')
        .expect(200);

      expect(res.body.summary.totalSensors).toBe(1);
      expect(res.body.summary.totalDataPoints).toBe(2);
    });
  });
});
