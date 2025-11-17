// Converted from Vitest to Jest
import express from 'express';
import request from 'supertest';
import { createServiceManagementRoutes } from '../../src/routes/service-management.routes';
import type { ServiceStatus } from '../../src/services/service-manager.service';
import * as serviceManager from '../../src/services/service-manager.service';

jest.mock('../../src/services/service-manager.service');

describe('service-management.routes', () => {
  let app: express.Express;

  beforeEach(() => {
    jest.clearAllMocks();
    app = express();
    app.use(express.json());
    app.use('/api/v1', createServiceManagementRoutes({ repository: { query: jest.fn() } as any }));
  });

  describe('GET /api/v1/services/status', () => {
    test('returns 200 with services array', async () => {
      const mockServices: ServiceStatus[] = [
        {
          name: 'munbon-scheduler',
          status: 'online',
          uptimeMs: 3600000,
          uptimeFormatted: '0d 1h 0m',
          cpu: 5,
          memory: 50000000,
          restartCount: 2,
          createdAt: Date.now() - 7200000
        },
        {
          name: 'munbon-gis',
          status: 'stopped',
          uptimeMs: 0,
          uptimeFormatted: '0d 0h 0m',
          cpu: 0,
          memory: 0,
          restartCount: 0,
          createdAt: Date.now() - 3600000
        }
      ];

      jest.mocked(serviceManager.getServicesList).mockResolvedValue(mockServices);

      const response = await request(app).get('/api/v1/services/status');

      expect(response.status).toBe(200);
      expect(response.body).toEqual({
        services: mockServices,
        count: 2
      });
    });

    test('returns 500 on error', async () => {
      jest.mocked(serviceManager.getServicesList).mockRejectedValue(new Error('PM2 connection failed'));

      const response = await request(app).get('/api/v1/services/status');

      expect(response.status).toBe(500);
      expect(response.body).toHaveProperty('error');
    });
  });

  describe('POST /api/v1/services/:name/start', () => {
    test('returns 200 on success', async () => {
      const mockStatus: ServiceStatus = {
        name: 'munbon-scheduler',
        status: 'online',
        uptimeMs: 100,
        uptimeFormatted: '0d 0h 0m',
        cpu: 5,
        memory: 50000000,
        restartCount: 3,
        createdAt: Date.now()
      };

      jest.mocked(serviceManager.startService).mockResolvedValue(undefined);
      jest.mocked(serviceManager.getServiceStatus).mockResolvedValue(mockStatus);

      const response = await request(app)
        .post('/api/v1/services/munbon-scheduler/start');

      expect(response.status).toBe(200);
      expect(response.body).toEqual({
        message: 'Service started successfully',
        service: mockStatus
      });
      expect(serviceManager.startService).toHaveBeenCalledWith('munbon-scheduler');
    });

    test('returns 500 when start fails', async () => {
      jest.mocked(serviceManager.startService).mockRejectedValue(new Error('Failed to start'));

      const response = await request(app)
        .post('/api/v1/services/munbon-scheduler/start');

      expect(response.status).toBe(500);
      expect(response.body).toHaveProperty('error');
    });
  });

  describe('POST /api/v1/services/:name/stop', () => {
    test('returns 200 on success', async () => {
      const mockStatus: ServiceStatus = {
        name: 'munbon-scheduler',
        status: 'stopped',
        uptimeMs: 0,
        uptimeFormatted: '0d 0h 0m',
        cpu: 0,
        memory: 0,
        restartCount: 2,
        createdAt: Date.now()
      };

      jest.mocked(serviceManager.stopService).mockResolvedValue(undefined);
      jest.mocked(serviceManager.getServiceStatus).mockResolvedValue(mockStatus);

      const response = await request(app)
        .post('/api/v1/services/munbon-scheduler/stop');

      expect(response.status).toBe(200);
      expect(response.body).toEqual({
        message: 'Service stopped successfully',
        service: mockStatus
      });
      expect(serviceManager.stopService).toHaveBeenCalledWith('munbon-scheduler');
    });

    test('returns 500 when stop fails', async () => {
      jest.mocked(serviceManager.stopService).mockRejectedValue(new Error('Failed to stop'));

      const response = await request(app)
        .post('/api/v1/services/munbon-scheduler/stop');

      expect(response.status).toBe(500);
      expect(response.body).toHaveProperty('error');
    });
  });
});
