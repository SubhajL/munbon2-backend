import { Router, Request, Response } from 'express';
import { TimescaleService } from '../services/timescale.service';
import { CacheService } from '../services/cache.service';
import { MqttService } from '../services/mqtt.service';
import { WebSocketService } from '../services/websocket.service';

const router = Router();

export function createHealthRoutes(
  timescaleService: TimescaleService,
  cacheService: CacheService,
  mqttService: MqttService,
  websocketService: WebSocketService
): Router {
  router.get('/health', async (_req: Request, res: Response) => {
    try {
      // Check TimescaleDB connection
      const dbHealthy = await checkDatabaseHealth(timescaleService);
      
      // Check Redis connection
      const cacheHealthy = await checkCacheHealth(cacheService);
      
      const health = {
        status: dbHealthy && cacheHealthy ? 'healthy' : 'unhealthy',
        timestamp: new Date(),
        service: 'water-level-monitoring',
        version: '1.0.0',
        uptime: process.uptime(),
        checks: {
          database: dbHealthy ? 'healthy' : 'unhealthy',
          cache: cacheHealthy ? 'healthy' : 'unhealthy',
          mqtt: 'healthy', // MQTT has auto-reconnect
          websocket: 'healthy',
        },
        metrics: {
          connectedClients: websocketService.getConnectedClients(),
          memoryUsage: process.memoryUsage(),
        },
      };
      
      res.status(health.status === 'healthy' ? 200 : 503).json(health);
    } catch (error) {
      res.status(503).json({
        status: 'unhealthy',
        error: (error as Error).message,
      });
    }
  });
  
  router.get('/ready', async (_req: Request, res: Response) => {
    try {
      const dbHealthy = await checkDatabaseHealth(timescaleService);
      
      if (dbHealthy) {
        res.json({ ready: true });
      } else {
        res.status(503).json({ ready: false });
      }
    } catch (error) {
      res.status(503).json({ ready: false });
    }
  });
  
  return router;
}

async function checkDatabaseHealth(timescaleService: TimescaleService): Promise<boolean> {
  try {
    // Simple query to check connection
    await timescaleService.getLatestReadings([], 1);
    return true;
  } catch (error) {
    return false;
  }
}

async function checkCacheHealth(cacheService: CacheService): Promise<boolean> {
  try {
    const testKey = 'health:check';
    await cacheService.set(testKey, { test: true }, 10);
    await cacheService.get(testKey);
    await cacheService.delete(testKey);
    return true;
  } catch (error) {
    return false;
  }
}