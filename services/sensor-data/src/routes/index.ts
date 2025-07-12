import { Express, Request, Response, NextFunction } from 'express';
import { Logger } from 'pino';
import { SensorDataService } from '../services/sensor-data.service';
import { TimescaleRepository } from '../repository/timescale.repository';
import { createSensorRoutes } from './sensors.routes';
import { createWaterLevelRoutes } from './water-level.routes';
import { createMoistureRoutes } from './moisture.routes';
import { createExternalRoutes } from './external.routes';

interface RouteOptions {
  sensorDataService: SensorDataService;
  timescaleRepo: TimescaleRepository;
  logger: Logger;
}

export function setupRoutes(app: Express, options: RouteOptions): void {
  const { sensorDataService, timescaleRepo, logger } = options;

  // Mount API route modules
  app.use('/api/v1', createSensorRoutes({
    repository: timescaleRepo,
    sensorDataService,
    logger
  }));

  app.use('/api/v1', createWaterLevelRoutes({
    repository: timescaleRepo,
    logger
  }));

  app.use('/api/v1', createMoistureRoutes({
    repository: timescaleRepo,
    logger
  }));

  app.use('/api/v1/external', createExternalRoutes({
    repository: timescaleRepo,
    logger
  }));

  // Sensor data ingestion endpoint (for HTTP fallback)
  app.post('/api/v1/:token/telemetry', async (req: Request, res: Response, next: NextFunction): Promise<void> => {
    try {
      const token = req.params.token;
      const validTokens = getValidTokens();
      
      if (!validTokens[token]) {
        res.status(401).json({ error: 'Invalid token' });
        return;
      }

      await sensorDataService.processSensorData(req.body);
      
      res.json({
        status: 'success',
        message: 'Telemetry received',
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      next(error);
    }
  });

  // Get sensor attributes/configuration
  app.get('/api/v1/:token/attributes', (req: Request, res: Response): void => {
    const token = req.params.token;
    const validTokens = getValidTokens();
    
    if (!validTokens[token]) {
      res.status(401).json({ error: 'Invalid token' });
      return;
    }

    const sharedKeys = req.query.sharedKeys as string;
    
    const configs: Record<string, any> = {
      interval: {
        water_level: 60,
        moisture: 300,
        default: 300
      },
      thresholds: {
        water_level_critical_high: 25,
        water_level_critical_low: 5,
        moisture_critical_low: 20,
        moisture_optimal: 60
      },
      calibration: {
        water_level_offset: 0,
        moisture_offset: 0
      }
    };
    
    const response = sharedKeys ? configs[sharedKeys] || {} : configs;
    res.json(response);
  });

  // Get sensor data with time range
  app.get('/api/v1/sensors/:sensorId/data', async (req: Request, res: Response, next: NextFunction): Promise<void> => {
    try {
      const { sensorId } = req.params;
      const { start, end, aggregation } = req.query;
      
      const startTime = new Date(start as string || Date.now() - 24 * 60 * 60 * 1000);
      const endTime = new Date(end as string || Date.now());
      
      const data = await sensorDataService.getSensorData(
        sensorId,
        startTime,
        endTime,
        aggregation as string
      );
      
      res.json({
        sensorId,
        startTime,
        endTime,
        aggregation,
        count: data.length,
        data
      });
    } catch (error) {
      next(error);
    }
  });

  // Get active sensors
  app.get('/api/v1/sensors/active', async (_req: Request, res: Response, next: NextFunction): Promise<void> => {
    try {
      const sensors = await sensorDataService.getActiveSensors();
      res.json({
        count: sensors.length,
        sensors
      });
    } catch (error) {
      next(error);
    }
  });

  // Get sensors by location
  app.get('/api/v1/sensors/nearby', async (req: Request, res: Response, next: NextFunction): Promise<void> => {
    try {
      const { lat, lng, radius } = req.query;
      
      if (!lat || !lng) {
        res.status(400).json({ error: 'lat and lng are required' });
        return;
      }
      
      const sensors = await sensorDataService.getSensorsByLocation(
        parseFloat(lat as string),
        parseFloat(lng as string),
        parseFloat(radius as string || '5')
      );
      
      res.json({
        count: sensors.length,
        center: { lat: parseFloat(lat as string), lng: parseFloat(lng as string) },
        radius: parseFloat(radius as string || '5'),
        sensors
      });
    } catch (error) {
      next(error);
    }
  });

  // Direct query endpoint (for development/debugging)
  app.post('/api/v1/admin/query', async (req: Request, res: Response, next: NextFunction): Promise<void> => {
    try {
      // Check for admin auth
      const adminToken = req.headers['x-admin-token'];
      if (adminToken !== process.env.ADMIN_TOKEN) {
        res.status(401).json({ error: 'Unauthorized' });
        return;
      }

      const { query, params } = req.body;
      if (!query) {
        res.status(400).json({ error: 'Query is required' });
        return;
      }

      const result = await timescaleRepo.query(query, params);
      res.json({
        rowCount: result.rowCount,
        rows: result.rows
      });
    } catch (error) {
      next(error);
    }
  });

  // Health check
  app.get('/health', (_req: Request, res: Response): void => {
    res.json({
      status: 'healthy',
      service: 'sensor-data',
      timestamp: new Date().toISOString()
    });
  });

  // Readiness check
  app.get('/ready', async (_req: Request, res: Response): Promise<void> => {
    try {
      // Check database connection
      await timescaleRepo.query('SELECT 1');
      res.json({
        status: 'ready',
        service: 'sensor-data',
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      res.status(503).json({
        status: 'not ready',
        service: 'sensor-data',
        error: 'Database connection failed',
        timestamp: new Date().toISOString()
      });
    }
  });
}

function getValidTokens(): Record<string, string> {
  const tokens: Record<string, string> = {};
  const tokenEnv = process.env.VALID_TOKENS || '';
  
  tokenEnv.split(',').forEach(pair => {
    const [token, name] = pair.split(':');
    if (token && name) {
      tokens[token.trim()] = name.trim();
    }
  });
  
  return tokens;
}