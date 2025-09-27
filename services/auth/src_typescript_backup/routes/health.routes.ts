import { Router } from 'express';
import { AppDataSource } from '../config/database';
import { createClient } from 'redis';
import { config } from '../config';

const router = Router();

router.get('/', async (req, res) => {
  const health = {
    status: 'healthy',
    timestamp: new Date().toISOString(),
    service: 'auth-service',
    version: '1.0.0',
    uptime: process.uptime(),
    environment: config.env,
    checks: {
      database: 'unknown',
      redis: 'unknown',
    },
  };

  // Check database
  try {
    await AppDataSource.query('SELECT 1');
    health.checks.database = 'healthy';
  } catch (error) {
    health.checks.database = 'unhealthy';
    health.status = 'degraded';
  }

  // Check Redis
  try {
    const redisClient = createClient({ url: config.redis.url });
    await redisClient.connect();
    await redisClient.ping();
    await redisClient.quit();
    health.checks.redis = 'healthy';
  } catch (error) {
    health.checks.redis = 'unhealthy';
    health.status = 'degraded';
  }

  const statusCode = health.status === 'healthy' ? 200 : 503;
  res.status(statusCode).json(health);
});

router.get('/live', (req, res) => {
  res.status(200).json({ status: 'alive' });
});

router.get('/ready', async (req, res) => {
  try {
    await AppDataSource.query('SELECT 1');
    res.status(200).json({ status: 'ready' });
  } catch (error) {
    res.status(503).json({ status: 'not ready' });
  }
});

export { router as healthRoutes };