import { Router } from 'express';
import { plotPlantingDateController } from '@controllers/plot-planting-date.controller';
import { validateRequest } from '@middleware/validate-request';
import { body, param, query } from 'express-validator';

const router = Router();

// Validation rules
const updatePlantingDateValidation = [
  param('plotId').notEmpty().withMessage('Plot ID is required'),
  body('plantingDate').isISO8601().withMessage('Invalid planting date format'),
  body('cropType').isIn(['rice', 'corn', 'sugarcane']).withMessage('Invalid crop type'),
  body('season').optional().isIn(['wet', 'dry']).withMessage('Invalid season'),
  body('status').optional().isIn(['planned', 'active']).withMessage('Invalid status'),
];

const batchUpdateValidation = [
  body('plotIds').isArray({ min: 1 }).withMessage('plotIds must be a non-empty array'),
  body('plotIds.*').isString().notEmpty().withMessage('Each plot ID must be a non-empty string'),
  body('plantingDate').isISO8601().withMessage('Invalid planting date format'),
  body('cropType').isIn(['rice', 'corn', 'sugarcane']).withMessage('Invalid crop type'),
  body('season').optional().isIn(['wet', 'dry']).withMessage('Invalid season'),
  body('status').optional().isIn(['planned', 'active']).withMessage('Invalid status'),
];

const dateRangeValidation = [
  query('startDate').isISO8601().withMessage('Invalid start date format'),
  query('endDate').isISO8601().withMessage('Invalid end date format'),
  query('zoneId').optional().isString(),
];

const updateStatusValidation = [
  param('plotId').notEmpty().withMessage('Plot ID is required'),
  body('status').isIn(['active', 'harvested', 'fallow', 'planned']).withMessage('Invalid status'),
];

// Routes

// Update planting date for single plot
router.put(
  '/plot/:plotId/planting-date',
  updatePlantingDateValidation,
  validateRequest,
  plotPlantingDateController.updatePlotPlantingDate
);

// Batch update planting dates
router.post(
  '/plots/batch-update-planting-dates',
  batchUpdateValidation,
  validateRequest,
  plotPlantingDateController.batchUpdatePlantingDates
);

// Get plots by planting date range
router.get(
  '/plots/by-planting-date',
  dateRangeValidation,
  validateRequest,
  plotPlantingDateController.getPlotsByPlantingDateRange
);

// Get upcoming planting schedules
router.get(
  '/plots/upcoming-plantings',
  query('daysAhead').optional().isInt({ min: 1, max: 365 }),
  validateRequest,
  plotPlantingDateController.getUpcomingPlantingSchedules
);

// Update crop status
router.put(
  '/plot/:plotId/crop-status',
  updateStatusValidation,
  validateRequest,
  plotPlantingDateController.updateCropStatus
);

// Get plots ready for harvest
router.get(
  '/plots/ready-for-harvest',
  query('daysWindow').optional().isInt({ min: 1, max: 30 }),
  validateRequest,
  plotPlantingDateController.getPlotsReadyForHarvest
);

// Get planting date statistics by zone
router.get(
  '/plots/planting-stats-by-zone',
  plotPlantingDateController.getPlantingDateStatsByZone
);

export default router;