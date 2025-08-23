import { Router, Request, Response, NextFunction } from 'express';
import { body, query, param, validationResult } from 'express-validator';
import { DatabaseService } from '../services/database.service';
import { CacheService } from '../services/cache.service';
import { AlertService } from '../services/alert.service';
import { AnalyticsService } from '../services/analytics.service';
import { IrrigationService } from '../services/irrigation.service';
import { logger } from '../utils/logger';

export function createWeatherRoutes(
  databaseService: DatabaseService,
  cacheService: CacheService,
  alertService: AlertService,
  analyticsService: AnalyticsService,
  irrigationService: IrrigationService
): Router {
  const router = Router();

  // Validation middleware
  const handleValidationErrors = (req: Request, res: Response, next: NextFunction) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }
    next();
  };

  // GET /current - Get current weather
  router.get('/current',
    [
      query('lat').optional().isFloat({ min: -90, max: 90 }),
      query('lng').optional().isFloat({ min: -180, max: 180 }),
      query('stationIds').optional().isString(),
    ],
    handleValidationErrors,
    async (req: Request, res: Response) => {
      try {
        const { lat, lng, stationIds } = req.query;
        
        const location = lat && lng ? {
          lat: parseFloat(lat as string),
          lng: parseFloat(lng as string),
        } : undefined;
        
        const stationIdArray = stationIds 
          ? (stationIds as string).split(',').map(id => id.trim())
          : undefined;

        const readings = await databaseService.getCurrentWeather(location, stationIdArray);
        
        res.json({
          success: true,
          data: readings,
          count: readings.length,
          timestamp: new Date(),
        });
      } catch (error) {
        logger.error({ error }, 'Failed to get current weather');
        res.status(500).json({
          success: false,
          error: 'Failed to get current weather',
        });
      }
    }
  );

  // GET /historical - Get historical weather data
  router.get('/historical',
    [
      query('startTime').isISO8601(),
      query('endTime').isISO8601(),
      query('lat').optional().isFloat({ min: -90, max: 90 }),
      query('lng').optional().isFloat({ min: -180, max: 180 }),
      query('stationIds').optional().isString(),
    ],
    handleValidationErrors,
    async (req: Request, res: Response) => {
      try {
        const { startTime, endTime, lat, lng, stationIds } = req.query;
        
        const location = lat && lng ? {
          lat: parseFloat(lat as string),
          lng: parseFloat(lng as string),
        } : undefined;
        
        const stationIdArray = stationIds 
          ? (stationIds as string).split(',').map(id => id.trim())
          : undefined;

        const readings = await databaseService.getHistoricalWeather(
          new Date(startTime as string),
          new Date(endTime as string),
          location,
          stationIdArray
        );
        
        res.json({
          success: true,
          data: readings,
          count: readings.length,
          startTime,
          endTime,
        });
      } catch (error) {
        logger.error({ error }, 'Failed to get historical weather');
        res.status(500).json({
          success: false,
          error: 'Failed to get historical weather',
        });
      }
    }
  );

  // GET /aggregated - Get aggregated weather data
  router.get('/aggregated',
    [
      query('startTime').isISO8601(),
      query('endTime').isISO8601(),
      query('interval').isIn(['1 hour', '6 hours', '1 day', '1 week', '1 month']),
      query('lat').optional().isFloat({ min: -90, max: 90 }),
      query('lng').optional().isFloat({ min: -180, max: 180 }),
      query('stationId').optional().isString(),
    ],
    handleValidationErrors,
    async (req: Request, res: Response) => {
      try {
        const { startTime, endTime, interval, lat, lng, stationId } = req.query;
        
        const location = lat && lng ? {
          lat: parseFloat(lat as string),
          lng: parseFloat(lng as string),
        } : undefined;

        const aggregated = await databaseService.getAggregatedWeather(
          new Date(startTime as string),
          new Date(endTime as string),
          interval as string,
          location,
          stationId as string
        );
        
        res.json({
          success: true,
          data: aggregated,
          count: aggregated.length,
          interval,
        });
      } catch (error) {
        logger.error({ error }, 'Failed to get aggregated weather');
        res.status(500).json({
          success: false,
          error: 'Failed to get aggregated weather',
        });
      }
    }
  );

  // GET /stations - Get weather stations
  router.get('/stations',
    [
      query('active').optional().isBoolean(),
    ],
    handleValidationErrors,
    async (req: Request, res: Response) => {
      try {
        const { active } = req.query;
        
        const stations = await databaseService.getWeatherStations(
          active !== undefined ? active === 'true' : undefined
        );
        
        res.json({
          success: true,
          data: stations,
          count: stations.length,
        });
      } catch (error) {
        logger.error({ error }, 'Failed to get weather stations');
        res.status(500).json({
          success: false,
          error: 'Failed to get weather stations',
        });
      }
    }
  );

  // GET /forecast - Get weather forecast
  router.get('/forecast',
    [
      query('lat').isFloat({ min: -90, max: 90 }),
      query('lng').isFloat({ min: -180, max: 180 }),
      query('days').optional().isInt({ min: 1, max: 14 }),
    ],
    handleValidationErrors,
    async (req: Request, res: Response) => {
      try {
        const { lat, lng, days } = req.query;
        
        const location = {
          lat: parseFloat(lat as string),
          lng: parseFloat(lng as string),
        };

        const forecasts = await databaseService.getWeatherForecasts(
          location,
          days ? parseInt(days as string) : 7
        );
        
        res.json({
          success: true,
          data: forecasts,
          count: forecasts.length,
          location,
        });
      } catch (error) {
        logger.error({ error }, 'Failed to get weather forecast');
        res.status(500).json({
          success: false,
          error: 'Failed to get weather forecast',
        });
      }
    }
  );

  // GET /analytics - Get weather analytics
  router.get('/analytics',
    [
      query('lat').isFloat({ min: -90, max: 90 }),
      query('lng').isFloat({ min: -180, max: 180 }),
      query('period').optional().isIn(['1d', '7d', '30d', '90d', '1y']),
    ],
    handleValidationErrors,
    async (req: Request, res: Response) => {
      try {
        const { lat, lng, period } = req.query;
        
        const location = {
          lat: parseFloat(lat as string),
          lng: parseFloat(lng as string),
        };

        const analytics = await analyticsService.getWeatherAnalytics(
          location,
          period as string || '7d'
        );
        
        res.json({
          success: true,
          data: analytics,
        });
      } catch (error) {
        logger.error({ error }, 'Failed to get weather analytics');
        res.status(500).json({
          success: false,
          error: 'Failed to get weather analytics',
        });
      }
    }
  );

  // GET /analytics/trends - Get weather trends
  router.get('/analytics/trends',
    [
      query('lat').isFloat({ min: -90, max: 90 }),
      query('lng').isFloat({ min: -180, max: 180 }),
      query('metric').isIn(['temperature', 'rainfall', 'humidity', 'pressure']),
      query('period').optional().isIn(['7d', '30d', '90d', '1y']),
    ],
    handleValidationErrors,
    async (req: Request, res: Response) => {
      try {
        const { lat, lng, metric, period } = req.query;
        
        const location = {
          lat: parseFloat(lat as string),
          lng: parseFloat(lng as string),
        };

        const trends = await analyticsService.getWeatherTrends(
          location,
          metric as any,
          period as string || '30d'
        );
        
        res.json({
          success: true,
          data: trends,
        });
      } catch (error) {
        logger.error({ error }, 'Failed to get weather trends');
        res.status(500).json({
          success: false,
          error: 'Failed to get weather trends',
        });
      }
    }
  );

  // GET /analytics/anomalies - Detect weather anomalies
  router.get('/analytics/anomalies',
    [
      query('lat').isFloat({ min: -90, max: 90 }),
      query('lng').isFloat({ min: -180, max: 180 }),
      query('threshold').optional().isFloat({ min: 1, max: 5 }),
    ],
    handleValidationErrors,
    async (req: Request, res: Response) => {
      try {
        const { lat, lng, threshold } = req.query;
        
        const location = {
          lat: parseFloat(lat as string),
          lng: parseFloat(lng as string),
        };

        const anomalies = await analyticsService.detectAnomalies(
          location,
          threshold ? parseFloat(threshold as string) : 2.5
        );
        
        res.json({
          success: true,
          data: anomalies,
        });
      } catch (error) {
        logger.error({ error }, 'Failed to detect anomalies');
        res.status(500).json({
          success: false,
          error: 'Failed to detect anomalies',
        });
      }
    }
  );

  // GET /analytics/comparison - Compare weather between locations
  router.post('/analytics/comparison',
    [
      body('locations').isArray({ min: 2, max: 10 }),
      body('locations.*.lat').isFloat({ min: -90, max: 90 }),
      body('locations.*.lng').isFloat({ min: -180, max: 180 }),
      body('period').optional().isIn(['7d', '30d', '90d', '1y']),
    ],
    handleValidationErrors,
    async (req: Request, res: Response) => {
      try {
        const { locations, period } = req.body;
        
        const comparison = await analyticsService.getComparativeAnalytics(
          locations,
          period || '30d'
        );
        
        res.json({
          success: true,
          data: comparison,
        });
      } catch (error) {
        logger.error({ error }, 'Failed to compare weather');
        res.status(500).json({
          success: false,
          error: 'Failed to compare weather',
        });
      }
    }
  );

  // GET /evapotranspiration - Calculate evapotranspiration
  router.get('/evapotranspiration',
    [
      query('lat').isFloat({ min: -90, max: 90 }),
      query('lng').isFloat({ min: -180, max: 180 }),
      query('date').optional().isISO8601(),
      query('cropCoefficient').optional().isFloat({ min: 0.1, max: 2.0 }),
    ],
    handleValidationErrors,
    async (req: Request, res: Response) => {
      try {
        const { lat, lng, date, cropCoefficient } = req.query;
        
        const location = {
          lat: parseFloat(lat as string),
          lng: parseFloat(lng as string),
        };

        const et = await analyticsService.calculateEvapotranspiration(
          location,
          date ? new Date(date as string) : new Date(),
          cropCoefficient ? parseFloat(cropCoefficient as string) : 1.0
        );
        
        res.json({
          success: true,
          data: et,
        });
      } catch (error) {
        logger.error({ error }, 'Failed to calculate evapotranspiration');
        res.status(500).json({
          success: false,
          error: 'Failed to calculate evapotranspiration',
        });
      }
    }
  );

  // GET /irrigation/recommendation - Get irrigation recommendation
  router.get('/irrigation/recommendation',
    [
      query('lat').isFloat({ min: -90, max: 90 }),
      query('lng').isFloat({ min: -180, max: 180 }),
      query('cropType').optional().isString(),
      query('growthStage').optional().isString(),
      query('soilMoisture').optional().isFloat({ min: 0, max: 100 }),
    ],
    handleValidationErrors,
    async (req: Request, res: Response) => {
      try {
        const { lat, lng, cropType, growthStage, soilMoisture } = req.query;
        
        const location = {
          lat: parseFloat(lat as string),
          lng: parseFloat(lng as string),
        };

        const recommendation = await irrigationService.getIrrigationRecommendation(
          location,
          cropType as string || 'rice',
          growthStage as string || 'vegetative',
          soilMoisture ? parseFloat(soilMoisture as string) : undefined
        );
        
        res.json({
          success: true,
          data: recommendation,
        });
      } catch (error) {
        logger.error({ error }, 'Failed to get irrigation recommendation');
        res.status(500).json({
          success: false,
          error: 'Failed to get irrigation recommendation',
        });
      }
    }
  );

  // GET /irrigation/schedule - Get irrigation schedule
  router.get('/irrigation/schedule',
    [
      query('lat').isFloat({ min: -90, max: 90 }),
      query('lng').isFloat({ min: -180, max: 180 }),
      query('cropType').isString(),
      query('growthStage').isString(),
      query('fieldSize').isFloat({ min: 0.1, max: 10000 }),
      query('system').optional().isIn(['drip', 'sprinkler', 'flood']),
    ],
    handleValidationErrors,
    async (req: Request, res: Response) => {
      try {
        const { lat, lng, cropType, growthStage, fieldSize, system } = req.query;
        
        const location = {
          lat: parseFloat(lat as string),
          lng: parseFloat(lng as string),
        };

        const schedule = await irrigationService.getIrrigationSchedule(
          location,
          cropType as string,
          growthStage as string,
          parseFloat(fieldSize as string),
          system as any || 'flood'
        );
        
        res.json({
          success: true,
          data: schedule,
        });
      } catch (error) {
        logger.error({ error }, 'Failed to get irrigation schedule');
        res.status(500).json({
          success: false,
          error: 'Failed to get irrigation schedule',
        });
      }
    }
  );

  // GET /irrigation/water-balance - Get water balance analysis
  router.get('/irrigation/water-balance',
    [
      query('lat').isFloat({ min: -90, max: 90 }),
      query('lng').isFloat({ min: -180, max: 180 }),
      query('cropType').isString(),
      query('growthStage').isString(),
      query('period').optional().isIn(['7d', '30d', '90d']),
    ],
    handleValidationErrors,
    async (req: Request, res: Response) => {
      try {
        const { lat, lng, cropType, growthStage, period } = req.query;
        
        const location = {
          lat: parseFloat(lat as string),
          lng: parseFloat(lng as string),
        };

        const waterBalance = await irrigationService.getWaterBalanceAnalysis(
          location,
          cropType as string,
          growthStage as string,
          period as string || '30d'
        );
        
        res.json({
          success: true,
          data: waterBalance,
        });
      } catch (error) {
        logger.error({ error }, 'Failed to get water balance');
        res.status(500).json({
          success: false,
          error: 'Failed to get water balance',
        });
      }
    }
  );

  // GET /alerts - Get active weather alerts
  router.get('/alerts',
    [
      query('lat').optional().isFloat({ min: -90, max: 90 }),
      query('lng').optional().isFloat({ min: -180, max: 180 }),
      query('radius').optional().isFloat({ min: 1, max: 500 }),
    ],
    handleValidationErrors,
    async (req: Request, res: Response) => {
      try {
        const { lat, lng, radius } = req.query;
        
        const location = lat && lng ? {
          lat: parseFloat(lat as string),
          lng: parseFloat(lng as string),
        } : undefined;

        const alerts = await alertService.getActiveAlerts(
          location,
          radius ? parseFloat(radius as string) : undefined
        );
        
        res.json({
          success: true,
          data: alerts,
          count: alerts.length,
        });
      } catch (error) {
        logger.error({ error }, 'Failed to get alerts');
        res.status(500).json({
          success: false,
          error: 'Failed to get alerts',
        });
      }
    }
  );

  // PUT /alerts/:id/acknowledge - Acknowledge an alert
  router.put('/alerts/:id/acknowledge',
    [
      param('id').isUUID(),
      body('acknowledgedBy').isString(),
    ],
    handleValidationErrors,
    async (req: Request, res: Response) => {
      try {
        const { id } = req.params;
        const { acknowledgedBy } = req.body;
        
        await alertService.acknowledgeAlert(id, acknowledgedBy);
        
        res.json({
          success: true,
          message: 'Alert acknowledged',
        });
      } catch (error) {
        logger.error({ error }, 'Failed to acknowledge alert');
        res.status(500).json({
          success: false,
          error: 'Failed to acknowledge alert',
        });
      }
    }
  );

  return router;
}