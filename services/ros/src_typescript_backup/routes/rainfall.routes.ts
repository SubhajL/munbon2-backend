import { Router } from 'express';
import { rainfallController } from '@controllers/rainfall.controller';
import { validateRequest } from '@middleware/validate-request';
import { rainfallValidation } from '@utils/validation/rainfall.validation';

const router = Router();

// Get weekly effective rainfall
router.get(
  '/weekly/:areaId',
  validateRequest(rainfallValidation.getWeeklyRainfall),
  rainfallController.getWeeklyEffectiveRainfall
);

// Add rainfall data
router.post(
  '/',
  validateRequest(rainfallValidation.addRainfall),
  rainfallController.addRainfallData
);

// Bulk import rainfall data
router.post(
  '/import',
  validateRequest(rainfallValidation.importRainfall),
  rainfallController.importRainfallData
);

// Get rainfall history
router.get(
  '/history/:areaId',
  validateRequest(rainfallValidation.getRainfallHistory),
  rainfallController.getRainfallHistory
);

// Update rainfall data
router.put(
  '/:areaId/:date',
  validateRequest(rainfallValidation.updateRainfall),
  rainfallController.updateRainfallData
);

// Delete rainfall data
router.delete(
  '/:areaId/:date',
  validateRequest(rainfallValidation.deleteRainfall),
  rainfallController.deleteRainfallData
);

// Get rainfall statistics
router.get(
  '/statistics/:areaId',
  validateRequest(rainfallValidation.getRainfallStatistics),
  rainfallController.getRainfallStatistics
);

export default router;