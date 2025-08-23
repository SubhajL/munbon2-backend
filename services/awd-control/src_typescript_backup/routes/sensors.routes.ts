import { Router, Request, Response, NextFunction } from 'express';
import { param, query, validationResult } from 'express-validator';
import { AppError } from '../middleware/errorHandler';
import { sensorManagementService } from '../services/sensor-management.service';
import { sensorRepository } from '../repositories/sensor.repository';

export const sensorsRouter = Router();

// Validation middleware
const validateRequest = (req: Request, _res: Response, next: NextFunction) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    throw new AppError(400, 'Validation error', true, errors.array());
  }
  next();
};

// GET /api/v1/awd/sensors/:sensorId/status - Get sensor status
sensorsRouter.get('/:sensorId/status',
  [param('sensorId').isString().notEmpty()],
  validateRequest,
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { sensorId } = req.params;
      
      const status = await sensorRepository.getSensorStatus(sensorId);
      
      if (!status) {
        throw new AppError(404, 'Sensor not found');
      }
      
      res.json({
        success: true,
        data: status,
      });
    } catch (error) {
      next(error);
    }
  }
);

// GET /api/v1/awd/sensors/field/:fieldId - Get all sensors for a field
sensorsRouter.get('/field/:fieldId',
  [param('fieldId').isUUID()],
  validateRequest,
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { fieldId } = req.params;
      
      const sensorConfig = await sensorRepository.getFieldSensorConfig(fieldId);
      const health = await sensorManagementService.getFieldSensorHealth(fieldId);
      
      res.json({
        success: true,
        data: {
          fieldId,
          sensorConfig,
          health,
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

// GET /api/v1/awd/sensors/field/:fieldId/readings - Get current sensor readings
sensorsRouter.get('/field/:fieldId/readings',
  [param('fieldId').isUUID()],
  validateRequest,
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { fieldId } = req.params;
      
      const [waterLevel, moisture] = await Promise.all([
        sensorManagementService.getCurrentWaterLevel(fieldId),
        sensorManagementService.getCurrentMoistureLevel(fieldId)
      ]);
      
      res.json({
        success: true,
        data: {
          fieldId,
          waterLevel,
          moisture,
          timestamp: new Date().toISOString(),
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

// GET /api/v1/awd/sensors/field/:fieldId/history - Get sensor reading history
sensorsRouter.get('/field/:fieldId/history',
  [
    param('fieldId').isUUID(),
    query('type').isIn(['water_level', 'moisture']).optional(),
    query('startDate').isISO8601().optional(),
    query('endDate').isISO8601().optional(),
    query('hours').isInt({ min: 1, max: 168 }).optional().toInt(),
  ],
  validateRequest,
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { fieldId } = req.params;
      const { type, startDate, endDate, hours } = req.query;
      
      // Calculate date range
      let start: Date;
      let end: Date;
      
      if (startDate && endDate) {
        start = new Date(startDate as string);
        end = new Date(endDate as string);
      } else {
        end = new Date();
        const hoursBack = typeof hours === 'number' ? hours : 24;
        start = new Date(end.getTime() - hoursBack * 60 * 60 * 1000);
      }
      
      const results: any = {};
      
      if (!type || type === 'water_level') {
        results.waterLevel = await sensorRepository.getWaterLevelHistory(
          fieldId,
          start,
          end
        );
      }
      
      if (!type || type === 'moisture') {
        results.moisture = await sensorRepository.getMoistureHistory(
          fieldId,
          start,
          end
        );
      }
      
      res.json({
        success: true,
        data: {
          fieldId,
          startDate: start.toISOString(),
          endDate: end.toISOString(),
          ...results,
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

// GET /api/v1/awd/sensors/field/:fieldId/irrigation-check - Check if irrigation is needed
sensorsRouter.get('/field/:fieldId/irrigation-check',
  [param('fieldId').isUUID()],
  validateRequest,
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { fieldId } = req.params;
      
      const check = await sensorManagementService.checkIrrigationNeed(fieldId);
      
      res.json({
        success: true,
        data: {
          fieldId,
          ...check,
          timestamp: new Date().toISOString(),
        },
      });
    } catch (error) {
      next(error);
    }
  }
);