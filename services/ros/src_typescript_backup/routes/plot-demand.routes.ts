import { Router } from 'express';
import { plotWaterDemandController } from '@controllers/plot-water-demand.controller';
import { validateRequest } from '@middleware/validate-request';
import { body, param, query } from 'express-validator';

const router = Router();

// Validation rules
const calculatePlotDemandValidation = [
  param('plotId').notEmpty().withMessage('Plot ID is required'),
  body('cropType').isIn(['rice', 'corn', 'sugarcane']).withMessage('Invalid crop type'),
  body('plantingDate').isISO8601().withMessage('Invalid planting date format'),
  body('includeRainfall').optional().isBoolean(),
  body('includeLandPreparation').optional().isBoolean(),
];

const calculateBatchDemandValidation = [
  body('plotIds').isArray({ min: 1 }).withMessage('plotIds must be a non-empty array'),
  body('plotIds.*').isString().notEmpty().withMessage('Each plot ID must be a non-empty string'),
  body('cropType').isIn(['rice', 'corn', 'sugarcane']).withMessage('Invalid crop type'),
  body('plantingDate').isISO8601().withMessage('Invalid planting date format'),
  body('includeRainfall').optional().isBoolean(),
  body('includeLandPreparation').optional().isBoolean(),
];

const getPlotsByAreaValidation = [
  param('areaType').isIn(['zone', 'section']).withMessage('areaType must be zone or section'),
  param('areaId').notEmpty().withMessage('Area ID is required'),
];

const getHistoricalDemandValidation = [
  param('plotId').notEmpty().withMessage('Plot ID is required'),
  query('startYear').optional().isInt({ min: 2000, max: 2100 }),
  query('endYear').optional().isInt({ min: 2000, max: 2100 }),
];

const getCurrentWeekValidation = [
  query('week').optional().isInt({ min: 1, max: 53 }),
  query('year').optional().isInt({ min: 2000, max: 2100 }),
];

// Routes

// Single plot calculation
router.post(
  '/plot/:plotId/calculate',
  calculatePlotDemandValidation,
  validateRequest,
  plotWaterDemandController.calculatePlotDemand
);

// Batch calculation for multiple plots
router.post(
  '/plots/batch-calculate',
  calculateBatchDemandValidation,
  validateRequest,
  plotWaterDemandController.calculateBatchPlotDemand
);

// Get plots by area (zone or section)
router.get(
  '/plots/by-area/:areaType/:areaId',
  getPlotsByAreaValidation,
  validateRequest,
  plotWaterDemandController.getPlotsByArea
);

// Get plot information
router.get(
  '/plot/:plotId',
  param('plotId').notEmpty(),
  validateRequest,
  plotWaterDemandController.getPlotInfo
);

// Get historical demand for a plot
router.get(
  '/plot/:plotId/history',
  getHistoricalDemandValidation,
  validateRequest,
  plotWaterDemandController.getPlotHistoricalDemand
);

// Get current week demand for all active plots
router.get(
  '/plots/current-week',
  getCurrentWeekValidation,
  validateRequest,
  plotWaterDemandController.getCurrentWeekDemand
);

// Calculate aggregate demand for all plots in a zone
router.post(
  '/zone/:zoneId/calculate',
  [
    param('zoneId').notEmpty().withMessage('Zone ID is required'),
    ...calculatePlotDemandValidation.slice(1), // Skip plotId validation
  ],
  validateRequest,
  plotWaterDemandController.calculateZoneDemand
);

export default router;