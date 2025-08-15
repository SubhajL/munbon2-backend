import { Router, Request, Response, NextFunction } from 'express';
import { Logger } from 'pino';
import { TimescaleRepository } from '../repository/timescale.repository';

interface RouteOptions {
  repository: TimescaleRepository;
  logger: Logger;
}

export function createExternalPublicRoutes(_options: RouteOptions): Router {
  const router = Router();

  // API key authentication middleware
  const apiKeyAuth = (req: Request, res: Response, next: NextFunction): void => {
    const apiKey = req.headers['x-api-key'] as string;
    const validApiKeys = (process.env.EXTERNAL_API_KEYS || '').split(',').filter(k => k);
    
    if (!apiKey || !validApiKeys.includes(apiKey)) {
      res.status(401).json({ error: 'Invalid API key' });
      return;
    }
    
    next();
  };

  // Apply API key authentication to all routes
  router.use(apiKeyAuth);

  // Basic health check endpoint
  router.get('/health', (_req: Request, res: Response) => {
    res.json({ 
      status: 'ok',
      service: 'sensor-data-external-api',
      timestamp: new Date().toISOString()
    });
  });

  // TODO: Implement actual query methods in repository before enabling these routes
  // The following routes are commented out until the repository methods are implemented:
  // - getWaterLevelReadings
  // - getMoistureReadings
  // - getSensors
  // - getLatestReading
  // - getSensorStatistics

  return router;
}