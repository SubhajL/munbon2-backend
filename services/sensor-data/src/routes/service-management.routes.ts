import { Router, Request, Response } from 'express';
import { TimescaleRepository } from '../repository/timescale.repository';
import {
  getServicesList,
  getServiceStatus,
  startService,
  stopService
} from '../services/service-manager.service';

interface ServiceManagementRoutesOptions {
  repository: TimescaleRepository;
}

export function createServiceManagementRoutes(opts: ServiceManagementRoutesOptions): Router {
  const router = Router();
  const repo = opts.repository;

  router.get('/services/status', async (_req: Request, res: Response) => {
    try {
      const services = await getServicesList();

      res.json({
        services,
        count: services.length
      });
    } catch (error) {
      res.status(500).json({
        error: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  });

  router.post('/services/:name/start', async (req: Request, res: Response) => {
    try {
      const { name } = req.params;

      await startService(name);
      const service = await getServiceStatus(name);

      res.json({
        message: 'Service started successfully',
        service
      });
    } catch (error) {
      res.status(500).json({
        error: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  });

  router.post('/services/:name/stop', async (req: Request, res: Response) => {
    try {
      const { name } = req.params;

      await stopService(name);
      const service = await getServiceStatus(name);

      res.json({
        message: 'Service stopped successfully',
        service
      });
    } catch (error) {
      res.status(500).json({
        error: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  });

  // Admin: smoothing params (GET)
  router.get('/admin/smoothing/params', async (req: Request, res: Response) => {
    const admin = req.headers['x-admin-token'];
    if (admin !== process.env.ADMIN_TOKEN) {
      res.status(401).json({ error: 'Unauthorized' });
      return;
    }
    try {
      const sensorId = (req.query.sensorId as string) || null;
      const sql = `
        SELECT sensor_id, w, kx, kv, alpha, updated_at
        FROM public.smoothing_params
        WHERE ($1::text IS NULL OR sensor_id = $1 OR sensor_id = '*')
        ORDER BY CASE WHEN sensor_id='*' THEN 1 ELSE 0 END, sensor_id;
      `;
      const result = await repo.query(sql, [sensorId]);
      res.json({ params: result.rows });
    } catch (err: any) {
      res.status(500).json({ error: err?.message || 'Database error' });
    }
  });

  // Admin: smoothing params (POST upsert)
  router.post('/admin/smoothing/params', async (req: Request, res: Response) => {
    const admin = req.headers['x-admin-token'];
    if (admin !== process.env.ADMIN_TOKEN) {
      res.status(401).json({ error: 'Unauthorized' });
      return;
    }
    try {
      const { sensorId, w, kx, kv, alpha } = req.body || {};
      if (!sensorId || !Number.isInteger(w) || typeof kx !== 'number' || typeof kv !== 'number' || typeof alpha !== 'number') {
        res.status(400).json({ error: 'Invalid payload' });
        return;
      }
      const sql = `SELECT public.upsert_smoothing_params($1,$2,$3,$4,$5) AS ok;`;
      const result = await repo.query(sql, [sensorId, w, kx, kv, alpha]);
      res.json({ updated: true, result: result.rows[0] || null });
    } catch (err: any) {
      res.status(500).json({ error: err?.message || 'Database error' });
    }
  });

  return router;
}
