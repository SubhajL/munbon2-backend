import { Router } from 'express';
import { waterDemandController } from '@controllers/water-demand.controller';
import { cropWeekController } from '@controllers/crop-week.controller';
import { validateRequest } from '@middleware/validate-request';
import { waterDemandValidation } from '@utils/validation/water-demand.validation';

const router = Router();

// Calculate water demand for a specific crop week
router.post(
  '/calculate',
  validateRequest(waterDemandValidation.calculateWaterDemand),
  waterDemandController.calculateWaterDemand
);

// Calculate water demand for entire crop season
router.post(
  '/seasonal',
  validateRequest(waterDemandValidation.calculateSeasonalWaterDemand),
  waterDemandController.calculateSeasonalWaterDemand
);

// Get water demand for a particular area for a crop week
router.get(
  '/area/:areaId/week',
  validateRequest(waterDemandValidation.getWaterDemandByCropWeek),
  waterDemandController.getWaterDemandByCropWeek
);

// Get water demand for entire crop season by week
router.get(
  '/area/:areaId/seasonal',
  validateRequest(waterDemandValidation.getSeasonalWaterDemandByWeek),
  waterDemandController.getSeasonalWaterDemandByWeek
);

// Get water demand summary for an area type
router.get(
  '/summary/:areaType',
  validateRequest(waterDemandValidation.getWaterDemandSummary),
  waterDemandController.getWaterDemandSummary
);

// Crop week calculation endpoints
router.post(
  '/crop-week/current',
  cropWeekController.calculateCurrentCropWeek
);

router.post(
  '/crop-week/plots',
  cropWeekController.getCropWeeksForPlots
);

router.post(
  '/crop-week/planting-date',
  cropWeekController.calculatePlantingDate
);

export default router;