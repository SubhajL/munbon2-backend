import { Router, Request, Response, NextFunction } from 'express';
import Joi from 'joi';
import { TimescaleService } from '../services/timescale.service';
import { CacheService } from '../services/cache.service';
import { AlertService } from '../services/alert.service';
import { logger } from '../utils/logger';

const router = Router();

export function createMoistureRoutes(
  timescaleService: TimescaleService,
  cacheService: CacheService,
  alertService: AlertService
): Router {
  // Get latest readings for multiple sensors
  router.get('/readings/latest', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const schema = Joi.object({
        sensorIds: Joi.string().optional(),
        limit: Joi.number().min(1).max(1000).default(100),
      });
      
      const { error, value } = schema.validate(req.query);
      if (error) {
        return res.status(400).json({ error: error.details[0].message });
      }
      
      const sensorIds = value.sensorIds ? value.sensorIds.split(',') : undefined;
      
      const readings = await timescaleService.getLatestReadings(sensorIds, value.limit);
      
      res.json({
        success: true,
        count: readings.length,
        data: readings,
      });
    } catch (error) {
      next(error);
    }
  });

  // Get readings for a specific sensor
  router.get('/sensors/:sensorId/readings', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { sensorId } = req.params;
      
      const schema = Joi.object({
        startTime: Joi.date().iso().required(),
        endTime: Joi.date().iso().default(() => new Date()),
        limit: Joi.number().min(1).max(10000).optional(),
      });
      
      const { error, value } = schema.validate(req.query);
      if (error) {
        return res.status(400).json({ error: error.details[0].message });
      }
      
      // Check cache first
      const cacheKey = `moisture:${sensorId}:readings:${value.startTime.getTime()}-${value.endTime.getTime()}`;
      const cached = await cacheService.get(cacheKey);
      
      if (cached) {
        return res.json({
          success: true,
          fromCache: true,
          data: cached,
        });
      }
      
      const readings = await timescaleService.getReadingsByTimeRange(
        sensorId,
        value.startTime,
        value.endTime,
        value.limit
      );
      
      // Cache for 5 minutes
      await cacheService.set(cacheKey, readings, 300);
      
      res.json({
        success: true,
        count: readings.length,
        data: readings,
      });
    } catch (error) {
      next(error);
    }
  });

  // Get aggregated readings
  router.get('/sensors/:sensorId/aggregated', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { sensorId } = req.params;
      
      const schema = Joi.object({
        startTime: Joi.date().iso().required(),
        endTime: Joi.date().iso().default(() => new Date()),
        interval: Joi.string().valid('5m', '15m', '1h', '6h', '1d').required(),
      });
      
      const { error, value } = schema.validate(req.query);
      if (error) {
        return res.status(400).json({ error: error.details[0].message });
      }
      
      // Check cache
      const cacheKey = `moisture:${sensorId}:agg:${value.interval}:${value.startTime.getTime()}-${value.endTime.getTime()}`;
      const cached = await cacheService.get(cacheKey);
      
      if (cached) {
        return res.json({
          success: true,
          fromCache: true,
          data: cached,
        });
      }
      
      const aggregations = await timescaleService.getAggregatedReadings(
        sensorId,
        value.startTime,
        value.endTime,
        value.interval
      );
      
      // Cache for longer periods
      const cacheTTL = value.interval === '1d' ? 3600 : 600; // 1 hour for daily, 10 min for others
      await cacheService.set(cacheKey, aggregations, cacheTTL);
      
      res.json({
        success: true,
        interval: value.interval,
        count: aggregations.length,
        data: aggregations,
      });
    } catch (error) {
      next(error);
    }
  });

  // Get analytics for a sensor
  router.get('/sensors/:sensorId/analytics', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { sensorId } = req.params;
      
      const schema = Joi.object({
        period: Joi.string().valid('1h', '1d', '7d', '30d').default('1d'),
      });
      
      const { error, value } = schema.validate(req.query);
      if (error) {
        return res.status(400).json({ error: error.details[0].message });
      }
      
      // Check cache
      const cacheKey = `moisture:${sensorId}:analytics:${value.period}`;
      const cached = await cacheService.get(cacheKey);
      
      if (cached) {
        return res.json({
          success: true,
          fromCache: true,
          data: cached,
        });
      }
      
      const analytics = await timescaleService.getAnalytics(sensorId, value.period);
      
      // Cache analytics
      await cacheService.set(cacheKey, analytics, 600); // 10 minutes
      
      res.json({
        success: true,
        data: analytics,
      });
    } catch (error) {
      next(error);
    }
  });

  // Get active sensors
  router.get('/sensors/active', async (req: Request, res: Response, next: NextFunction) => {
    try {
      // Check cache
      const cached = await cacheService.get('moisture:sensors:active');
      
      if (cached) {
        return res.json({
          success: true,
          fromCache: true,
          count: (cached as any[]).length,
          data: cached,
        });
      }
      
      const sensors = await timescaleService.getActiveSensors();
      
      // Cache for 1 minute
      await cacheService.set('moisture:sensors:active', sensors, 60);
      
      res.json({
        success: true,
        count: sensors.length,
        data: sensors,
      });
    } catch (error) {
      next(error);
    }
  });

  // Get sensors by location
  router.get('/sensors/nearby', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const schema = Joi.object({
        lat: Joi.number().min(-90).max(90).required(),
        lng: Joi.number().min(-180).max(180).required(),
        radius: Joi.number().min(0.1).max(100).default(5), // km
      });
      
      const { error, value } = schema.validate(req.query);
      if (error) {
        return res.status(400).json({ error: error.details[0].message });
      }
      
      const sensors = await timescaleService.getSensorsByLocation(
        value.lat,
        value.lng,
        value.radius
      );
      
      res.json({
        success: true,
        count: sensors.length,
        center: { lat: value.lat, lng: value.lng },
        radiusKm: value.radius,
        data: sensors,
      });
    } catch (error) {
      next(error);
    }
  });

  // Get alerts for a sensor
  router.get('/sensors/:sensorId/alerts', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { sensorId } = req.params;
      
      const alerts = await alertService.getActiveAlerts(sensorId);
      
      res.json({
        success: true,
        count: alerts.length,
        data: alerts,
      });
    } catch (error) {
      next(error);
    }
  });

  // Acknowledge an alert
  router.post('/alerts/:alertId/acknowledge', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { alertId } = req.params;
      
      const schema = Joi.object({
        acknowledgedBy: Joi.string().required(),
      });
      
      const { error, value } = schema.validate(req.body);
      if (error) {
        return res.status(400).json({ error: error.details[0].message });
      }
      
      await alertService.acknowledgeAlert(alertId, value.acknowledgedBy);
      
      res.json({
        success: true,
        message: 'Alert acknowledged',
      });
    } catch (error) {
      next(error);
    }
  });

  return router;
}