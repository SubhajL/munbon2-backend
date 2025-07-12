import { Router } from 'express';
import { body, param, query, validationResult } from 'express-validator';
import { WaterDemandController } from '../controllers/water-demand.controller';
import { authMiddleware } from '../middleware/auth.middleware';
import { asyncHandler } from '../middleware/async-handler';

const router = Router();
const controller = new WaterDemandController();

// Validation middleware
const validateRequest = (req: any, res: any, next: any) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res.status(400).json({ errors: errors.array() });
  }
  next();
};

// Routes

/**
 * Calculate water demand for parcels
 * POST /api/v1/water-demand/calculate
 */
router.post(
  '/calculate',
  authMiddleware,
  [
    body('parcels')
      .isArray({ min: 1 })
      .withMessage('Parcels must be a non-empty array'),
    body('parcels.*')
      .isString()
      .withMessage('Each parcel ID must be a string'),
    body('method')
      .isIn(['RID-MS', 'ROS', 'AWD'])
      .withMessage('Method must be RID-MS, ROS, or AWD'),
    body('parameters').optional().isObject(),
    body('parameters.cropType').optional().isString(),
    body('parameters.plantingDate').optional().isISO8601(),
    body('parameters.irrigationEfficiency')
      .optional()
      .isFloat({ min: 0.1, max: 1.0 })
      .withMessage('Irrigation efficiency must be between 0.1 and 1.0'),
  ],
  validateRequest,
  controller.calculateWaterDemand.bind(controller)
);

/**
 * Get water demand for a specific parcel
 * GET /api/v1/water-demand/parcels/:parcelId
 */
router.get(
  '/parcels/:parcelId',
  authMiddleware,
  [
    param('parcelId').isString().withMessage('Invalid parcel ID'),
    query('date').optional().isISO8601(),
  ],
  validateRequest,
  controller.getParcelWaterDemand.bind(controller)
);

/**
 * Get water demand history for a parcel
 * GET /api/v1/water-demand/history/:parcelId
 */
router.get(
  '/history/:parcelId',
  authMiddleware,
  [
    param('parcelId').isString().withMessage('Invalid parcel ID'),
    query('startDate').notEmpty().isISO8601(),
    query('endDate').notEmpty().isISO8601(),
  ],
  validateRequest,
  asyncHandler(controller.getWaterDemandHistory.bind(controller))
);

/**
 * Update water demand method for parcels
 * PUT /api/v1/water-demand/parcels/method
 */
router.put(
  '/parcels/method',
  authMiddleware,
  [
    body('parcels')
      .isArray({ min: 1 })
      .withMessage('Parcels must be a non-empty array'),
    body('parcels.*')
      .isString()
      .withMessage('Each parcel ID must be a string'),
    body('method')
      .isIn(['RID-MS', 'ROS', 'AWD'])
      .withMessage('Method must be RID-MS, ROS, or AWD'),
  ],
  validateRequest,
  controller.updateWaterDemandMethod.bind(controller)
);

/**
 * Get water demand statistics by zone
 * GET /api/v1/water-demand/zones/:zone/statistics
 */
router.get(
  '/zones/:zone/statistics',
  authMiddleware,
  [
    param('zone').isString().withMessage('Invalid zone'),
  ],
  validateRequest,
  controller.getZoneWaterDemandStatistics.bind(controller)
);

/**
 * Get water demand summary
 * GET /api/v1/water-demand/summary
 */
router.get(
  '/summary',
  authMiddleware,
  [
    query('groupBy')
      .optional()
      .isIn(['zone', 'method', 'cropType'])
      .withMessage('Group by must be zone, method, or cropType'),
    query('startDate').optional().isISO8601(),
    query('endDate').optional().isISO8601(),
  ],
  validateRequest,
  controller.getWaterDemandSummary.bind(controller)
);

/**
 * Export water demand data
 * GET /api/v1/water-demand/export
 */
router.get(
  '/export',
  authMiddleware,
  [
    query('format')
      .isIn(['csv', 'json', 'excel'])
      .withMessage('Format must be csv, json, or excel'),
    query('zone').optional().isString(),
    query('method')
      .optional()
      .isIn(['RID-MS', 'ROS', 'AWD']),
    query('startDate').optional().isISO8601(),
    query('endDate').optional().isISO8601(),
  ],
  validateRequest,
  controller.exportWaterDemandData.bind(controller)
);

/**
 * Get water demand forecast
 * GET /api/v1/water-demand/forecast
 */
router.get(
  '/forecast',
  authMiddleware,
  [
    query('zone').optional().isString(),
    query('days')
      .optional()
      .isInt({ min: 1, max: 30 })
      .toInt()
      .withMessage('Days must be between 1 and 30'),
  ],
  validateRequest,
  controller.getWaterDemandForecast.bind(controller)
);

/**
 * Trigger manual water demand update
 * POST /api/v1/water-demand/update-all
 */
router.post(
  '/update-all',
  authMiddleware,
  controller.triggerWaterDemandUpdate.bind(controller)
);

export const waterDemandRoutes = router;