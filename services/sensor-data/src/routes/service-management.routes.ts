import { Router, Request, Response } from 'express';
import {
  getServicesList,
  getServiceStatus,
  startService,
  stopService
} from '../services/service-manager.service';

export function createServiceManagementRoutes(): Router {
  const router = Router();

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

  return router;
}
