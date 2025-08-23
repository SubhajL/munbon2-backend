import { Router, Request, Response } from 'express';
import { getPostgresPool, getTimescalePool } from '../config/database';
import { getRedisClient } from '../config/redis';
import { logger } from '../utils/logger';

export const healthRouter = Router();

healthRouter.get('/', async (_req: Request, res: Response) => {
  res.json({
    status: 'ok',
    service: 'awd-control-service',
    timestamp: new Date().toISOString(),
  });
});

healthRouter.get('/ready', async (_req: Request, res: Response) => {
  const checks = {
    postgres: false,
    timescale: false,
    redis: false,
  };

  try {
    // Check PostgreSQL
    const pgPool = getPostgresPool();
    await pgPool.query('SELECT 1');
    checks.postgres = true;
  } catch (error) {
    logger.error(error, 'PostgreSQL health check failed');
  }

  try {
    // Check TimescaleDB
    const tsPool = getTimescalePool();
    await tsPool.query('SELECT 1');
    checks.timescale = true;
  } catch (error) {
    logger.error(error, 'TimescaleDB health check failed');
  }

  try {
    // Check Redis
    const redis = getRedisClient();
    await redis.ping();
    checks.redis = true;
  } catch (error) {
    logger.error(error, 'Redis health check failed');
  }

  const allHealthy = Object.values(checks).every(check => check === true);
  const status = allHealthy ? 200 : 503;

  res.status(status).json({
    ready: allHealthy,
    checks,
    timestamp: new Date().toISOString(),
  });
});

healthRouter.get('/live', (_req: Request, res: Response) => {
  res.json({
    alive: true,
    uptime: process.uptime(),
    timestamp: new Date().toISOString(),
  });
});