import express from 'express';
import request from 'supertest';
import { createServiceManagementRoutes } from '../../src/routes/service-management.routes';
import type { TimescaleRepository } from '../../src/repository/timescale.repository';

describe('smoothing-admin.routes', () => {
  let app: express.Express;
  const mockRepo = { query: jest.fn() } as unknown as TimescaleRepository;

  beforeEach(() => {
    jest.clearAllMocks();
    app = express();
    app.use(express.json());
    process.env.ADMIN_TOKEN = 'secret';
    app.use('/api/v1', createServiceManagementRoutes({ repository: mockRepo }));
  });

  test('GET /api/v1/admin/smoothing/params requires admin token', async () => {
    const res = await request(app).get('/api/v1/admin/smoothing/params');
    expect(res.status).toBe(401);
  });

  test('GET /api/v1/admin/smoothing/params returns rows', async () => {
    (mockRepo.query as any).mockResolvedValueOnce({ rows: [
      { sensor_id: '*', w: 12, kx: 3.0, kv: 4.0, alpha: 0.25, updated_at: '2025-11-07T00:00:00Z' },
      { sensor_id: 'MS-00001-00001', w: 10, kx: 3.0, kv: 5.0, alpha: 0.35, updated_at: '2025-11-07T00:00:00Z' },
    ]});

    const res = await request(app)
      .get('/api/v1/admin/smoothing/params')
      .set('x-admin-token', 'secret');

    expect(res.status).toBe(200);
    expect(mockRepo.query).toHaveBeenCalled();
    expect(res.body.params).toHaveLength(2);
  });

  test('POST /api/v1/admin/smoothing/params requires admin token', async () => {
    const res = await request(app)
      .post('/api/v1/admin/smoothing/params')
      .send({ sensorId: 'MS-00001-00001', w: 10, kx: 3.0, kv: 4.0, alpha: 0.3 });
    expect(res.status).toBe(401);
  });

  test('POST /api/v1/admin/smoothing/params upserts params', async () => {
    (mockRepo.query as any).mockResolvedValueOnce({ rows: [{ ok: true }] });

    const payload = { sensorId: 'MS-00001-00001', w: 10, kx: 3.0, kv: 4.0, alpha: 0.3 };
    const res = await request(app)
      .post('/api/v1/admin/smoothing/params')
      .set('x-admin-token', 'secret')
      .send(payload);

    expect(res.status).toBe(200);
    expect(mockRepo.query).toHaveBeenCalled();
    const [[sql, params]] = (mockRepo.query as any).mock.calls;
    expect(sql.toLowerCase()).toContain('upsert_smoothing_params');
    expect(params).toEqual(['MS-00001-00001', 10, 3.0, 4.0, 0.3]);
  });
});