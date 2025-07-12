import { Router } from 'express';
import { waterLevelController } from '@controllers/water-level.controller';
import { validateRequest } from '@middleware/validate-request';
import { waterLevelValidation } from '@utils/validation/water-level.validation';

const router = Router();

// Get current water level
router.get(
  '/current/:areaId',
  validateRequest(waterLevelValidation.getCurrentLevel),
  waterLevelController.getCurrentWaterLevel
);

// Add water level measurement
router.post(
  '/',
  validateRequest(waterLevelValidation.addWaterLevel),
  waterLevelController.addWaterLevelMeasurement
);

// Bulk import water level data
router.post(
  '/import',
  validateRequest(waterLevelValidation.importWaterLevels),
  waterLevelController.importWaterLevelData
);

// Get water level history
router.get(
  '/history/:areaId',
  validateRequest(waterLevelValidation.getWaterLevelHistory),
  waterLevelController.getWaterLevelHistory
);

// Update water level data
router.put(
  '/:id',
  validateRequest(waterLevelValidation.updateWaterLevel),
  waterLevelController.updateWaterLevel
);

// Delete water level data
router.delete(
  '/:id',
  validateRequest(waterLevelValidation.deleteWaterLevel),
  waterLevelController.deleteWaterLevel
);

// Get water level statistics
router.get(
  '/statistics/:areaId',
  validateRequest(waterLevelValidation.getWaterLevelStatistics),
  waterLevelController.getWaterLevelStatistics
);

// Get water level trends
router.get(
  '/trends/:areaId',
  validateRequest(waterLevelValidation.getWaterLevelTrends),
  waterLevelController.getWaterLevelTrends
);

export default router;