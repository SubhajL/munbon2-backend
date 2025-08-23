import { Router, Request, Response } from 'express';
import mongoose from 'mongoose';
import { getRedisClient } from '../config/redis';

const router = Router();

router.get('/', async (req: Request, res: Response) => {
  const healthStatus = {
    status: 'healthy',
    service: 'ros-service',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    environment: process.env.NODE_ENV,
    version: process.env.npm_package_version || '1.0.0'
  };

  res.json(healthStatus);
});

router.get('/ready', async (req: Request, res: Response) => {
  try {
    // Check MongoDB connection
    if (mongoose.connection.readyState !== 1) {
      throw new Error('MongoDB not connected');
    }

    // Check Redis connection
    const redis = getRedisClient();
    await redis.ping();

    res.json({
      status: 'ready',
      service: 'ros-service',
      timestamp: new Date().toISOString(),
      dependencies: {
        mongodb: 'connected',
        redis: 'connected'
      }
    });
  } catch (error) {
    res.status(503).json({
      status: 'not ready',
      service: 'ros-service',
      timestamp: new Date().toISOString(),
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

router.get('/live', (req: Request, res: Response) => {
  res.json({
    status: 'alive',
    service: 'ros-service',
    timestamp: new Date().toISOString()
  });
});

export default router;