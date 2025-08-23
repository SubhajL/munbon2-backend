import { Router, Request, Response, NextFunction } from 'express';
import Joi from 'joi';
import { TimescaleService } from '../services/timescale.service';
import { CacheService } from '../services/cache.service';
import { AlertService } from '../services/alert.service';
import { GateControlService } from '../services/gate-control.service';
import { logger } from '../utils/logger';

const router = Router();

export function createWaterLevelRoutes(
  timescaleService: TimescaleService,
  cacheService: CacheService,
  alertService: AlertService,
  gateControlService: GateControlService
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
      const cacheKey = `water-level:${sensorId}:readings:${value.startTime.getTime()}-${value.endTime.getTime()}`;
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
      const cacheKey = `water-level:${sensorId}:agg:${value.interval}:${value.startTime.getTime()}-${value.endTime.getTime()}`;
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
      const cacheKey = `water-level:${sensorId}:analytics:${value.period}`;
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

  // Get rate of change
  router.get('/sensors/:sensorId/rate-of-change', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { sensorId } = req.params;
      
      const schema = Joi.object({
        minutes: Joi.number().min(5).max(1440).default(60),
      });
      
      const { error, value } = schema.validate(req.query);
      if (error) {
        return res.status(400).json({ error: error.details[0].message });
      }
      
      const rateOfChange = await timescaleService.getRateOfChange(sensorId, value.minutes);
      
      res.json({
        success: true,
        sensorId,
        minutes: value.minutes,
        rateOfChangeCmPerHour: rateOfChange,
        trend: rateOfChange > 0.5 ? 'increasing' : rateOfChange < -0.5 ? 'decreasing' : 'stable',
      });
    } catch (error) {
      next(error);
    }
  });

  // Get active sensors
  router.get('/sensors/active', async (req: Request, res: Response, next: NextFunction) => {
    try {
      // Check cache
      const cached = await cacheService.get('water-level:sensors:active');
      
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
      await cacheService.set('water-level:sensors:active', sensors, 60);
      
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

  // Get gate control recommendation
  router.get('/gates/:gateId/recommendation', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { gateId } = req.params;
      
      const schema = Joi.object({
        sensorId: Joi.string().required(),
      });
      
      const { error, value } = schema.validate(req.query);
      if (error) {
        return res.status(400).json({ error: error.details[0].message });
      }
      
      // Get latest reading for the sensor
      const readings = await timescaleService.getLatestReadings([value.sensorId], 1);
      
      if (readings.length === 0) {
        return res.status(404).json({ error: 'No recent readings found for sensor' });
      }
      
      const recommendation = await gateControlService.generateRecommendation(
        gateId,
        value.sensorId,
        readings[0]
      );
      
      res.json({
        success: true,
        data: recommendation,
      });
    } catch (error) {
      next(error);
    }
  });

  // Get gate status
  router.get('/gates/:gateId/status', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { gateId } = req.params;
      
      const status = await gateControlService.getGateStatus(gateId);
      
      res.json({
        success: true,
        data: status,
      });
    } catch (error) {
      next(error);
    }
  });

  return router;
}